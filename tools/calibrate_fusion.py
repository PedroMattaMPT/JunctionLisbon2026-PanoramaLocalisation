#!/usr/bin/env python3
"""Calibrate the fusion constants on cached perception (T39, PLAN.md 3.2 and 4.6). CPU only.

For every panorama of a validation reference set, the OCR, VLM, kNN / region-head and GeoCLIP results
are read from the perception cache that panoloc.pipeline writes (runs/perception/<file>-<size>/:
ocr.json, vlm.json, retrieval.json, geoclip.json, landmarks.json); the clues and hints are built once with the name
index, then re-fused under candidate settings and scored with panoloc.evaluate.score_case: the
coordinate repeated 10 times, scored in the reference's own category (GHSL-inferred for Panoramax).

Settings: one reliability multiplier per clue family (names, regions, VLM landmarks, kNN, region head,
GeoCLIP, Commons gallery, verified landmarks) and fusion's AGREE_GAIN, RESIDUAL_WEIGHT and MAX_GROUP_RATIO. Search: coordinate ascent over
a coarse grid, a few rounds, maximising the mean own-category score. Panoramas from one Panoramax
collection are correlated, so the report also gives a 2-fold cross-validation split by collection
(fit on one half, score on the other): adopt a setting only if it also wins out of fold.

Only validation sets: the warm-up references are evaluation-only and the final set is for one run (T54),
so both are refused. Panoramas whose OCR or VLM results are not cached are skipped and counted.

Usage (from the repo root):
  .venv/bin/python tools/calibrate_fusion.py --set runs/eval/val_first100.json [--cache runs/perception]
                                             [--rounds 2] [--out runs/eval/calibration-<time>.json]
Prints the default and best settings with their scores; the JSON has every evaluated setting.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from panoloc import evaluate as ev  # noqa: E402
from panoloc import fusion  # noqa: E402
from panoloc.candidates import Candidate  # noqa: E402
from panoloc.names import NameIndex  # noqa: E402
from panoloc.pipeline import (EVAL_CACHE, GEOCLIP_RELIABILITY, KNN_RELIABILITY, LANDMARK_RELIABILITY,  # noqa: E402
                              REGION_HEAD_RELIABILITY, VERIFIED_RELIABILITY)

FAMILIES = {"ocr_name": "names", "ocr_postcode": "names", "vlm_landmark": "landmarks", "ocr_region": "regions",
            "vlm_region": "regions", "knn": "knn", "region_head": "region_head", "geoclip": "geoclip",
            "landmark_gallery": "gallery", "landmark_verified": "verified"}
GRID = {
    "names": [0.0, 0.5, 1.0, 1.5, 2.0],
    "regions": [0.0, 0.5, 1.0, 1.5, 2.0],
    "landmarks": [0.0, 0.5, 1.0, 1.5, 2.0],
    "knn": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "region_head": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "geoclip": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "gallery": [0.0, 0.5, 1.0, 2.0, 3.0],
    "verified": [0.0, 0.5, 1.0, 1.4],
    "AGREE_GAIN": [0.0, 1.0, 3.0, 6.0],
    "RESIDUAL_WEIGHT": [0.02, 0.05, 0.1, 0.2],
    "MAX_GROUP_RATIO": [2.0, 4.0, 8.0, 16.0],
}
GALLERY_BASE = 0.2
DEFAULT = {"names": 1.0, "regions": 1.0, "landmarks": 1.0, "knn": 1.0, "region_head": 1.0, "geoclip": 1.0,
           "gallery": LANDMARK_RELIABILITY / GALLERY_BASE, "verified": 1.0,
           "AGREE_GAIN": fusion.AGREE_GAIN, "RESIDUAL_WEIGHT": fusion.RESIDUAL_WEIGHT,
           "MAX_GROUP_RATIO": fusion.MAX_GROUP_RATIO}


def _cached(cache, ref):
    path = ROOT / ref.path
    entry = Path(cache) / f"{path.name}-{path.stat().st_size}"
    docs = {}
    for name in ("ocr", "vlm", "retrieval", "geoclip", "landmarks"):
        f = entry / f"{name}.json"
        if f.is_file():
            docs[name] = json.loads(f.read_text(encoding="utf-8"))
    return docs


def build_case(ref, docs, names):
    """Clues and hints for one panorama, built once with the default reliabilities."""
    ocr, vlm = docs["ocr"], docs["vlm"]
    hints = fusion.hints_from_ocr(ocr["items"]) + fusion.hints_from_vlm(vlm["hints"])
    countries = fusion.confident_countries(fusion.country_prior(hints))
    signs = {s["sign_id"]: s["confidence"] for s in ocr["signs"]}
    clues = fusion.clues_from_ocr(ocr["items"], names, signs, countries=countries)
    clues += fusion.clues_from_vlm(vlm["landmarks"], vlm["hints"], names, countries=countries)
    if "retrieval" in docs:
        r = docs["retrieval"]
        clues.append(fusion.Clue("knn", "knn", "pe-core", KNN_RELIABILITY, [Candidate(**c) for c in r["knn"]], None))
        clues.append(fusion.Clue("region_head", "region_head", "pe-core", REGION_HEAD_RELIABILITY,
                                 [Candidate(**c) for c in r["region_head"]], None))
    if "geoclip" in docs:
        clues.append(fusion.Clue("geoclip", "geoclip", "geoclip", GEOCLIP_RELIABILITY,
                                 [Candidate(**c) for c in docs["geoclip"]["candidates"]], None))
    if "landmarks" in docs:
        checked = [Candidate(**c) for c in docs["landmarks"]["candidates"]]
        verified = [c for c in checked if (c.details or {}).get("verified_match")]
        if checked:  # tried at GALLERY_BASE; the default multiplier reproduces the pipeline (0 while it is off)
            clues.append(fusion.Clue("landmark_gallery", "landmark_gallery", "pe-core", GALLERY_BASE, checked, None))
        if verified:
            clues.append(fusion.Clue("landmark_verified", "landmark_verified", "verified", VERIFIED_RELIABILITY,
                                     verified, None))
    return SimpleNamespace(ref=ref, clues=clues, base=[c.reliability for c in clues], hints=hints)


def predict(case, setting):
    for clue, base in zip(case.clues, case.base):
        clue.reliability = min(1.0, base * setting[FAMILIES.get(clue.kind, "names")])
    for name in ("AGREE_GAIN", "RESIDUAL_WEIGHT", "MAX_GROUP_RATIO"):
        setattr(fusion, name, setting[name])
    f = fusion.fuse(case.clues, case.hints)
    return (f.output.lat, f.output.lng)


def score(cases, setting):
    """Mean own-category score (the evaluator's score_ref) over the cases."""
    total = 0.0
    for case in cases:
        point = predict(case, setting)
        result = ev.score_case(case.ref, ev.Prediction(case.ref.key, [point] * 10))
        total += result.get("score_ref", 0.0)
    return total / len(cases) if cases else 0.0


def ascend(cases, start, rounds):
    best, best_score, history = dict(start), score(cases, start), []
    for _ in range(rounds):
        improved = False
        for name, values in GRID.items():
            for v in values:
                if v == best[name]:
                    continue
                trial = {**best, name: v}
                s = score(cases, trial)
                history.append({"setting": trial, "score": round(s, 2)})
                if s > best_score + 1e-9:
                    best, best_score, improved = trial, s, True
        if not improved:
            break
    return best, best_score, history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", required=True, help="a validation reference-set JSON (or 'val')")
    parser.add_argument("--cache", default=str(EVAL_CACHE))
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.set in ("warmup", "final") or "warmup" in args.set or "final" in Path(args.set).stem:
        parser.error("calibration runs on validation sets only (warm-up: evaluation only; final: one run, T54)")
    refset = ev.load_set(args.set)
    raw = {r["key"]: r for r in json.loads(Path(refset.source).read_text(encoding="utf-8"))["references"]}

    t0 = time.perf_counter()
    cases, skipped = [], []
    with NameIndex.open() as names:
        for ref in refset.references:
            docs = _cached(args.cache, ref) if ref.path else {}
            if "ocr" not in docs or "vlm" not in docs or ref.category not in ev.CATEGORIES:
                skipped.append(ref.key)
                continue
            case = build_case(ref, docs, names)
            case.collection = (raw.get(ref.key, {}).get("info") or {}).get("collection", ref.key)
            case.has_retrieval = "retrieval" in docs and "geoclip" in docs
            cases.append(case)
    print(f"{len(cases)} cases built in {time.perf_counter() - t0:.1f} s ({len(skipped)} skipped: no cached "
          f"OCR/VLM or no category); {sum(c.has_retrieval for c in cases)} with cached retrieval and GeoCLIP")
    if not cases:
        return 1

    default_score = score(cases, DEFAULT)
    best, best_score, history = ascend(cases, DEFAULT, args.rounds)
    print(f"default {default_score:8.1f}  {DEFAULT}")
    print(f"best    {best_score:8.1f}  {best}")

    collections = sorted({c.collection for c in cases})
    folds = [[c for c in cases if collections.index(c.collection) % 2 == k] for k in (0, 1)]
    cv = []
    for k in (0, 1):
        fit, held = folds[k], folds[1 - k]
        if not fit or not held:
            continue
        fold_best, _, _ = ascend(fit, DEFAULT, args.rounds)
        cv.append({"fit_fold": k, "n_fit": len(fit), "n_held": len(held), "setting": fold_best,
                   "held_default": round(score(held, DEFAULT), 2), "held_fitted": round(score(held, fold_best), 2),
                   "held_full_best": round(score(held, best), 2)})
        print(f"fold {k}: fit {len(fit)}, held out {len(held)}: default {cv[-1]['held_default']:.1f} -> "
              f"fitted {cv[-1]['held_fitted']:.1f}")

    out = Path(args.out or ROOT / "runs" / "eval" / f"calibration-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": refset.name, "source": refset.source, "n_cases": len(cases), "skipped": skipped,
                               "collections": len(collections), "default": {"setting": DEFAULT, "score": default_score},
                               "best": {"setting": best, "score": best_score}, "cross_validation": cv,
                               "history": history, "grid": GRID}, indent=1), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
