#!/usr/bin/env python3
"""Evaluate PE-Core kNN retrieval (TASKS.md T36) on validation data only -> Data/osv5m/emb/eval_knn.json.

Two tracks, both validation splits (PLAN.md 4.6); the OSV-5M `test` partition and the Panoramax `final`
split are reserved for the one final run (T54) and are refused here:
  osv5m_val      every OSV-5M `val` image as a single-view query against a `train`-only gallery
                 (val groups never share a sequence or 10 km block with train)
  panoramax_val  every Panoramax `val` panorama (Data/panoramax/{PT,ES,FR}.csv) as its runtime views
                 (panoloc.retrieval.embed_views defaults: 12 x 60 degrees) against the
                 default train + val gallery. Panoramas wider than 6080 px are first resized to the
                 challenge's width of 6080 px, keeping their aspect (PLAN.md 4.6). 11 of the 207 are
                 not 2:1 (partial panoramas); they stay in, with panoloc.views' warning
Metrics per track and country: median top-1 error, share within 1 / 25 / 100 / 750 km, and the mean
challenge score of the top-1 coordinate repeated x10 (panoloc.scoring.list_score) as urban and as
non-urban. `top1` is the heaviest candidate; `best_point` is the candidate with the highest expected
theta under the candidate weights (panoloc.scoring.best_point), as fusion would choose it.
`coverage` is the share of queries with any of the first 4 / 10 / 20 candidates within 1 / 25 / 100 km.

  .venv/bin/python tools/eval_knn.py embed-panoramax     # caches view embeddings (GPU, both crops)
  .venv/bin/python tools/eval_knn.py eval                # needs the complete bank (tools/embed_bank.py)
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from panoloc import retrieval  # noqa: E402
from panoloc.scoring import best_point, haversine_m, list_score  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PMX = ROOT / "Data" / "panoramax"
PMX_CACHE = retrieval.EMB_DIR / "panoramax_val_views.npz"
OUT = retrieval.EMB_DIR / "eval_knn.json"
CHALLENGE_SIZE = (6080, 3040)
THRESHOLDS_KM = (1, 25, 100, 750)
CROPS = ("4:3", "square")


def panoramax_val():
    frames = [pd.read_csv(PMX / f"{c}.csv").assign(country=c) for c in ("PT", "ES", "FR")]
    df = pd.concat(frames, ignore_index=True)
    df = df[df["split"] == "val"].reset_index(drop=True)  # never `final`
    df["path"] = [PMX / "images" / c / f"{i}.jpg" for c, i in zip(df["country"], df["id"])]
    return df


def load_resized(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as im:
        if im.width > CHALLENGE_SIZE[0]:  # keep the aspect: a few Panoramax pictures are not 2:1
            size = (CHALLENGE_SIZE[0], round(im.height * CHALLENGE_SIZE[0] / im.width))
            im.draft("RGB", size)
            im = im.convert("RGB").resize(size, Image.BILINEAR)
        return np.array(im.convert("RGB"))


def embed_panoramax(args):
    df = panoramax_val()
    model = retrieval.PECore()
    out = {c: [] for c in CROPS}
    t0 = time.time()
    for i, path in enumerate(df["path"]):
        pano = load_resized(path)
        for c in CROPS:
            emb, names = retrieval.embed_views(model, pano, crop=c)  # the runtime defaults (fov, count, size)
            out[c].append(emb.astype(np.float16))
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{len(df)} panoramas, {(time.time() - t0) / (i + 1):.2f} s each", flush=True)
    np.savez(PMX_CACHE, ids=np.array(df["id"].astype(str).tolist(), dtype=str), names=np.array(names, dtype=str),
             view_fov=retrieval.VIEW_FOV, **{f"emb_{c.replace(':', 'x')}": np.stack(out[c]) for c in CROPS})
    print(f"wrote {PMX_CACHE}: {len(df)} panoramas in {time.time() - t0:.0f} s")


def metrics(errors_m, top1, truths):
    e = np.asarray(errors_m) / 1000
    res = {"n": len(e), "median_km": round(float(np.median(e)), 2), "mean_km": round(float(np.mean(e)), 1)}
    for t in THRESHOLDS_KM:
        res[f"within_{t}km"] = round(float(np.mean(e <= t)), 4)
    for cat in ("urban", "non-urban"):
        res[f"score_{cat}"] = round(float(np.mean([list_score([p] * 10, y, cat) for p, y in zip(top1, truths)])), 1)
    return res


def evaluate(cands_list, truths, countries, label):
    """cands_list: one candidate list per query. Returns metrics for top1 and best_point, overall and by country."""
    out = {}
    picks = {"top1": [c[0].point for c in cands_list]}
    for cat in ("non-urban", "urban"):
        hyp = [[(c.point, c.weight) for c in cands] for cands in cands_list]
        picks[f"best_point_{cat}"] = [best_point([c.point for c in cands], h, category=cat)[0]
                                      for cands, h in zip(cands_list, hyp)]
    countries = np.asarray(countries)
    # candidate coverage (PLAN.md 4.6): is any of the first n candidates within t km?
    best_of = {n: np.array([min([haversine_m(c.point, y) for c in cands[:n]] or [np.inf]) for cands, y in zip(cands_list, truths)])
               for n in (4, 10, 20)}
    out["coverage"] = {f"top{n}_within_{t}km": round(float(np.mean(d <= t * 1000)), 4)
                       for n, d in best_of.items() for t in (1, 25, 100)}
    for name, pts in picks.items():
        err = np.array([haversine_m(p, y) for p, y in zip(pts, truths)])
        out[name] = {"all": metrics(err, pts, truths)}
        for c in ("PT", "ES", "FR"):
            m = countries == c
            if m.any():
                out[name][c] = metrics(err[m], [p for p, k in zip(pts, m) if k], [y for y, k in zip(truths, m) if k])
    print(f"{label}: top1 median {out['top1']['all']['median_km']} km, "
          + ", ".join(f"<{t} km {out['top1']['all'][f'within_{t}km']:.3f}" for t in THRESHOLDS_KM)
          + f"; score urban {out['top1']['all']['score_urban']}, non-urban {out['top1']['all']['score_non-urban']}"
          + f" | best_point non-urban median {out['best_point_non-urban']['all']['median_km']} km,"
          + f" score {out['best_point_non-urban']['all']['score_non-urban']}", flush=True)
    return out


def run_eval(args):
    report = {"embed_version": retrieval.EMBED_VERSION, "k": args.k, "per_view_k": retrieval.PER_VIEW_K,
              "note": "validation splits only; OSV-5M test and Panoramax final are reserved for T54"}
    # OSV-5M val: single images vs a train-only gallery
    t = time.time()
    bank = retrieval.Bank.open(partitions=("train",))
    meta, emb = retrieval.load_embeddings(partitions=("val",))
    print(f"train gallery {len(bank)}, val queries {len(meta)} ({time.time() - t:.0f} s)", flush=True)
    sims, rows = bank.neighbours(emb.astype(np.float32), retrieval.PER_VIEW_K)
    cands = [retrieval.aggregate(sims[i:i + 1], rows[i:i + 1], bank, k=args.k) for i in range(len(meta))]
    truths = list(zip(meta["lat"], meta["lon"]))
    report["osv5m_val"] = evaluate(cands, truths, meta["country"], "osv5m_val")
    report["osv5m_val"]["gallery"] = {"partitions": ["train"], "size": len(bank)}
    region_hit = np.mean([c[0].details["region"] == r for c, r in zip(cands, meta["region"])])
    report["osv5m_val"]["top1_region_accuracy"] = round(float(region_hit), 4)
    del bank

    # Panoramax val: the runtime views vs the default gallery
    bank = retrieval.Bank.open()
    df = panoramax_val()
    z = np.load(PMX_CACHE)
    if z["ids"].tolist() != df["id"].astype(str).tolist():
        sys.exit("panoramax cache does not match the val split: rerun embed-panoramax")
    truths = list(zip(df["lat"], df["lon"]))
    report["panoramax_val"] = {"gallery": {"partitions": list(retrieval.GALLERY_PARTITIONS), "size": len(bank)}}
    names = z["names"].tolist()
    report["panoramax_val"]["views"] = {"names": names, "fov_deg": float(z["view_fov"])}
    for crop in CROPS:
        views = z[f"emb_{crop.replace(':', 'x')}"].astype(np.float32)
        for tau in args.taus:
            cands = [bank.search(v, k=args.k, tau=tau, view_names=names) for v in views]
            report["panoramax_val"][f"crop={crop},tau={tau}"] = evaluate(cands, truths, df["country"],
                                                                        f"panoramax_val crop={crop} tau={tau}")
        cands = [bank.search(v, k=args.k, view_names=names, dedup="image") for v in views]
        report["panoramax_val"][f"crop={crop},tau={retrieval.TAU},dedup=image"] = evaluate(
            cands, truths, df["country"], f"panoramax_val crop={crop} tau={retrieval.TAU} no group dedup")
        # a single view (h000) alone, to see what the other views add
        cands = [bank.search(v[:1], k=args.k) for v in views]
        report["panoramax_val"][f"crop={crop},single_view"] = evaluate(cands, truths, df["country"],
                                                                      f"panoramax_val crop={crop} single view")
    OUT.write_text(json.dumps(report, indent=1))
    print(f"wrote {OUT}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("embed-panoramax")
    e = sub.add_parser("eval")
    e.add_argument("--k", type=int, default=retrieval.DEFAULT_K)
    e.add_argument("--taus", type=float, nargs="+", default=[0.01, 0.02, 0.05, 0.1])
    args = ap.parse_args(argv)
    {"embed-panoramax": embed_panoramax, "eval": run_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
