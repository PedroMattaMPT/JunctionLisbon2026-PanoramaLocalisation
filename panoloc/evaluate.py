"""Score predictions against a reference set: the warm-up baseline or an external split (PLAN.md 4.6-4.8).

This module is the only code that may read Data/warmup_locations.* (RULES.md, PLAN.md 4.6). The
warm-up references are evaluation-only: nothing here may flow back into the agent's inputs, prompts,
bank, training, calibration, thresholds or galleries. Reports therefore carry distances and scores,
never the reference coordinates or place descriptions. tests/test_evaluate.py fails if any other
file in panoloc/ or tools/ names the warm-up file.

Reference sets (`load_set`):
  warmup  Data/warmup_locations.json, refused unless its sha256 (and the .csv's) match WARMUP_SHA256.
          Primary = confidence "high" (the 19 references with 5-12 m radii); the 60 km one is reported
          as diagnostic only. Category = the file's `urban` estimate, source "inferred".
  val, final  Data/splits/external_{val,final}.json from tools/build_splits.py (Panoramax, split by
          whole collections). Every record is primary; the category is GHSL-inferred; radius unknown.
  a path  any JSON with the same "references" format.
A reference is matched by panorama filename (`key`, or one of its `aliases`). Scoring the final set
appends a line to Data/splits/final_runs.log: it is meant for one run (TASKS.md T54, PLAN.md 4.7).

Predictions (`load_predictions`): a run folder holding log.json (panoloc.runlog), a folder of run
folders (searched at any depth, so pass one experiment's folder, not all of runs/), a log.json itself,
or a plain JSON {panorama_filename: [[lat, lng], ...]}. A run that never finished has no log.json:
its events.jsonl is read instead. From a log, the
scored list is the last output.produced under its own penalty snapshot; every output is kept as the
trajectory. Several runs of one panorama: the latest started wins, and n_runs says so.

Per case: Haversine distance of the first coordinate; the list score under both categories (PLAN.md
1.3: the label is unknown while solving) at the nominal distance and at the reference radius bounds
(PLAN.md 4.6: lower uses d + r, upper max(0, d - r)); the fraction of the unpenalised maximum; and
the output method and uncertainty from the log. A reference with no prediction scores zero and
counts as a miss: every primary case stays in the denominator (PLAN.md 4.8). Distance medians and
means are over predicted cases only.

  refs = load_set("warmup")
  preds = load_predictions(["runs/"])
  report = evaluate(refs, preds)            # JSON-ready dict
  print(format_table(report))

Batch runner (`run_predictor`): calls predict(panorama_path, runs_dir) once per reference, with the
image path and a fresh empty folder for that panorama, nothing else; the predictor returns its run
folder (or that fresh folder, or a log.json path) or a list of [lat, lng]. A predictor exception is
recorded and scores zero.
"""
import hashlib
import importlib
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from panoloc.runlog import coordinate
from panoloc.scoring import MAX_ENTRIES, entry_score, haversine_m, max_score

REPO = Path(__file__).resolve().parent.parent
WARMUP_JSON = Path("Data/warmup_locations.json")
WARMUP_CSV = Path("Data/warmup_locations.csv")
WARMUP_PANORAMAS = Path("Data/Panorama Warm-Up")
WARMUP_FEEDBACK = Path("Data/warmup_feedback.json")  # organiser check of our references (RULES.md), evaluation only
FEEDBACK_UNDER_10_M = 10.0  # "under 10 m": the scorer counts any distance below 10 m as 0 anyway
# Frozen on 2026-10-10 (TASKS.md T23). A change means the baseline moved: re-freeze on purpose, never silently.
WARMUP_SHA256 = {
    "warmup_locations.json": "7027b8c7620b9a46fc79781f55990beba4913eb8675257bbf89c5848bc5754b7",
    "warmup_locations.csv": "7aa38e54a6fb511c13fda53bcb04818baf7161d77d9da3c5f29eb5b4e3e2c5a7",
}
SPLITS_DIR = Path("Data/splits")
FINAL_RUNS_LOG = "final_runs.log"
REFSET_SCHEMA = "panoloc.refset/1"
REPORT_SCHEMA = "panoloc.eval/1"
CATEGORIES = ("urban", "non-urban")
THRESHOLDS_M = (25, 100, 1_000, 10_000, 100_000)
# PLAN.md 4.8, provisional planning targets, frozen as stated there
TARGET_URBAN_HIT_M = 100.0
TARGET_URBAN_HIT_SHARE = 0.5
TARGET_MEAN_CONSERVATIVE_SHARE = 0.30


class ReferenceChanged(Exception):
    """The warm-up reference file no longer matches its frozen hash."""


@dataclass
class Reference:
    key: str                              # panorama filename: the match key
    lat: float
    lng: float
    path: str | None = None               # the image a predictor gets, relative to the repo root
    error_radius_m: float | None = None   # None: unknown, so results are nominal-only
    primary: bool = True
    category: str | None = None           # urban | non-urban | None
    category_source: str = "unknown"      # inferred | official | unknown (PLAN.md 1.3)
    tags: dict = field(default_factory=dict)
    aliases: list = field(default_factory=list)


@dataclass
class ReferenceSet:
    name: str
    references: list
    source: str = ""
    sha256: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class Prediction:
    key: str
    coordinates: list                     # [(lat, lng)], at most 10, the scored list
    multiplier: float = 1.0               # penalty multiplier in force when the list was produced
    special_one: bool = False
    penalty: dict | None = None           # the log's snapshot
    method: str | None = None
    uncertainty_m: float | None = None
    uncertainty_source: str | None = None
    trajectory: list = field(default_factory=list)  # every output: {output_id, t, coordinates, multiplier}
    source: str = ""
    run_id: str | None = None
    n_runs: int = 1
    error: str | None = None
    elapsed_s: float | None = None


# -- reference sets -------------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_frozen(path, expected):
    """Raise ReferenceChanged unless the file's sha256 is `expected`; return the hash."""
    actual = sha256_file(path)
    if actual != expected:
        raise ReferenceChanged(f"{path} changed: sha256 {actual}, frozen {expected}. Refusing to evaluate "
                               "against a moved baseline; re-freeze WARMUP_SHA256 deliberately if the change is intended.")
    return actual


def load_warmup(root=REPO):
    root = Path(root)
    hashes = {name: check_frozen(root / WARMUP_JSON.parent / name, digest) for name, digest in WARMUP_SHA256.items()}
    records = json.loads((root / WARMUP_JSON).read_text(encoding="utf-8"))
    feedback_path = root / WARMUP_FEEDBACK
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))["feedback"] if feedback_path.is_file() else {}
    refs = []
    for r in records:
        category, category_source = ("urban" if r["urban"] else "non-urban"), "inferred"
        radius, primary = float(r["error_radius_m"]), r["confidence"] == "high"
        fb = feedback.get(r["file"])
        if fb:  # checked by the organisers: the reference is within distance_m of the camera
            d = fb["distance_m"]
            radius, primary = (FEEDBACK_UNDER_10_M if d == "lt10" else float(d)), True
            if fb.get("category") in CATEGORIES:
                category, category_source = fb["category"], "official"
        refs.append(Reference(
            key=r["file"], lat=float(r["lat"]), lng=float(r["lon"]), path=str(WARMUP_PANORAMAS / r["file"]),
            error_radius_m=radius, primary=primary, category=category, category_source=category_source,
            tags={"country": r["country"], "category": category, "confidence": r["confidence"],
                  "organiser_checked": bool(fb)}))
    checked = sum(bool(feedback.get(r["file"])) for r in records)
    return ReferenceSet("warmup", refs, source=str(WARMUP_JSON), sha256=hashes["warmup_locations.json"],
                        meta={"estimated": checked < len(records), "is_ground_truth": False, "hashes": hashes,
                              "organiser_checked": checked,
                              "feedback": {"source": str(WARMUP_FEEDBACK), "sha256": sha256_file(feedback_path)}
                              if feedback else None,
                              "primary_rule": "organiser-checked (radius = their stated distance), else confidence "
                                              "== high (5-12 m radii); the rest diagnostic only",
                              "category_source": "official where the organisers revealed it, else the baseline's "
                                                 "own urban estimate"})


def load_refset_file(path, name=None):
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    refs = [Reference(**{k: v for k, v in r.items() if k in Reference.__dataclass_fields__})
            for r in doc["references"]]
    meta = {k: v for k, v in doc.items() if k != "references"}
    return ReferenceSet(name or doc.get("set") or path.stem, refs, source=str(path), sha256=sha256_file(path), meta=meta)


def load_set(name, root=REPO):
    """'warmup', 'val', 'final' or the path of a reference-set JSON."""
    root = Path(root)
    if name == "warmup":
        return load_warmup(root)
    if name in ("val", "final"):
        return load_refset_file(root / SPLITS_DIR / f"external_{name}.json", name)
    return load_refset_file(name)


def record_final_use(command, root=REPO, n=None):
    """Append one line to Data/splits/final_runs.log and return how many runs it now lists."""
    log = Path(root) / SPLITS_DIR / FINAL_RUNS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "command": command,
                            "n_cases": n}, ensure_ascii=False) + "\n")
    count = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"WARNING: the external final set is meant for ONE run (TASKS.md T54, PLAN.md 4.7). "
          f"{log} now lists {count} run(s); after the first, treat it as validation data.", file=sys.stderr)
    return count


# -- predictions ----------------------------------------------------------------------------------

def _coords(values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"expected a non-empty list of [lat, lng], got {values!r}")
    if len(values) > MAX_ENTRIES:
        raise ValueError(f"at most {MAX_ENTRIES} coordinates, got {len(values)}")
    return [tuple(coordinate(v).values()) for v in values]


def prediction_from_log(doc, source=""):
    """A Prediction from a panoloc.runlog log.json document (None when it has no output)."""
    outputs = doc.get("outputs") or ([doc["final_output"]] if doc.get("final_output") else [])
    if not outputs:
        return None
    trajectory = [{"output_id": o.get("output_id"), "t": o.get("t"),
                   "coordinates": [(c["lat"], c["lng"]) for c in o["coordinates"]],
                   "multiplier": (o.get("penalty") or {}).get("multiplier", 1.0), "method": o.get("output_method")}
                  for o in outputs]
    last = outputs[-1]
    return Prediction(
        key=doc["panorama"], coordinates=trajectory[-1]["coordinates"], multiplier=trajectory[-1]["multiplier"],
        special_one=bool(last.get("special_one", doc.get("special_one", False))), penalty=last.get("penalty"),
        method=last.get("output_method"), uncertainty_m=last.get("position_uncertainty_m"),
        uncertainty_source=last.get("uncertainty_source"), trajectory=trajectory, source=str(source),
        run_id=doc.get("run_id"))


def doc_from_events(path):
    """A log.json-like document rebuilt from an unfinished run's events.jsonl (a torn last line is skipped)."""
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        return None
    start = next((e for e in events if e["type"] == "run.started"), events[0])
    return {"panorama": start["panorama"], "run_id": start["run_id"], "started_at": start["ts"],
            "special_one": start["payload"].get("special_one", False), "events": events,
            "outputs": [{"t": e["t"], "seq": e["seq"], **e["payload"]} for e in events if e["type"] == "output.produced"]}


def _read_run(folder):
    if (folder / "log.json").is_file():
        return folder / "log.json", json.loads((folder / "log.json").read_text(encoding="utf-8"))
    if (folder / "events.jsonl").is_file():
        return folder / "events.jsonl", doc_from_events(folder / "events.jsonl")
    return None


def run_documents(path):
    """[(path, document)] for every run folder at or below `path`; an unfinished run is read from events.jsonl."""
    path = Path(path)
    folders = sorted({p.parent for name in ("log.json", "events.jsonl") for p in path.rglob(name)})
    found = [_read_run(f) for f in folders]
    return [f for f in found if f and f[1]]


def _is_log(doc):
    return isinstance(doc, dict) and "panorama" in doc and "events" in doc


def load_predictions(sources):
    """{key: Prediction} from run folders, folders of runs, log.json / events.jsonl files or plain JSON files."""
    found = {}
    for src in sources:
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(src)
        if src.is_dir():
            docs = run_documents(src)
        elif src.name == "events.jsonl":
            docs = [(src, doc_from_events(src))]
        else:
            docs = [(src, json.loads(src.read_text(encoding="utf-8")))]
        for p, doc in docs:
            if doc is None:
                continue
            if _is_log(doc):
                pred = prediction_from_log(doc, p)
                if pred:
                    found.setdefault(pred.key, []).append((doc.get("started_at") or "", pred))
            elif isinstance(doc, dict):
                for key, coords in doc.items():
                    try:
                        pred = Prediction(Path(key).name, _coords(coords), source=str(p))
                    except (ValueError, TypeError, KeyError) as exc:
                        raise ValueError(f"{p}: {key}: {exc} (want {{filename: [[lat, lng], ...]}})") from None
                    found.setdefault(pred.key, []).append(("", pred))
            else:
                raise ValueError(f"{p}: neither a panoloc log nor a {{filename: [[lat, lng], ...]}} JSON")
    result = {}
    for key, items in found.items():
        items.sort(key=lambda item: item[0])
        pred = items[-1][1]
        pred.n_runs = len(items)
        result[key] = pred
    return result


def prediction_from_result(key, result):
    """Turn a predictor's return value (run folder, log.json path, or [[lat, lng], ...]) into a Prediction."""
    if isinstance(result, (str, Path)):
        result = Path(result)
        if result.is_file():
            docs = [(result, doc_from_events(result) if result.name == "events.jsonl"
                     else json.loads(result.read_text(encoding="utf-8")))]
        else:
            docs = run_documents(result)
        if len(docs) != 1 or not _is_log(docs[0][1]):
            raise ValueError(f"predictor returned {result}, which is not exactly one run")
        path, doc = docs[0]
        pred = prediction_from_log(doc, path)
        if pred is None:
            raise ValueError(f"{path} has no output.produced")
        if pred.key != key:
            print(f"warning: {path} is for {pred.key}, scored as {key}", file=sys.stderr)
            pred.key = key
        return pred
    return Prediction(key, _coords(result), source="predictor")


# -- scoring --------------------------------------------------------------------------------------

def _bounded_distances(d, r):
    """(nominal, upper-score distance, lower-score distance) for a reference radius r (None: nominal only)."""
    r = r or 0.0
    return {"nominal": d, "upper": max(0.0, d - r), "lower": d + r}


def _list_score(distances, category, multiplier, special):
    return sum(entry_score(rank, d, category, multiplier, special) for rank, d in enumerate(distances, start=1))


def hit_status(d, r, threshold):
    """inside: within the threshold throughout the reference radius; outside: beyond it throughout; else boundary."""
    r = r or 0.0
    if d + r <= threshold:
        return "inside"
    if max(0.0, d - r) > threshold:
        return "outside"
    return "boundary"


def score_case(ref, pred):
    case = {"key": ref.key, "primary": ref.primary, "category": ref.category, "category_source": ref.category_source,
            "error_radius_m": ref.error_radius_m, "tags": ref.tags, "predicted": False}
    if pred is None or pred.error or not pred.coordinates:
        case.update(error=pred.error if pred else "no prediction", score={c: {"nominal": 0.0, "lower": 0.0, "upper": 0.0}
                                                                           for c in CATEGORIES})
        case.update(score_ref=0.0, score_ref_conservative=0.0, fraction_of_max_ref=0.0,
                    fraction_of_max_ref_conservative=0.0, fraction_of_max={c: 0.0 for c in CATEGORIES})
        if pred is not None:
            case["elapsed_s"] = pred.elapsed_s
        return case
    truth = (ref.lat, ref.lng)
    dists = [haversine_m(g, truth) for g in pred.coordinates]
    bounds = [_bounded_distances(d, ref.error_radius_m) for d in dists]
    score = {c: {b: round(_list_score([x[b] for x in bounds], c, pred.multiplier, pred.special_one), 2)
                 for b in ("nominal", "lower", "upper")} for c in CATEGORIES}
    top = max_score(special=pred.special_one)
    d1 = dists[0]
    case.update(
        predicted=True, distance_m=round(d1, 1), distance_min_m=round(bounds[0]["upper"], 1),
        distance_max_m=round(bounds[0]["lower"], 1), best_distance_m=round(min(dists), 1),
        n_coordinates=len(dists), score=score, max_score=round(top, 2),
        fraction_of_max={c: round(score[c]["nominal"] / top, 4) for c in CATEGORIES},
        hits={str(t): hit_status(d1, ref.error_radius_m, t) for t in THRESHOLDS_M},
        multiplier=pred.multiplier, penalty=pred.penalty, special_one=pred.special_one, method=pred.method,
        uncertainty_m=pred.uncertainty_m, uncertainty_source=pred.uncertainty_source, source=pred.source,
        run_id=pred.run_id, n_runs=pred.n_runs, elapsed_s=pred.elapsed_s,
        trajectory=[{"output_id": o["output_id"], "t": o["t"], "method": o["method"], "multiplier": o["multiplier"],
                     "distance_m": round(haversine_m(o["coordinates"][0], truth), 1),
                     **{f"score_{c}": round(_list_score([haversine_m(g, truth) for g in o["coordinates"]], c,
                                                        o["multiplier"], pred.special_one), 2) for c in CATEGORIES}}
                    for o in pred.trajectory])
    if ref.category in CATEGORIES:
        case.update(score_ref=score[ref.category]["nominal"], score_ref_conservative=score[ref.category]["lower"],
                    fraction_of_max_ref=round(score[ref.category]["nominal"] / top, 4),
                    fraction_of_max_ref_conservative=round(score[ref.category]["lower"] / top, 4))
    return case


def _stats(values):
    return {"total": round(sum(values), 2), "mean": round(sum(values) / len(values), 2) if values else None}


def aggregate(cases):
    """Metrics over a group of cases. Shares and score means count a missing prediction as a miss / zero."""
    n = len(cases)
    if not n:
        return {"n": 0}
    done = [c for c in cases if c["predicted"]]
    dists = [c["distance_m"] for c in done]
    out = {"n": n, "n_predicted": len(done), "n_missing": n - len(done),
           "distance_m": {"median": round(statistics.median(dists), 1) if dists else None,
                          "mean": round(statistics.fmean(dists), 1) if dists else None},
           "within": {str(t): round(sum(c["predicted"] and c["distance_m"] <= t for c in cases) / n, 4)
                      for t in THRESHOLDS_M},
           "within_robust": {str(t): round(sum(c["predicted"] and c["hits"][str(t)] == "inside" for c in cases) / n, 4)
                             for t in THRESHOLDS_M},
           "score": {c: _stats([x["score"][c]["nominal"] for x in cases]) for c in CATEGORIES},
           "mean_fraction_of_max": {c: round(statistics.fmean(x["fraction_of_max"][c] for x in cases), 4)
                                    for c in CATEGORIES}}
    with_ref = [c for c in cases if c["category"] in CATEGORIES]
    if with_ref:
        out["score"]["ref_category"] = _stats([c["score_ref"] for c in with_ref])
        out["score"]["ref_conservative"] = _stats([c["score_ref_conservative"] for c in with_ref])
        out["mean_fraction_of_max"]["ref_category"] = round(statistics.fmean(c["fraction_of_max_ref"] for c in with_ref), 4)
        out["mean_fraction_of_max"]["ref_conservative"] = round(
            statistics.fmean(c["fraction_of_max_ref_conservative"] for c in with_ref), 4)
    return out


def by_tag(cases):
    """{tag: {value: aggregate}} over every tag the references carry (None values skipped)."""
    groups = {}
    for c in cases:
        for tag, value in (c["tags"] or {}).items():
            if value is None or isinstance(value, (dict, list)):
                continue
            groups.setdefault(tag, {}).setdefault(str(value).lower() if isinstance(value, bool) else str(value),
                                                  []).append(c)
    return {tag: {value: aggregate(cs) for value, cs in sorted(values.items())} for tag, values in sorted(groups.items())}


def plan_targets(primary):
    """PLAN.md 4.8 accuracy gate over the primary cases, exactly as stated there (provisional targets)."""
    urban = [c for c in primary if c["category"] == "urban"]
    hits = sum(c["predicted"] and c["hits"][str(int(TARGET_URBAN_HIT_M))] == "inside" for c in urban)
    need = math.ceil(TARGET_URBAN_HIT_SHARE * len(urban))
    with_ref = [c for c in primary if c["category"] in CATEGORIES]
    mean_cons = statistics.fmean(c["fraction_of_max_ref_conservative"] for c in with_ref) if with_ref else None
    radius_known = all(c["error_radius_m"] is not None for c in primary)
    return {
        "provisional": True,
        "radius_aware": radius_known,
        "note": ("Targets apply to the retained configuration's realistic human-assisted runs; autonomous or oracle "
                 "runs are reported against them but cannot pass the gate (PLAN.md 4.8)."
                 + ("" if radius_known else " Reference radius unknown: nominal-only.")),
        "urban_camera_accuracy": {
            "rule": "first coordinate with d_ref + error_radius_m <= 100 m on at least 50% of urban primary references",
            "urban_references": len(urban), "hits": hits, "required": need,
            "pass": bool(urban) and hits >= need},
        "mean_conservative_score": {
            "rule": "mean over all primary cases of the score at d_max (d_ref + radius), per-output penalties, "
                    "reference category, divided by the unpenalised maximum; a missing case counts 0",
            "value": round(mean_cons, 4) if mean_cons is not None else None,
            "required": TARGET_MEAN_CONSERVATIVE_SHARE,
            "pass": mean_cons is not None and mean_cons >= TARGET_MEAN_CONSERVATIVE_SHARE},
    }


def evaluate(refset, predictions, *, sources=None):
    """The JSON-ready report of `predictions` ({key: Prediction}) against `refset`."""
    by_key = {}
    for ref in refset.references:
        for k in [ref.key, *ref.aliases]:
            by_key[k] = ref
    matched = {}
    for key, pred in predictions.items():
        ref = by_key.get(key)
        if ref is not None:
            matched[ref.key] = pred
    cases = [score_case(ref, matched.get(ref.key)) for ref in refset.references]
    primary = [c for c in cases if c["primary"]]
    return {
        "schema": REPORT_SCHEMA,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "set": refset.name,
        "reference": {"source": refset.source, "sha256": refset.sha256, "n": len(cases), "n_primary": len(primary),
                      "primary_keys": [c["key"] for c in primary], **refset.meta},
        "predictions": {"sources": [str(s) for s in (sources or [])], "n": len(predictions),
                        "unmatched": sorted(k for k in predictions if k not in by_key)},
        "primary": aggregate(primary),
        "by_tag": by_tag(primary),
        "diagnostic": [{k: c.get(k) for k in ("key", "predicted", "distance_m", "error_radius_m", "hits", "error")}
                       for c in cases if not c["primary"]],
        "targets_plan_4_8": plan_targets(primary),
        "cases": cases,
    }


# -- batch runner ---------------------------------------------------------------------------------

def load_predictor(spec):
    """'module:function' -> the function. The repo root is importable."""
    module, _, name = spec.partition(":")
    if not module or not name:
        raise ValueError(f"--predict wants module:function, got {spec!r}")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    return getattr(importlib.import_module(module), name)


def run_predictor(refset, predict, runs_dir, *, limit=None, root=REPO, on_case=None):
    """Call predict(panorama_path, case_dir) once per reference; returns {key: Prediction}.

    Each call gets the image path and a new empty folder <runs_dir>/<NNN>-<name>/ for its run, nothing
    else: no reference, category or tag, and no state from another panorama (RULES.md).
    """
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    refs = refset.references[:limit] if limit else refset.references
    predictions = {}
    for i, ref in enumerate(refs, start=1):
        path = Path(root) / ref.path if ref.path else None
        case_dir = runs_dir / f"{i:03d}-{Path(ref.key).stem}"  # a fresh folder per panorama: nothing shared
        t0 = time.monotonic()
        try:
            if path is None or not path.exists():
                raise FileNotFoundError(f"no image for {ref.key}: {path}")
            case_dir.mkdir(parents=True, exist_ok=False)
            pred = prediction_from_result(ref.key, predict(str(path), str(case_dir)))
        except Exception as exc:  # one failed panorama scores zero; the batch goes on
            pred = Prediction(ref.key, [], error=f"{type(exc).__name__}: {str(exc)[:300]}")
        pred.elapsed_s = round(time.monotonic() - t0, 2)
        predictions[ref.key] = pred
        if on_case:
            on_case(i, len(refs), ref, pred)
    return predictions


# -- output ---------------------------------------------------------------------------------------

def _km(d):
    if d is None:
        return "-"
    return f"{d:,.0f} m" if d < 1000 else f"{d / 1000:,.1f} km"


def _pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def _agg_line(a):
    if not a.get("n"):
        return "n=0"
    w = a["within"]
    line = (f"n={a['n']} (missing {a['n_missing']})  median {_km(a['distance_m']['median'])}, "
            f"mean {_km(a['distance_m']['mean'])}  |  within 25 m {_pct(w['25'])}, 100 m {_pct(w['100'])}, "
            f"1 km {_pct(w['1000'])}, 10 km {_pct(w['10000'])}, 100 km {_pct(w['100000'])}")
    s = a["score"]
    line += (f"\n    score urban total {s['urban']['total']:,.0f} mean {s['urban']['mean']:,.0f}"
             f"  |  non-urban total {s['non-urban']['total']:,.0f} mean {s['non-urban']['mean']:,.0f}")
    if "ref_category" in s:
        line += (f"  |  own category mean {s['ref_category']['mean']:,.0f} "
                 f"({_pct(a['mean_fraction_of_max']['ref_category'])} of max, conservative "
                 f"{_pct(a['mean_fraction_of_max']['ref_conservative'])})")
    return line


def format_table(report, max_rows=30):
    """A short readable summary of a report for stdout; per-case rows only for sets of at most max_rows."""
    ref, preds = report["reference"], report["predictions"]
    lines = [f"set {report['set']}: {ref['n']} references ({ref['n_primary']} primary), {preds['n']} predictions"
             + (f", {len(preds['unmatched'])} unmatched" if preds["unmatched"] else ""),
             f"{'panorama':<44} {'cat':<4} {'d1':>9} {'urban':>7} {'non-urb':>7} {'own%':>5} {'pen':>5}  method / unc"]
    rows = [c for c in report["cases"] if c["primary"]]
    if len(rows) > max_rows:
        lines[-1] = f"({len(rows)} cases: per-case rows are in the JSON report)"
        rows = []
    for c in rows:
        cat = {"urban": "U", "non-urban": "N"}.get(c["category"], "?")
        if not c["predicted"]:
            lines.append(f"{c['key'][:44]:<44} {cat:<4} {'-':>9}  {c.get('error') or 'no prediction'}")
            continue
        unc = "" if c["uncertainty_m"] is None else f" ±{_km(c['uncertainty_m'])}"
        lines.append(f"{c['key'][:44]:<44} {cat:<4} {_km(c['distance_m']):>9} {c['score']['urban']['nominal']:>7,.0f} "
                     f"{c['score']['non-urban']['nominal']:>7,.0f} {_pct(c.get('fraction_of_max_ref')):>5} "
                     f"{c['multiplier']:>5.3f}  {c['method'] or '-'}{unc}")
    lines.append(f"primary: {_agg_line(report['primary'])}")
    for tag, values in report["by_tag"].items():
        if tag in ("confidence",):
            continue
        for value, a in values.items():
            w = a.get("within", {})
            lines.append(f"  {tag + '=' + value:<36} n={a['n']:<4} median {_km(a['distance_m']['median']):>9}  "
                         f"<=100 m {_pct(w.get('100')):>4}  <=1 km {_pct(w.get('1000')):>4}  "
                         f"<=10 km {_pct(w.get('10000')):>4}  own {_pct(a['mean_fraction_of_max'].get('ref_category'))}")
    for d in report["diagnostic"]:
        lines.append(f"diagnostic {d['key']}: d1 {_km(d['distance_m'])} (reference radius {_km(d['error_radius_m'])})"
                     + ("" if d["predicted"] else f"  {d.get('error') or 'no prediction'}"))
    t = report["targets_plan_4_8"]
    u, m = t["urban_camera_accuracy"], t["mean_conservative_score"]
    lines.append(f"PLAN 4.8 (provisional{'' if t['radius_aware'] else ', nominal-only'}): urban within 100 m robust "
                 f"{u['hits']}/{u['urban_references']} (need {u['required']}) {'PASS' if u['pass'] else 'FAIL'}; "
                 f"mean conservative {_pct(m['value'])} of max (need {_pct(m['required'])}) "
                 f"{'PASS' if m['pass'] else 'FAIL'}")
    return "\n".join(lines)


def write_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_jsonable) + "\n", encoding="utf-8")
    return path


def _jsonable(value):
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")
