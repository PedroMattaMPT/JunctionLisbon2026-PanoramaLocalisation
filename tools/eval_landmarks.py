#!/usr/bin/env python3
"""Evaluate the Commons landmark gallery (TASKS.md T33; PLAN.md 4.5) on Panoramax `val` -> Data/gallery/emb/eval_landmarks.json.

Queries: every Panoramax `val` panorama (Data/panoramax/{PT,ES,FR}.csv), as the horizontal views
panoloc.retrieval.embed_views makes at run time (N_VIEWS views of VIEW_FOV degrees). The `final`
split is reserved for the one final run (T54) and is never read. The view embeddings come from
tools/eval_knn.py's cache (Data/osv5m/emb/panoramax_val_views.npz: same PE-Core, panoramas first
resized to 6080 px wide) when it holds every val panorama with the current view layout; otherwise
they are embedded here and cached in Data/gallery/emb/panoramax_val_views.npz.

Reported, overall and per country, for the gallery as embedded now:
  coverage    share of panoramas with any gallery landmark within 100 m / 1 km / 5 km of the camera.
              This is a ceiling for any method that outputs a landmark point; `planned` is the same
              for every photo fetch_commons plans (all of PT, the first 30,000 of ES and FR), the
              ceiling once the download completes
  retrieval   distance from the camera to the top-1 landmark and to the nearest of the top 5; share
              within 100 m / 1 km / 5 km over all panoramas, and over the panoramas covered at that
              distance (the retrieval recall where a hit was possible)
  similarity  top-1 cosine similarity of hits within 1 km vs. the rest, to calibrate a floor
The distance is to the landmark's own point (Wikidata P625), not to a camera position.

  .venv/bin/python tools/eval_landmarks.py                # ~1 min with the cached view embeddings
  .venv/bin/python tools/eval_landmarks.py --beta 0 --k 20 --out /dev/null    # variants, not saved
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from panoloc import landmarks, retrieval  # noqa: E402

PMX = ROOT / "Data" / "panoramax"
BANK_CACHE = retrieval.EMB_DIR / "panoramax_val_views.npz"
OWN_CACHE = landmarks.EMB_DIR / "panoramax_val_views.npz"
OUT = landmarks.EMB_DIR / "eval_landmarks.json"
CHALLENGE_WIDTH = 6080
THRESHOLDS_M = (100, 1000, 5000)
PLANNED_CAP = {"PT": None, "ES": 30000, "FR": 30000}
EARTH_M = 6_371_000.0


def panoramax_val():
    rows = []
    for cc in ("PT", "ES", "FR"):
        with open(PMX / f"{cc}.csv", newline="") as f:
            for r in csv.DictReader(f):
                if r["split"] == "val":  # never `final`
                    rows.append({"id": r["id"], "country": cc, "lat": float(r["lat"]), "lon": float(r["lon"]),
                                 "path": PMX / "images" / cc / f"{r['id']}.jpg"})
    return rows


def dist_m(lat, lon, lats, lons):
    """Haversine distance from one point to arrays of points, in metres."""
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 2 * EARTH_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def load_resized(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as im:
        if im.width > CHALLENGE_WIDTH:
            size = (CHALLENGE_WIDTH, round(im.height * CHALLENGE_WIDTH / im.width))
            im.draft("RGB", size)
            im = im.convert("RGB").resize(size, Image.BILINEAR)
        return np.array(im.convert("RGB"))


def view_embeddings(rows, crop):
    """({panorama id: V x 1024 float32}, view names) for the val panoramas, with panoloc.retrieval's
    runtime views (embed_views defaults: N_VIEWS views of VIEW_FOV degrees)."""
    key = f"emb_{crop.replace(':', 'x')}"
    want_names = [f"h{round(i * 360 / retrieval.N_VIEWS):03d}" for i in range(retrieval.N_VIEWS)]
    for cache in (BANK_CACHE, OWN_CACHE):
        if cache.exists():
            z = np.load(cache, allow_pickle=True)  # our own cache files
            names = z["names"].tolist() if "names" in z.files else [f"h{45 * i:03d}" for i in range(8)]
            fov = float(z["view_fov"]) if "view_fov" in z.files else 90.0
            got = {str(i): e.astype(np.float32) for i, e in zip(z["ids"], z[key])}
            if names == want_names and fov == retrieval.VIEW_FOV and all(r["id"] in got for r in rows):
                print(f"view embeddings from {cache.relative_to(ROOT)}: {len(names)} views of {fov:g} degrees", flush=True)
                return got, names
    model = retrieval.PECore()
    out, names = {c: [] for c in ("4:3", "square")}, None
    t0 = time.time()
    for i, r in enumerate(rows):
        pano = load_resized(r["path"])
        for c in out:
            emb, names = retrieval.embed_views(model, pano, crop=c)
            out[c].append(emb.astype(np.float16))
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{len(rows)} panoramas embedded, {(time.time() - t0) / (i + 1):.1f} s each", flush=True)
    np.savez(OWN_CACHE, ids=np.array([r["id"] for r in rows]), names=np.array(names), view_fov=retrieval.VIEW_FOV,
             **{f"emb_{c.replace(':', 'x')}": np.stack(v) for c, v in out.items()})
    return {r["id"]: e.astype(np.float32) for r, e in zip(rows, out[crop])}, names


def planned_points():
    """(lat, lon) arrays of every photo fetch_commons plans to fetch (PLANNED_CAP per country)."""
    lats, lons = [], []
    for cc, cap in PLANNED_CAP.items():
        path = landmarks.COMMONS_DIR / cc / "plan.csv"
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f)):
                if cap is not None and i >= cap:
                    break
                lats.append(float(r["lat"]))
                lons.append(float(r["lon"]))
    return np.array(lats), np.array(lons)


def share(mask):
    mask = np.asarray(mask, bool)
    return round(float(mask.mean()), 4) if mask.size else None


def finite_median(a):
    """Median distance in metres; None when it is infinite (most panoramas without a candidate) or empty."""
    med = float(np.median(a)) if len(a) else float("inf")
    return round(med) if np.isfinite(med) else None


def summarise(recs):
    near = np.array([r["nearest_gallery_m"] for r in recs])
    planned = np.array([r["nearest_planned_m"] for r in recs])
    top1 = np.array([r["top1_m"] for r in recs])
    best5 = np.array([r["best5_m"] for r in recs])
    out = {"n": len(recs), "with_candidates": share([r["top1_qid"] is not None for r in recs]),
           "coverage": {f"within_{t}m": share(near <= t) for t in THRESHOLDS_M},
           "coverage_planned": {f"within_{t}m": share(planned <= t) for t in THRESHOLDS_M},
           "top1": {"median_m": finite_median(top1),
                    **{f"within_{t}m": share(top1 <= t) for t in THRESHOLDS_M}},
           "best_of_top5": {"median_m": finite_median(best5),
                            **{f"within_{t}m": share(best5 <= t) for t in THRESHOLDS_M}},
           "given_coverage": {}}
    for t in THRESHOLDS_M:
        m = near <= t
        out["given_coverage"][f"{t}m"] = {"n_covered": int(m.sum()), "top1_within": share(top1[m] <= t),
                                          "best5_within": share(best5[m] <= t)}
    return out


def similarity_stats(recs):
    good = np.array([r["top1_similarity"] for r in recs if r["top1_similarity"] is not None and r["top1_m"] <= 1000])
    bad = np.array([r["top1_similarity"] for r in recs if r["top1_similarity"] is not None and r["top1_m"] > 1000])
    q = lambda a: {f"p{p}": round(float(np.percentile(a, p)), 4) for p in (10, 50, 90)} if len(a) else None  # noqa: E731
    return {"top1_within_1km": {"n": len(good), **(q(good) or {})}, "top1_beyond_1km": {"n": len(bad), **(q(bad) or {})}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--crop", default=retrieval.VIEW_CROP, choices=("4:3", "square"))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--per-view-k", type=int, default=landmarks.PER_VIEW_K)
    ap.add_argument("--tau", type=float, default=landmarks.TAU)
    ap.add_argument("--beta", type=float, default=landmarks.HUB_BETA, help="hubness correction (0 = plain cosine)")
    ap.add_argument("--min-similarity", type=float, default=landmarks.MIN_SIMILARITY)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    rows = panoramax_val()
    t0 = time.time()
    gallery = landmarks.Gallery.open()
    print(f"gallery {len(gallery):,} photos {gallery.countries()} loaded in {time.time() - t0:.1f} s", flush=True)
    emb, view_names = view_embeddings(rows, args.crop)
    plat, plon = planned_points()
    glat, glon = gallery.meta["lat"], gallery.meta["lon"]
    recs, t_search = [], 0.0
    for r in rows:
        t = time.time()
        cands = gallery.search(emb[r["id"]], k=args.k, per_view_k=args.per_view_k, tau=args.tau, beta=args.beta,
                               min_similarity=args.min_similarity, view_names=view_names)
        t_search += time.time() - t
        d = [float(dist_m(r["lat"], r["lon"], np.array([c.lat]), np.array([c.lng]))[0]) for c in cands]
        nearest = dist_m(r["lat"], r["lon"], glat, glon)
        i_near = int(np.argmin(nearest))
        top = cands[0] if cands else None
        recs.append({"id": r["id"], "country": r["country"], "nearest_gallery_m": round(float(nearest[i_near]), 1),
                     "nearest_gallery_qid": str(gallery.meta["qid"][i_near]),
                     "nearest_planned_m": round(float(dist_m(r["lat"], r["lon"], plat, plon).min()), 1) if len(plat) else None,
                     "n_gallery_within_1km": int((nearest <= 1000).sum()),
                     "top1_qid": top.details["qid"] if top else None, "top1_name": top.details["name"] if top else None,
                     "top1_m": round(d[0], 1) if d else float("inf"), "top1_similarity": top.details["similarity"] if top else None,
                     "top1_weight": round(top.weight, 4) if top else None, "top1_n_views": top.details["n_views"] if top else None,
                     "best5_m": round(min(d[:5]), 1) if d else float("inf"),
                     "best5_rank": int(np.argmin(d[:5])) + 1 if d else None})
    by_country = {cc: summarise([x for x in recs if x["country"] == cc]) for cc in ("PT", "ES", "FR")}
    report = {"task": "T33", "queries": "Panoramax val (never final), 8 horizontal views each",
              "gallery": {"photos": len(gallery), "by_country": gallery.countries(),
                          "manifest_written": landmarks.read_manifest().get("written")},
              "settings": {"crop": args.crop, "views": len(view_names), "view_fov": retrieval.VIEW_FOV,
                           "k": args.k, "per_view_k": args.per_view_k, "tau": args.tau, "beta": args.beta,
                           "min_similarity": args.min_similarity, "embed_version": retrieval.EMBED_VERSION},
              "distance_note": "camera to the landmark's Wikidata point, not to a camera position",
              "search_ms_per_panorama": round(1000 * t_search / len(rows), 1),
              "all": summarise(recs), "by_country": by_country, "similarity": similarity_stats(recs),
              "per_panorama": recs}
    if args.out != "/dev/null":
        Path(args.out).write_text(json.dumps(report, indent=1))
    a = report["all"]
    print(json.dumps({k: report[k] for k in ("gallery", "settings", "search_ms_per_panorama", "similarity")}, indent=1))
    for name, s in [("all", a)] + list(by_country.items()):
        print(f"{name:>3} n={s['n']:3d} with candidates {s['with_candidates']} coverage {s['coverage']} planned {s['coverage_planned']}\n"
              f"    top1 {s['top1']} best5 {s['best_of_top5']}\n    given coverage {s['given_coverage']}")


if __name__ == "__main__":
    main()
