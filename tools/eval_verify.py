#!/usr/bin/env python3
"""Validate MegaLoc + ALIKED/LightGlue verification on separate-capture pairs (TASKS.md T41; PLAN.md 3.3).

Queries are Panoramax `val` panoramas (never `final`), references the Commons landmark photos of
panoloc.landmarks: different cameras, different days, different photographers.
  pairs   candidate pairs -> Data/gallery/emb/verify/pairs.json, and the 8 horizontal views (1024 px,
          panorama first resized to 6080 px wide) of every panorama involved in verify/views/<id>/
            near  every gallery landmark within NEAR_M of a val camera (true pairs once a person has
                  confirmed that a view shows it, see `sheets`)
            far   the top-5 PE-Core gallery neighbours of a val panorama that lie more than FAR_M
                  away (cannot be the same object), for the near panoramas and FAR_SAMPLE others
  sheets  contact sheets in verify/sheets/ for a person to label: one per near pair (the Commons photo
          + the 8 views), or with --per-panorama one per panorama (its 8 views + every near landmark's
          photo, numbered). verify/labels.json maps "<panorama id>/<qid>" to "visible <view>" (the
          landmark is in that view, e.g. "visible h090"), "not_visible" or "unsure"
  match   every pair through panoloc.verify.Verifier: MegaLoc similarity per view, ALIKED + LightGlue +
          MAGSAC against all 8 views at every photo scale (PHOTO_SCALES; the best view and scale kept,
          and the best among MegaLoc's top 3 views, as Verifier.verify does), with timings
          -> verify/matches.json
  report  inlier distributions of true (labelled visible) and false (far, and near but not visible)
          pairs, the smallest threshold with no false pair at or above it, precision and recall there,
          time per pair -> Data/gallery/emb/eval_verify.json
Timings are on the dev laptop's RTX 5080 capped at 80 W and shared with the VLM: lower bounds on speed.

  .venv/bin/python tools/eval_verify.py pairs
  .venv/bin/python tools/eval_verify.py sheets
  .venv/bin/python tools/eval_verify.py match
  .venv/bin/python tools/eval_verify.py report
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402

from panoloc import landmarks  # noqa: E402

VDIR = landmarks.EMB_DIR / "verify"
PAIRS = VDIR / "pairs.json"
LABELS = VDIR / "labels.json"
MATCHES = VDIR / "matches.json"
OUT = landmarks.EMB_DIR / "eval_verify.json"
NEAR_M = 300
FAR_M = 5000
FAR_SAMPLE = 30
VIEW_SIZE = 1024
VIEW_NAMES = [f"h{45 * i:03d}" for i in range(8)]


def ev():
    import eval_landmarks
    return eval_landmarks


def cut_and_cache(row):
    """The 8 horizontal views of a val panorama, cached as JPEGs in verify/views/<id>/."""
    from PIL import Image
    d = VDIR / "views" / row["id"]
    if all((d / f"{n}.jpg").exists() for n in VIEW_NAMES):
        return d
    from panoloc.views import cut_views
    d.mkdir(parents=True, exist_ok=True)
    for v in cut_views(ev().load_resized(row["path"]), size=VIEW_SIZE):
        if v.name in VIEW_NAMES:
            Image.fromarray(v.image).save(d / f"{v.name}.jpg", quality=92)
    return d


def cmd_pairs(args):
    e = ev()
    rows = e.panoramax_val()
    gallery = landmarks.Gallery.open()
    emb, emb_names = e.view_embeddings(rows, "4:3")
    glat, glon = gallery.meta["lat"], gallery.meta["lon"]
    near, far, near_ids = [], [], set()
    for r in rows:
        d = e.dist_m(r["lat"], r["lon"], glat, glon)
        for i in np.flatnonzero(d <= NEAR_M):
            near.append({"pano": r["id"], "country": r["country"], "qid": str(gallery.meta["qid"][i]),
                         "name": str(gallery.meta["name"][i]), "dist_m": round(float(d[i]), 1), "kind": "near",
                         "photo": str(gallery.meta["photo"][i])})
            near_ids.add(r["id"])
    others = [r for r in rows if r["id"] not in near_ids]
    random.Random(0).shuffle(others)
    far_rows = [r for r in rows if r["id"] in near_ids] + others[:FAR_SAMPLE]
    for r in far_rows:
        for c in gallery.search(emb[r["id"]], k=5, view_names=emb_names):
            dist = float(e.dist_m(r["lat"], r["lon"], np.array([c.lat]), np.array([c.lng]))[0])
            if dist > FAR_M:
                far.append({"pano": r["id"], "country": r["country"], "qid": c.details["qid"], "name": c.details["name"],
                            "dist_m": round(dist), "kind": "far", "photo": c.details["photo"],
                            "pecore_similarity": c.details["similarity"], "pecore_rank": c.details["rank"]})
    by_id = {r["id"]: r for r in rows}
    t0 = time.time()
    for i, pid in enumerate(sorted({p["pano"] for p in near + far})):
        cut_and_cache(by_id[pid])
        if (i + 1) % 10 == 0:
            print(f"views of {i + 1} panoramas cut, {(time.time() - t0) / (i + 1):.1f} s each", flush=True)
    VDIR.mkdir(parents=True, exist_ok=True)
    PAIRS.write_text(json.dumps({"near_m": NEAR_M, "far_m": FAR_M, "gallery_photos": len(gallery),
                                 "pairs": near + far}, indent=1))
    print(f"{len(near)} near pairs over {len(near_ids)} panoramas, {len(far)} far pairs over {len(far_rows)} panoramas")


def panorama_sheets(pairs, out, v=384, t=192, per_row=8):
    """One sheet per panorama: its 8 views (2 rows of 4) above its near landmarks' photos, numbered."""
    from PIL import Image, ImageDraw
    by = {}
    for p in pairs:
        by.setdefault(p["pano"], []).append(p)
    for pid, plist in by.items():
        plist.sort(key=lambda p: p["dist_m"])
        rows = -(-len(plist) // per_row)
        sheet = Image.new("RGB", (4 * v, 2 * v + rows * (t + 16)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, n in enumerate(VIEW_NAMES):
            with Image.open(VDIR / "views" / pid / f"{n}.jpg") as im:
                sheet.paste(im.convert("RGB").resize((v, v)), ((i % 4) * v, (i // 4) * v))
            draw.text(((i % 4) * v + 4, (i // 4) * v + 2), n, fill="yellow")
        for j, p in enumerate(plist):
            x, y = (j % per_row) * t, 2 * v + (j // per_row) * (t + 16)
            with Image.open(landmarks.COMMONS_DIR / p["photo"]) as im:
                im = im.convert("RGB")
                im.thumbnail((t - 4, t - 4))
                sheet.paste(im, (x, y + 14))
            draw.text((x + 2, y + 1), f"{j} {p['name'][:22]} {p['dist_m']:.0f}m", fill="black")
        sheet.save(out / f"pano_{pid[:8]}.jpg", quality=85)
    return len(by)


def cmd_sheets(args):
    from PIL import Image, ImageDraw
    pairs = [p for p in json.loads(PAIRS.read_text())["pairs"] if p["kind"] == "near"]
    out = VDIR / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    if args.per_panorama:
        print(f"{panorama_sheets(pairs, out)} panorama sheets in {out}")
        return
    t = 300
    for p in pairs:
        sheet = Image.new("RGB", (5 * t, 2 * t + 24), "white")
        with Image.open(landmarks.COMMONS_DIR / p["photo"]) as im:
            im = im.convert("RGB")
            im.thumbnail((t, 2 * t))
            sheet.paste(im, (0, 24))
        for i, n in enumerate(VIEW_NAMES):
            with Image.open(VDIR / "views" / p["pano"] / f"{n}.jpg") as v:
                v = v.convert("RGB").resize((t, t))
                sheet.paste(v, ((1 + i % 4) * t, 24 + (i // 4) * t))
                ImageDraw.Draw(sheet).text(((1 + i % 4) * t + 4, 26 + (i // 4) * t), n, fill="yellow")
        ImageDraw.Draw(sheet).text((4, 4), f"{p['qid']} {p['name'][:60]} | {p['dist_m']:.0f} m from the camera",
                                   fill="black")
        sheet.save(out / f"{p['pano'][:8]}_{p['qid']}.jpg", quality=85)
    print(f"{len(pairs)} sheets in {out}")


def cmd_match(args):
    import torch
    from dataclasses import replace
    from panoloc.verify import PHOTO_SCALES, Verifier, match_summary, rgb_array
    pairs = json.loads(PAIRS.read_text())["pairs"]
    t0 = time.time()
    ver = Verifier(megaloc=True)  # the analysis records MegaLoc similarity per view
    load_s = time.time() - t0
    print(f"verifier loaded in {load_s:.1f} s, GPU {torch.cuda.memory_allocated() / 2**30:.2f} GiB", flush=True)
    by_pano = {}
    for p in pairs:
        by_pano.setdefault(p["pano"], []).append(p)
    timing = {"view_features_ms": [], "photo_features_ms": [], "match_ms": [], "megaloc_ms_per_image": []}
    results = []
    for pid, plist in by_pano.items():
        views = [rgb_array(VDIR / "views" / pid / f"{n}.jpg") for n in VIEW_NAMES]
        t = time.perf_counter()
        vdesc = ver.global_descriptors(views)
        torch.cuda.synchronize()
        timing["megaloc_ms_per_image"].append((time.perf_counter() - t) * 1000 / len(views))
        vfeats = []
        for v in views:
            t = time.perf_counter()
            vfeats.append(ver.features(v))
            torch.cuda.synchronize()
            timing["view_features_ms"].append((time.perf_counter() - t) * 1000)
        for p in plist:
            photo = rgb_array(landmarks.COMMONS_DIR / p["photo"])
            sim = vdesc @ ver.global_descriptors([photo])[0]
            per_view = []
            for size in PHOTO_SCALES:
                t = time.perf_counter()
                pf = ver.features(photo, size)
                torch.cuda.synchronize()
                timing["photo_features_ms"].append((time.perf_counter() - t) * 1000)
                for n, vf in zip(VIEW_NAMES, vfeats):
                    m = replace(ver.match_features(vf, pf, n), scale=size)
                    timing["match_ms"].append(m.ms)
                    per_view.append(match_summary(m))
            best = max(per_view, key=lambda m: (m["inliers"], m["confident"]))
            ml_order = [VIEW_NAMES[i] for i in np.argsort(-sim)]
            top3 = [m for m in per_view if m["view"] in ml_order[:3]]
            best_top3 = max(top3, key=lambda m: (m["inliers"], m["confident"]))
            results.append({**p, "best": best, "best_megaloc_top3": best_top3, "per_view": per_view,
                            "megaloc": {"max": round(float(sim.max()), 4), "best_view": ml_order[0],
                                        "rank_of_best_match_view": ml_order.index(best["view"]) + 1,
                                        "per_view": [round(float(s), 4) for s in sim]}})
        print(f"{len(results)}/{len(pairs)} pairs, {time.time() - t0:.0f} s", flush=True)
    peak = torch.cuda.max_memory_allocated() / 2**30
    ver.close()
    MATCHES.write_text(json.dumps({"load_s": round(load_s, 1), "peak_gpu_gib": round(peak, 2),
                                   "photo_scales": list(PHOTO_SCALES),
                                   "timing_median_ms": {k: round(float(np.median(v)), 1) for k, v in timing.items() if v},
                                   "results": results}, indent=1))
    print(f"wrote {MATCHES}; peak GPU {peak:.2f} GiB; median ms "
          f"{ {k: round(float(np.median(v)), 1) for k, v in timing.items() if v} }")


def pct(a, ps=(0, 10, 25, 50, 75, 90, 100)):
    a = np.asarray(a, float)
    return {f"p{p}": round(float(np.percentile(a, p)), 3) for p in ps} if len(a) else {}


def cmd_report(args):
    m = json.loads(MATCHES.read_text())
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    true, near_neg, far_neg, unlabelled = [], [], [], 0
    for r in m["results"]:
        if r["kind"] == "far":
            far_neg.append(r)
            continue
        lab = labels.get(f"{r['pano']}/{r['qid']}", "")
        if lab.startswith("visible"):
            r["label_view"] = lab.split()[1] if len(lab.split()) > 1 else None
            true.append(r)
        elif lab == "not_visible":
            near_neg.append(r)
        else:
            unlabelled += 1
    inl = lambda rs: [r["best"]["inliers"] for r in rs]  # noqa: E731
    neg = far_neg + near_neg
    thresholds = sorted({x for x in inl(true + neg)} | {args.min_inliers} if args.min_inliers else {x for x in inl(true + neg)})
    table = []
    for t in thresholds:
        tp = sum(x >= t for x in inl(true))
        fp = sum(x >= t for x in inl(neg))
        table.append({"min_inliers": t, "tp": tp, "fp": fp, "fn": len(true) - tp,
                      "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                      "recall": round(tp / len(true), 3) if true else None})
    clean = [row for row in table if row["fp"] == 0 and row["tp"] > 0]
    chosen = args.min_inliers or (min(clean, key=lambda row: row["min_inliers"])["min_inliers"] if clean else None)
    at = next((row for row in table if row["min_inliers"] == chosen), None)
    view_agree = [r["best"]["view"] == r.get("label_view") for r in true if r.get("label_view")]
    # per panorama: does a panorama that shows a gallery landmark get one verified, and does any get a false one?
    panos_true = {r["pano"] for r in true}
    hit = {r["pano"] for r in true if chosen is not None and r["best"]["inliers"] >= chosen}
    top3 = lambda rs: [r.get("best_megaloc_top3", r["best"])["inliers"] for r in rs]  # noqa: E731
    shortcut = {"tp": sum(x >= chosen for x in top3(true)), "fp": sum(x >= chosen for x in top3(neg))} if chosen else {}
    false_hit = {r["pano"] for r in neg if chosen is not None and r["best"]["inliers"] >= chosen}
    all_panos = {r["pano"] for r in m["results"]}
    report = {"task": "T41", "pairs": {"true_visible": len(true), "near_not_visible": len(near_neg),
                                        "far": len(far_neg), "near_unlabelled_or_unsure": unlabelled},
              "inliers": {"true": pct(inl(true)), "near_not_visible": pct(inl(near_neg)), "far": pct(inl(far_neg))},
              "spread": {"true": pct([r["best"]["spread"] for r in true]),
                         "false": pct([r["best"]["spread"] for r in neg])},
              "megaloc_max_similarity": {"true": pct([r["megaloc"]["max"] for r in true]),
                                         "near_not_visible": pct([r["megaloc"]["max"] for r in near_neg]),
                                         "far": pct([r["megaloc"]["max"] for r in far_neg])},
              "megaloc_rank_of_best_match_view_true": pct([r["megaloc"]["rank_of_best_match_view"] for r in true]),
              "best_match_view_equals_labelled_view": round(float(np.mean(view_agree)), 3) if view_agree else None,
              "threshold": {"min_inliers": chosen, "rule": "smallest inlier count with no false pair at or above it",
                            **(at or {})},
              "per_panorama": {"panoramas": len(all_panos), "showing_a_gallery_landmark": len(panos_true),
                               "with_a_verified_true_landmark": len(hit), "with_a_false_verification": len(false_hit)},
              "megaloc_top3_views_only": {**shortcut, "note": "Verifier.verify's default: only the 3 views of "
                                                             "highest MegaLoc similarity are matched"},
              "photo_scales": m.get("photo_scales"),
              "table": table,
              "timing_median_ms": m["timing_median_ms"], "verifier_load_s": m["load_s"], "peak_gpu_gib": m["peak_gpu_gib"],
              "timing_note": "RTX 5080 Laptop capped at 80 W, shared with the VLM: lower bounds on speed",
              "true_pairs": [{k: r[k] for k in ("pano", "qid", "name", "dist_m")} | {"inliers": r["best"]["inliers"],
                                                                                 "view": r["best"]["view"]} for r in true],
              "top_false_pairs": sorted(({k: r[k] for k in ("pano", "qid", "name", "dist_m", "kind")}
                                         | {"inliers": r["best"]["inliers"]} for r in neg),
                                        key=lambda x: -x["inliers"])[:10]}
    OUT.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k not in ("table", "true_pairs")}, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pairs", "match"):
        sub.add_parser(name)
    sp = sub.add_parser("sheets")
    sp.add_argument("--per-panorama", action="store_true", help="one sheet per panorama with all its near landmarks")
    rp = sub.add_parser("report")
    rp.add_argument("--min-inliers", type=int, default=0, help="report at this threshold instead of the chosen one")
    args = ap.parse_args(argv)
    {"pairs": cmd_pairs, "sheets": cmd_sheets, "match": cmd_match, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
