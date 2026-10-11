#!/usr/bin/env python3
"""Build the external validation and final reference sets from the Panoramax sample (TASKS.md T22).

Writes Data/splits/external_val.json and Data/splits/external_final.json in the reference-set format
panoloc/evaluate.py reads, so `tools/evaluate.py --set val` works like `--set warmup`.

The split is NOT made here: it is the `split` column of Data/panoramax/{PT,ES,FR}.csv, assigned by
tools/fetch_panoramax.py to whole collections (val 207, final 92). Kept exactly as it is: other
tracks already evaluate on `val`. The final set is for one run of the retained configuration
(PLAN.md 4.7, T54); tools/evaluate.py logs every use in Data/splits/final_runs.log.

The OSV-5M official test split (5,206 perspective images, Data/osv5m/index/test.csv) stays reserved
as the final external test of the pixel route (PLAN.md 4.6). Nothing is built on it here: no bank,
calibration, threshold or tag. Keep it that way.

Every reference is primary, with an unknown position radius (Panoramax GPS accuracy is not given), so
results are nominal-only. Tags, all evaluation metadata, never agent input:
  country         PT, ES or FR, from the CSV.
  category        urban | non-urban, inferred from GHSL SMOD E2025 at 1 km (Data/geo/ghsl/smod):
                  urban iff the cell's class >= 21, i.e. the DEGURBA level-1 "cities" (30) and "towns and
                  semi-dense areas" (21, 22, 23); rural clusters (13), low and very low density rural
                  (12, 11) and water (10) are non-urban. A village centre is usually class 13, so it counts
                  as non-urban here although a human labeller might call it urban: the category is an
                  assumption (PLAN.md 1.3), and the evaluator reports both scoring scenarios anyway.
  degurba         the SMOD class name, for finer per-tag results.
  landmark_nearby a Wikidata item with a heritage designation (Data/wikidata/wikidata_ptesfr.csv.gz,
                  `heritage` column) within 150 m of the camera.
  offroad         no car road (OSM highway motorway..residential, service, living_street, road and the
                  _link ramps) within 30 m. Queried from Overpass with a 300 m search radius and cached
                  in Data/splits/cache/roads.json; on a network failure the tag stays null.
  full_sphere     the image is a 2:1 equirectangular (a few Panoramax "360" pictures are partial).
Each record's `info` keeps the raw values: SMOD class, nearest heritage item, road distances,
collection, capture time, size, licence.

--images also writes challenge-like copies to Data/splits/images/<set>/: EXIF stripped (Panoramax
originals carry GPS, the challenge files carry nothing), full spheres resized to 6080x3040, and named
IMG_YYYYMMDD_hhmmss_00_NNN.jpg from the capture time in UTC with a per-set counter, so the filename
parser sees the same format as on Sunday. A reference then points at its copy and lists the copy's
name as an alias, so predictions keyed by either name match. Run it at low priority: about 1 s of CPU
per image.

Usage (from the repo root):
  .venv/bin/python tools/build_splits.py                 # tags + JSON (Overpass for roads, cached)
  nice -n 19 .venv/bin/python tools/build_splits.py --images
  .venv/bin/python tools/build_splits.py --no-roads      # offline
"""
import argparse
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
COUNTRIES = ("PT", "ES", "FR")
PANORAMAX = Path("Data/panoramax")
SPLITS = Path("Data/splits")
SMOD_TIF = Path("Data/geo/ghsl/smod/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif")
WIKIDATA = Path("Data/wikidata/wikidata_ptesfr.csv.gz")
ROADS_CACHE = SPLITS / "cache" / "roads.json"
SMOD_LABELS = {30: "urban_centre", 23: "dense_urban_cluster", 22: "semi_dense_urban_cluster", 21: "suburban",
               13: "rural_cluster", 12: "low_density_rural", 11: "very_low_density_rural", 10: "water"}
URBAN_MIN_SMOD = 21
LANDMARK_RADIUS_M = 150.0
OFFROAD_M = 30.0
ROAD_SEARCH_M = 300
CAR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service",
             "living_street", "road", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
FOOT_WAYS = {"pedestrian", "footway", "path", "track", "steps", "cycleway", "bridleway"}
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "panoloc-build-splits/1 (https://github.com/PedroMattaMPT)"
CHALLENGE_SIZE = (6080, 3040)
EARTH_RADIUS_M = 6_371_000.0


def smod_category(smod):
    """(category, degurba label) for a GHSL SMOD class; (None, None) for nodata."""
    if smod not in SMOD_LABELS:
        return None, None
    return ("urban" if smod >= URBAN_MIN_SMOD else "non-urban"), SMOD_LABELS[smod]


def haversine_many(lat, lng, lats, lngs):
    """Distances in metres from one point to arrays of points."""
    p1, p2 = math.radians(lat), np.radians(lats)
    h = np.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin((np.radians(lngs) - math.radians(lng)) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def nearest_items(lat, lng, lats, lngs, radius_m):
    """(indices within radius_m sorted by distance, their distances), with a cheap bounding-box prefilter."""
    dlat = radius_m / 111_000 + 1e-4
    dlng = dlat / max(0.1, math.cos(math.radians(lat)))
    box = np.flatnonzero((np.abs(lats - lat) <= dlat) & (np.abs(lngs - lng) <= dlng))
    if not len(box):
        return box, np.array([])
    d = haversine_many(lat, lng, lats[box], lngs[box])
    keep = d <= radius_m
    order = np.argsort(d[keep])
    return box[keep][order], d[keep][order]


def point_to_polyline_m(lat, lng, coords):
    """Shortest distance in metres from a point to a polyline [(lat, lng), ...] (local flat projection)."""
    k = math.cos(math.radians(lat))
    pts = np.radians(np.asarray(coords, dtype=float)) * EARTH_RADIUS_M
    x, y = (pts[:, 1] - math.radians(lng) * EARTH_RADIUS_M) * k, pts[:, 0] - math.radians(lat) * EARTH_RADIUS_M
    if len(pts) == 1:
        return float(math.hypot(x[0], y[0]))
    ax, ay, bx, by = x[:-1], y[:-1], x[1:], y[1:]
    dx, dy = bx - ax, by - ay
    t = np.clip(-(ax * dx + ay * dy) / np.maximum(dx * dx + dy * dy, 1e-12), 0, 1)
    return float(np.min(np.hypot(ax + t * dx, ay + t * dy)))


# -- sources --------------------------------------------------------------------------------------

def load_panoramax(root):
    rows = []
    for cc in COUNTRIES:
        with open(root / PANORAMAX / f"{cc}.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r["country"] = cc
                r["image"] = str(PANORAMAX / "images" / cc / f"{r['id']}.jpg")
                rows.append(r)
    return rows


def smod_classes(root, points):
    import pyproj
    import rasterio
    with rasterio.open(root / SMOD_TIF) as src:
        to_moll = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        xy = [to_moll.transform(lng, lat) for lat, lng in points]
        return [int(v[0]) for v in src.sample(xy)]


def heritage_items(root):
    import pandas as pd
    df = pd.read_csv(root / WIKIDATA, usecols=["qid", "lat", "lon", "heritage", "label_en", "label_pt", "label_es",
                                               "label_fr"], dtype=str, keep_default_na=False)
    df = df[df.heritage != ""]
    label = df.label_en.where(df.label_en != "", df.label_pt.where(df.label_pt != "", df.label_es.where(
        df.label_es != "", df.label_fr)))
    return df.lat.astype(float).to_numpy(), df.lon.astype(float).to_numpy(), df.qid.to_list(), label.to_list()


def overpass_ways(points, timeout=180):
    """Every highway way within ROAD_SEARCH_M of any of `points`, with geometry."""
    body = "".join(f"way(around:{ROAD_SEARCH_M},{lat:.7f},{lng:.7f})[highway];" for lat, lng in points)
    query = f"[out:json][timeout:{timeout}];({body});out tags geom;"
    req = urllib.request.Request(OVERPASS_URL, data=urllib.parse.urlencode({"data": query}).encode(),
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
        doc = json.load(resp)
    return [(e["tags"].get("highway"), [(g["lat"], g["lon"]) for g in e["geometry"]])
            for e in doc.get("elements", []) if e.get("type") == "way" and e.get("geometry")]


def road_distances(root, rows, batch=10, retries=3):
    """{id: {"car_road_m", "any_way_m"} or None}: nearest car road / any highway, None beyond the radius."""
    cache_path = root / ROADS_CACHE
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [r for r in rows if r["id"] not in cache]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        pts = [(float(r["lat"]), float(r["lon"])) for r in chunk]
        for attempt in range(retries):
            try:
                ways = overpass_ways(pts)
                break
            except Exception as exc:  # the venue network blips: retry, then leave the tag null
                print(f"overpass batch {i // batch + 1}: {type(exc).__name__}: {exc}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            continue
        for r, (lat, lng) in zip(chunk, pts):
            car = [point_to_polyline_m(lat, lng, g) for kind, g in ways if kind in CAR_ROADS]
            any_way = [point_to_polyline_m(lat, lng, g) for kind, g in ways if kind in CAR_ROADS | FOOT_WAYS]
            near = lambda ds: round(min(ds), 1) if ds and min(ds) <= ROAD_SEARCH_M else None  # noqa: E731
            cache[r["id"]] = {"car_road_m": near(car), "any_way_m": near(any_way)}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=0, sort_keys=True))
        print(f"roads: {min(i + batch, len(todo))}/{len(todo)}", file=sys.stderr)
        time.sleep(2)
    return cache


def capture_utc(text):
    """(UTC datetime, assumed_utc) from the CSV's ISO capture time."""
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc), True
    return dt.astimezone(timezone.utc), False


def challenge_name(dt, counter):
    return f"IMG_{dt:%Y%m%d_%H%M%S}_00_{counter:03d}.jpg"


def write_copy(src, dst, full_sphere):
    """EXIF-free JPEG copy, a full sphere resized to the challenge's 6080x3040."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 300_000_000  # the largest Panoramax sphere is 23800x11900; draft() decodes it smaller
    with Image.open(src) as im:
        if full_sphere:
            im.draft("RGB", CHALLENGE_SIZE)
        im = im.convert("RGB")
        if full_sphere and im.size != CHALLENGE_SIZE:
            im = im.resize(CHALLENGE_SIZE, Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=92)  # no exif= argument: metadata is dropped
        tmp.replace(dst)


# -- build ----------------------------------------------------------------------------------------

def build(root=REPO, roads=True, images=False):
    root = Path(root)
    rows = load_panoramax(root)
    points = [(float(r["lat"]), float(r["lon"])) for r in rows]
    smods = smod_classes(root, points)
    hlat, hlng, hqid, hlabel = heritage_items(root)
    road = road_distances(root, rows) if roads else {}
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 300_000_000  # header reads only; Panoramax spheres reach 23800x11900

    sets = {"val": [], "final": []}
    for r, (lat, lng), smod in zip(rows, points, smods):
        category, degurba = smod_category(smod)
        idx, dist = nearest_items(lat, lng, hlat, hlng, LANDMARK_RADIUS_M)
        with Image.open(root / r["image"]) as im:
            width, height = im.size
        full_sphere = abs(width / height - 2.0) < 0.02
        rd = road.get(r["id"])
        offroad = None if rd is None else (rd["car_road_m"] is None or rd["car_road_m"] > OFFROAD_M)
        when, assumed = capture_utc(r["datetime"])
        sets[r["split"]].append({
            "key": f"{r['id']}.jpg", "lat": lat, "lng": lng, "path": r["image"], "error_radius_m": None,
            "primary": True, "category": category, "category_source": "inferred" if category else "unknown",
            "tags": {"country": r["country"], "category": category, "degurba": degurba,
                     "landmark_nearby": bool(len(idx)), "offroad": offroad, "full_sphere": full_sphere},
            "aliases": [],
            "info": {"source": "panoramax", "id": r["id"], "collection": r["collection"], "smod_class": smod,
                     "heritage_within_150m": int(len(idx)),
                     "nearest_heritage": ({"qid": hqid[idx[0]], "label": hlabel[idx[0]], "distance_m": round(float(dist[0]), 1)}
                                          if len(idx) else None),
                     "car_road_m": rd and rd["car_road_m"], "any_way_m": rd and rd["any_way_m"],
                     "road_lookup": "ok" if rd else ("skipped" if not roads else "failed"),
                     "captured_utc": when.isoformat(), "capture_tz_assumed_utc": assumed,
                     "width": width, "height": height, "license": r["license"],
                     "original_path": r["image"]}})

    for name, refs in sets.items():
        refs.sort(key=lambda x: (x["tags"]["country"], x["info"]["captured_utc"], x["key"]))
        for n, ref in enumerate(refs, start=1):
            copy = SPLITS / "images" / name / challenge_name(datetime.fromisoformat(ref["info"]["captured_utc"]), n)
            if images and not (root / copy).exists():
                write_copy(root / ref["path"], root / copy, ref["tags"]["full_sphere"])
                print(f"{name}: {n}/{len(refs)} {copy.name}", file=sys.stderr, flush=True)
            if (root / copy).exists():
                ref["path"], ref["aliases"] = str(copy), [copy.name]
        doc = {"schema": "panoloc.refset/1", "set": name,
               "built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "built_by": "tools/build_splits.py",
               "source": "Panoramax sample, Data/panoramax/{PT,ES,FR}.csv; split column kept as assigned "
                         "by tools/fetch_panoramax.py (whole collections)",
               "estimated": False, "is_ground_truth": False,
               "reference_note": "camera GPS from Panoramax, accuracy unknown: nominal-only results",
               "rules": {"category": f"GHSL SMOD E2025 1 km class >= {URBAN_MIN_SMOD} -> urban (DEGURBA cities + "
                                     "towns/semi-dense); otherwise non-urban",
                         "landmark_nearby": f"Wikidata heritage item within {LANDMARK_RADIUS_M:.0f} m",
                         "offroad": (f"no OSM car road within {OFFROAD_M:.0f} m (Overpass, {ROAD_SEARCH_M} m search)"
                                     if roads else "not computed (--no-roads)"),
                         "full_sphere": "width / height within 0.02 of 2"},
               "counts": summarise(refs), "references": refs}
        out = root / SPLITS / f"external_{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{out.relative_to(root)}: {len(refs)} references {json.dumps(doc['counts'])}")
    return sets


def summarise(refs):
    counts = {}
    for ref in refs:
        for tag, value in ref["tags"].items():
            key = "null" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
            counts.setdefault(tag, {}).setdefault(key, 0)
            counts[tag][key] += 1
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-roads", action="store_true", help="skip the Overpass road lookup (offroad stays null)")
    ap.add_argument("--images", action="store_true", help="also write EXIF-free challenge-format copies")
    args = ap.parse_args()
    build(roads=not args.no_roads, images=args.images)


if __name__ == "__main__":
    main()
