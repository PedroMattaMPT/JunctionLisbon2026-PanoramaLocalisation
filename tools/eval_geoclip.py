#!/usr/bin/env python3
"""Evaluate GeoCLIP (panoloc.geoclip_gen, TASKS.md T38) on the Panoramax val split -> Data/geoclip/eval_geoclip.json.

The same 207 Panoramax `val` panoramas and metrics as tools/eval_knn.py (never the `final` split):
8 horizontal views per panorama, per-view probabilities averaged, candidates clustered at 25 km. Each
gallery (stock, osv5m, merged) is scored, and kNN's numbers from eval_knn.json are copied in for the
comparison. View features are cached in Data/geoclip/panoramax_val_feats.npz.

Also OSV_SUBSET random OSV-5M `val` images (seed 0) as single-image queries, against the stock gallery
only (the osv5m and merged galleries contain the val coordinates themselves), next to PE-Core kNN on
the same images against the train-only bank.

Usage: .venv/bin/python tools/eval_geoclip.py
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from eval_knn import OUT as KNN_OUT, evaluate, load_resized, panoramax_val  # noqa: E402
from panoloc import geoclip_gen  # noqa: E402
from panoloc.retrieval import view_image  # noqa: E402

CACHE = geoclip_gen.GALLERY_DIR / "panoramax_val_feats.npz"
OUT = geoclip_gen.GALLERY_DIR / "eval_geoclip.json"
OSV_SUBSET = 2000


def main():
    from panoloc.views import cut_views
    df = panoramax_val()
    gen = geoclip_gen.GeoCLIPGen(gallery="stock")
    ids = df["id"].astype(str).tolist()
    if CACHE.exists() and np.load(CACHE)["ids"].tolist() == ids:
        feats = np.load(CACHE)["feats"]
    else:
        t0, feats = time.time(), []
        for i, path in enumerate(df["path"]):
            views = [v for v in cut_views(load_resized(path), size=512) if v.name.startswith("h")]
            feats.append(gen.image_features([view_image(v, geoclip_gen.VIEW_CROP) for v in views]))
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(df)} panoramas, {(time.time() - t0) / (i + 1):.2f} s each", flush=True)
        feats = np.stack(feats)
        np.savez(CACHE, ids=np.array(ids), feats=feats)
    truths = list(zip(df["lat"], df["lon"]))
    report = {"split": "panoramax val", "n": len(df), "views": 8, "crop": geoclip_gen.VIEW_CROP,
              "cluster_m": geoclip_gen.CLUSTER_M, "aggregation": "mean of per-view softmax"}
    for name in geoclip_gen.GALLERIES:
        gen.set_gallery(name)
        t = time.time()
        cands = [gen.candidates_from_probs(gen.probs_from_features(f), k=10) for f in feats]
        report[f"gallery={name}"] = evaluate(cands, truths, df["country"], f"geoclip gallery={name}")
        report[f"gallery={name}"]["gallery_size"] = len(gen.lat)
        report[f"gallery={name}"]["seconds_per_panorama"] = round((time.time() - t) / len(df), 3)
    report["osv5m_val_subset"] = osv_subset(gen)
    if KNN_OUT.exists():
        knn = json.loads(KNN_OUT.read_text()).get("panoramax_val", {})
        report["knn_for_comparison"] = {k: v["top1"]["all"] for k, v in knn.items() if isinstance(v, dict) and "top1" in v}
    OUT.write_text(json.dumps(report, indent=1))
    print(f"wrote {OUT}")


def osv_subset(gen):
    from PIL import Image
    from panoloc import retrieval
    meta, emb = retrieval.load_embeddings(partitions=("val",), dtype=np.float32)
    pick = np.sort(np.random.default_rng(0).choice(len(meta), OSV_SUBSET, replace=False))
    meta, emb = meta.iloc[pick].reset_index(drop=True), emb[pick]
    truths = list(zip(meta["lat"], meta["lon"]))
    feats = []
    for i in range(0, len(meta), 32):
        ims = [Image.open(retrieval.OSV_DIR / "images" / d / f"{j}.jpg").convert("RGB")
               for j, d in zip(meta["id"][i:i + 32], meta["subdir"][i:i + 32])]
        feats.append(gen.image_features(ims))
    feats = np.concatenate(feats)
    gen.set_gallery("stock")
    out = {"n": len(meta), "seed": 0}
    out["geoclip_stock"] = evaluate([gen.candidates_from_probs(gen.probs_from_features(f), k=10) for f in feats],
                                    truths, meta["country"], "osv5m val subset: geoclip stock")
    bank = retrieval.Bank.open(partitions=("train",))
    out["knn_train_bank"] = evaluate([bank.search(e, k=20) for e in emb], truths, meta["country"],
                                     "osv5m val subset: pe-core knn")
    return out


if __name__ == "__main__":
    main()
