#!/usr/bin/env python3
"""Paired autonomous and assisted validation on the warm-up set (TASKS.md T40, PLAN.md 3.4, 4.8).

Evaluation code only (RULES.md, PLAN.md 4.6). References come from panoloc.evaluate.load_set; each
simulated operator (panoloc.oracle) is built per panorama from that panorama's reference and passed to
pipeline.run_panorama, which gets back only an option ID or a skip. The policy is frozen in
EVALUATION.md ("Operator policy").

For every panorama, each mode gets a fresh run with one shared Models object (weights only) and the
shared perception cache (runs/perception/, as tools/evaluate.py --predict panoloc.pipeline:predict*):
  autonomous  operator "never": the paired comparator, rerun here so the code is the same
  nominal     the nominal oracle            radius   the radius-aware oracle
  human       the seeded simulated human (0.70 right / 0.10 wrong / 0.20 skip)
Then each mode is scored with panoloc.evaluate (load_predictions + evaluate) into <out>/<mode>/report.json,
and <out>/summary.json holds, per mode: the PLAN 4.8 numbers, nominal / conservative / upper own-category
scores, the per-panorama paired difference from the autonomous run (and from --baseline, a tools/evaluate.py
report), answered / skipped / right / wrong counts, place-option recall and time. Each case folder also
holds oracle.json: the operator's decisions (option IDs and distances, never reference coordinates).

Before a panorama whose VLM result is not cached, it waits while runs/vlm_compare/.gemma_window
names a live process (another session holds the VLM; ignored after 20 minutes). With --follow SECONDS
(or $PANOLOC_FOLLOW_CACHE_S for the tools/evaluate.py wrappers) it first waits for the panorama's OCR
and VLM results to appear in the cache, so it can trail a run that is still producing them.

  .venv/bin/python tools/eval_assisted.py run [--modes autonomous,nominal,radius,human] [--retrieval]
      [--limit N] [--out runs/eval/assisted-<time>] [--baseline runs/eval/warmup-.../report.json] [--follow S]
  .venv/bin/python tools/eval_assisted.py summary runs/eval/assisted-<time> [--baseline REPORT]
  .venv/bin/python tools/eval_assisted.py row runs/eval/warmup-<time>/report.json --name "B0"  # EVALUATION.md row
  .venv/bin/python tools/eval_assisted.py paired runs/eval/assisted-<time>/summary.json       # per-panorama table
  .venv/bin/python tools/eval_assisted.py containment runs/eval/assisted-<time>  # chosen option holds next output?
  CUDA_VISIBLE_DEVICES= .venv/bin/python tools/eval_assisted.py sweep --set runs/eval/val_first100.json --out DIR
      [--configs autonomous,g0.1-q2,...]   # T79 gate grid, simulated human, perception cache only (no GPU)
  .venv/bin/python tools/eval_assisted.py sweep-summary --dirs DIR [DIR] --sets SET [SET]   # per set and combined
  .venv/bin/python tools/eval_assisted.py sweep-average DIR1/sweep.json DIR2/sweep.json ...  # mean over seeds

The autonomous baselines (T24) run through tools/evaluate.py with these wrappers, which only add the
evaluation-side waits and the code fingerprint (eval_meta.json in each case folder):
  .venv/bin/python tools/evaluate.py run --set warmup --predict tools.eval_assisted:predict_no_retrieval  # B0
  .venv/bin/python tools/evaluate.py run --set warmup --predict tools.eval_assisted:predict                # B1
"""
import argparse
import hashlib
import json
import math
from collections import Counter
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from panoloc import evaluate as ev  # noqa: E402
from panoloc import oracle, pipeline, questions  # noqa: E402
from panoloc.scoring import haversine_m  # noqa: E402

GEMMA_WINDOW = REPO / "runs" / "vlm_compare" / ".gemma_window"
WINDOW_MAX_AGE_S = 20 * 60
WINDOW_POLL_S = 30
FOLLOW_POLL_S = 15
FOLLOW_ENV = "PANOLOC_FOLLOW_CACHE_S"  # tools/evaluate.py wrappers: follow another run's perception cache
MODES = ("autonomous",) + oracle.MODES
EARTH_M_PER_DEG = 6_371_000.0 * math.pi / 180
PERCEPTION_STAGES = {"read": "ocr.json", "describe": "vlm.json", "retrieve": "retrieval.json",
                     "geoclip": "geoclip.json", "landmarks": "landmarks.json"}


def code_fingerprint(root=REPO):
    """sha256 over panoloc/*.py (relative path and bytes, sorted), and the per-file hashes."""
    h, files = hashlib.sha256(), {}
    for path in sorted((Path(root) / "panoloc").glob("*.py")):
        data = path.read_bytes()
        files[path.name] = hashlib.sha256(data).hexdigest()[:12]
        h.update(path.name.encode() + b"\0" + data + b"\0")
    return {"sha256": h.hexdigest(), "files": files}


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def vlm_window_open(path=GEMMA_WINDOW, now=None):
    """True while another session holds the VLM: the file exists, is under 20 minutes old and its PID lives."""
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if age > WINDOW_MAX_AGE_S:
        return False
    try:
        pid = int(text.split()[0])
    except (ValueError, IndexError):
        return True  # a window without a readable PID still counts until it is 20 minutes old
    return _pid_alive(pid)


def _cache_dir():
    return Path(os.environ.get("PANOLOC_PERCEPTION_CACHE", pipeline.EVAL_CACHE))


def wait_for_vlm(panorama_path, cache=None, poll_s=WINDOW_POLL_S, log=None):
    """Wait while the VLM window is open, unless this image's VLM result is already cached; returns seconds waited."""
    path = Path(panorama_path)
    cache = Path(cache) if cache else _cache_dir()
    if (cache / f"{path.name}-{path.stat().st_size}" / "vlm.json").is_file():
        return 0.0
    t0 = time.monotonic()
    while vlm_window_open():
        if log:
            log(f"VLM window open ({GEMMA_WINDOW}): waiting {poll_s} s before {path.name}")
        time.sleep(poll_s)
    return time.monotonic() - t0


def wait_for_cache(panorama_path, max_s, cache=None, poll_s=FOLLOW_POLL_S, log=None):
    """Wait, at most max_s, until this image's OCR and VLM results are in the perception cache, so a run
    that follows another one (the same image, earlier in that run) never repeats its perception work.
    Returns the seconds waited; after max_s the run goes on and does the work itself."""
    path = Path(panorama_path)
    folder = (Path(cache) if cache else _cache_dir()) / f"{path.name}-{path.stat().st_size}"
    t0 = time.monotonic()
    while not all((folder / name).is_file() for name in ("ocr.json", "vlm.json")):
        if time.monotonic() - t0 > max_s:
            break
        if log and time.monotonic() - t0 < poll_s:
            log(f"waiting for the cached perception of {path.name} (at most {max_s:.0f} s)")
        time.sleep(poll_s)
    return time.monotonic() - t0


def _log(message):
    print(message, file=sys.stderr, flush=True)


def _write_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return path


def _waits(panorama_path):
    """The evaluation-side waits before a run: the followed cache ($PANOLOC_FOLLOW_CACHE_S), the VLM window."""
    follow = float(os.environ.get(FOLLOW_ENV) or 0)
    followed = wait_for_cache(panorama_path, follow, log=_log) if follow > 0 else 0.0
    return followed, wait_for_vlm(panorama_path, log=_log)


def _record(runs_dir, waits):
    _write_json(Path(runs_dir) / "eval_meta.json", {"code": code_fingerprint(), "follow_wait_s": round(waits[0], 1),
                                                    "vlm_window_wait_s": round(waits[1], 1)})


def predict_no_retrieval(panorama_path, runs_dir):
    """panoloc.pipeline.predict_no_retrieval after the evaluation-side waits (B0)."""
    _record(runs_dir, _waits(panorama_path))
    return pipeline.predict_no_retrieval(panorama_path, runs_dir)


def predict(panorama_path, runs_dir):
    """panoloc.pipeline.predict (with the photo bank) after the evaluation-side waits (B1)."""
    _record(runs_dir, _waits(panorama_path))
    return pipeline.predict(panorama_path, runs_dir)


# -- the paired runs --------------------------------------------------------------------------------

def first_place_question(hypotheses, ref):
    """The place question the initial hypotheses give, built whether or not the pipeline asked it
    (pipeline._next_question's rule), and whether any of its places holds the reference."""
    sep = pipeline.PLACE_SEPARATION_M
    supported = [h for h in hypotheses if h.weight > 0]
    try:
        if len(questions.distinct(supported, sep)) < 2:
            return {"built": False}
        q = questions.place_question(hypotheses, min_separation_m=sep)
    except Exception as exc:  # the probe must never turn a finished run into an error
        return {"built": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    point = (ref.lat, ref.lng)
    places = [o for o in q.options if not o.complement]
    holding = [o.radius_m for o in places if o.contains(point)]
    return {"built": True, "n_places": len(places), "recall": oracle.place_recall(q, point),
            "holding_radius_m": holding[0] if holding else None,
            "nearest_place_m": round(min(haversine_m(o.latlng, point) for o in places), 1),
            "radii_m": [o.radius_m for o in places]}


def _log_facts(log_path):
    doc = json.loads(Path(log_path).read_text(encoding="utf-8"))
    status = [q["status"] for q in doc.get("questions", [])]
    kinds = [q["kind"] for q in doc.get("questions", [])]
    outputs = doc.get("outputs") or []
    first = json.dumps([[c["lat"], c["lng"]] for c in outputs[0]["coordinates"]]) if outputs else ""
    from_cache = {e["stage"] for e in doc["events"]
                  if e["type"] == "evidence.added" and e["payload"].get("kind") == "perception_cache"}
    ran = {s["stage"] for s in doc.get("stages", []) if s.get("status") == "finished"}
    return {"asked": len(status), "answered": status.count("answered"), "skipped": status.count("skipped"),
            "first_output_sha": hashlib.sha256(first.encode()).hexdigest()[:16], "kinds": kinds,
            "initial_s": outputs[0]["t"] if outputs else None, "total_s": doc.get("duration_s"),
            "multiplier": (doc.get("penalty") or {}).get("multiplier"), "versions": doc.get("versions"),
            "cached": [s["stage"] for s in doc.get("stages", []) if "(cached)" in str(s.get("model"))],
            "computed": sorted((ran & set(PERCEPTION_STAGES)) - from_cache)}


def run_case(ref, mode, models, case_dir, follow_s=0.0, *, min_gain=None, max_questions=None, seed=oracle.HUMAN_SEED,
             sticky_skip=None, sticky_mistake=None):
    """One fresh run of one panorama under one mode; returns the case record (no reference coordinates).
    min_gain and max_questions override the pipeline's question gate when given (T79)."""
    path = REPO / ref.path
    case_dir.mkdir(parents=True, exist_ok=False)
    followed = wait_for_cache(path, follow_s, log=_log) if follow_s > 0 else 0.0
    waited = wait_for_vlm(path, log=_log)
    op = "never" if mode == "autonomous" else oracle.make_operator(mode, ref, seed=seed, sticky_skip=sticky_skip,
                                                                    sticky_mistake=sticky_mistake)
    gate = {k: v for k, v in (("min_gain", min_gain), ("max_questions", max_questions)) if v is not None}
    record = {"key": ref.key, "mode": mode, "primary": ref.primary, "follow_wait_s": round(followed, 1),
              "vlm_window_wait_s": round(waited, 1)}
    t0 = time.monotonic()
    try:
        result = pipeline.run_panorama(path, models, runs_dir=case_dir, operator=op, print_fn=lambda *a, **k: None,
                                       **gate)
        record.update(run_dir=str(result.run_dir.relative_to(REPO)), timings=result.timings,
                      **_log_facts(result.log_path),
                      first_place_question=first_place_question(result.fused.hypotheses, ref))
    except Exception as exc:  # one failed panorama scores zero; the batch goes on
        record["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    record["elapsed_s"] = round(time.monotonic() - t0, 2)
    if op != "never":
        record["decisions"] = op.decisions
        record["operator"] = oracle.summarise(op.decisions)
    _write_json(case_dir / "oracle.json", record)
    return record


def run(args):
    refset = ev.load_set("warmup")
    if args.limit:
        refset.references = refset.references[:args.limit]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    unknown = sorted(set(modes) - set(MODES))
    if unknown or "autonomous" not in modes:
        raise SystemExit(f"--modes takes {', '.join(MODES)} and must include autonomous (the paired comparator); "
                         f"got {modes}")
    out = Path(args.out or REPO / "runs" / "eval" / f"assisted-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}").resolve()
    models = pipeline.Models(retrieval=args.retrieval, perception_cache=_cache_dir())
    meta = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "modes": modes,
            "retrieval": args.retrieval, "perception_cache": str(_cache_dir()), "code_start": code_fingerprint(),
            "operator_policy": {"human_rates": oracle.HUMAN_RATES, "human_seed": oracle.HUMAN_SEED,
                                "edge_samples": oracle.EDGE_SAMPLES, "max_questions": pipeline.MAX_QUESTIONS,
                                "ask_anyway": False, "urban_probability": pipeline.fusion.DEFAULT_URBAN_PROBABILITY,
                                "place_tolerance": "the option's stated radius_m"}}
    _write_json(out / "meta.json", meta)
    for i, ref in enumerate(refset.references, start=1):
        for mode in modes:
            rec = run_case(ref, mode, models, out / mode / "runs" / f"{i:03d}-{Path(ref.key).stem}", args.follow)
            what = rec.get("error") or (f"asked {rec['asked']}, answered {rec['answered']}, skipped {rec['skipped']}"
                                        f" ({rec['elapsed_s']:.1f} s)")
            _log(f"[{i}/{len(refset.references)}] {ref.key} {mode}: {what}")
    meta.update(finished=datetime.now(timezone.utc).isoformat(timespec="seconds"), code_end=code_fingerprint(),
                versions=models.versions())
    _write_json(out / "meta.json", meta)
    return summarise_dir(out, refset, baseline=args.baseline)


# -- the summary ------------------------------------------------------------------------------------

def _share(case, bound):
    if not case["predicted"] or case["category"] not in ev.CATEGORIES:
        return 0.0
    return case["score"][case["category"]][bound] / case["max_score"]


def _median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def _paired(cases, base_cases):
    """Per-panorama difference of the conservative own-category share from base_cases (same keys)."""
    base = {c["key"]: c for c in base_cases}
    diffs = {c["key"]: round(_share(c, "lower") - _share(base[c["key"]], "lower"), 4)
             for c in cases if c["key"] in base}
    values = list(diffs.values())
    return {"per_panorama": diffs, "mean": round(statistics.fmean(values), 4) if values else None,
            "better": sum(v > 1e-9 for v in values), "worse": sum(v < -1e-9 for v in values),
            "same": sum(abs(v) <= 1e-9 for v in values)}


def mode_summary(report, records, auto_report=None, baseline=None, auto_first=None):
    primary = [c for c in report["cases"] if c["primary"]]
    keys = {c["key"] for c in primary}
    recs = [r for r in records if r["key"] in keys]
    if not primary:
        return {"n_primary": 0}
    t = report["targets_plan_4_8"]
    agg = report["primary"]
    ops = [r.get("operator") or {} for r in recs]
    built = [r["first_place_question"] for r in recs if (r.get("first_place_question") or {}).get("built")]
    out = {
        "n_primary": len(primary),
        "urban_robust_100m": f"{t['urban_camera_accuracy']['hits']}/{t['urban_camera_accuracy']['urban_references']}",
        "urban_robust_pass": t["urban_camera_accuracy"]["pass"],
        "mean_conservative_share": t["mean_conservative_score"]["value"],
        "mean_conservative_pass": t["mean_conservative_score"]["pass"],
        "own_category_share": {b: round(statistics.fmean(_share(c, b) for c in primary), 4)
                               for b in ("nominal", "lower", "upper")},
        "median_d1_m": agg["distance_m"]["median"],
        "nominal_mean_score": {c: agg["score"][c]["mean"] for c in ev.CATEGORIES},
        "within_robust": agg["within_robust"],
        "questions": {k: sum(r.get(k, 0) for r in recs) for k in ("asked", "answered", "skipped")},
        "operator": {k: sum(o.get(k, 0) for o in ops) for k in ("right", "wrong", "place_questions", "place_recall",
                                                                  "option_for_disagrees")},
        "first_place_question": {"built": len(built), "recall": sum(bool(b["recall"]) for b in built),
                                 "recall_radius_le_1km": sum((b.get("holding_radius_m") or 1e12) <= 1000
                                                             for b in built),
                                 "median_nearest_place_m": _median([b.get("nearest_place_m") for b in built]),
                                 "of": len(recs)},
        "time_s": {"initial_median": _median([r.get("initial_s") for r in recs]),
                   "initial_max": max((r["initial_s"] for r in recs if r.get("initial_s") is not None), default=None),
                   "total_median": _median([r.get("total_s") for r in recs]),
                   "cached_perception": sum(len(r.get("cached", [])) == 2 for r in recs)},
        "errors": [r["key"] for r in recs if r.get("error")],
    }
    if auto_report is not None:
        out["paired_vs_autonomous"] = _paired(primary, [c for c in auto_report["cases"] if c["primary"]])
        out["paired_vs_autonomous"]["same_first_output"] = sum(
            r.get("first_output_sha") is not None and r.get("first_output_sha") == auto_first.get(r["key"])
            for r in recs)
    if baseline is not None:
        out["paired_vs_baseline"] = _paired(primary, [c for c in baseline["cases"] if c["primary"]])
    return out


def summarise_dir(out, refset=None, baseline=None):
    out = Path(out).resolve()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    if refset is None:
        refset = ev.load_set("warmup")
    base_doc = json.loads(Path(baseline).read_text(encoding="utf-8")) if baseline else None
    reports, records = {}, {}
    for mode in meta["modes"]:
        runs = out / mode / "runs"
        if not runs.is_dir():
            continue
        records[mode] = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(runs.glob("*/oracle.json"))]
        done = {r["key"] for r in records[mode]}
        refs = ev.ReferenceSet(refset.name, [r for r in refset.references if r.key in done], refset.source,
                               refset.sha256, refset.meta)
        preds = ev.load_predictions([runs]) if any(runs.rglob("log.json")) else {}
        reports[mode] = ev.evaluate(refs, preds, sources=[str(runs)])
        ev.write_report(reports[mode], out / mode / "report.json")
    auto = reports.get("autonomous")
    auto_first = {r["key"]: r.get("first_output_sha") for r in records.get("autonomous", [])}
    summary = {"dir": str(out), "meta": meta, "baseline": str(baseline) if baseline else None,
               "note": "Oracle and simulated-human results cannot pass the human-assisted gate (PLAN.md 4.8); "
                       "scores are against the estimated warm-up references, not organiser measurements.",
               "modes": {m: mode_summary(reports[m], records[m], auto if m != "autonomous" else None, base_doc,
                                         auto_first) for m in reports}}
    summary["per_panorama"] = per_panorama(reports, records)
    _write_json(out / "summary.json", summary)
    print(format_summary(summary))
    print(f"summary: {out / 'summary.json'}")
    return summary


def per_panorama(reports, records):
    rows = {}
    for mode, report in reports.items():
        recs = {r["key"]: r for r in records[mode]}
        for c in report["cases"]:
            if not c["primary"]:
                continue
            r = recs.get(c["key"], {})
            row = rows.setdefault(c["key"], {"category": c["category"]})
            fpq = r.get("first_place_question") or {}
            row[mode] = {"d1_m": c.get("distance_m"), "cons_share": round(_share(c, "lower"), 4),
                         "asked": r.get("asked"), "answered": r.get("answered"), "skipped": r.get("skipped"),
                         "outcomes": [d["outcome"] for d in r.get("decisions", [])],
                         "first_place_recall": fpq.get("recall") if fpq.get("built") else None}
    return rows


def _pct(x):
    return "-" if x is None else f"{100 * x:.1f}%"


def format_summary(summary):
    lines = [f"{'mode':<11} {'urban<=100m':>11} {'cons':>6} {'nom':>6} {'upper':>6} {'median d1':>10} "
             f"{'asked/ans/skip':>14} {'right/wrong':>11} {'recall(1st)':>11} {'d vs auto':>9} {'+/-/=':>8} "
             f"{'same o1':>7}"]
    for mode, s in summary["modes"].items():
        if not s.get("n_primary"):
            lines.append(f"{mode:<11} no primary case")
            continue
        q, o, own = s["questions"], s["operator"], s["own_category_share"]
        p = s.get("paired_vs_autonomous") or {}
        fpq = s["first_place_question"]
        lines.append(f"{mode:<11} {s['urban_robust_100m']:>11} {_pct(s['mean_conservative_share']):>6} "
                     f"{_pct(own['nominal']):>6} {_pct(own['upper']):>6} {str(s['median_d1_m']):>10} "
                     f"{q['asked']:>4}/{q['answered']}/{q['skipped']:<5} {o['right']:>5}/{o['wrong']:<5} "
                     f"{fpq['recall']:>4}/{fpq['built']:<6} {_pct(p.get('mean')):>9} "
                     f"{p.get('better', '-')}/{p.get('worse', '-')}/{p.get('same', '-')}"
                     f" {str(p.get('same_first_output', '-')) + '/' + str(s['n_primary']) if p else '-':>7}")
    lines.append(summary["note"])
    return "\n".join(lines)


# -- a results row for EVALUATION.md ----------------------------------------------------------------

def _km(d):
    return "-" if d is None else f"{d:,.0f} m" if d < 1000 else f"{d / 1000:,.1f} km"


def code_note(codes):
    """The fingerprint a run loaded (its first), and the panoloc files edited while it ran: a running
    process keeps the modules it imported, so those edits did not reach it (unless first imported later)."""
    if not codes:
        return "-"
    first = codes[0]
    changed = sorted({f for c in codes[1:] for f, h in c["files"].items() if first["files"].get(f) != h})
    return first["sha256"][:12] + (f" (edited during the run: {', '.join(changed)})" if changed else "")


def report_row(report_path, name, operator="autonomous", runs=None):
    """The EVALUATION.md results row of a tools/evaluate.py (or eval_assisted) report, with the code
    fingerprints, question counts and times read from the run folder next to it (or `runs`)."""
    report_path = Path(report_path).resolve()
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    runs = Path(runs).resolve() if runs else report_path.parent / "runs"
    logs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(runs.rglob("log.json"))]
    codes = [json.loads(p.read_text(encoding="utf-8"))["code"] for p in sorted(runs.rglob("eval_meta.json"))]
    meta = report_path.parent.parent / "meta.json"
    if not codes and meta.is_file():
        m = json.loads(meta.read_text(encoding="utf-8"))
        codes = [m["code_start"]] + ([m["code_end"]] if "code_end" in m else [])
    primary = set(rep["reference"]["primary_keys"])
    status = [q["status"] for d in logs if d["panorama"] in primary for q in d.get("questions", [])]
    cached = [d for d in logs if any("(cached)" in str(s.get("model")) for s in d.get("stages", []))]
    fresh = [d for d in logs if d not in cached and d.get("outputs")]
    initial = sorted(d["outputs"][0]["t"] for d in fresh)
    t, agg = rep["targets_plan_4_8"], rep["primary"]
    u, m = t["urban_camera_accuracy"], t["mean_conservative_score"]
    if not logs:
        timing = "no run logs"
    elif initial:
        timing = (f"initial median {statistics.median(initial):.0f} s, max {initial[-1]:.0f} s, over 150 s "
                  f"{sum(x > 150 for x in initial)}/{len(initial)} (uncached runs)")
    else:
        timing = "perception cached: not a time measurement"
    if cached and initial:
        timing += f"; {len(cached)} partly cached"
    rel = report_path.relative_to(REPO) if report_path.is_relative_to(REPO) else report_path
    return (f"| {name} | {rep['created'][:16].replace('T', ' ')} | {code_note(codes)} | {operator} "
            f"| `{rel}` | {u['hits']}/{u['urban_references']} | {_pct(m['value'])} "
            f"| {_km(agg['distance_m']['median'])} "
            f"| {agg['score']['urban']['mean']:,.0f} / {agg['score']['non-urban']['mean']:,.0f} "
            f"| {status.count('answered')} / {status.count('skipped')} | {timing} |")


def paired_table(summary_path):
    """Markdown: per primary panorama, the autonomous first distance and conservative share, then per
    assisted mode the paired difference in conservative share and the questions answered / skipped."""
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    modes = [m for m in summary["modes"] if m != "autonomous"]
    head = "| Panorama | Cat. | Autonomous d1, cons. | " + " | ".join(f"{m}: Δ cons., ans/skip" for m in modes) + " |"
    lines = [head, "|" + "---|" * (3 + len(modes))]
    for key, row in sorted(summary["per_panorama"].items()):
        auto = row.get("autonomous", {})
        cells = [f"`{key}`", {"urban": "U", "non-urban": "N"}.get(row["category"], "?"),
                 f"{_km(auto.get('d1_m'))}, {_pct(auto.get('cons_share'))}"]
        for m in modes:
            r = row.get(m, {})
            if not r:
                cells.append("-")
                continue
            delta = r["cons_share"] - auto.get("cons_share", 0.0)
            cells.append(f"{100 * delta:+.1f} pt, {r.get('answered')}/{r.get('skipped')}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# -- containment: does the chosen option hold the next output? (no reference needed) --------------

def _option_holds(option, point, zones):
    """(holds, geometry text) for one logged option dict; holds is None when its geometry is unknown."""
    if option.get("zone_id"):
        return zones.contains(option["zone_id"], point), f"zone {option['zone_id']}"
    if option.get("cell"):  # T42 cell: the exact polygon, GeoJSON [lng, lat], edges included
        geometry = ("polygon", oracle._geojson_polygons(option["cell"]))
        return oracle.geometry_contains(geometry, point), f"cell {option.get('cell_id')}"
    if option.get("bbox"):
        b = option["bbox"]
        inside = b["south"] <= point[0] <= b["north"] and b["west"] <= point[1] <= b["east"]
        return inside, f"box S{b['south']:.5f} W{b['west']:.5f} N{b['north']:.5f} E{b['east']:.5f}"
    if option.get("radius_m") is not None and option.get("point"):
        c = (option["point"]["lat"], option["point"]["lng"])
        return (haversine_m(c, point) <= option["radius_m"] + 1e-6,
                f"disc {c[0]:.6f}, {c[1]:.6f} r {option['radius_m']:.0f} m")
    return None, "unknown"


def _answer_holds(question, chosen, point, zones):
    """(holds, geometry text) of an answered option; a complement holds what no listed option holds."""
    if not chosen.get("complement"):
        return _option_holds(chosen, point, zones)
    held = [(o["id"], *_option_holds(o, point, zones)) for o in question["options"] if not o.get("complement")]
    holds = None if any(h is None for _, h, _ in held) else not any(h for _, h, _ in held)
    return holds, "complement of " + ", ".join(f"{k}: {g}" for k, _, g in held)


def containment(paths):
    """Every answered question in the run logs under `paths`: does the chosen option hold the output
    produced right after the answer ("violations")? And does that output still respect every earlier
    answer of the run ("earlier")? Reads no reference. Returns {"checked", "unknown", "violations", "earlier"}."""
    from panoloc.zones import Zones
    zones, result = None, {"checked": 0, "unknown": 0, "violations": [], "earlier": [], "overrides": [],
                           "skipped_overridden": 0}
    for root in paths:
        for log in sorted(Path(root).resolve().rglob("log.json")):
            doc = json.loads(log.read_text(encoding="utf-8"))
            events = doc["events"]
            asked = {e["payload"]["question_id"]: e["payload"] for e in events if e["type"] == "question.asked"}
            overridden = {}  # question ID -> event index of its answer_overridden (recovery: the latest answer wins)
            for k, e in enumerate(events):
                if e["type"] == "evidence.added" and e["payload"].get("kind") == "answer_overridden":
                    overridden.setdefault(e["payload"].get("question_id"), k)
                    result["overrides"].append({"panorama": doc["panorama"], "log": str(log.relative_to(REPO)),
                                                "question_id": e["payload"].get("question_id"),
                                                "by": e["payload"].get("by")})
            answered = []
            for i, e in enumerate(events):
                if e["type"] != "question.answered":
                    continue
                q = asked[e["payload"]["question_id"]]
                chosen = next(o for o in q["options"] if o["id"] == e["payload"]["option_id"])
                answered.append((q, chosen))
                out, out_at = None, None  # the output this answer produced: before the next answer, if any
                for j, x in enumerate(events[i + 1:], start=i + 1):
                    if x["type"] == "question.answered":
                        break
                    if x["type"] == "output.produced":
                        out, out_at = x, j
                        break
                if out is None:
                    result["no_output"] = result.get("no_output", 0) + 1
                    continue
                c = out["payload"]["coordinates"][0]
                point = (c["lat"], c["lng"])
                if zones is None and any(o.get("zone_id") for o in q["options"]):
                    zones = Zones.open()
                holds, geometry = _answer_holds(q, chosen, point, zones)
                result["checked"] += 1
                entry = {"panorama": doc["panorama"], "log": str(log.relative_to(REPO)), "question_id": q["question_id"],
                         "kind": q["kind"], "option_id": chosen["id"], "label": chosen["label"], "geometry": geometry,
                         "output_id": out["payload"]["output_id"], "output": [round(point[0], 6), round(point[1], 6)],
                         "output_role": out["payload"].get("source_role"), "note": out["payload"].get("note")}
                if holds is None:
                    result["unknown"] += 1
                elif not holds:
                    result["violations"].append(entry)
                    continue
                for q0, chosen0 in answered[:-1]:
                    if overridden.get(q0["question_id"], len(events)) < out_at:
                        result["skipped_overridden"] += 1  # dropped by a later answer: not a constraint any more
                        continue
                    held0, geometry0 = _answer_holds(q0, chosen0, point, zones)
                    if held0 is False:
                        result["earlier"].append({**entry, "contradicts": {
                            "question_id": q0["question_id"], "option_id": chosen0["id"], "label": chosen0["label"],
                            "geometry": geometry0}})
    return result


# -- T79: the question-gate sweep on external validation sets (never the warm-up set) --------------

def cache_complete(panorama_path, cache=None):
    """True when every perception stage of this image is in the cache, so a run needs no model."""
    path = Path(panorama_path)
    folder = (Path(cache) if cache else _cache_dir()) / f"{path.name}-{path.stat().st_size}"
    return all((folder / name).is_file() for name in PERCEPTION_STAGES.values())


def sweep_configs(min_gains, max_questions):
    """[(name, min_gain, max_questions)]: the autonomous reference first, then the simulated human."""
    return [("autonomous", None, None)] + [(f"g{g:g}-q{m}", g, m) for m in max_questions for g in min_gains]


def set_constants(specs):
    """Set panoloc.pipeline module constants for this process from ["NAME=VALUE", ...] (Python literals);
    only existing upper-case names. Returns {name: value}."""
    import ast
    done = {}
    for spec in specs or []:
        name, _, value = spec.partition("=")
        if not (name.isupper() and hasattr(pipeline, name)):
            raise SystemExit(f"--set-const: panoloc.pipeline has no constant {name!r}")
        setattr(pipeline, name, ast.literal_eval(value))
        done[name] = getattr(pipeline, name)
    return done


def sweep(args):
    """Run the gate grid with the seeded simulated human on an external set, from the perception cache only."""
    if Path(args.set).name.startswith("warmup") or args.set == "warmup":
        raise SystemExit("tune on external validation only, never on the warm-up set (PLAN.md 4.6)")
    refset = ev.load_set(args.set)
    refs = refset.references[:args.limit] if args.limit else list(refset.references)
    index = {r.key: i for i, r in enumerate(refset.references, start=1)}
    configs = sweep_configs([float(g) for g in args.min_gains.split(",")], [int(m) for m in args.max_questions.split(",")])
    if args.configs:
        configs = [c for c in configs if c[0] in args.configs.split(",")]
    out = Path(args.out).resolve()
    constants = set_constants(args.set_const)  # in this eval process, before any run; pipeline.py is not edited
    models = pipeline.Models(retrieval=True, perception_cache=_cache_dir())
    started = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "set": args.set,
               "seed": args.seed, "mode": args.mode, "constants": constants, "sticky_skip": args.sticky_skip,
               "sticky_mistake": getattr(args, "sticky_mistake", None),
               "code_start": code_fingerprint()}
    pending, deadline = list(refs), time.monotonic() + args.wait
    while pending:
        ready = [r for r in pending if cache_complete(REPO / r.path)]
        for ref in ready:
            for name, gain, most in configs:
                case_dir = out / name / "runs" / f"{index[ref.key]:03d}-{Path(ref.path).stem}"
                if case_dir.exists():
                    continue  # resumable: a finished case is kept
                rec = run_case(ref, "autonomous" if gain is None else args.mode, models, case_dir,
                               min_gain=gain, max_questions=most, seed=args.seed, sticky_skip=args.sticky_skip,
                               sticky_mistake=getattr(args, "sticky_mistake", None))
                what = rec.get("error") or (f"answered {rec['answered']}, skipped {rec['skipped']}"
                                            + (f", COMPUTED {rec['computed']}" if rec.get("computed") else ""))
                _log(f"[{index[ref.key]}] {ref.key} {name}: {what} ({rec['elapsed_s']:.1f} s)")
            pending.remove(ref)
        if pending and not ready:
            if time.monotonic() > deadline:
                break
            time.sleep(30)
    for name, gain, most in configs:
        _write_json(out / name / "config.json", {**started, "config": name, "min_gain": gain, "max_questions": most,
                                                 "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                 "code_end": code_fingerprint(), "skipped_uncached": [r.key for r in pending]})
    _log(f"done: {len(refs) - len(pending)} panoramas, {len(pending)} skipped (perception not cached)")


def _sweep_cases(folder, refset):
    """{config: [(case, record)]} for the primary cases of one sweep folder, scored with panoloc.evaluate."""
    by_config = {}
    for cfg in sorted(p for p in Path(folder).iterdir() if (p / "runs").is_dir()):
        records = {r["key"]: r for r in (json.loads(p.read_text(encoding="utf-8"))
                                         for p in sorted((cfg / "runs").glob("*/oracle.json")))}
        refs = ev.ReferenceSet(refset.name, [r for r in refset.references if r.key in records], refset.source,
                               refset.sha256, refset.meta)
        report = ev.evaluate(refs, ev.load_predictions([cfg / "runs"]), sources=[str(cfg)])
        ev.write_report(report, cfg / "report.json")
        by_config[cfg.name] = [(c, records[c["key"]]) for c in report["cases"] if c["primary"]]
    return by_config


def _sweep_row(pairs, auto):
    """Metrics of one configuration over its (case, record) pairs, paired with the autonomous cases."""
    own = [c.get("score_ref") or 0.0 for c, _ in pairs]
    share = [c.get("fraction_of_max_ref") or 0.0 for c, _ in pairs]
    diff = [(c.get("score_ref") or 0.0) - (auto[c["key"]].get("score_ref") or 0.0) for c, _ in pairs if c["key"] in auto]
    ops = [r.get("operator") or {} for _, r in pairs]
    dist = [c["distance_m"] for c, _ in pairs if c.get("predicted")]
    return {"n": len(pairs), "mean_own": round(statistics.fmean(own), 1) if own else None,
            "share_of_max": round(statistics.fmean(share), 4) if share else None,
            "paired_diff": round(statistics.fmean(diff), 1) if diff else None,
            "paired_diff_share": round(statistics.fmean(diff) / ev.max_score(), 4) if diff else None,
            "better": sum(d > 1e-6 for d in diff), "worse": sum(d < -1e-6 for d in diff),
            "answered": sum(r.get("answered", 0) for _, r in pairs), "skipped": sum(r.get("skipped", 0) for _, r in pairs),
            "wrong": sum(o.get("wrong", 0) for o in ops), "median_d1_m": round(statistics.median(dist), 1) if dist else None,
            "computed": sum(bool(r.get("computed")) for _, r in pairs), "errors": sum(bool(r.get("error")) for _, r in pairs)}


def sweep_summary(folders, sets, out=None):
    """Per set and combined: one row per configuration (markdown), written to <out or first folder>/sweep.json."""
    pooled, result = {}, {"sets": {}, "combined": {}}
    for folder, name in zip(folders, sets):
        by_config = _sweep_cases(folder, ev.load_set(name))
        skipped = sorted({k for cfg in Path(folder).glob("*/config.json")
                          for k in json.loads(cfg.read_text(encoding="utf-8")).get("skipped_uncached", [])})
        auto = {c["key"]: c for c, _ in by_config.get("autonomous", [])}
        result["sets"][name] = {"skipped_uncached": skipped,
                                "rows": {cfg: _sweep_row(pairs, auto) for cfg, pairs in by_config.items()}}
        for cfg, pairs in by_config.items():
            pooled.setdefault(cfg, []).extend(pairs)
    auto = {c["key"]: c for c, _ in pooled.get("autonomous", [])}
    result["combined"] = {cfg: _sweep_row(pairs, auto) for cfg, pairs in pooled.items()}
    _write_json(Path(out or folders[0]) / "sweep.json", result)
    for title, rows in [*((f"{k} (skipped uncached: {len(v['skipped_uncached'])})", v["rows"])
                          for k, v in result["sets"].items()), ("combined", result["combined"])]:
        _print_sweep_table(title, rows)
    return result


def _print_sweep_table(title, rows):
    print(f"\n{title}\n| Config | n | Mean own score | % of max | Paired Δ (pts, % of max) | Better / worse "
          "| Answered / skipped / wrong | Median d1 |\n|---|---|---|---|---|---|---|---|")
    for cfg, r in sorted(rows.items(), key=lambda kv: (kv[0] != "autonomous", kv[0])):
        delta = ("" if cfg == "autonomous" or r["paired_diff"] is None
                 else f"{r['paired_diff']:+,.0f} ({100 * r['paired_diff_share']:+.2f})")
        print(f"| {cfg} | {r['n']:g} | {r['mean_own']:,.0f} | {_pct(r['share_of_max'])} | {delta} "
              f"| {r['better']:g} / {r['worse']:g} | {r['answered']:g} / {r['skipped']:g} / {r['wrong']:g} "
              f"| {_km(r['median_d1_m'])} |" + (f" COMPUTED {r['computed']}" if r["computed"] else "")
              + (f" ERRORS {r['errors']}" if r["errors"] else ""))


def sweep_average(paths):
    """Average the rows of several sweep.json files (one per simulated-human seed): means of the means and
    of the counts. Prints the per-set and combined tables; returns them."""
    docs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]

    def average(rows_list):
        out = {}
        for cfg in rows_list[0]:
            vals = [rows[cfg] for rows in rows_list if cfg in rows]
            out[cfg] = {k: (round(statistics.fmean(v[k] for v in vals), 4) if isinstance(vals[0][k], float)
                            else statistics.fmean(v[k] for v in vals)) if vals[0][k] is not None else None
                        for k in vals[0]}
        return out

    result = {"seeds": len(docs), "sets": {name: average([d["sets"][name]["rows"] for d in docs])
                                           for name in docs[0]["sets"]},
              "combined": average([d["combined"] for d in docs])}
    for name, rows in result["sets"].items():
        _print_sweep_table(f"{name}, mean of {len(docs)} seeds", rows)
    _print_sweep_table(f"combined, mean of {len(docs)} seeds", result["combined"])
    return result


LAND_TOLERANCE_M = 25.0  # panoloc.cells clips cells to land with this tolerance; option_for snaps up to 1 km


def _cell_distance_m(option_cell, point):
    """Metres from `point` to a logged cell polygon (GeoJSON [lng, lat]), on a local equirectangular frame."""
    import shapely
    from shapely.geometry import shape
    lat0 = math.radians(point[0])
    poly = shape(option_cell)
    kx, ky = EARTH_M_PER_DEG * math.cos(lat0), EARTH_M_PER_DEG
    local = shapely.transform(poly, lambda xy: (xy - [point[1], point[0]]) * [kx, ky])
    return float(shapely.distance(local, shapely.Point(0, 0)))


def classify_containment(res):
    """Sort containment() entries (T79): nothing fits every answer; the simulated human's own wrong answer
    (oracle.json outcome "wrong" for any answer up to the current one: later scopes build on it); sea point after
    place-only answers (cell routes before the 02:10 land rule); land band, by design (within 25 m plus the
    leaf's deviation_m of land, zones.on_land); pier/offshore limit (beyond that, within 1 km); cell point at
    sea; sub-cell Outside contradicting its parent cell; other cell-route cases; the earlier-cell-answer gap (a
    place or zone output contradicting an earlier cell answer); and real ones."""
    from panoloc.zones import Zones
    zones, logs, out = Zones.open(), {}, {}

    def facts(log):
        if log not in logs:
            doc = json.loads((REPO / log).read_text(encoding="utf-8"))
            asked = {e["payload"]["question_id"]: e["payload"] for e in doc["events"] if e["type"] == "question.asked"}
            order = [(e["payload"]["question_id"], asked[e["payload"]["question_id"]])
                     for e in doc["events"] if e["type"] == "question.answered"]
            rec = (REPO / log).parent.parent / "oracle.json"
            outcomes = {d["question_id"]: d["outcome"] for d in
                        json.loads(rec.read_text(encoding="utf-8")).get("decisions", [])} if rec.is_file() else {}
            logs[log] = (order, outcomes)
        return logs[log]

    for kind in ("violations", "earlier"):
        for entry in res[kind]:
            order, outcomes = facts(entry["log"])
            point = tuple(entry["output"])
            is_cell = "cell " in entry["geometry"] or "cell answer" in (entry.get("note") or "")
            loc = zones.locate(*point)
            off_m = None if loc is None else loc.distance_m
            ids = [qid for qid, _ in order]
            here = ids.index(entry["question_id"])
            # a wrong pick taints everything after it (later scopes are built on it): any wrong answer up to the
            # current one. The nominal oracle never errs, so its runs stay the clean test for pipeline gaps.
            window = ids[:here + 1]
            before = [q for qid, q in order[:here] if not any(o.get("cell") for o in q["options"])]
            if "fits every answer" in (entry.get("note") or ""):
                label = "nothing fits every answer"
            elif any(outcomes.get(q) == "wrong" for q in window):
                label = "simulated human's own wrong answer"
            elif is_cell and (loc is None or off_m > LAND_TOLERANCE_M) and before and all(q["kind"] == "place" for q in before):
                label = "sea point after place-only answer (fixed at 02:10)"
            elif is_cell and loc is not None and off_m > 0 and zones.on_land(point, LAND_TOLERANCE_M):
                label = "land band, by design"
            elif is_cell and loc is not None and LAND_TOLERANCE_M < off_m <= 1000:
                label = "pier/offshore limit"
            elif is_cell and loc is None:
                label = "cell point at sea (beyond 1 km of land)"
            elif (is_cell and kind == "earlier" and entry["geometry"].startswith("complement")
                  and entry["contradicts"]["geometry"].startswith("cell ")):
                label = "sub-cell Outside contradicts its parent"
            elif is_cell:
                label = "other cell-route case"
            elif kind == "earlier" and ("cell " in entry["contradicts"]["geometry"]):
                label = "earlier-cell-answer gap"
            else:
                label = "real"
            entry["class"], entry["off_land_m"] = label, None if off_m is None else round(off_m, 1)
            if label == "pier/offshore limit":
                q = dict(order)[entry["question_id"]]
                cells = [o for o in q["options"] if o.get("cell")]
                if cells:
                    entry["nearest_cell_m"] = round(min(_cell_distance_m(o["cell"], point) for o in cells), 1)
            out.setdefault(kind, {}).setdefault(label, []).append(entry)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run every mode on the warm-up set, then summarise")
    r.add_argument("--modes", default=",".join(MODES))
    r.add_argument("--retrieval", action="store_true", help="with the PE-Core photo bank (the B1 configuration)")
    r.add_argument("--limit", type=int, help="only the first N references")
    r.add_argument("--out", help="output folder (default runs/eval/assisted-<UTC time>)")
    r.add_argument("--baseline", help="a tools/evaluate.py report.json to pair against as well (e.g. B0)")
    r.add_argument("--follow", type=float, default=0.0, metavar="SECONDS",
                   help="before each panorama, wait up to SECONDS for its OCR and VLM results in the perception "
                        "cache (another run is producing them), so no perception work is repeated")
    s = sub.add_parser("summary", help="rescore and summarise an existing output folder")
    s.add_argument("out")
    s.add_argument("--baseline")
    w = sub.add_parser("row", help="print the EVALUATION.md results row of a report.json")
    w.add_argument("report")
    w.add_argument("--name", required=True)
    w.add_argument("--operator", default="autonomous")
    w.add_argument("--runs", help="the run folder (default: runs/ next to the report)")
    t = sub.add_parser("paired", help="print the per-panorama paired table of a summary.json (markdown)")
    t.add_argument("summary")
    c = sub.add_parser("containment", help="answered questions whose chosen option misses the next output")
    c.add_argument("paths", nargs="+")
    c.add_argument("--classify", action="store_true", help="sort the cases into the T79 categories")
    w = sub.add_parser("sweep", help="T79: min_gain x max_questions with the simulated human, cache only")
    w.add_argument("--set", required=True, help="an external reference set (never warmup)")
    w.add_argument("--out", required=True)
    w.add_argument("--min-gains", default="0.0526,0.1,0.2,0.3,0.5")
    w.add_argument("--max-questions", default="2,4")
    w.add_argument("--configs", help="only these configuration names (to split the grid over processes)")
    w.add_argument("--seed", type=int, default=oracle.HUMAN_SEED)
    w.add_argument("--mode", default="human", choices=oracle.MODES, help="the simulated operator (default human)")
    w.add_argument("--sticky-skip", type=float, help="human mode: an identical re-asked question is skipped again "
                   "with this probability (the conservative reading of skip retries); default: independent draws")
    w.add_argument("--sticky-mistake", type=float, help="human mode: when the right option lies outside an earlier "
                   "mistake, repeat the mistake with this probability (the conservative reading of recovery)")
    w.add_argument("--set-const", action="append", metavar="NAME=VALUE",
                   help="set a panoloc.pipeline constant in this process before any run, e.g. MAX_PLACE_MISSES=99")
    w.add_argument("--wait", type=float, default=3600.0, help="seconds to wait for uncached panoramas, then skip them")
    w.add_argument("--limit", type=int)
    y = sub.add_parser("sweep-summary", help="per set and combined tables of sweep folders")
    y.add_argument("--dirs", nargs="+", required=True)
    y.add_argument("--sets", nargs="+", required=True, help="the reference set of each folder, in order")
    a2 = sub.add_parser("sweep-average", help="average sweep.json files of several seeds")
    a2.add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    if args.command == "run":
        run(args)
    elif args.command == "summary":
        summarise_dir(args.out, baseline=args.baseline)
    elif args.command == "paired":
        print(paired_table(args.summary))
    elif args.command == "sweep":
        sweep(args)
    elif args.command == "sweep-summary":
        sweep_summary(args.dirs, args.sets)
    elif args.command == "sweep-average":
        sweep_average(args.files)
    elif args.command == "containment":
        res = containment(args.paths)
        for v in res["violations"]:
            print("violation", json.dumps(v, ensure_ascii=False))
        for v in res["earlier"]:
            print("earlier  ", json.dumps(v, ensure_ascii=False))
        if args.classify:
            for o in res["overrides"]:
                rec = (REPO / o["log"]).parent.parent / "oracle.json"
                outcomes = ({d["question_id"]: d["outcome"] for d in json.loads(rec.read_text(encoding="utf-8"))
                             .get("decisions", [])} if rec.is_file() else {})
                o["overridden_outcome"] = outcomes.get(o["question_id"])
            kinds = {"wrong": "override corrected a wrong answer", "right": "OVERRIDE DISCARDED A CORRECT ANSWER"}
            for label, n in sorted(Counter(kinds.get(o["overridden_outcome"], "override, outcome unknown")
                                           for o in res["overrides"]).items()):
                print(f"{'overrides':<10} {label:<52} {n}")
            for o in res["overrides"]:
                if o["overridden_outcome"] == "right":
                    print("flagged   ", json.dumps(o, ensure_ascii=False))
            for kind, groups in classify_containment(res).items():
                for label, entries in sorted(groups.items()):
                    extra = ""
                    if label == "pier/offshore limit":
                        extra = " (off land m, nearest cell m: " + ", ".join(
                            f"{e['off_land_m']}/{e.get('nearest_cell_m')}" for e in entries) + ")"
                    print(f"{kind:<10} {label:<52} {len(entries)}{extra}")
        free = [sum("unrestricted" in (v.get("note") or "") for v in res[k]) for k in ("violations", "earlier")]
        print(f"checked {res['checked']} answered questions: {len(res['violations'])} violations "
              f"({free[0]} with an unrestricted choice), {len(res['earlier'])} outputs contradicting an earlier "
              f"answer ({free[1]} unrestricted), {res['unknown']} with unknown geometry, "
              f"{res.get('no_output', 0)} answers that produced no output, {len(res['overrides'])} overridden answers "
              f"({res['skipped_overridden']} later checks skipped them)")
    else:
        print(report_row(args.report, args.name, args.operator, args.runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
