#!/usr/bin/env python3
"""Evaluate panorama predictions against the warm-up baseline or an external split (TASKS.md T23, T22).

The logic lives in panoloc/evaluate.py (conventions there). This script and that module are the only
code allowed to read Data/warmup_locations.*: evaluation only, never agent input (RULES.md, PLAN.md 4.6).

Usage (from the repo root, with the venv):
  # score existing predictions: run folders (log.json), a folder of runs, or {filename: [[lat, lng], ...]}
  .venv/bin/python tools/evaluate.py score --set warmup --predictions runs/eval/warmup-xyz [more ...]
  .venv/bin/python tools/evaluate.py --set val --predictions preds.json        # "score" is the default

  # run a predictor on every panorama of a set, then score: predict(panorama_path, runs_dir) returns
  # its run folder (or log.json path) or [[lat, lng], ...]; one fresh call per panorama
  .venv/bin/python tools/evaluate.py run --set val --predict panoloc.pipeline:predict --limit 20

  # check the frozen warm-up hashes
  .venv/bin/python tools/evaluate.py hash

Sets: warmup (19 primary + 1 diagnostic), val / final (Data/splits/external_*.json from
tools/build_splits.py), or a path to a reference-set JSON. Scoring or running `--set final` appends to
Data/splits/final_runs.log: that set is for one run only (T54).
The JSON report goes to --out (default runs/eval/<set>-<UTC time>/report.json); a table goes to stdout.
`run` keeps each panorama's run under runs/eval/<set>-<time>/runs/NNN-<name>/; a predictor that returns
plain lists also gets them saved as predictions.json there. Rescore with `score --predictions` on either.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from panoloc import evaluate as ev  # noqa: E402

COMMANDS = ("score", "run", "hash")


def _out_dir(args):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path(args.runs_dir) / f"{Path(args.set).stem}-{stamp}"


def _finish(args, refset, preds, sources, out_dir):
    report = ev.evaluate(refset, preds, sources=sources)
    path = ev.write_report(report, Path(args.out) if args.out else out_dir / "report.json")
    print(ev.format_table(report))
    print(f"report: {path}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS + ("-h", "--help"):
        argv.insert(0, "score")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("score", "run"):
        p = sub.add_parser(name)
        p.add_argument("--set", default="warmup", help="warmup, val, final or a reference-set JSON path")
        p.add_argument("--out", help="report path (default runs/eval/<set>-<time>/report.json)")
        p.add_argument("--runs-dir", default="runs/eval", help="parent folder for run outputs and reports")
    sub.choices["score"].add_argument("--predictions", nargs="+", required=True,
                                      help="run folders, folders of runs, log.json or plain JSON files")
    run = sub.choices["run"]
    run.add_argument("--predict", required=True, help="module:function, called as function(panorama_path, runs_dir)")
    run.add_argument("--limit", type=int, help="only the first N panoramas of the set")
    sub.add_parser("hash")
    args = ap.parse_args(argv)

    if args.command == "hash":
        for name, digest in ev.WARMUP_SHA256.items():
            path = ev.REPO / ev.WARMUP_JSON.parent / name
            ok = ev.sha256_file(path) == digest
            print(f"{'ok     ' if ok else 'CHANGED'} {path.relative_to(ev.REPO)} {digest}")
        return 0

    refset = ev.load_set(args.set)
    if args.set == "final":  # logged before anything runs, so a crashed attempt still counts
        ev.record_final_use(" ".join(["tools/evaluate.py", *argv]), n=len(refset.references))
    out_dir = _out_dir(args)
    if args.command == "score":
        _finish(args, refset, ev.load_predictions(args.predictions), args.predictions, out_dir)
        return 0

    predict = ev.load_predictor(args.predict)
    runs_dir = out_dir / "runs"

    def progress(i, n, ref, pred):
        what = pred.error or f"{len(pred.coordinates)} coordinates"
        print(f"[{i}/{n}] {ref.key}: {what} ({pred.elapsed_s:.1f} s)", file=sys.stderr, flush=True)

    preds = ev.run_predictor(refset, predict, runs_dir, limit=args.limit, on_case=progress)
    plain = {k: p.coordinates for k, p in preds.items() if p.source == "predictor" and p.coordinates}
    if plain:  # lists returned without a run log: keep them so the run can be rescored
        ev.write_report(plain, out_dir / "predictions.json")
    if args.limit:  # score only what ran: the rest of the set would count as misses
        refset.references = refset.references[:args.limit]
    _finish(args, refset, preds, [f"predict={args.predict}", str(runs_dir)], out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
