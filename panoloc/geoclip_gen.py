"""GeoCLIP as an extra candidate generator over a Portugal/Spain/France gallery (PLAN.md 4.5; TASKS.md T38).

GeoCLIP (geoclip 1.2.3: CLIP ViT-L/14 image tower + MLP, and a GPS location encoder) scores an image
against a gallery of coordinates. The stock gallery is 100k points sampled from GeoCLIP's Flickr
training photos, worldwide; a uniform grid is known to fail (PLAN.md 4.5). Galleries here
(Data/geoclip/gallery_<name>.csv, built once by `python -m panoloc.geoclip_gen build-galleries`):
  stock   the stock points inside the PT/ES/FR geoBoundaries outlines (islands included, France's
          overseas territories excluded by the lon >= -32 / lat >= 27 box)
  osv5m   the camera positions of the OSV-5M train + val bank (roadside coverage; never `test`)
  merged  both, exact duplicates removed
Each point carries its country (outline or OSV-5M metadata); a candidate takes its centre's. The stock
gallery is thin on Portugal (PT 813, ES 5,696, FR 4,566 points), the OSV-5M one dense (PT 51,551).
"stock" is the default (GALLERY): it scored best on the Panoramax validation split (eval_geoclip.json).

Per view, softmax over the gallery (GeoCLIP's own logit scale); a panorama averages the per-view
distributions (an average, never a product: PLAN.md 3.2). Candidates come from greedy clustering of
the TOP_POINTS most probable gallery points: in probability order, a point within cluster_m of an
existing centre adds its probability to that centre, else it starts a new one. Each centre is an
`area` Candidate: GeoCLIP's coordinate is a gallery point where photos were taken, not this camera.
  weight     the cluster's averaged probability mass (unnormalised support, not calibrated)
  extent_m   the probability-weighted mean distance of its members to the centre, at least 1 km
             (details["extent_source"] = "gallery probability spread")
  group      "geoclip": its own encoder (OpenAI CLIP-L), but it still shares scene information with
             the PE-Core sources and can make correlated mistakes (PLAN.md 3.2)

  gen = GeoCLIPGen()                                   # ~0.7 GB of GPU memory in float16
  cands = gen.candidates(load_panorama(path), k=10)    # or the pipeline's cut_views() list
Evaluated with 8 square views of 90 degrees (cut_views' default), the default for a panorama array.

Every call depends only on its arguments and the read-only gallery: no state carries across panoramas.
"""
import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc.candidates import Candidate

REPO_ROOT = Path(__file__).resolve().parent.parent
GALLERY_DIR = REPO_ROOT / "Data" / "geoclip"
GALLERIES = ("stock", "osv5m", "merged")
GALLERY = "stock"
VIEW_CROP = "square"  # GeoCLIP's processor centre-crops to 224: a square view keeps everything
VIEW_SIZE = 512
TOP_POINTS = 3000
CLUSTER_M = 25_000.0
MIN_EXTENT_M = 1000.0
GROUP = "geoclip"
SOURCE = "geoclip"
EUROPE_BOX = {"lat": (27.0, 52.0), "lon": (-32.0, 10.0)}  # PT/ES/FR incl. Azores, Madeira, Canaries, Corsica
EARTH_R = 6_371_000.0


def _haversine_to(lat, lon, lats, lons):
    p1, p2 = np.radians(lat), np.radians(lats)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def cluster(lat, lon, prob, cluster_m=CLUSTER_M, top=TOP_POINTS):
    """Greedy clustering of the `top` most probable points -> [(centre index, mass, extent_m)], heaviest first."""
    order = np.argsort(-prob)[:top]
    centres, mass, spread = [], [], []
    for i in order:
        if centres:
            d = _haversine_to(lat[i], lon[i], lat[centres], lon[centres])
            j = int(np.argmin(d))
            if d[j] <= cluster_m:
                mass[j] += prob[i]
                spread[j] += prob[i] * d[j]
                continue
        centres.append(int(i))
        mass.append(float(prob[i]))
        spread.append(0.0)
    out = [(c, m, max(s / m if m > 0 else 0.0, MIN_EXTENT_M)) for c, m, s in zip(centres, mass, spread)]
    return sorted(out, key=lambda t: -t[1])


class GeoCLIPGen:
    """GeoCLIP image tower (float16, text tower dropped) + precomputed gallery location features."""

    def __init__(self, gallery=GALLERY, device=None, threads=4):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from geoclip import GeoCLIP
        torch.set_num_threads(threads)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        model = GeoCLIP()
        clip = model.image_encoder.CLIP
        clip.text_model, clip.text_projection = None, None  # get_image_features never uses them
        self.dtype = torch.float16 if self.device != "cpu" else torch.float32
        self.clip_vision = clip.to(self.device, self.dtype).eval()
        self.mlp = model.image_encoder.mlp.to(self.device).float().eval()
        self.processor = model.image_encoder.image_processor
        self.logit_scale = float(model.logit_scale.exp())
        self.location_encoder = model.location_encoder.to(self.device).float().eval()
        del model
        self._torch = torch
        self.set_gallery(gallery)

    def set_gallery(self, name):
        """Switch to another built gallery (encodes its coordinates once)."""
        torch = self._torch
        g, self.country = read_gallery(name)
        self.gallery_name, self.lat, self.lon = name, g[:, 0], g[:, 1]
        with torch.inference_mode():
            gps = torch.from_numpy(g).float().to(self.device)
            feats = torch.cat([self.location_encoder(gps[i:i + 8192]) for i in range(0, len(gps), 8192)])
            self.loc_feats = torch.nn.functional.normalize(feats, dim=1)

    def image_features(self, images):
        """PIL images (or arrays) -> N x 512 float32 normalised GeoCLIP image features."""
        from geoclip.model.image_encoder import _extract_image_features
        torch = self._torch
        ims = [im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im)) for im in images]
        x = self.processor(images=[im.convert("RGB") for im in ims], return_tensors="pt")["pixel_values"]
        with torch.inference_mode():
            f = _extract_image_features(self.clip_vision.get_image_features(pixel_values=x.to(self.device, self.dtype)))
            return torch.nn.functional.normalize(self.mlp(f.float()), dim=1).cpu().numpy()

    def probs_from_features(self, features):
        """N x 512 image features -> N x G float32 softmax over the current gallery."""
        torch = self._torch
        with torch.inference_mode():
            f = torch.from_numpy(np.atleast_2d(features)).float().to(self.device)
            return torch.softmax(self.logit_scale * f @ self.loc_feats.T, dim=1).cpu().numpy()

    def view_probs(self, images):
        """PIL images (or arrays) -> V x G float32 softmax over the gallery, one row per image."""
        return self.probs_from_features(self.image_features(images))

    def candidates_from_probs(self, probs, k=10, cluster_m=CLUSTER_M):
        """Averaged per-view probabilities -> top-k `area` Candidates (module docstring)."""
        p = np.atleast_2d(probs).mean(axis=0)
        out = []
        for rank, (i, mass, extent) in enumerate(cluster(self.lat, self.lon, p, cluster_m)[:k], start=1):
            out.append(Candidate(
                float(self.lat[i]), float(self.lon[i]), "area", f"{SOURCE}:{self.gallery_name}/{i}",
                label=f"GeoCLIP {self.gallery_name} gallery point {i}", weight=float(mass), accuracy_m=None,
                extent_m=float(extent), country=str(self.country[i]) or None, group=GROUP,
                details={"prob_mass": round(float(mass), 5), "peak_prob": round(float(p[i]), 6), "rank": rank,
                         "gallery": self.gallery_name, "gallery_size": len(p), "cluster_m": cluster_m,
                         "n_views": len(np.atleast_2d(probs)), "extent_source": "gallery probability spread",
                         "note": "GeoCLIP gallery point: where photos were taken, not this camera"}))
        return out

    def candidates(self, pano_or_views, k=10, crop=VIEW_CROP):
        """Candidates for ONE panorama: its equirectangular array (cut here into the evaluated 8 x 90
        degree views of 512 px), panoloc.views Views (horizontal ones used) or plain images."""
        from panoloc.retrieval import view_image
        if isinstance(pano_or_views, np.ndarray) and pano_or_views.ndim == 3 and pano_or_views.shape[1] > pano_or_views.shape[0]:
            from panoloc.views import cut_views
            pano_or_views = cut_views(pano_or_views, size=VIEW_SIZE)
        items = list(pano_or_views)
        if items and hasattr(items[0], "name"):
            items = [view_image(v, crop) for v in items if v.name.startswith("h")]
        return self.candidates_from_probs(self.view_probs(items), k=k)


def gallery_path(name):
    return GALLERY_DIR / f"gallery_{name}.csv"


def read_gallery(name=GALLERY):
    """(N x 2 float64 lat/lon, N country codes) of a built gallery."""
    import pandas as pd
    if name not in GALLERIES:
        raise ValueError(f"gallery must be one of {GALLERIES}, got {name!r}")
    df = pd.read_csv(gallery_path(name), dtype={"country": str}, keep_default_na=False)
    return df[["lat", "lon"]].to_numpy(dtype=float), df["country"].to_numpy(dtype=str)


def build_galleries():
    """Write Data/geoclip/gallery_{stock,osv5m,merged}.csv (lat,lon,country)."""
    import json

    import geoclip
    import pandas as pd
    import shapely
    from shapely.geometry import shape

    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    stock = pd.read_csv(Path(geoclip.__file__).parent / "model" / "gps_gallery" / "coordinates_100K.csv")
    box = stock["LAT"].between(*EUROPE_BOX["lat"]) & stock["LON"].between(*EUROPE_BOX["lon"])
    stock = stock[box]
    country = np.full(len(stock), "", dtype=object)
    for iso, cc in (("PRT", "PT"), ("ESP", "ES"), ("FRA", "FR")):
        doc = json.loads((REPO_ROOT / "Data" / "geo" / "boundaries" / "geoboundaries" / f"{iso}-ADM0.geojson").read_text())
        geom = shape(doc["features"][0]["geometry"]).buffer(0.01)  # ~1 km: keep coastal points
        shapely.prepare(geom)
        inside = shapely.contains_xy(geom, stock["LON"].to_numpy(), stock["LAT"].to_numpy())
        country[inside & (country == "")] = cc
    g_stock = pd.DataFrame({"lat": stock["LAT"].to_numpy(), "lon": stock["LON"].to_numpy(), "country": country})
    g_stock = g_stock[g_stock["country"] != ""]

    from panoloc.retrieval import read_partitions
    meta = read_partitions()
    g_osv = meta.loc[meta["partition"].isin(["train", "val"]), ["lat", "lon", "country"]]
    g_merged = pd.concat([g_stock, g_osv], ignore_index=True).round({"lat": 6, "lon": 6}).drop_duplicates(["lat", "lon"])
    for name, g in (("stock", g_stock), ("osv5m", g_osv), ("merged", g_merged)):
        g.to_csv(gallery_path(name), index=False, float_format="%.6f")
        print(f"{name}: {len(g)} points -> {gallery_path(name)}", g["country"].value_counts().to_dict())


def main(argv=None):
    ap = argparse.ArgumentParser(description="GeoCLIP PT/ES/FR galleries")
    ap.add_argument("cmd", choices=["build-galleries"])
    ap.parse_args(argv)
    build_galleries()


if __name__ == "__main__":
    main()
