"""Zero-shot panorama geolocation with StreetCLIP (geolocal/StreetCLIP).

StreetCLIP is a CLIP ViT-L/14-336 model that scores images against place-name
prompts; it has no coordinate head. We turn it into an image -> (lat, lng)
model the way the StreetCLIP paper does, hierarchically:

    p(place) = p(country) * p(region | country) * p(place | region)

over a GeoNames gazetteer of towns in Portugal, Spain and France, and return
each top place's coordinates. Each panorama is cut into 8 horizontal
perspective views (90 deg FOV); per-view log-probabilities are averaged.

Usage:
    python streetclip/geolocate.py "Data/Panorama Warm-Up" -o streetclip/results/streetclip_predictions.json
"""

import argparse
import json
import math
import re
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "geolocal/StreetCLIP"
COUNTRIES = {"PT": "Portugal", "ES": "Spain", "FR": "France"}
GEONAMES = "https://download.geonames.org/export/dump/"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "streetclip"

# Prompt templates from the StreetCLIP paper.
COUNTRY_PROMPT = "A Street View photo in {country}."
REGION_PROMPT = "A Street View photo in {region}, {country}."
PLACE_PROMPT = "A Street View photo close to {place}, {region}, {country}."

VIEW_SIZE = 336  # StreetCLIP input resolution
N_VIEWS = 8
FOV_DEG = 90.0


def _download(name: str) -> Path:
    path = CACHE_DIR / name
    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {GEONAMES + name}", file=sys.stderr)
        urllib.request.urlretrieve(GEONAMES + name, path)
    return path


def load_gazetteer(min_population: int) -> list[dict]:
    """Populated places in PT/ES/FR from GeoNames cities1000, with region names."""
    regions = {}
    for line in _download("admin1CodesASCII.txt").read_text(encoding="utf-8").splitlines():
        code, name = line.split("\t")[:2]
        regions[code] = name

    places = []
    with zipfile.ZipFile(_download("cities1000.zip")) as zf:
        text = zf.read("cities1000.txt").decode("utf-8")
    for line in text.splitlines():
        f = line.split("\t")
        country, admin1, population = f[8], f[10], int(f[14] or 0)
        region = regions.get(f"{country}.{admin1}")
        if country not in COUNTRIES or region is None or population < min_population:
            continue
        places.append({
            "geonameid": int(f[0]),
            "place": f[1],
            "region": region,
            "country": COUNTRIES[country],
            "latitude": float(f[4]),
            "longitude": float(f[5]),
            "population": population,
        })
    return places


def _features(output) -> torch.Tensor:
    """Normalised projected embeddings; transformers 5 wraps them in pooler_output."""
    emb = output if isinstance(output, torch.Tensor) else output.pooler_output
    return torch.nn.functional.normalize(emb, dim=-1)


@torch.no_grad()
def encode_texts(model, processor, texts: list[str], batch_size: int = 256) -> torch.Tensor:
    out = []
    for i in range(0, len(texts), batch_size):
        inputs = processor(text=texts[i:i + batch_size], return_tensors="pt", padding=True)
        out.append(_features(model.get_text_features(**inputs)))
    return torch.cat(out)


def text_embeddings(model, processor, places: list[dict], regions: list[tuple], min_population: int) -> dict:
    """Country, region and place prompt embeddings, cached on disk."""
    cache = CACHE_DIR / f"text_embeddings_pop{min_population}.pt"
    if cache.exists():
        return torch.load(cache, weights_only=True)

    countries = list(COUNTRIES.values())
    print(f"Encoding {len(countries)} countries, {len(regions)} regions, "
          f"{len(places)} places (cached after the first run)", file=sys.stderr)
    emb = {
        "country": encode_texts(model, processor, [COUNTRY_PROMPT.format(country=c) for c in countries]),
        "region": encode_texts(model, processor,
                               [REGION_PROMPT.format(region=r, country=c) for c, r in regions]),
        "place": encode_texts(model, processor,
                              [PLACE_PROMPT.format(**p) for p in places]),
    }
    torch.save(emb, cache)
    return emb


def perspective_views(pano: Image.Image) -> list[Image.Image]:
    """Cut an equirectangular panorama into N_VIEWS horizontal pinhole views."""
    # Downscale first so bilinear sampling doesn't alias: 90 deg of the
    # panorama then spans roughly VIEW_SIZE pixels.
    width = int(VIEW_SIZE * 360 / FOV_DEG)
    src = np.asarray(pano.convert("RGB").resize((width, width // 2), Image.LANCZOS), dtype=np.float32)
    h, w = src.shape[:2]

    focal = (VIEW_SIZE / 2) / math.tan(math.radians(FOV_DEG) / 2)
    u, v = np.meshgrid(np.arange(VIEW_SIZE) - (VIEW_SIZE - 1) / 2,
                       np.arange(VIEW_SIZE) - (VIEW_SIZE - 1) / 2)
    views = []
    for k in range(N_VIEWS):
        yaw = 2 * math.pi * k / N_VIEWS
        lon = yaw + np.arctan2(u, focal)
        lat = -np.arctan2(v, np.hypot(u, focal))
        x = ((lon / (2 * math.pi)) % 1.0) * w - 0.5
        y = (0.5 - lat / math.pi) * h - 0.5

        x0 = np.floor(x).astype(int)
        y0 = np.clip(np.floor(y).astype(int), 0, h - 2)
        dx, dy = (x - x0)[..., None], np.clip(y - y0, 0, 1)[..., None]
        x0, x1 = x0 % w, (x0 + 1) % w
        img = ((1 - dy) * ((1 - dx) * src[y0, x0] + dx * src[y0, x1])
               + dy * ((1 - dx) * src[y0 + 1, x0] + dx * src[y0 + 1, x1]))
        views.append(Image.fromarray(img.clip(0, 255).astype(np.uint8)))
    return views


@torch.no_grad()
def image_embeddings(model, processor, views: list[Image.Image]) -> torch.Tensor:
    inputs = processor(images=views, return_tensors="pt")
    return _features(model.get_image_features(**inputs))


def grouped_log_softmax(logits: torch.Tensor, groups: torch.Tensor, n_groups: int) -> torch.Tensor:
    """log_softmax of logits (views x items) within each group of items."""
    shift = logits.max(dim=1, keepdim=True).values
    exp = (logits - shift).exp()
    totals = torch.zeros(logits.shape[0], n_groups).index_add_(1, groups, exp)
    return logits - shift - totals[:, groups].log()


def capture_time(path: Path) -> str | None:
    m = re.search(r"(\d{8})_(\d{6})", path.name)
    if not m:
        return None
    return datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S").isoformat()


def geolocate(path, model, processor, places, regions, emb, top_k) -> dict:
    countries = list(COUNTRIES.values())
    region_index = {r: i for i, r in enumerate(regions)}
    region_country = torch.tensor([countries.index(c) for c, _ in regions])
    place_region = torch.tensor([region_index[(p["country"], p["region"])] for p in places])

    views = perspective_views(Image.open(path))
    img = image_embeddings(model, processor, views)
    scale = model.logit_scale.exp()

    # Hierarchical log-probabilities per view, then averaged over views.
    lp_country = (scale * img @ emb["country"].T).log_softmax(dim=1)
    lp_region = grouped_log_softmax(scale * img @ emb["region"].T, region_country, len(countries))
    lp_place = grouped_log_softmax(scale * img @ emb["place"].T, place_region, len(regions))
    lp_region_joint = lp_country[:, region_country] + lp_region
    lp_joint = lp_region_joint[:, place_region] + lp_place

    p_country = lp_country.mean(0).softmax(0)
    p_region = lp_region_joint.mean(0).softmax(0)
    p_place = lp_joint.mean(0).softmax(0)

    top = p_place.topk(top_k)
    predictions = [
        {
            "rank": rank,
            "latitude": round(places[i]["latitude"], 6),
            "longitude": round(places[i]["longitude"], 6),
            "place": places[i]["place"],
            "region": places[i]["region"],
            "country": places[i]["country"],
            "probability": round(prob, 6),
        }
        for rank, (prob, i) in enumerate(zip(top.values.tolist(), top.indices.tolist()), start=1)
    ]
    top_regions = p_region.topk(5)
    return {
        "image": str(path),
        "captured_at": capture_time(path),
        "latitude": predictions[0]["latitude"],
        "longitude": predictions[0]["longitude"],
        "predictions": predictions,
        "country_probabilities": {c: round(p, 4) for c, p in zip(countries, p_country.tolist())},
        "top_regions": [
            {"region": regions[i][1], "country": regions[i][0], "probability": round(p, 4)}
            for p, i in zip(top_regions.values.tolist(), top_regions.indices.tolist())
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", type=Path, help="panorama files or directories (searched recursively)")
    parser.add_argument("-o", "--output", type=Path, help="write the JSON here instead of stdout")
    parser.add_argument("--top-k", type=int, default=10, help="candidate locations per panorama (challenge max: 10)")
    parser.add_argument("--min-population", type=int, default=5000,
                        help="smallest town in the gazetteer (>= 1000)")
    args = parser.parse_args()

    paths = []
    for p in args.inputs:
        paths += sorted(q for q in p.rglob("*") if q.suffix.lower() in {".jpg", ".jpeg", ".png"}) if p.is_dir() else [p]
    if not paths:
        parser.error("no images found")

    torch.set_grad_enabled(False)
    model = CLIPModel.from_pretrained(MODEL_ID).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    places = load_gazetteer(args.min_population)
    regions = sorted({(p["country"], p["region"]) for p in places})
    emb = text_embeddings(model, processor, places, regions, args.min_population)

    results = []
    for n, path in enumerate(paths, start=1):
        result = geolocate(path, model, processor, places, regions, emb, args.top_k)
        best = result["predictions"][0]
        print(f"[{n}/{len(paths)}] {path.name}: {best['latitude']}, {best['longitude']} "
              f"({best['place']}, {best['country']}, p={best['probability']:.3f})", file=sys.stderr)
        results.append(result)

    out = json.dumps({"model": MODEL_ID, "results": results}, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out + "\n", encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
