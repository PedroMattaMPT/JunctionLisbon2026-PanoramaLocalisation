"""One panorama end to end: views, OCR and VLM, retrieval, names, fusion, questions, coordinates (PLAN.md 3; T20).

Stages, each logged by Run.stage. A failed optional stage is logged and the run goes on without it:
  prepare   core      parse the filename, load the panorama, cut the 8 horizontal views + sky + ground
  read      optional  PP-OCRv6 on the CPU (panoloc.ocr)                  } run side by side: CPU and GPU
  describe  optional  the VLM checklist and landmark hypotheses (panoloc.vlm) }
  retrieve  optional  PE-Core kNN over the photo bank and the region head (panoloc.retrieval): group pe-core
  geoclip   optional  GeoCLIP over its PT/ES/FR gallery (panoloc.geoclip_gen): group geoclip
  landmarks optional  Commons landmark photos (panoloc.landmarks, group pe-core), then a geometric check of
                      the top hits (panoloc.verify: ALIKED + LightGlue + RANSAC, group verified, independent
                      of the encoder). A verified hit is still a landmark coordinate, not the camera's
  names     optional  OCR and VLM clues looked up in the name index (panoloc.fusion adapters)
  fuse      core      hypotheses, P(country), the expected-score selection (panoloc.fusion)
  output    core      the first coordinate, before any question (PLAN 3.5: an initial answer first)
  ask       loop      questions while one is worth its x0.95 (panoloc.questions), each answer re-selects
The perception results are saved next to the log (ocr.json, vlm.json) for review and recalibration.

Perception cache (evaluation only): with Models(perception_cache=DIR), OCR and VLM results, and the
kNN, region-head, GeoCLIP and landmark candidates (retrieval.json, geoclip.json, landmarks.json), are stored in
DIR/<file name>-<size>/ and reused when the same file is run again, so fusion can be recalibrated (T39)
without paying a minute of OCR and VLM per panorama again. A cached stage logs a perception_cache
evidence event and the saved signs, scene checks, items and hints it reused. The live CLI uses no cache unless
--perception-cache is given. A cache entry describes one image file only; nothing crosses panoramas.

Models (OCR engine, VLM client, name index, PE-Core and the bank) load once in a Models object and are
reused across panoramas: they hold weights and settings only. Every panorama gets a fresh Run, and
nothing it found reaches another panorama (RULES.md, partner clarification 1).

Operators (who answers questions):
  "never"  no question is asked (autonomous evaluation)
  "ask"    the team answers on stdin (panoloc.questions.ask_operator)
  "skip"   each worth-asking question is logged and skipped: costs nothing, changes nothing
  callable answer_fn(question) -> option ID or None (a simulated operator for evaluation, T40). It
           receives the Question only; it must never see a reference coordinate.
Each step builds the place and the zone question still in the schedule and asks the one with the best
expected gain, never one already put to the team in this run (identical kind and options). A skip
changes no belief, so after one the loop moves on to the other kinds and infers nothing from the silence
(RULES.md); an answer resets the schedule. After "None of these" the identical place question can't
come back, and after MAX_PLACE_MISSES of them in a row only zone questions are asked until an answer
picks a place or zone (PLAN.md 3.4: the zone fallback).

Zone questions use named zones (panoloc.zones over Data/index/zones.gpkg: districts, provinces,
regions ... down to parishes; T32) when the index is built, else latitude/longitude box cells. Named
zone questions chain: the next one stays inside the zone an answer picked, with an explicit outside
option, and a picked zone that holds no hypothesis gets its weight spread over its subzones.

Questions are off by default (ASK_QUESTIONS, user decision Sun 05:30: with a realistic team every gate lost
to never asking); ask_anyway=True or an explicit min_gain turns them on. Gate: a question is asked when its
expected gain beats min_gain (default MIN_GAIN, the x0.95 break-even), at most MAX_QUESTIONS place/zone answers and
MAX_CELL_QUESTIONS cell answers. A skipped question may come back, identical, up to CELL_SKIP_RETRIES /
MAIN_SKIP_RETRIES times on a fixed schedule; nothing is inferred from the skip and it costs nothing.

Answers: every output and every later question fits every answer so far (place, zone and cell): questions
are built from the hypotheses the answers allow, picked zones keep the exclusions inside them, and with no
hypothesis left a point is built inside every answered area (cells.constrain). A cell route (panoloc.cells,
T42) starts when a hypothesis dominates, after a place pick or after a zone pick down to a leaf, and narrows
to a geographic_cell output with a conservative bound. Wrong-answer recovery (RECOVERY) is off: on val it
dropped correct answers about as often as it fixed wrong ones.

Place options that only carry a generator ID ("osv5m:...", "geoclip:...") are relabelled before a question
with the zone that holds them ("Photo-bank match in Arroios, Lisboa (PT)"), so the team can check them.

Urban probability: while the category is unknown and urban_probability is None (the default), it comes
from GHSL urbanity at the heaviest hypotheses (panoloc.urban, T80), logged as an assumption; neutral for
the first output on cached val (1,904 vs 1,900 at a fixed 0.5), it lets urban cell refinement go below
40-80 m. Pass a number to fix it. It is estimated again when a cell route starts (ROUTE_URBAN_REESTIMATE,
kept by the val sweep).

Category: pass category ("urban" / "non-urban") with category_source "official" only when the
organisers supply it; otherwise both scenarios are scored with urban_probability (PLAN 1.3).

  from panoloc.pipeline import Models, run_panorama
  models = Models()                                     # loads lazily, once per process
  result = run_panorama("Data/Panorama Warm-Up/IMG_....jpg", models, operator="ask")
  result.output.coordinates(), result.log_path

CLI: python -m panoloc.pipeline <panorama.jpg> [--operator never|ask|skip] [--no-ocr] [--no-vlm]
[--no-retrieval] [--category urban|non-urban] [--special-one] [--ask-anyway] [--runs-dir runs]
Evaluation hook (tools/evaluate.py --predict panoloc.pipeline:predict): predict(path, runs_dir) -> run dir.
"""
import argparse
import importlib
import inspect
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from panoloc import fusion, questions, urban
from panoloc.candidates import Candidate, Output, normalise
from panoloc.runlog import Run
from panoloc.views import cut_views, load_panorama, parse_filename

try:  # the cell route (T42) needs shapely, so .venv only; without it the loop is as before
    from panoloc import cells
except ImportError:
    cells = None

# Placeholders until T39. kNN and the region head share PE-Core, so fusion never lets one confirm the
# other, and together they carry 0.55. On Panoramax val (track 2), GeoCLIP alone scored non-urban 3,507 and
# kNN 2,479; on OSV-5M val, kNN 5,288 and GeoCLIP 1,432: they are complementary.
VLM_PLUGIN = "panoloc.local_vlm"  # optional, untracked: a module with make_client, selected_model and claims
# Place reasoning (panoloc.reason): the VLM sees the whole panorama and every other finding, then names places.
# On (Sun 09:15). Warm-up, no questions: own-category mean 36.5% -> 56.0%, and 5 -> 10 urban panoramas within
# 100 m. First 30 of val: 21.8% -> 43.1%, all 30 answered, median 16.5 s per panorama with perception cached. The
# reply carries answers only, never the model's reasoning. REASON_LOCAL (the local VLM) has not been measured.
REASON = True
REASON_LOCAL = True  # Sun 10:50: val first 30 1.7% -> 13.9%, warm-up 29.1% -> 30.8% (reason.RELIABILITY_SCALE_LOCAL)
# Refine (T83): the VLM plugin's optional refine(models, pano, fused, reasoned, log), a tool-using step that looks
# for the exact camera position around the first output (map features, imagery, bearing resection in code). Its
# answer becomes a second output; a timeout, failure or no answer keeps the first. Measured Sun 10:05 with no
# questions: val first 30 39.3% -> 58.9% (urban within 100 m 14 -> 20 of 29), warm-up 61.7% -> 79.3%.
REFINE = True
REFINE_LOCAL = False  # the same step on the local VLM (panoloc.locate); not measured as a gain yet
REFINE_DEADLINE_S = 200.0
REFINE_UNCERTAINTY_M = {"high": 10.0, "medium": 25.0, "low": 100.0}
KNN_RELIABILITY = 0.3
REGION_HEAD_RELIABILITY = 0.375  # x1.5 by T39 (see fusion.OCR_NAME_RELIABILITY)
GEOCLIP_RELIABILITY = 0.35
KNN_K = 20
REGION_HEAD_K = 4
GEOCLIP_K = 10
# Commons landmark gallery (T33/T41, Panoramax val): PT top-1 within 100 m of the camera 13.7%; verification
# at >= 21 inliers kept 11 of 48 true pairs and 0 of 508 false ones. Gallery hits share PE-Core; verified hits
# don't. Unverified gallery hits, own-category mean on cached val (tools/calibrate_fusion.py, Sun 01:00):
#   reliability      0      0.05    0.10    0.20
#   val_first100   1,235   1,227    823     661    (ES/FR: the gallery is PT only, so its hits there are wrong)
#   val_pt30       3,791   4,147   4,187   3,930
# 0.05 keeps most of the PT gain at almost no ES/FR cost. Re-check when ES/FR Commons photos are embedded.
LANDMARK_RELIABILITY = 0.05
VERIFIED_RELIABILITY = 0.7
LANDMARK_K = 10
VERIFY_TOP = 10
VLM_DEADLINE_S = 90.0
OCR_DEADLINE_S = 40.0
MAX_QUESTIONS = 6  # place and zone answers; the gain gate usually stops sooner (T79: 4 beat 2 at every gate)
MIN_GAIN = questions.BREAK_EVEN  # a question is asked only when its expected gain beats this
# Questions are off by default (user, Sun 05:30): with a realistic simulated team (70% right, 10% wrong, 20%
# sticky skips) every gate lost to never asking on the warm-up (19 x 3 seeds): never 36.5% of max, gate 1.0
# 33.2% (0.4 questions per panorama), gate 0.5 32.1% (1.6), the 05:00 default 26.3% (7.1); val ES30 22.1% /
# 22.7% / 21.1% / 21.7%. ask_anyway, or an explicit min_gain, turns them on (rehearsals, a team that wants them)
ASK_QUESTIONS = False
ANSWER_ACCURACY = questions.DEFAULT_ANSWER_ACCURACY  # assumed share of right answers: the gate's expected gain,
# the soft update after an answer and the cell routes all use it (the app's realistic batch: 8 of 58 answers wrong)
# Skips (Sun 03:20): a skipped question may come back, identical, on a fixed schedule; nothing is inferred
# from the skip. With a simulated team whose re-asked skips stick (p 0.75): warm-up +1.2 pt (D2), val_130
# +248 per panorama at 2/2 (1/1: +0); about 1.3 more skipped prompts per panorama of team time
CELL_SKIP_RETRIES = 2  # a skipped cell question is asked again up to this many times before the route stops
MAIN_SKIP_RETRIES = 2  # skipped place/zone questions that may come back (identical) per panorama
ANSWER_SLACK = 0  # off: it rarely fires, val +10 / nominal -45. 1: when nothing fits every answer, hypotheses fitting all answers but one come before a built point
# Recovery from a wrong answer: a hypothesis that breaks exactly one earlier answer but still holds
# RECOVERY_SHARE of the soft weight may be offered again in a place question; if the team then picks it, the
# latest answer wins and the earlier one it contradicts is dropped (logged). Warm-up (D2, 3 seeds, sticky-skip
# simulated team): 14.0% -> 16.0% of max, urban <= 100 m 2.7 -> 3.7 per seed (share 0.05: 15.2%); always-right
# operator 5,342 -> 5,285. Val_130 (steps,plan, 03:45): overrides dropped a correct answer 87 times and fixed a
# wrong one 50 times (nominal -266, PT seeds -331/-98): off. Since 03:50 an answer is only overridden when the
# answers truly contradict (no point can satisfy them all); re-measure before turning it on
RECOVERY = False
RECOVERY_SHARE = 0.15
RECOVERY_EVIDENCE = True  # re-offer only hypotheses backed by strong independent evidence (verified landmark, OCR)
RECOVERY_MIN_OWN = 0.2  # an OCR clue's own fusion weight that counts as strong
REDOMINANCE = True  # after an answer that starts no route, start one if a hypothesis now dominates (D2, 319)
POINT_BASE_HYPOTHESES = 3  # zones around this many heaviest hypotheses seed a point that fits every answer
MAX_PLACE_MISSES = 2  # consecutive "None of these" place answers; then zone questions only, until a pick (T26 v2)
ROUTE_URBAN_REESTIMATE = True  # re-estimate P(urban) when a cell route starts (T80); off = keep the fusion-time value
MAX_CELL_QUESTIONS = 12  # cell answers have their own budget; the target bound or the gain gate stops them sooner
QUESTION_SCHEDULE = ("place", "zone")
PLACE_SEPARATION_M = questions.DEFAULT_MIN_SEPARATION_M
UNNAMED_SOURCES = {"osv5m": "Photo-bank match", "geoclip": "GeoCLIP estimate"}
LABEL_CHECK_TOP = 60  # heaviest hypotheses whose repeated labels get their zones appended


class Models:
    """Everything loaded once per process: weights and settings only, never a panorama's state."""

    def __init__(self, *, ocr=True, vlm=True, retrieval=True, landmarks=True, vlm_model=None, perception_cache=None):
        self.use = {"ocr": ocr, "vlm": vlm, "retrieval": retrieval, "landmarks": retrieval and landmarks}
        self.vlm_model = vlm_model
        self.perception_cache = Path(perception_cache) if perception_cache else None
        self._ocr = self._vlm = self._vlm_local = self._pecore = self._bank = self._head = self._geoclip = None
        self._zones = None  # panoloc.zones.Zones, or False once it failed to load
        self._gallery = self._verifier = None

    def ocr(self):
        if self._ocr is None:
            from panoloc.ocr import Engine
            self._ocr = Engine()
        return self._ocr

    def vlm(self):
        """The VLM: the optional plugin (VLM_PLUGIN) when it provides a client for this configuration, else
        Ollama (panoloc.vlm). PANOLOC_VLM=local always means Ollama."""
        if self._vlm is None:
            plugin = vlm_plugin()
            client = plugin.make_client(self.vlm_model) if plugin and self._plugin_may(plugin) else None
            self._vlm = client or self.vlm_local()
        return self._vlm

    def _plugin_may(self, plugin):
        return not self.vlm_model or plugin.claims(self.vlm_model)

    def vlm_name(self):
        """The model vlm() uses, without building the client (the VLM perception cache is keyed by it)."""
        if self._vlm is not None:
            return self._vlm.model
        plugin = vlm_plugin()
        name = plugin.selected_model(self.vlm_model) if plugin and self._plugin_may(plugin) else None
        if name:
            return name
        from panoloc.vlm import DEFAULT_MODEL
        return self._local_model() or DEFAULT_MODEL

    def _local_model(self):
        plugin = vlm_plugin()
        return self.vlm_model if self.vlm_model and not (plugin and plugin.claims(self.vlm_model)) else None

    def vlm_local(self):
        """The Ollama VLM: the default, and the per-panorama fallback when the plugin's VLM fails."""
        if self._vlm_local is None:
            from panoloc.vlm import OllamaClient
            local = self._local_model()
            self._vlm_local = OllamaClient(**({"model": local} if local else {}))
        return self._vlm_local

    def retrieval(self):
        if self._bank is None:
            from panoloc import retrieval
            self._pecore = retrieval.PECore()
            self._head = retrieval.RegionHead.load()
            self._bank = retrieval.Bank.open()
        return self._pecore, self._bank, self._head

    def zones(self):
        """The named-zone index (Data/index/zones.gpkg), or None: zone questions then use box cells."""
        if self._zones is None:
            try:
                from panoloc.zones import Zones
                self._zones = Zones.open()
            except (ImportError, OSError, RuntimeError) as exc:  # ZonesNotBuilt is a FileNotFoundError
                print(f"zone index unavailable, zone questions use box cells: {exc}", file=sys.stderr)
                self._zones = False
        return self._zones or None

    def landmarks(self):
        if self._gallery is None:
            from panoloc.landmarks import Gallery
            self._gallery = Gallery.open()
        return self._gallery

    def verifier(self):
        if self._verifier is None:
            from panoloc.verify import Verifier
            self._verifier = Verifier()
        return self._verifier

    def geoclip(self):
        if self._geoclip is None:
            from panoloc.geoclip_gen import GeoCLIPGen
            self._geoclip = GeoCLIPGen()
        return self._geoclip

    def versions(self):
        return {"pipeline": "panoloc.pipeline v1", "fusion": "panoloc.fusion v1 (uncalibrated placeholders)",
                **({"vlm_model": self._vlm.model} if self._vlm else {}),
                **({"vlm_fallback_model": self._vlm_local.model}
                   if self._vlm_local and self._vlm_local is not self._vlm else {})}


@dataclass
class PanoramaResult:
    run_id: str
    run_dir: Path
    log_path: Path
    output: object
    fused: object
    outputs: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)
    review_state: dict | None = None


def _write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, default=str), encoding="utf-8")


def _cache_file(models, path, name):
    if models.perception_cache is None:
        return None
    return models.perception_cache / f"{path.name}-{path.stat().st_size}" / name


def _cached(run, stage, file, model, log_fn):
    """A cached stage: the saved document, or None when absent. Logged inside its optional stage (a
    perception_cache event, then log_fn(doc, model)), so a logging error fails the stage, not the run."""
    if file is None or not file.is_file():
        return None
    doc = json.loads(file.read_text(encoding="utf-8"))
    model = f"{model} (cached)"
    with run.stage(stage, optional=True, model=model):
        run.evidence("perception_cache", {"file": str(file), "observation": f"{stage}: reused {file.name} from the "
                                          "perception cache (same image file)"}, stage=stage, actor="agent")
        log_fn(doc, model)
    _write_json(run.dir / file.name, doc)
    return doc


def _store(file, doc):
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        _write_json(tmp, doc)
        os.replace(tmp, file)


def _read(models, path, pano, views, run):
    file = _cache_file(models, path, "ocr.json")
    def log_items(doc, model):
        sign_ids = {}
        signs = {s["sign_id"]: s for s in doc["signs"]}
        for sign in doc["signs"]:
            if sign.get("text") and sign.get("box"):
                sign_ids[sign["sign_id"]] = run.evidence("ocr_text", {k: sign.get(k) for k in
                    ("sign_id", "text", "confidence", "box", "views", "alternatives", "reread", "source",
                     "in_photographer_zone")}, stage="read", model=model)
        for item in doc["items"]:
            payload = {k: item.get(k) for k in ("item_id", "sign_id", "value", "countries", "regions", "strength",
                                               "source", "notes", "details", "readings")}
            sign = signs.get(item.get("sign_id"), {})
            if item.get("sign_id") in sign_ids:
                payload.update(text=item.get("raw", sign.get("text")), box=sign.get("box"),
                               confidence=sign.get("confidence"), ocr_evidence_id=sign_ids[item["sign_id"]])
            run.evidence(item["kind"], payload,
                         stage="read", model=model)

    doc = _cached(run, "read", file, "PP-OCRv6", log_items)
    if doc is not None:
        signs = [SimpleNamespace(sign_id=s["sign_id"], confidence=s["confidence"], text=s.get("text"),
                                 box=s.get("box")) for s in doc["signs"]]
        return SimpleNamespace(items=doc["items"], signs=signs)
    from panoloc.ocr import log_ocr, read_panorama
    engine = models.ocr()
    with run.stage("read", optional=True, model=engine.name, deadline_s=OCR_DEADLINE_S):
        result = read_panorama(pano, engine, views=views)
        log_ocr(run, result)
        doc = result.to_dict()
        _write_json(run.dir / "ocr.json", doc)
        _store(file, doc)
        return result
    return None  # the stage failed and was logged


def vlm_plugin():
    """The optional VLM plugin module (VLM_PLUGIN: make_client, selected_model, claims), or None when it is
    absent or PANOLOC_VLM=local."""
    if os.environ.get("PANOLOC_VLM", "").lower() == "local":
        return None
    try:
        return importlib.import_module(VLM_PLUGIN)
    except ImportError:
        return None


def _vlm_cache_name(model):
    """Ollama models keep the original vlm.json; a plugin model gets its own file, so one model's cached answers
    never stand in for another's."""
    plugin = vlm_plugin() or _plugin_for_names()
    return f"vlm-{model}.json" if plugin and plugin.claims(model) else "vlm.json"


def _plugin_for_names():
    try:  # naming only: a plugin model keeps its own cache file even while PANOLOC_VLM=local
        return importlib.import_module(VLM_PLUGIN)
    except ImportError:
        return None


def _describe(models, path, views, run):
    def log_landmarks(doc, model):
        from panoloc.vlm import log_cached_results
        log_cached_results(run, doc, model)

    name = models.vlm_name()
    file = _cache_file(models, path, _vlm_cache_name(name))
    doc = _cached(run, "describe", file, name, log_landmarks)
    if doc is not None:
        return SimpleNamespace(landmarks=doc["landmarks"], hints=doc["hints"])
    from panoloc.vlm import VLMError, describe_panorama
    client = models.vlm()
    with run.stage("describe", optional=True, model=client.model, deadline_s=VLM_DEADLINE_S):
        try:
            result = describe_panorama(views, client, run=run)
        except VLMError as exc:  # the plugin's VLM failed (network, rate limit, refusal): the panorama again locally
            local = models.vlm_local()
            if local is client:
                raise
            run.evidence("vlm_fallback", {"from_model": client.model, "to_model": local.model,
                                          "error": type(exc).__name__,
                                          "observation": f"{client.model} failed, every view asked again on "
                                                         f"{local.model}: {exc}"[:300]},
                         stage="describe", model=local.model)
            file = _cache_file(models, path, _vlm_cache_name(local.model))
            result = describe_panorama(views, local, run=run)
        doc = result.to_dict(raw=False)
        _write_json(run.dir / "vlm.json", doc)
        if not result.partial:
            _store(file, doc)
        return result
    return None


def _reason(models, path, pano, ocr, vlm, clues, hints, run):
    """Place reasoning (panoloc.reason): the reply dict, or None when it is off, unavailable or failed."""
    if not REASON:
        return None  # off: no stage, no event, so runs match the measured configuration
    from panoloc import reason
    from panoloc.vlm import VLMError
    name = models.vlm_name()  # without building the client: a cached answer loads no model
    plugin = vlm_plugin()
    local = not (plugin and plugin.claims(name))
    if local and not REASON_LOCAL:
        run.skip_stage("reason", "place reasoning is off for the local VLM (pipeline.REASON_LOCAL)")
        return None
    file = _cache_file(models, path, reason.cache_name(name, local))
    doc = _cached(run, "reason", file, name, lambda d, m: _log_reasoning(run, d, m))
    if doc is not None:
        return doc
    client = models.vlm()
    context = reason.build_context(filename=Path(path).name, ocr=ocr, vlm=vlm, clues=clues, hints=hints,
                                   zones=models.zones())
    with run.stage("reason", optional=True, model=client.model, deadline_s=reason.TIMEOUT_S * 2):
        try:
            doc = reason.reason_place(client, pano, context, signs=getattr(ocr, "signs", []) if ocr else [])
        except VLMError as exc:
            run.evidence("reason_failed", {"observation": f"place reasoning failed: {exc}"[:300]}, stage="reason",
                         model=client.model)
            return None
        _log_reasoning(run, doc, client.model)
        _write_json(run.dir / "reason.json", doc)
        _store(file, doc)
        return doc
    return None


def _apply_reasoning(clues, doc, run):
    """OCR name clues the reasoning ruled out are dropped (a panel depicting another town, a brand); its places
    are added as VLM landmark clues, looked up near the municipality it gives."""
    from panoloc import reason
    from panoloc.names import NameIndex
    bad = reason.misleading_keys(doc)
    kept = [c for c in clues if not (c.kind == "ocr_name" and reason.is_misleading(c.text, bad))]
    if len(kept) < len(clues):
        run.evidence("ocr_dropped", {"observation": "OCR names the place reasoning ruled out: " + ", ".join(
            c.text for c in clues if c not in kept)}, stage="names", actor="agent")
    with NameIndex.open() as names:
        added = reason.clues_from_reasoning(doc, names)
    run.evidence("reasoning_clues", {"observation": f"{len(added)} clues from place reasoning", "clues": [
        {"clue_id": c.clue_id, "text": c.text, "reliability": round(c.reliability, 3), "candidates": len(c.candidates),
         "best": c.candidates[0].label if c.candidates else None} for c in added]}, stage="names", actor="agent")
    return kept + added


def _refine(models, pano, fused, reasoned, run):
    """The plugin's refine step under a hard wall-time cap: a second Output, or None (the first output stands)."""
    import threading
    from panoloc.scoring import haversine_m
    plugin = vlm_plugin()
    name = models.vlm_name()
    if not (REFINE and models.use["vlm"]):
        return None
    if plugin is not None and plugin.claims(name):
        if not hasattr(plugin, "refine"):
            return None
        step = plugin.refine
    elif REFINE_LOCAL:
        from panoloc import locate
        step = locate.refine_run
    else:
        return None
    stop, box = threading.Event(), {}

    def log(payload):
        if not stop.is_set():
            run.evidence("refine_tool", payload, stage="refine", model=name)

    def work():
        try:
            box["result"] = step(models, pano, fused, reasoned, log)
        except Exception as exc:  # reported below; the first output stands
            box["error"] = exc

    def keep(why):
        run.evidence("refine_skipped", {"observation": f"refine: {why}; the first output stands"[:300]},
                     stage="refine", actor="agent")

    with run.stage("refine", optional=True, model=name, deadline_s=REFINE_DEADLINE_S):
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(REFINE_DEADLINE_S)
        stop.set()
        if worker.is_alive():
            return keep(f"no answer within {REFINE_DEADLINE_S:.0f} s")
        if "error" in box:
            return keep(f"failed: {type(box['error']).__name__}: {box['error']}")
        r = box.get("result")
        if not r:
            return keep("no position submitted")
        conf, method = r.get("confidence", "low"), r.get("method", "")
        moved = haversine_m((fused.output.lat, fused.output.lng), (r["lat"], r["lng"]))
        out = Output(r["lat"], r["lng"], "coarse_candidate", "camera", [f"refine:{conf}"] + list(fused.output.sources[:3]),
                     REFINE_UNCERTAINTY_M.get(conf, 100.0), "source_estimate",
                     f"refined camera position ({conf}: {method}); {moved:.0f} m from the first output")
        run.evidence("refined_position", {"observation": out.note, "confidence": conf, "method": method,
                                          "moved_m": round(moved, 1), "steps": r.get("steps"),
                                          "elapsed_s": r.get("elapsed_s")}, stage="refine", actor="agent")
        return out
    return None


def _log_reasoning(run, doc, model):
    run.evidence("place_reasoning", {
        "observation": "; ".join(f"{p['name']} ({p.get('municipality')}, {p['country']}) p={p['probability']:.2f}"
                                 for p in doc.get("places") or []) or "no place named",
        "places": doc.get("places"), "camera_street": doc.get("camera_street"),
        "misleading_texts": doc.get("misleading_texts"), "country": doc.get("country"),
        "timing": doc.get("timing")}, stage="reason", model=model)


def _short(cands, n=3):
    return ", ".join(f"{c.country} {c.details.get('region') or c.label}".strip() for c in cands[:n])


def _candidates(doc, key):
    return [Candidate(**c) for c in doc[key]]


def _retrieve(models, path, pano, run):
    """kNN neighbours and region-head areas from the panorama's own views (12 x 60 degrees, as measured)."""
    from panoloc import retrieval
    clues, embedded = [], None
    file = _cache_file(models, path, "retrieval.json")
    with run.stage("retrieve", optional=True, model="PE-Core-L-14-336"):
        if file is not None and file.is_file():
            doc = json.loads(file.read_text(encoding="utf-8"))
            knn, regions = _candidates(doc, "knn"), _candidates(doc, "region_head")
            run.evidence("perception_cache", {"file": str(file), "observation": "retrieve: reused retrieval.json from "
                                              "the perception cache (same image file)"}, stage="retrieve", actor="agent")
        else:
            pecore, bank, head = models.retrieval()
            embeddings, names = retrieval.embed_views(pecore, pano)
            embedded = (embeddings, names)
            knn = bank.search(embeddings, k=KNN_K, view_names=names)
            regions = head.candidates(embeddings, k=REGION_HEAD_K)
            _store(file, {"knn": [c.to_dict() for c in knn], "region_head": [c.to_dict() for c in regions],
                          "embed_version": retrieval.EMBED_VERSION, "k": KNN_K})
        run.evidence("knn", {"neighbours": [c.to_dict() for c in knn[:10]], "count": len(knn),
                             "observation": f"{len(knn)} photo-bank neighbour groups; top: {_short(knn)}"},
                     stage="retrieve", model="PE-Core-L-14-336")
        clues.append(fusion.Clue("knn", "knn", "pe-core", KNN_RELIABILITY, knn, scale=None, text="PE-Core kNN"))
        run.evidence("region_head", {"regions": [c.to_dict() for c in regions],
                                     "observation": f"region head: {_short(regions, REGION_HEAD_K)}"},
                     stage="retrieve", model="PE-Core region head")
        clues.append(fusion.Clue("region_head", "region_head", "pe-core", REGION_HEAD_RELIABILITY, regions,
                                 scale=None, text="PE-Core region head"))
    return clues, embedded


def _landmarks(models, path, pano, views, run, embedded=None):
    """Commons landmark hits, the top ones checked geometrically against the 8 horizontal 90-degree views."""
    from panoloc import retrieval
    file = _cache_file(models, path, "landmarks.json")
    with run.stage("landmarks", optional=True, model="Commons gallery + ALIKED/LightGlue"):
        if file is not None and file.is_file():
            checked = _candidates(json.loads(file.read_text(encoding="utf-8")), "candidates")
            run.evidence("perception_cache", {"file": str(file), "observation": "landmarks: reused landmarks.json "
                                              "from the perception cache (same image file)"}, stage="landmarks",
                         actor="agent")
        else:
            gallery = models.landmarks()
            if embedded is None:
                pecore, _, _ = models.retrieval()
                embedded = retrieval.embed_views(pecore, pano)
            found = gallery.search(embedded[0], k=LANDMARK_K, view_names=embedded[1])
            horizontal = [v for v in views if v.name.startswith("h")]
            checked = models.verifier().verify(horizontal, found, gallery.photo_path, top=VERIFY_TOP) if found else []
            _store(file, {"candidates": [c.to_dict() for c in checked], "k": LANDMARK_K, "top": VERIFY_TOP})
        verified = [c for c in checked if (c.details or {}).get("verified_match")]
        run.evidence("landmark_gallery", {
            "candidates": [{"label": c.label, "source": c.source, "weight": round(c.weight, 4),
                            "verified_match": bool((c.details or {}).get("verified_match")),
                            "inliers": (c.details or {}).get("inliers")} for c in checked],
            "observation": f"{len(checked)} gallery landmark hits, {len(verified)} verified"
                           + (": " + ", ".join(c.label for c in verified) if verified else "")},
            stage="landmarks", model="Commons gallery + ALIKED/LightGlue")
        clues = []
        if checked and LANDMARK_RELIABILITY > 0:
            clues.append(fusion.Clue("landmark_gallery", "landmark_gallery", "pe-core", LANDMARK_RELIABILITY, checked,
                                     scale=None, text="Commons landmark gallery"))
        if verified:
            clues.append(fusion.Clue("landmark_verified", "landmark_verified", "verified", VERIFIED_RELIABILITY,
                                     verified, scale=None, text="geometrically verified landmark"))
        return clues
    return []


def _geoclip(models, path, pano, run):
    file = _cache_file(models, path, "geoclip.json")
    with run.stage("geoclip", optional=True, model="GeoCLIP"):
        if file is not None and file.is_file():
            cands = _candidates(json.loads(file.read_text(encoding="utf-8")), "candidates")
            run.evidence("perception_cache", {"file": str(file), "observation": "geoclip: reused geoclip.json from "
                                              "the perception cache (same image file)"}, stage="geoclip", actor="agent")
        else:
            cands = models.geoclip().candidates(pano, k=GEOCLIP_K)
            _store(file, {"candidates": [c.to_dict() for c in cands], "k": GEOCLIP_K})
        run.evidence("geoclip", {"candidates": [c.to_dict() for c in cands],
                                 "observation": f"GeoCLIP: {_short(cands)}"}, stage="geoclip", model="GeoCLIP")
        return [fusion.Clue("geoclip", "geoclip", "geoclip", GEOCLIP_RELIABILITY, cands, scale=None, text="GeoCLIP")]
    return []


def _clues(ocr, vlm, run):
    from panoloc.names import NameIndex
    clues, hints = [], []
    if ocr is not None:
        hints += fusion.hints_from_ocr(ocr.items)
    if vlm is not None:
        hints += fusion.hints_from_vlm(vlm.hints)
    countries = fusion.confident_countries(fusion.country_prior(hints))
    with run.stage("names", optional=True, model="name index"):
        with NameIndex.open() as names:
            if ocr is not None:
                clues += fusion.clues_from_ocr(ocr.items, names, {s.sign_id: s.confidence for s in ocr.signs},
                                               countries=countries)
            if vlm is not None:
                clues += fusion.clues_from_vlm(vlm.landmarks, vlm.hints, names, countries=countries)
            osm = [{k: o.get(k) for k in ("country", "extract_timestamp")} for o in getattr(names, "osm", [])]
        run.evidence("name_lookups", {"clues": [{"clue_id": c.clue_id, "kind": c.kind, "group": c.group,
                                                 "text": c.text, "reliability": round(c.reliability, 3),
                                                 "candidates": len(c.candidates),
                                                 "best": c.candidates[0].label if c.candidates else None}
                                                for c in clues],
                                      "names_osm": osm, "lookup_countries": countries,
                                      "observation": f"{len(clues)} clues from names, postcodes and regions"
                                                     + (f"; name lookups limited to {countries[0]}" if countries else "")},
                     stage="names", actor="agent")
    return clues, hints


def _in_area(h, zones):
    """True when h lies in Portugal, Spain or France: inside (or within 1 km of) a named zone, else the
    allowed bounding box when the zone index is missing. Outside points are never offered as outputs."""
    if zones is not None:
        return zones.locate(h.lat, h.lng) is not None
    return questions.ALLOWED_AREA.contains(h.point)


def _consistent(h, answers, zones=None):
    """True when hypothesis h lies in the allowed area and in every option the team picked
    (answers: [(question, option_id)]). option_for maps an outside point to the nearest option, so the
    area check comes first (T79 recheck: a Sicilian point passed as "France")."""
    return _in_area(h, zones) and all(q.option_for(h).id == q.option(option_id).id for q, option_id in answers)


def _point_fitting_answers(hypotheses, answers, zones):
    """An area Candidate inside the intersection of every answered option, on land (cells.constrain), or None.

    Bases, in order: the zones around the heaviest hypotheses from the smallest up (parish, municipality,
    district: never a whole country, which takes seconds to clip), then the latest answered place disc or
    named zone. Its representative point is allowed by every answer; extent_m is its bound (T79:
    with correct answers a consistent point always exists even when no hypothesis is one)."""
    if cells is None:
        return None
    bases, seen = [], set()

    def add(key, make):
        if key not in seen:
            seen.add(key)
            bases.append(make)

    # Nearest the evidence first: the zones around the heaviest hypotheses, smallest up (never a whole
    # country); then the answered options themselves (warm-up 779, D2: "Portugal" minus the excluded
    # districts put the point on Madeira, 963 km off, while a hypothesis 9.7 km from the camera was in reach)
    if zones is not None:
        for h in sorted(hypotheses, key=lambda h: h.weight, reverse=True)[:POINT_BASE_HYPOTHESES]:
            loc = zones.locate(h.lat, h.lng)
            for z in (reversed(loc.chain[1:]) if loc is not None else ()):  # leaf first
                add(z.id, lambda z=z.id: cells.Scope.from_zone(zones, z))
    for q, option_id in reversed(answers):
        o = q.option(option_id)
        if o.complement:
            continue
        if getattr(o, "zone_id", None) and zones is not None:
            add(o.zone_id, lambda z=o.zone_id: cells.Scope.from_zone(zones, z))
        elif o.point is not None and getattr(o, "radius_m", None):
            add((o.point["lat"], o.point["lng"]), lambda o=o: cells.Scope.disc(o.point["lat"], o.point["lng"], o.radius_m))
    for make in bases:
        try:
            scope = cells.constrain(make(), list(answers), zones=zones)
            if scope is None:
                continue
            lat, lng, bound = scope.rep
            return Candidate(lat, lng, "area", f"answers:{scope.scope_id}", label="Inside every answered area",
                             weight=1e-9, extent_m=max(float(bound), 1.0),
                             details={"extent_source": "geometric_bound", "built_from_answers": len(answers)})
        except Exception:  # an unbuildable base: try the next one
            continue
    return None


def _select_and_log(run, hypotheses, *, category, urban_probability, note, answers=(), zones=None):
    """Re-select after an answer. The soft weights still score every point, but only hypotheses consistent
    with every answered option are offered as the output (T79: 2.6% of answers were followed by an output
    outside the chosen option). With none consistent, the last chosen option's own area point stands in;
    failing that (a complement with nothing outside it), the unrestricted choice, noted in the log."""
    allowed = [_consistent(h, answers, zones) for h in hypotheses]
    if not any(allowed) and ANSWER_SLACK and len(answers) >= 2:
        # one answer may be wrong: hypotheses fitting every answer but one (the team's error rate is not zero)
        slack = [any(_consistent(h, answers[:i] + answers[i + 1:], zones) for i in range(len(answers)))
                 for h in hypotheses]
        if any(slack):
            allowed = slack
            note += "; no hypothesis fits every answer: one that fits all answers but one"
    if not any(allowed) and answers:
        built = _point_fitting_answers(hypotheses, answers, zones)
        if built is not None and _consistent(built, answers, zones):
            hypotheses = [*hypotheses, built]
            allowed = [False] * (len(hypotheses) - 1) + [True]
            note += "; no hypothesis fits every answer: a point built inside every answered area"
    if not any(allowed):
        # Stand-ins: the answered options' own area points, latest first, kept only if they fit every answer
        stand_ins = []
        for q, option_id in reversed(answers):
            try:
                c = questions.area_candidate(q.option(option_id), weight=1e-9)
            except ValueError:
                continue
            if _consistent(c, answers, zones):
                stand_ins.append(c)
        if stand_ins:
            hypotheses = [*hypotheses, stand_ins[0]]
            allowed = [False] * (len(hypotheses) - 1) + [True]
            note += "; no hypothesis fits every answer: an answered option's representative point"
        else:
            allowed = None
            note += "; nothing fits every answer: unrestricted choice"
    selection = fusion.select(hypotheses, category=category, urban_probability=urban_probability, allowed=allowed)
    output = fusion.make_output(hypotheses[selection["index"]], selection, note)
    output.log(run)
    return output, selection


def _next_question(hypotheses, kind, *, category, urban_probability, zones=None, zone_scope=None, zone_exclude=()):
    if kind == "place":
        supported = [h for h in hypotheses if h.weight > 0]
        if len(questions.distinct(supported, PLACE_SEPARATION_M)) < 2:
            return None, None
        q = questions.place_question(hypotheses, min_separation_m=PLACE_SEPARATION_M)
    elif zones is not None:
        try:  # named zones; chained, the scope is the zone an earlier answer picked
            q = questions.region_question(hypotheses, zones, scope=zone_scope, exclude=zone_exclude)
        except ValueError:  # the scope is a parish (a leaf), or nothing is left in it: box cells inside it (T42)
            box = zones.get(zone_scope).bbox if zone_scope else None
            q = questions.zone_question(hypotheses, scope=questions.Box(*box) if box else None)
    else:
        q = questions.zone_question(hypotheses)
    gain = questions.expected_gain(hypotheses, q, category=category, answer_accuracy=ANSWER_ACCURACY,
                                   urban_probability=None if category else urban_probability)
    return q, gain


def readable_labels(hypotheses, zones):
    """Copies with a checkable label: generator points get their source kind and the zones holding them
    ("Photo-bank match in Arroios, Lisboa (PT)"), and places sharing a label get their zones appended
    ("Serra (Tomar, Santarém)": warm-up 064 offered "Serra / Serra / Serra")."""
    if zones is None:
        return hypotheses

    def place_of(h, coarse=False):
        """'parish, municipality' (coarse: 'municipality, district'), short names where the index has them."""
        loc = zones.locate(h.lat, h.lng)
        if loc is None:
            return None, None
        chain = loc.chain[1:3] if coarse else loc.chain[1:]
        names = [z.short_name or z.name for z in chain][::-1]
        return ", ".join(dict.fromkeys(names[:2])) or loc.chain[0].name, loc.chain[0].country

    out = []
    for h in hypotheses:
        kind = UNNAMED_SOURCES.get(h.source.split(":", 1)[0])
        place, country = place_of(h) if kind else (None, None)
        if place is not None:
            h = Candidate(**{**h.to_dict(), "label": f"{kind} in {place} ({h.country or country})",
                             "details": {**(h.details or {}), "generator_label": h.label}})
        out.append(h)
    counts = {}
    for h in out[:LABEL_CHECK_TOP]:
        counts[h.label] = counts.get(h.label, 0) + 1
    for i, h in enumerate(out[:LABEL_CHECK_TOP]):
        if h.label and counts[h.label] > 1:
            place, _ = place_of(h, coarse=True)
            if place is not None:
                out[i] = Candidate(**{**h.to_dict(), "label": f"{h.label} ({place})",
                                      "details": {**(h.details or {}), "plain_label": h.label}})
    return out


def _pose(run, q, operator, print_fn):
    """Ask one question: log it, get the operator's option ID, log the answer or the skip (None)."""
    if operator == "ask":
        option = questions.ask_operator(run, q, print_fn=print_fn)
        return option.id if option else None
    q.question_id = run.ask(q.text, q.option_dicts(), kind=q.kind, **q.log_details())
    option_id = None if operator == "skip" else operator(q)
    if option_id is None:
        run.skip(q.question_id)
    else:
        run.answer(q.question_id, option_id)
    return option_id


def _recoverable(hypotheses, pool, answers, zones):
    """Hypotheses outside `pool` that break exactly one answer and keep RECOVERY_SHARE of the soft weight."""
    total = sum(h.weight for h in hypotheses) or 1.0
    taken = {id(h) for h in pool}
    out = []
    for h in hypotheses:
        if id(h) in taken or h.weight / total < RECOVERY_SHARE or not _in_area(h, zones):
            continue
        if RECOVERY_EVIDENCE and not _strong_evidence(h):
            continue  # generator guesses (photo bank, GeoCLIP) can't overrule the team (val_130: -125 nominal)
        broken = sum(q.option_for(h).id != q.option(o).id for q, o in answers)
        if broken == 1:
            out.append(h)
    return out


def _strong_evidence(h):
    """A verified landmark match, or a hypothesis whose own fusion weight comes from an OCR clue."""
    d = h.details or {}
    f = d.get("fusion") or {}
    if d.get("verified_match") or f.get("group") == "verified":
        return True
    return str(f.get("group", "")).startswith("ocr:") and (f.get("own") or 0) >= RECOVERY_MIN_OWN


def _latest_wins(run, hypotheses, answers, zones):
    """If no hypothesis fits every answer but some fit the latest one with one earlier answer dropped, drop
    that earlier answer (the most recent such) and log it: the team corrected itself."""
    if len(answers) < 2 or any(_consistent(h, answers, zones) for h in hypotheses):
        return answers
    if _point_fitting_answers(hypotheses, answers, zones) is not None:
        return answers  # the answers agree; only the candidates are missing there (val_130: 31 of 31 nominal
        # overrides had dropped a correct answer this way)
    latest = answers[-1]
    for i in range(len(answers) - 2, -1, -1):
        rest = answers[:i] + answers[i + 1:]
        if any(_consistent(h, rest, zones) for h in hypotheses):
            q, o = answers[i]
            run.evidence("answer_overridden", {"question_id": getattr(q, "question_id", None), "option_id": o,
                                               "by": getattr(latest[0], "question_id", None),
                                               "observation": f"answer {o} to {getattr(q, 'question_id', '?')} is dropped: "
                                                              "the latest answer contradicts it"},
                         stage="ask", actor="agent")
            return rest
    return answers


def _signature(q):
    """What makes two questions the same for the team: kind and option labels."""
    return (q.kind, tuple(o.label for o in q.options))


def _accepts(fn, name):
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _constrained(fn, *args, answers=(), **kwargs):
    """Call a cells function with constraints=[(question, option_id), ...] (every answer so far, in order)
    when it accepts that parameter (T42 clipping to earlier answers); without it, as before."""
    if answers and _accepts(fn, "constraints"):
        kwargs["constraints"] = list(answers)
    return fn(*args, **kwargs)


def _start_route(run, hypotheses, scope, why, *, category, urban_probability, urban_auto=False, answers=(),
                 zones=None):
    """A cells.CellRoute over `scope`, logged (T42). With urban_auto, P(urban) is estimated again from the
    current hypotheses: after an answer, the place or zone the team picked carries most of their weight."""
    if urban_auto and category is None and ROUTE_URBAN_REESTIMATE:
        estimate, _ = urban.urban_probability(hypotheses)
        urban_probability = estimate if estimate is not None else urban_probability
    extra = {"zones": zones} if zones is not None and _accepts(cells.CellRoute.start, "zones") else {}
    if _accepts(cells.CellRoute.start, "answer_accuracy"):
        extra["answer_accuracy"] = ANSWER_ACCURACY
    route = _constrained(cells.CellRoute.start, hypotheses, scope, answers=answers, category=category, **extra,
                                  urban_probability=None if category else urban_probability)
    run.evidence("cell_route", {"observation": f"cell route starts: {why}", "scope": scope.to_dict(),
                                "target_bound_m": cells.target_bound_m(category),
                                "urban_probability": None if category else round(urban_probability, 4)},
                 stage="ask", actor="agent")
    return route


def _cell_questions(run, route, operator, *, budget, min_gain, print_fn, outputs, answers=None):
    """Cell questions until the route's target bound, the gain gate, a skip, the budget, or an answer
    outside its root. Every answer logs a geographic_cell output (cells.log_cell_output) and joins
    `answers`, so later re-selections and routes respect it too (T79: an "Outside this area" cell answer
    was ignored by a later zone re-selection)."""
    answered, retries = 0, CELL_SKIP_RETRIES
    while answered < budget and route.scope is not None and not route.done():
        q = route.question()
        gain = route.gain(q)
        if not gain["gain"] > min_gain:
            break
        q.details["expected_gain"] = {**gain, "min_gain": min_gain}
        option_id = _pose(run, q, operator, print_fn)
        if option_id is None:
            if retries > 0:  # a fixed schedule: the same question once more; nothing is inferred from the skip
                retries -= 1
                continue
            break  # a skip changes nothing; the route stays where it is
        if answers is not None:
            answers.append((q, option_id))
        route = route.answer(q, option_id)
        answered += 1
        out = route.output(note=f"after answer {option_id} to {q.question_id}")
        if out is not None:
            cells.log_cell_output(run, out, route)
            outputs.append(out)
    return route, answered


def _ask_loop(run, hypotheses, operator, *, category, urban_probability, max_questions, ask_anyway, print_fn,
              zones=None, min_gain=questions.BREAK_EVEN, max_cell_questions=MAX_CELL_QUESTIONS, urban_auto=False,
              outputs=None, state=None):
    """Ask while a question is worth its cost; appends each new output to `outputs` as it is logged and returns
    (hypotheses, outputs). urban_auto: re-estimate P(urban) from the current hypotheses when a cell route starts."""
    hypotheses = readable_labels(hypotheses, zones)
    outputs = [] if outputs is None else outputs
    asked, schedule = 0, list(QUESTION_SCHEDULE)
    answers = []  # (question, option_id) of every answered place, zone or cell question: outputs must fit them all
    posed = set()  # signatures of the place and zone questions already put to the team
    if state is not None:
        state.update(answers=answers, posed=posed)
    place_misses = 0  # consecutive place questions answered "None of these"
    main_retries = MAIN_SKIP_RETRIES
    zone_scope, zone_exclude = None, []  # chained zone questions: the zone answered so far, zones ruled out
    route, cell_answers = None, 0  # T42: the cell route, while one runs
    if cells is not None:  # a dominant landmark or area: cells around it before anything else
        scope, why = _constrained(cells.route_scope, hypotheses, answers=answers)
        if scope is not None:
            route = _start_route(run, hypotheses, scope, why, category=category, urban_probability=urban_probability,
                                 urban_auto=urban_auto, answers=answers, zones=zones)
    while True:
        if route is not None:
            route, n = _cell_questions(run, route, operator, budget=max_cell_questions - cell_answers,
                                       min_gain=min_gain, print_fn=print_fn, outputs=outputs, answers=answers)
            cell_answers += n
            if route.answered:  # the route moved: its beliefs, and its cell output if it has one, stand
                hypotheses = normalise(route.exit_hypotheses())
                hypotheses.sort(key=lambda h: h.weight, reverse=True)
                run.candidates([{"candidate_id": f"h{i}", **h.to_dict()} for i, h in enumerate(hypotheses[:50], 1)],
                               stage="ask")
                if route.scope is not None:
                    break  # target bound reached, not worth another x0.95, a skip, or the budget
                # "Outside this area" at the root: the camera is not there. Back to zone and place questions
                if route.root.zone_id is not None and zones is not None:
                    zone_exclude = sorted({*zone_exclude, route.root.zone_id})
                    above = zones.parent(route.root.zone_id)
                    zone_scope = above.id if above is not None else None
                schedule = ["zone", "place"]
            route = None  # no cell question was worth asking: the loop goes on as without the route
        if not (asked < max_questions and schedule):
            break
        # Every kind still in the schedule is built; the one with the best expected gain is asked (app batch
        # T26: a fixed place-then-zone order spent every other answer on a missing place question)
        built = []
        # Questions are built and judged on the hypotheses every answer so far allows (warm-up 779, D2: places
        # ruled out by "None of these" or "Elsewhere" were offered again); with fewer than two, on all of them
        pool = [h for h in hypotheses if _consistent(h, answers, zones)] if answers else hypotheses
        if RECOVERY and answers:
            pool += _recoverable(hypotheses, pool, answers, zones)
        few = len(pool) < 2  # too few allowed places to offer: zone questions only (they carry their exclusions)
        pool = hypotheses if few else pool
        for kind in schedule:
            if kind == "place" and (place_misses >= MAX_PLACE_MISSES or few):
                continue  # the place lists keep missing, or none is left: narrow the area with zones first
            q, gain = _next_question(pool, kind, category=category, urban_probability=urban_probability,
                                     zones=zones, zone_scope=zone_scope, zone_exclude=zone_exclude)
            if q is not None and _signature(q) not in posed:  # never the same question twice in a run
                built.append((gain["gain"], kind, q, gain))
        if not built:
            break
        _, kind, q, gain = max(built, key=lambda b: b[0])
        schedule.remove(kind)  # a skip moves on to the other kinds; an answer resets the schedule
        posed.add(_signature(q))
        forced = ask_anyway and asked == 0
        worth = gain["gain"] > min_gain
        if not (worth or forced):
            break  # the best question isn't worth its x0.95, so none is
        q.details["expected_gain"] = {**gain, "min_gain": min_gain}
        if forced and not worth:
            q.details["asked_below_break_even"] = True
        asked += 1
        option_id = _pose(run, q, operator, print_fn)
        if option_id is None:
            if main_retries > 0:  # a fixed schedule: the question may come back; nothing is inferred from the skip
                main_retries -= 1
                posed.discard(_signature(q))
                schedule = list(dict.fromkeys([*schedule, kind]))
                asked -= 1  # a skipped question costs nothing, so it doesn't use up the cap either
            continue  # a skip changes nothing; the schedule moves on
        answers.append((q, option_id))
        if RECOVERY:
            answers[:] = _latest_wins(run, hypotheses, answers, zones)
        missed = q.option(option_id).complement
        place_misses = place_misses + 1 if (q.kind == "place" and missed) else (place_misses if missed else 0)
        hypotheses = normalise(questions.apply_answer(hypotheses, q, option_id, answer_accuracy=ANSWER_ACCURACY))
        if isinstance(q, questions.RegionQuestion):
            before = list(zone_exclude)
            zone_scope, zone_exclude = questions.region_chain(q, option_id, zone_scope, zone_exclude)
            if zone_scope is not None and zones is not None:  # region_chain starts a picked zone with nothing
                # excluded; zones ruled out earlier that lie inside it stay out (warm-up 779, D2: Porto and Leiria,
                # ruled out by "Elsewhere", came back after "Portugal")
                zone_exclude = sorted({*zone_exclude, *(z for z in before if z != zone_scope
                                                        and zones.is_within(z, zone_scope))})
            chosen = q.option(option_id)
            if not chosen.complement and all(s.startswith("zone:") for s in chosen.covers):
                # no real hypothesis in the zone picked: spread its weight over its subzones (T42: cells)
                inside = [h for h in hypotheses if h.source in chosen.covers]
                weight = sum(h.weight for h in inside) or 1.0
                hypotheses = normalise([h for h in hypotheses if h.source not in chosen.covers]
                                       + zones.spread(chosen.zone_id, weight=weight))
            if cells is not None and not chosen.complement:  # T42: a leaf, or a zone no hypothesis is in: cells
                scope, why = _constrained(cells.route_scope, hypotheses, answers=answers, zones=zones,
                                          zone_scope=chosen.zone_id)
                if scope is not None:
                    route = _start_route(run, hypotheses, scope, why, category=category,
                                         urban_probability=urban_probability, urban_auto=urban_auto,
                                         answers=answers, zones=zones)
        elif q.kind == "place" and cells is not None and not q.option(option_id).complement:
            scope, why = _constrained(cells.route_scope, hypotheses, answers=answers, place_question=q,
                                      place_option_id=option_id, **({"zones": zones} if zones is not None else {}))
            if scope is not None:  # T42: the team picked a place; cells around its landmark or area
                route = _start_route(run, hypotheses, scope, why, category=category, urban_probability=urban_probability,
                                     urban_auto=urban_auto, answers=answers, zones=zones)
        if REDOMINANCE and route is None and cells is not None and not q.option(option_id).complement:
            # An answer that started no route (a district, a region) can still leave one hypothesis dominant:
            # the same check as before the first question (warm-up 319, D2: "Distrito de Lisboa", then a stop
            # at 87 m where a place pick had led to cells and 15 m)
            scope, why = _constrained(cells.route_scope, hypotheses, answers=answers)
            if scope is not None:
                route = _start_route(run, hypotheses, scope, why, category=category, urban_probability=urban_probability,
                                     urban_auto=urban_auto, answers=answers, zones=zones)
        hypotheses.sort(key=lambda h: h.weight, reverse=True)
        run.candidates([{"candidate_id": f"h{i}", **h.to_dict()} for i, h in enumerate(hypotheses[:50], 1)],
                       stage="ask")
        output, _ = _select_and_log(run, hypotheses, category=category, urban_probability=urban_probability,
                                    note=f"after answer {option_id} to {q.question_id}", answers=answers,
                                    zones=zones)
        outputs.append(output)
        schedule = list(QUESTION_SCHEDULE)  # an answer changed the beliefs: the schedule starts again
        if q.option(option_id).complement:
            schedule = ["zone", "place"]  # the options missed: the zone fallback comes first (PLAN.md 3.4)
    if state is not None:
        state.update(zone_scope=zone_scope, zone_exclude=zone_exclude)
    return hypotheses, outputs


def run_panorama(path, models=None, *, runs_dir="runs", operator="never", category=None, category_source=None,
                 special_one=False, urban_probability=None, max_questions=None,
                 ask_anyway=False, min_gain=None, print_fn=print, on_event=None, run_id=None, max_cell_questions=None):
    """Solve one panorama alone; returns a PanoramaResult. The run log is finished (log.json) on return.

    on_event(event) is called with every event as it is logged (panoloc.runlog.Run), e.g. for the console;
    run_id names the run (default: a fresh one from Run).
    """
    if not (operator in ("never", "ask", "skip") or callable(operator)):
        raise ValueError("operator must be 'never', 'ask', 'skip' or a callable")
    models = models or Models()
    path = Path(path)
    if category is not None and category_source is None:
        category_source = "inferred"
    run = Run(path.name, runs_dir, special_one=special_one, category=category, category_source=category_source,
              versions=models.versions(), on_event=on_event, run_id=run_id)
    t0 = time.perf_counter()
    timings = {}
    try:
        with run.stage("prepare"):
            name = parse_filename(path.name)
            pano = load_panorama(path)
            views = cut_views(pano)
            run.evidence("filename", {"valid": name.valid, "timestamp_utc": name.timestamp.isoformat()
                                      if getattr(name, "timestamp", None) else None,
                                      "yaw_convention": "yaw 0 = centre column of the equirectangular image, "
                                                        "increasing to the right (panoloc.views); heading unknown",
                                      "observation": f"filename {'parsed' if name.valid else 'not in the camera pattern'}"},
                         stage="prepare", actor="agent")
        timings["prepare_s"] = round(time.perf_counter() - t0, 2)

        ocr = vlm = None
        with ThreadPoolExecutor(max_workers=2) as pool:  # OCR on the CPU, the VLM on the GPU
            f_ocr = pool.submit(_read, models, path, pano, views, run) if models.use["ocr"] else None
            f_vlm = pool.submit(_describe, models, path, views, run) if models.use["vlm"] else None
            ocr = f_ocr.result() if f_ocr else None
            vlm = f_vlm.result() if f_vlm else None
        if not models.use["ocr"]:
            run.skip_stage("read", "disabled for this run")
        if not models.use["vlm"]:
            run.skip_stage("describe", "disabled for this run")
        timings["perception_s"] = round(time.perf_counter() - t0, 2)

        clues = []
        if models.use["retrieval"]:
            found, embedded = _retrieve(models, path, pano, run)
            clues += found
            clues += _geoclip(models, path, pano, run)
            if models.use["landmarks"]:
                clues += _landmarks(models, path, pano, views, run, embedded)
            else:
                run.skip_stage("landmarks", "disabled for this run")
        else:
            for stage in ("retrieve", "geoclip", "landmarks"):
                run.skip_stage(stage, "disabled for this run")
        name_clues, hints = _clues(ocr, vlm, run)
        clues += name_clues
        review_clues = list(clues)  # replace a self-check's VLM clue group, never count repeated reasoning twice
        reasoned = None
        if models.use["vlm"]:
            reasoned = _reason(models, path, pano, ocr, vlm, clues, hints, run)
            if reasoned:
                clues = _apply_reasoning(clues, reasoned, run)
        timings["clues_s"] = round(time.perf_counter() - t0, 2)

        cat = run.category["value"]
        with run.stage("fuse"):
            urban_auto = cat is None and urban_probability is None
            fixed = urban_probability if urban_probability is not None else fusion.DEFAULT_URBAN_PROBABILITY
            fused = fusion.fuse(clues, hints, category=cat, urban_probability=fixed)
            zones = models.zones()
            in_area = [_in_area(h, zones) for h in fused.hypotheses]
            reselect = not all(in_area)  # a Sicilian Commons hit or a Geneva GeoCLIP point is never an output
            if cat is None and urban_probability is None:
                estimate, detail = urban.urban_probability(fused.hypotheses)
                urban_probability = estimate if estimate is not None else fixed
                reselect = reselect or estimate is not None
            if reselect:
                fused.selection = fusion.select(fused.hypotheses, category=cat,
                                                urban_probability=None if cat else urban_probability,
                                                allowed=in_area if any(in_area) else None)
                fused.output = fusion.make_output(fused.hypotheses[fused.selection["index"]], fused.selection)
            if cat is None and urban_auto:
                run.evidence("urban_probability", {
                    "value": round(urban_probability, 4), "source": "GHSL SMOD at hypotheses" if estimate is not None
                    else "default", **detail,
                    "observation": f"category unknown: assumed P(urban) = {urban_probability:.2f}"
                                   + (f" from GHSL at the hypotheses ({detail['urban_share']:.0%} of their weight in "
                                      "urban cells)" if estimate is not None else f" (default: {detail.get('reason')})")},
                    stage="fuse", actor="agent")
            fusion.log_fusion(run, fused)
        fused.output.log(run)  # the initial answer, before any question
        timings["first_output_s"] = round(time.perf_counter() - t0, 2)
        outputs = [fused.output]
        ask_state = {}
        hypotheses = fused.hypotheses
        refined = _refine(models, pano, fused, reasoned, run)
        if refined is not None:
            refined.log(run)
            outputs.append(refined)
            timings["refined_output_s"] = round(time.perf_counter() - t0, 2)

        if operator != "never" and not (ASK_QUESTIONS or ask_anyway or min_gain is not None):
            run.skip_stage("ask", "questions are off by default (pipeline.ASK_QUESTIONS): the first output stands")
        elif operator != "never":
            with run.stage("ask", optional=True):  # a failure here is logged; the outputs so far stand
                hypotheses, _ = _ask_loop(run, fused.hypotheses, operator, category=cat, urban_probability=urban_probability,
                          max_questions=MAX_QUESTIONS if max_questions is None else max_questions,
                          ask_anyway=ask_anyway, print_fn=print_fn, zones=models.zones(),
                          min_gain=MIN_GAIN if min_gain is None else min_gain, urban_auto=urban_auto,
                          outputs=outputs, state=ask_state,
                          max_cell_questions=MAX_CELL_QUESTIONS if max_cell_questions is None else max_cell_questions)
        timings["total_s"] = round(time.perf_counter() - t0, 2)
    finally:
        log_path = run.finish()
    review_state = {"run": run, "path": path, "category": cat, "urban_probability": urban_probability,
                    "hypotheses": hypotheses, "base_clues": review_clues, "hints": hints, "ocr": ocr,
                    "vlm": vlm, "reasoned": reasoned, **ask_state}
    return PanoramaResult(run.run_id, run.dir, log_path, outputs[-1], fused, outputs, timings, review_state)


EVAL_CACHE = Path(__file__).resolve().parent.parent / "runs" / "perception"
_MODELS = {}


def _predict(key, panorama_path, runs_dir, **use):
    if key not in _MODELS:
        # Evaluation stays on the local VLM, whose answers fill the perception cache every comparison is paired on;
        # PANOLOC_VLM set to a plugin mode (anything but empty or "local") evaluates the plugin instead
        if os.environ.get("PANOLOC_VLM", "").lower() in ("", "local"):
            from panoloc.vlm import DEFAULT_MODEL as LOCAL_VLM
            use.setdefault("vlm_model", LOCAL_VLM)
        _MODELS[key] = Models(perception_cache=os.environ.get("PANOLOC_PERCEPTION_CACHE", EVAL_CACHE), **use)
    return run_panorama(panorama_path, _MODELS[key], runs_dir=runs_dir, operator="never",
                        print_fn=lambda *a: None).run_dir


def predict(panorama_path, runs_dir):
    """tools/evaluate.py hook: one autonomous run (no questions), every stage, perception cached in
    runs/perception/ (or $PANOLOC_PERCEPTION_CACHE); returns the run folder."""
    return _predict("all", panorama_path, runs_dir)


def predict_no_landmarks(panorama_path, runs_dir):
    """Every stage but the Commons landmark gallery and its verification."""
    return _predict("no_landmarks", panorama_path, runs_dir, landmarks=False)


def predict_no_retrieval(panorama_path, runs_dir):
    """The same without the photo bank: OCR, VLM, names and fusion only."""
    return _predict("no_retrieval", panorama_path, runs_dir, retrieval=False)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m panoloc.pipeline", description="Solve one panorama end to end.")
    parser.add_argument("panorama")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--operator", choices=("never", "ask", "skip"), default="ask")
    parser.add_argument("--category", choices=("urban", "non-urban"))
    parser.add_argument("--official", action="store_true", help="the category comes from the organisers")
    parser.add_argument("--urban-probability", type=float, default=None,
                        help="fix P(urban) while the category is unknown (default: from GHSL at the hypotheses)")
    parser.add_argument("--special-one", action="store_true")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--no-vlm", action="store_true")
    parser.add_argument("--no-retrieval", action="store_true")
    parser.add_argument("--vlm-model")
    parser.add_argument("--perception-cache", help="reuse and store OCR/VLM results here (evaluation only)")
    parser.add_argument("--max-questions", type=int, default=None, help="place/zone answers (default MAX_QUESTIONS)")
    parser.add_argument("--min-gain", type=float, default=None,
                        help="ask only when the expected gain exceeds this (default MIN_GAIN)")
    parser.add_argument("--ask-anyway", action="store_true",
                        help="ask the first question even below break-even (rehearsals, Gate A)")
    args = parser.parse_args(argv)
    models = Models(ocr=not args.no_ocr, vlm=not args.no_vlm, retrieval=not args.no_retrieval, vlm_model=args.vlm_model,
                    perception_cache=args.perception_cache)
    result = run_panorama(args.panorama, models, runs_dir=args.runs_dir, operator=args.operator,
                          category=args.category, category_source="official" if args.official else None,
                          special_one=args.special_one, urban_probability=args.urban_probability,
                          max_questions=args.max_questions, ask_anyway=args.ask_anyway, min_gain=args.min_gain)
    f = result.fused
    print(f"\nP(country): " + ", ".join(f"{c} {p:.0%}" for c, p in f.country.items()))
    for h in f.hypotheses[:8]:
        print(f"  {h.weight:6.1%}  {h.role:8s} {h.label or h.source}  ({h.lat:.5f}, {h.lng:.5f})  {h.source}")
    o = result.output
    print(f"Output: {o.lat:.6f}, {o.lng:.6f} x10  [{o.method}, {o.source_role}, "
          f"uncertainty {o.uncertainty_m and round(o.uncertainty_m)} m ({o.uncertainty_source})]")
    print(f"Timings: {result.timings}")
    print(f"Log: {result.log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
