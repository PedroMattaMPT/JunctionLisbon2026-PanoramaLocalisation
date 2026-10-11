"""Per-panorama run state, JSON event log and penalty tracker (PLAN.md 3.5, RULES.md).

One `Run` per panorama, and it starts empty: no evidence, candidates, questions, answers or
penalties come from another panorama (RULES.md, partner clarification 1). Each run gets a new
folder <runs_dir>/<run_id>/ and refuses to reuse one. Every event is appended to events.jsonl as
it happens, so a crash keeps the log; `export()` writes log.json, the single reviewable document
for the organisers, with summaries of questions, cues, outputs and stages ahead of the raw events.

Events follow design_system_prompt.md ("Implementation targets"):
  {"run_id", "panorama", "seq", "t", "ts", "type", "stage", "actor", "model", "payload"}
  t is seconds since the run started (monotonic clock); ts is the UTC start time plus t, so a clock
  change mid-run cannot reorder events; actor is agent, model or team.
Types: run.started, run.finished; stage.started, stage.finished, stage.skipped, stage.failed,
stage.timed_out, stage.progress; evidence.added; candidates.updated; question.asked, question.answered,
question.skipped; cue.sent; output.produced; conversion.applied (a teammate turned a place-name
answer into a coordinate, RULES.md rule 8; our agent should never need it).

Penalties (RULES.md rules 6-9) multiply every output produced after them, for this panorama only:
an answered question x0.95 (right or wrong), a cue x0.8, a place-name conversion x0.5. A skipped
question costs nothing and changes nothing; it is only logged. Every output.produced event carries
the penalty snapshot in force when it was produced.

  run = Run("IMG_20260115_143012_00_204.jpg")
  with run.stage("read", model="PP-OCRv6-medium"):
      run.evidence("postcode", {"text": "4050-253", "confidence": 0.94}, stage="read", model="PP-OCRv6-medium")
  with run.stage("detect", optional=True):   # a failure here is logged, and the run goes on
      ...
  run.output([(41.1496, -8.6110)] * 10, method="coarse_candidate")
  q = run.ask("Which side of the river is this?", ["North bank", "South bank", "None of these"])
  run.answer(q, "a")                          # or run.skip(q): free, and nothing is inferred from it
  run.finish()                                # writes log.json
"""
import json
import math
import os
import platform
import re
import secrets
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

QUESTION_FACTOR = 0.95  # each answered multiple-choice question (rule 7)
CUE_FACTOR = 0.8  # each text cue from the team (rule 6)
CONVERSION_FACTOR = 0.5  # a teammate converting a place name to a coordinate (rule 8)
MAX_OPTIONS = 4
MAX_CUE_CHARS = 1000
MAX_COORDINATES = 10
SCHEMA = "panoloc.log/1"
CATEGORIES = ("urban", "non-urban")
CATEGORY_SOURCES = ("official", "inferred", "unknown")  # PLAN.md 1.3

# Wording that would make a skip meaningful, which the partner ruled out (RULES.md)
SILENCE_RE = re.compile(
    r"\bskip\b.*\bif\b|\b(don'?t|do not) (answer|reply)\b|\bleave (it |this )?(blank|unanswered)\b"
    r"|\b(no (reply|answer)|silence)\b.*\bmeans?\b",
    re.IGNORECASE,
)


class StageTimeout(Exception):
    """Raise inside `Run.stage(...)` when a stage runs out of time; it is logged as stage.timed_out."""


class Penalties:
    """Counts the penalised interactions of one panorama."""

    def __init__(self):
        self.answered_questions = 0
        self.cues = 0
        self.conversions = 0

    @property
    def multiplier(self):
        return (QUESTION_FACTOR ** self.answered_questions * CUE_FACTOR ** self.cues
                * CONVERSION_FACTOR ** self.conversions)

    def snapshot(self):
        return {"answered_questions": self.answered_questions, "cues": self.cues,
                "conversions": self.conversions, "multiplier": round(self.multiplier, 10)}


def coordinate(value):
    """(lat, lng) or {"lat", "lng"} -> {"lat", "lng"}, checked. Latitude always comes first."""
    if isinstance(value, dict):
        lat, lng = value["lat"], value["lng"]
    else:
        lat, lng = value
    lat, lng = float(lat), float(lng)
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"not a coordinate: lat={lat}, lng={lng}")
    return {"lat": round(lat, 7), "lng": round(lng, 7)}


def default_versions():
    versions = {"schema": SCHEMA, "python": platform.python_version()}
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                timeout=5, cwd=Path(__file__).resolve().parent)
        versions["git_commit"] = commit.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        versions["git_commit"] = None
    return versions


def atomic_write_json(path, document):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o644)  # mkstemp makes it owner-only; the console and teammates read it
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class Run:
    """The whole state of one panorama's run: its event log, questions, penalties and outputs."""

    def __init__(self, panorama, runs_dir="runs", *, special_one=False, category=None, category_source=None,
                 versions=None, run_id=None, on_event=None, clock=time.monotonic):
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES} or None")
        category_source = category_source or ("unknown" if category is None else "inferred")
        if category_source not in CATEGORY_SOURCES or (category is None) != (category_source == "unknown"):
            raise ValueError("category_source must be 'unknown' exactly when category is None")
        started = datetime.now(timezone.utc)
        self.run_id = run_id or f"r-{started:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
        self.panorama = Path(panorama).name
        self.special_one = bool(special_one)
        self.category = {"value": category, "source": category_source}
        self.versions = {**default_versions(), **(versions or {})}
        self.dir = Path(runs_dir) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)  # a fresh folder: never another run's state
        self.events_path = self.dir / "events.jsonl"
        self.log_path = self.dir / "log.json"
        self.penalties = Penalties()
        self.events, self.questions, self.outputs = [], {}, []
        self.started_at, self.finished_at = started, None
        self._clock, self._t0 = clock, clock()
        self._on_event = on_event
        self._lock = threading.RLock()
        self._counters = {"q": 0, "e": 0, "o": 0}
        self._emit("run.started", {"panorama": self.panorama, "special_one": self.special_one,
                                   "category": self.category, "versions": self.versions})

    # -- events -------------------------------------------------------------------------------------

    def _next_id(self, prefix):
        self._counters[prefix] += 1
        return f"{prefix}{self._counters[prefix]}"

    def _penalised(self, counter, type_, payload, **kwargs):
        """Count one penalised interaction and log it with the new snapshot; undo the count if logging fails."""
        setattr(self.penalties, counter, getattr(self.penalties, counter) + 1)
        try:
            return self._emit(type_, {**payload, "penalty": self.penalties.snapshot()}, **kwargs)
        except BaseException:
            setattr(self.penalties, counter, getattr(self.penalties, counter) - 1)
            raise

    def _emit(self, type_, payload, *, stage=None, actor="agent", model=None):
        with self._lock:
            if self.finished_at is not None:
                raise RuntimeError(f"run {self.run_id} has finished; start a new Run for new work")
            t = round(self._clock() - self._t0, 3)
            event = {"run_id": self.run_id, "panorama": self.panorama, "seq": len(self.events) + 1, "t": t,
                     "ts": (self.started_at + timedelta(seconds=t)).isoformat(timespec="milliseconds"),
                     "type": type_, "stage": stage, "actor": actor, "model": model, "payload": payload}
            with open(self.events_path, "a", encoding="utf-8") as f:  # disk first: memory never holds more
                f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.events.append(event)
        if self._on_event:
            self._on_event(event)
        return event

    # -- pipeline stages ----------------------------------------------------------------------------

    @contextmanager
    def stage(self, name, *, optional=False, model=None, deadline_s=None):
        """Log a stage. A failure or StageTimeout in an optional stage is logged and swallowed."""
        self._emit("stage.started", {"optional": optional, "deadline_s": deadline_s}, stage=name, model=model)
        start = self._clock()
        try:
            yield
        except StageTimeout as exc:
            self._emit("stage.timed_out", {"optional": optional, "elapsed_s": round(self._clock() - start, 3),
                                           "message": str(exc)[:500]}, stage=name, model=model)
            if not optional:
                raise
        except Exception as exc:
            self._emit("stage.failed", {"optional": optional, "elapsed_s": round(self._clock() - start, 3),
                                        "error": type(exc).__name__, "message": str(exc)[:500]},
                       stage=name, model=model)
            if not optional:
                raise
        else:
            elapsed = round(self._clock() - start, 3)
            self._emit("stage.finished", {"elapsed_s": elapsed,
                                          "over_deadline": deadline_s is not None and elapsed > deadline_s},
                       stage=name, model=model)

    def skip_stage(self, name, reason):
        self._emit("stage.skipped", {"reason": reason}, stage=name)

    def progress(self, name, message, *, model=None, completed=None, total=None, view=None, box=None):
        """Stream a public task summary and measured work counts, separately from observations."""
        if completed is not None or total is not None:
            if not (type(completed) is int and type(total) is int and 0 <= completed <= total and total > 0):
                raise ValueError("progress counts must satisfy 0 <= completed <= total, with total > 0")
        return self._emit("stage.progress", {"message": str(message)[:500], "completed": completed,
                                            "total": total, "view": view, "box": box},
                          stage=name, actor="model" if model else "agent", model=model)

    def evidence(self, kind, payload, *, stage, model=None, actor="model"):
        """Log one observation (OCR text, a VLM answer, a retrieval hit); returns its evidence ID.

        The evidence ID and kind are set here, so the payload must not carry its own `kind` or
        `evidence_id` (it would silently replace them); name such fields differently, e.g. place_kind.
        """
        clash = sorted({"kind", "evidence_id"} & set(payload))
        if clash:
            raise ValueError(f"payload keys {clash} are reserved: the evidence kind is the first argument")
        with self._lock:
            evidence_id = self._next_id("e")
            self._emit("evidence.added", {"evidence_id": evidence_id, "kind": kind, **payload},
                       stage=stage, actor=actor, model=model)
        return evidence_id

    def candidates(self, candidates, *, stage="fuse"):
        """Log the current ranked hypotheses; coordinates in them are checked like outputs."""
        checked = []
        for c in candidates:
            c = dict(c)
            if "lat" in c or "lng" in c:
                c.update(coordinate(c))
            checked.append(c)
        self._emit("candidates.updated", {"candidates": checked}, stage=stage)

    # -- the human loop -----------------------------------------------------------------------------

    def ask(self, text, options, *, kind="feature", stage="ask", **details):
        """Log an agent-generated multiple-choice question (2-4 options); returns its question ID.

        Options are strings or dicts with at least "label" (and optionally "id", "detail", "links",
        a zone boundary, a representative point ...). String options get the IDs a, b, c, d.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("a question needs text")
        if SILENCE_RE.search(text):
            raise ValueError("the wording gives a skip a meaning; offer an explicit option instead (RULES.md)")
        if not 2 <= len(options) <= MAX_OPTIONS:
            raise ValueError(f"a question has 2 to {MAX_OPTIONS} options, got {len(options)}")
        opts = []
        for i, opt in enumerate(options):
            opt = {"label": opt} if isinstance(opt, str) else dict(opt)
            opt.setdefault("id", "abcd"[i])
            if not str(opt.get("label", "")).strip():
                raise ValueError(f"option {opt['id']} has no label")
            opts.append(opt)
        if len({o["id"] for o in opts}) != len(opts):
            raise ValueError("option IDs must be unique")
        with self._lock:
            question_id = self._next_id("q")
            event = self._emit("question.asked", {"question_id": question_id, "kind": kind, "text": text,
                                                  "options": opts, **details}, stage=stage)
            self.questions[question_id] = {"question_id": question_id, "kind": kind, "text": text, "options": opts,
                                           "status": "open", "answer": None, "asked_t": event["t"],
                                           "resolved_t": None}
        return question_id

    def _open_question(self, question_id):
        q = self.questions.get(question_id)
        if q is None:
            raise KeyError(f"no question {question_id}")
        if q["status"] != "open":
            raise ValueError(f"question {question_id} is already {q['status']}")
        return q

    def answer(self, question_id, option_id):
        """The team picked an option: costs x0.95 for every later output, right or wrong."""
        with self._lock:
            q = self._open_question(question_id)
            option = next((o for o in q["options"] if o["id"] == option_id), None)
            if option is None:
                raise ValueError(f"question {question_id} has no option {option_id!r}")
            event = self._penalised("answered_questions", "question.answered",
                                    {"question_id": question_id, "option_id": option_id, "label": option["label"]},
                                    stage="ask", actor="team")
            q.update(status="answered", answer=option_id, resolved_t=event["t"])
        return option

    def skip(self, question_id):
        """The team didn't answer: no cost, and the agent must not learn anything from it."""
        with self._lock:
            q = self._open_question(question_id)
            event = self._emit("question.skipped", {"question_id": question_id}, stage="ask", actor="team")
            q.update(status="skipped", resolved_t=event["t"])

    def cue(self, text):
        """A text cue from the team: costs x0.8. It must not name or hint at any place (rule 6)."""
        text = (text or "").strip()
        if not text:
            raise ValueError("an empty cue")
        if len(text) > MAX_CUE_CHARS:
            raise ValueError(f"a cue is at most {MAX_CUE_CHARS} characters, got {len(text)}")
        with self._lock:
            self._penalised("cues", "cue.sent", {"text": text, "chars": len(text)}, actor="team")

    def conversion(self, place, point, note=""):
        """A teammate picked a coordinate inside a place the agent named: costs x0.5 (rule 8)."""
        point = coordinate(point)
        with self._lock:
            self._penalised("conversions", "conversion.applied", {"place": place, "coordinate": point, "note": note},
                            actor="team")

    # -- outputs ------------------------------------------------------------------------------------

    def output(self, coordinates, *, method=None, uncertainty_m=None, uncertainty_source=None, sources=None,
               source_role=None, note=None):
        """Log a ranked list of up to 10 (lat, lng) guesses with the penalty snapshot in force now.

        method is the PLAN.md 3.3 output_method: reference_camera, geographic_cell or coarse_candidate;
        sources and source_role say where the coordinate came from and what it marks (camera, landmark,
        area). uncertainty_m stays None when unknown; it must never become a zero-metre estimate.
        panoloc.candidates.Output.log() fills all of these.
        """
        if not 1 <= len(coordinates) <= MAX_COORDINATES:
            raise ValueError(f"an output has 1 to {MAX_COORDINATES} coordinates, got {len(coordinates)}")
        ranked = [{"rank": i + 1, **coordinate(c)} for i, c in enumerate(coordinates)]
        with self._lock:
            output_id = self._next_id("o")
            payload = {"output_id": output_id, "coordinates": ranked, "output_method": method,
                       "sources": list(sources or []), "source_role": source_role,
                       "position_uncertainty_m": uncertainty_m, "uncertainty_source": uncertainty_source,
                       "category": self.category, "special_one": self.special_one,
                       "penalty": self.penalties.snapshot(), "note": note}
            event = self._emit("output.produced", payload, stage="output")
            self.outputs.append({"t": event["t"], "seq": event["seq"], **payload})
        return output_id

    # -- end of run ---------------------------------------------------------------------------------

    def reopen(self, output_id):
        """Resume this panorama for an explicit answer review, keeping counters and all receipts."""
        with self._lock:
            if self.finished_at is None or not self.outputs or self.outputs[-1]["output_id"] != output_id:
                raise ValueError("Only the latest answer of a finished run can be reviewed.")
            finished = self.finished_at
            self.finished_at = None
            try:
                self._emit("run.reopened", {"output_id": output_id, "reason": "answer_review",
                                             "penalty": self.penalties.snapshot()}, actor="team")
            except BaseException:
                self.finished_at = finished
                raise

    def finish(self):
        """Close the run (no event can follow) and write log.json; returns its path."""
        with self._lock:
            counts = {s: sum(q["status"] == s for q in self.questions.values()) for s in ("answered", "skipped", "open")}
            self._emit("run.finished", {"duration_s": round(self._clock() - self._t0, 3),
                                        "final_output": self.outputs[-1]["output_id"] if self.outputs else None,
                                        "questions": counts, "penalty": self.penalties.snapshot()})
            self.finished_at = self.started_at + timedelta(seconds=self.events[-1]["t"])
            return self.export()

    def export(self):
        """Write log.json (also mid-run): run identity, summaries, then every event in order."""
        with self._lock:
            stages = {}
            for e in self.events:
                if e["type"].startswith("stage."):
                    s = stages.setdefault(e["stage"], {"stage": e["stage"], "model": e["model"]})
                    if e["type"] == "stage.progress":
                        s["progress"] = e["payload"]
                        continue
                    s["status"] = e["type"].split(".", 1)[1]
                    for key in ("optional", "elapsed_s", "error", "message", "reason", "over_deadline"):
                        if key in e["payload"]:
                            s[key] = e["payload"][key]
            document = {
                "schema": SCHEMA, "run_id": self.run_id, "panorama": self.panorama,
                "special_one": self.special_one, "category": self.category, "versions": self.versions,
                "started_at": self.started_at.isoformat(timespec="milliseconds"),
                "finished_at": self.finished_at.isoformat(timespec="milliseconds") if self.finished_at else None,
                "duration_s": self.events[-1]["t"],
                "penalty": self.penalties.snapshot(),
                "final_output": self.outputs[-1] if self.outputs else None,
                "outputs": self.outputs,
                "questions": list(self.questions.values()),
                "cues": [{"t": e["t"], "text": e["payload"]["text"]} for e in self.events if e["type"] == "cue.sent"],
                "conversions": [{"t": e["t"], **e["payload"]} for e in self.events if e["type"] == "conversion.applied"],
                "stages": list(stages.values()),
                "events": self.events,
            }
            atomic_write_json(self.log_path, document)
            return self.log_path
