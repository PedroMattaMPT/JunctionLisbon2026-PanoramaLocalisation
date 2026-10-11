#!/usr/bin/env python3
"""Aqui live backend: the real panoloc pipeline behind the mock's HTTP layer (T76, T50).

  .venv/bin/python app/dev/live_server.py [--port 8788] [--console-port 5178] [--question-timeout S]
                                          [--no-warm] [--no-ocr] [--no-vlm] [--no-retrieval] [--no-landmarks]
                                          [--no-tiles] [--ask-anyway] [--min-gain G] [--max-questions N]
  Normally started and kept alive by app/start.sh (start | stop | status | restart).

Loopback only, with the mock's write token, Origin and size checks (server.Handler). One GPU worker holds
ONE panoloc.pipeline.Models, warmed at start-up (each model's load time and the VRAM are printed), and
solves one upload at a time while the others wait in the queue. Each upload is saved unchanged under
runs/app/<run_id>/ and solved alone by pipeline.run_panorama: a fresh Run, nothing carried across
panoramas. Its events reach the console through on_event, disk first. A question blocks the run until
the console answers it or skips it; the pipeline logs either (a skip costs nothing and changes nothing).

It also serves the built console (app/dist) on its own port and, with --console-port, on a second one, so
the page and /api share an origin. POST /api/runs/<id>/skip-remaining skips the open question and every
later one of that run (free and neutral); --question-timeout skips a question nobody answered in time.
Both log an operator.auto_skip event before the pipeline's question.skipped. /api/tiles/... is a caching
proxy for the map's street and satellite tiles (app/dev/tiles.py, cache in runs/app/tiles/).

Limits of this version: no text cues mid-run (T78; the endpoint answers 501), no submission transport
(copy the coordinates from the answer screen), no state across panoramas by design, and the run list
resets on restart (the folders in runs/app/ stay replayable). Questions follow the pipeline's own gate:
--ask-anyway asks the first one even below break-even and --min-gain -1 asks every scheduled one
(rehearsals only: each answer costs x0.95).
"""
import argparse
import inspect
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # every weight is cached locally (CLAUDE.md)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402  the mock's HTTP layer; it puts the repository root on sys.path
import tiles as tilemod  # noqa: E402
from panoloc import pipeline  # noqa: E402
from panoloc.runlog import Run  # noqa: E402

QUIET = lambda *args, **kwargs: None  # noqa: E731  run_panorama prints only for operator="ask"
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
                ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".json": "application/json",
                ".jsonl": "application/x-ndjson", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
                ".wasm": "application/wasm", ".map": "application/json"}


def log(message):
    print(f"[live {datetime.now():%H:%M:%S}] {message}", flush=True)


def new_run_id():
    return f"r-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


_gpu_cache = {"t": 0.0, "value": (None, 16.0)}


def gpu_memory_gb():
    """(used, total) GB on the GPU from nvidia-smi, cached for 5 s; (None, 16) when unavailable."""
    if time.monotonic() - _gpu_cache["t"] > 5:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout
            used, total = (float(v) / 1024 for v in out.splitlines()[0].split(","))
            _gpu_cache["value"] = (round(used, 2), round(total, 2))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            _gpu_cache["value"] = (None, 16.0)
        _gpu_cache["t"] = time.monotonic()
    return _gpu_cache["value"]


def torch_allocated_gb():
    torch = sys.modules.get("torch")
    try:
        return torch.cuda.memory_allocated() / 2 ** 30 if torch is not None and torch.cuda.is_available() else 0.0
    except Exception:  # noqa: BLE001  telemetry only
        return 0.0


class LiveContext:
    """One upload: its queue state, the events its Run pushed, and the console's pending responses.

    Lock order: the pipeline may call on_event while its Run holds the Run's lock, so nothing here calls
    into the Run while holding self.condition.
    """

    def __init__(self, filename, data, category, source, special, size, question_timeout=None):
        self.run_id = new_run_id()
        self.dir = server.ROOT / "runs/app" / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self.image = self.dir / Path(filename).name
        self.image.write_bytes(data)  # the original upload, unchanged
        self.filename, self.category, self.source, self.special_one, self.size = filename, category, source, special, size
        self.condition = threading.Condition(threading.RLock())
        self.events = {}  # seq -> event; OCR and VLM log from two threads, so hooks can arrive out of order
        self.questions, self.responses = {}, {}
        self.state, self.finished, self.error, self.run, self.timings = "queued", False, None, None, None
        self.question_timeout = question_timeout or None  # seconds; None waits for the console
        self.skip_rest, self.waiting, self.auto_skipped = False, None, []

    def on_event(self, event):
        """Run's hook: record the event and wake the streams. Never raises into a pipeline stage."""
        try:
            with self.condition:
                self.events[event["seq"]] = event
                p = event.get("payload") or {}
                if event["type"] == "question.asked":
                    self.questions[p["question_id"]] = {"status": "open", "text": p.get("text"), "kind": p.get("kind"),
                                                        "options": {o.get("id") for o in p.get("options", [])},
                                                        "option_list": p.get("options", [])}
                elif event["type"] in ("question.answered", "question.skipped") and p.get("question_id") in self.questions:
                    self.questions[p["question_id"]]["status"] = event["type"].split(".", 1)[1]
                self.condition.notify_all()
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def operator(self, question):
        """The pipeline's operator: block until the console answers (an option ID) or skips (None).

        Returns None at once after skip-remaining, and after question_timeout seconds without a response.
        """
        qid, reason, t0 = question.question_id, None, time.monotonic()
        with self.condition:
            info = self.questions.get(qid, {})
            self.state = "question waiting"
            self.waiting = {"question_id": qid, "text": info.get("text") or getattr(question, "text", None),
                            "kind": info.get("kind") or getattr(question, "kind", None), "since": t0}
            try:
                while qid not in self.responses:
                    elapsed = time.monotonic() - t0
                    if self.skip_rest:
                        reason = "skip_remaining"
                    elif self.question_timeout and elapsed >= self.question_timeout:
                        reason = "timeout"
                    if reason:
                        self.responses[qid] = None
                        break
                    self.condition.wait(timeout=min(5, self.question_timeout - elapsed) if self.question_timeout else 5)
            finally:
                self.state, self.waiting = "processing", None
            response = self.responses[qid]
        if reason:
            waited = round(time.monotonic() - t0, 1)
            self.auto_skipped.append({"question_id": qid, "reason": reason, "waited_s": waited})
            log(f"{self.run_id}: question {qid} skipped by {'skip-remaining' if reason == 'skip_remaining' else 'timeout'}"
                f" after {waited} s")
            self.audit("operator.auto_skip", {"question_id": qid, "reason": reason, "waited_s": waited,
                                              "timeout_s": self.question_timeout if reason == "timeout" else None},
                       actor="team" if reason == "skip_remaining" else "agent")
        return response

    def audit(self, type_, payload, actor="agent"):
        """One console audit event in the run's own log (never while holding self.condition)."""
        run = self.run
        if run is None:
            return
        try:
            run._emit(type_, payload, stage="ask", actor=actor)  # dev server only: Run has no public audit hook
        except Exception:  # noqa: BLE001  the log is best effort; the skip itself still happens
            traceback.print_exc()

    def respond(self, qid, option_id=None, skip=False):
        """Validate one console response and hand it to the waiting operator; the pipeline logs it."""
        with self.condition:
            q = self.questions.get(qid)
            if q is None:
                raise KeyError(f"No question {qid} in this run.")
            if q["status"] != "open" or qid in self.responses:
                raise ValueError(f"Question {qid} is already resolved.")
            if not skip and (not isinstance(option_id, str) or option_id not in q["options"]):
                raise ValueError(f"Question {qid} has no option {option_id!r}.")
            self.responses[qid] = None if skip else option_id
            self.condition.notify_all()

    def skip_remaining(self):
        """Skip the open question and every later one: each becomes a free, neutral skip. Returns the open
        question's ID, if any."""
        with self.condition:
            if self.finished:
                raise ValueError("This run has finished; no question is left to skip.")
            self.skip_rest = True
            self.condition.notify_all()
            return self.waiting["question_id"] if self.waiting else None

    def waiting_info(self):
        """The question this run waits on, for the queue view; None when it isn't waiting."""
        w = self.waiting
        if not w:
            return None
        waited = time.monotonic() - w["since"]
        return {"question_id": w["question_id"], "text": w["text"], "kind": w["kind"], "waiting_s": round(waited),
                "timeout_in_s": round(max(0.0, self.question_timeout - waited)) if self.question_timeout else None}

    def summary(self, position=None):
        return {"run_id": self.run_id, "status": self.state, "special_one": self.special_one, "panorama": self.filename,
                "question": self.waiting_info(), "skip_remaining": self.skip_rest,
                **({"position": position} if position else {}), **({"error": self.error} if self.error else {})}

    def pending(self, after, wait_s=15):
        """The contiguous events after seq `after` (waiting up to wait_s for one), and whether the job is done."""
        with self.condition:
            if after + 1 not in self.events and not self.finished:
                self.condition.wait(timeout=wait_s)
            out = []
            while after + 1 in self.events:
                after += 1
                out.append(self.events[after])
            return out, self.finished and after + 1 not in self.events


class RunFactory:
    """Wraps pipeline.Run so the worker keeps a handle on the job's Run (log.json mid-run, audit events),
    and the Run takes the ID the console already holds when run_panorama has no run_id parameter.

    Safe because one worker builds one Run at a time.
    """

    def __init__(self, cls):
        self.cls, self.next = cls, None

    def __call__(self, *args, **kwargs):
        ctx, self.next = self.next, None
        if ctx is not None:
            kwargs.setdefault("run_id", ctx.run_id)
        run = self.cls(*args, **kwargs)
        if ctx is not None:
            ctx.run = run
        return run


class LiveWorker:
    """The one GPU worker: warms one Models at start-up, then solves queued uploads one at a time."""

    def __init__(self, args):
        self.args = args
        self.condition = threading.Condition()
        self.runs, self.queue, self.current = {}, [], None
        use = dict(ocr=not args.no_ocr, vlm=not args.no_vlm, retrieval=not args.no_retrieval)
        landmarks = not getattr(args, "no_landmarks", False) and use["retrieval"]
        if "landmarks" in inspect.signature(pipeline.Models).parameters:
            use["landmarks"] = landmarks  # Commons gallery + verifier, about 2.5 GiB of GPU at run time
        self.models = pipeline.Models(**use)
        log(f"models: {use}; landmark stage {'on' if landmarks else 'off'}")
        self.params = inspect.signature(pipeline.run_panorama).parameters
        if "on_event" not in self.params:
            raise SystemExit("panoloc.pipeline.run_panorama has no on_event; update panoloc first.")
        base = pipeline.Run.cls if isinstance(pipeline.Run, RunFactory) else pipeline.Run
        self.factory = pipeline.Run = RunFactory(base)  # always: ctx.run is the job's Run
        m = self.models
        names = None
        try:
            from panoloc.names import NameIndex
            names = lambda: NameIndex.open().close()  # noqa: E731  opened per panorama; checked here
        except ImportError:
            pass
        def zones():
            if m.zones() is None:
                raise RuntimeError("zone index not built: zone questions use box cells")
        retrieval, vlm, ocr = not args.no_retrieval, not args.no_vlm, not args.no_ocr
        plugin = m.vlm() if vlm and m.vlm() is not m.vlm_local() else None  # the optional VLM plugin is active
        self.roster = [  # id, name, role, loader (None: disabled), on the CPU
            ("ocr", "PP-OCRv6 medium", "Reads signs on the CPU", m.ocr if ocr else None, True),
            ("vlm-plugin", f"{plugin.model if plugin else 'VLM plugin'} (API)", "Answers the scene checklist",
             plugin.load if plugin else None, True),
            ("qwen", "Qwen3.5-9B (Ollama)", "Checklist fallback if the plugin fails" if plugin else "Answers the scene checklist",
             (lambda: m.vlm_local().load()) if vlm else None, False),
            ("pe", "PE-Core + photo bank", "Retrieves similar reference photos", m.retrieval if retrieval else None, False),
            ("geo", "GeoCLIP", "Samples candidate coordinates", m.geoclip if retrieval else None, False),
            ("gallery", "Commons landmark gallery", "Finds landmark photos", m.landmarks if landmarks else None, False),
            ("match", "ALIKED + LightGlue", "Checks geometric matches", m.verifier if landmarks else None, False),
            ("zones", "Zone index", "Names the question zones", zones, True),
            ("names", "Local name index", "Finds landmark and area points", names, True),
        ]
        self.status = {mid: {"id": mid, "name": name, "role": role, "state": "cold" if load else "disabled", "gb": 0,
                             **({"cpu": True} if cpu else {})} for mid, name, role, load, cpu in self.roster}
        self.warm_state, self.warm_s = "cold", None
        threading.Thread(target=self.work, daemon=True, name="gpu-worker").start()

    def add(self, ctx):
        with self.condition:
            self.runs[ctx.run_id] = ctx
            self.queue.append(ctx)
            self.condition.notify()
        log(f"queued {ctx.run_id} ({ctx.filename}); {len(self.queue)} waiting")

    def warm(self):
        """Load every model now, so the first panorama isn't slow. A failed load is logged; its stage fails
        softly later (optional) and the run goes on without it."""
        self.warm_state = "warming"
        t_all = time.perf_counter()
        for mid, name, _, load, _ in self.roster:
            if load is None:
                continue
            entry = self.status[mid]
            entry["state"] = "loading"
            before, t0 = torch_allocated_gb(), time.perf_counter()
            try:
                load()
                entry["state"] = "resident"
            except Exception as exc:  # noqa: BLE001
                entry["state"], entry["error"] = "failed", f"{type(exc).__name__}: {exc}"[:300]
                traceback.print_exc()
            entry["load_s"] = round(time.perf_counter() - t0, 2)
            if mid == "qwen" and entry["state"] == "resident":
                try:
                    entry["gb"] = round(sum(x.get("size_vram", 0) for x in self.models.vlm_local().loaded()
                                            if x.get("name") == self.models.vlm_local().model) / 2 ** 30, 2)
                except Exception:  # noqa: BLE001
                    pass
            elif not entry.get("cpu"):
                entry["gb"] = round(max(0.0, torch_allocated_gb() - before), 2)
            _gpu_cache["t"] = 0
            used, total = gpu_memory_gb()
            log(f"warm {name}: {entry['state']} in {entry['load_s']} s, +{entry['gb']} GB; this process "
                f"{torch_allocated_gb():.2f} GB allocated; GPU {used}/{total} GB used"
                + (f"; {entry['error']}" if entry.get("error") else ""))
        self.warm_s = round(time.perf_counter() - t_all, 1)
        self.warm_state = "online"
        log(f"warm-up done in {self.warm_s} s")

    def work(self):
        if self.args.no_warm:
            self.warm_state = "online"
            log("models load lazily on the first panorama (--no-warm)")
        else:
            self.warm()
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                ctx = self.queue.pop(0)
                self.current = ctx.run_id
            try:
                self.solve(ctx)
            finally:
                with self.condition:
                    self.current = None

    def solve(self, ctx):
        ctx.state = "processing"
        log(f"start {ctx.run_id} ({ctx.filename})")
        t0 = time.perf_counter()
        kwargs = dict(runs_dir=ctx.dir, operator=ctx.operator, category=ctx.category, category_source=ctx.source,
                      special_one=ctx.special_one, max_questions=self.args.max_questions, ask_anyway=self.args.ask_anyway,
                      print_fn=QUIET, on_event=ctx.on_event)
        if self.args.min_gain is not None and "min_gain" in self.params:
            kwargs["min_gain"] = self.args.min_gain
        if "run_id" in self.params:
            kwargs["run_id"] = ctx.run_id
        self.factory.next = ctx
        try:
            result = pipeline.run_panorama(ctx.image, self.models, **kwargs)
            ctx.timings, ctx.state = result.timings, "finished"
            log(f"finished {ctx.run_id} in {time.perf_counter() - t0:.1f} s: {result.timings}")
        except Exception as exc:  # noqa: BLE001  the server stays up; the run ends with a visible error
            traceback.print_exc()
            ctx.error, ctx.state = f"{type(exc).__name__}: {exc}"[:500], "failed"
            self.record_failure(ctx, exc, time.perf_counter() - t0)
            log(f"failed {ctx.run_id}: {ctx.error}")
        finally:
            self.factory.next = None
            with ctx.condition:
                ctx.finished = True
                ctx.condition.notify_all()

    def record_failure(self, ctx, exc, elapsed):
        """Show the failure in the run's own log: a stage.failed "pipeline" event, unless a core stage already
        logged one. Without any Run yet, a minimal Run in the job folder carries it."""
        payload = {"optional": False, "elapsed_s": round(elapsed, 3), "error": type(exc).__name__,
                   "message": f"The pipeline stopped: {exc}"[:500]}
        try:
            run = ctx.run
            if run is None:
                run = Run(ctx.filename, ctx.dir, run_id=ctx.run_id, special_one=ctx.special_one, category=ctx.category,
                          category_source=ctx.source, versions={"live_server": "app/dev/live_server.py"}, on_event=ctx.on_event)
                ctx.run = run
                run._emit("stage.failed", payload, stage="pipeline")
                run.finish()
                return
            if any(e["type"] == "stage.failed" and not e["payload"].get("optional") for e in run.events):
                return
            with run._lock:  # the pipeline already closed the Run; reopen it for this one event (dev server only)
                closed, run.finished_at = run.finished_at, None
                try:
                    run._emit("stage.failed", payload, stage="pipeline")
                finally:
                    run.finished_at = closed
                run.export()
        except Exception:  # noqa: BLE001
            traceback.print_exc()


class LiveHandler(server.Handler):
    """The mock's HTTP layer with the live worker behind it. Same routes, token and Origin checks, plus the
    built console, skip-remaining and the tile proxy."""

    def log_message(self, fmt, *args):
        # Leave out the console's polling, streams, tiles and static files; never print cues or uploads.
        line = str(args[0]) if args else ""
        if not re.search(r"GET (/api/(status|runs)(/[\w-]+/events)?[ ?]|/api/tiles/|/(?!api/))", line):
            super().log_message(fmt, *args)

    def do_GET(self):
        try:
            if not self.allowed_host():
                return self.json({"error": "Local host required."}, 403)
            url, worker = urlsplit(self.path), self.server.worker
            if url.path == "/api/status":
                used, total = gpu_memory_gb()
                with worker.condition:
                    queue, current = [c.run_id for c in worker.queue], worker.current
                ctx = worker.runs.get(current) if current else None
                tiles = getattr(self.server, "tiles", None)
                return self.json({"worker": worker.warm_state, "mock": False, "live": True,
                                  "gpu": {"used_gb": used, "total_gb": total},
                                  "models": list(worker.status.values()), "csrf_token": server.TOKEN,
                                  "tile_source": tiles.describe()[0]["url"] if tiles else None,
                                  "tile_layers": tiles.describe() if tiles else [],
                                  "warm_s": worker.warm_s, "queue": queue, "current": current,
                                  "current_panorama": ctx.filename if ctx else None,
                                  "current_question": ctx.waiting_info() if ctx else None,
                                  "question_timeout_s": getattr(worker.args, "question_timeout", None) or None,
                                  "limits": {"cues": "not supported in this version (T78)",
                                             "submit": "not wired: copy the coordinates"}})
            if url.path == "/api/runs":
                with worker.condition:
                    runs = list(worker.runs.values())
                    positions = {c.run_id: i + 1 for i, c in enumerate(worker.queue)}
                return self.json([ctx.summary(positions.get(ctx.run_id)) for ctx in runs])
            match = re.fullmatch(r"/api/tiles/([a-z]+)/(\d{1,2})/(\d{1,7})/(\d{1,7})(?:\.(?:png|jpe?g))?", url.path)
            if match:
                return self.send_tile(match[1], int(match[2]), int(match[3]), int(match[4]))
            match = re.fullmatch(r"/api/runs/([\w-]+)/(events|log\.json)", url.path)
            if match:
                ctx = self.context(match[1])
                if match[2] == "log.json":
                    if ctx.run is None:
                        raise ValueError("This run has not started yet; its log exists once the worker takes it.")
                    if ctx.run.finished_at is None:
                        ctx.run.export()  # mid-run: the current events; finish() rewrites it at the end
                    return self.json(json.loads(ctx.run.log_path.read_text(encoding="utf-8")))
                after = int(self.headers.get("Last-Event-ID") or parse_qs(url.query).get("after", ["0"])[0])
                return self.stream(ctx, max(0, after))
            if url.path.startswith("/api/files/"):
                return self.send_file(server.ROOT / "runs/app", unquote(url.path.removeprefix("/api/files/")))
            if not url.path.startswith("/api/"):
                return self.send_console(url.path)
            return self.json({"error": "Route not available."}, 404)
        except (KeyError, ValueError) as error:
            self.json({"error": str(error).strip("'\"")}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_tile(self, layer, z, x, y):
        tiles = getattr(self.server, "tiles", None)
        if tiles is None:
            return self.json({"error": "The tile proxy is off (--no-tiles)."}, 404)
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            return self.json({"error": "Tiles are for the operator console only."}, 403)  # no hotlinking via our User-Agent
        try:
            data, ctype, cached = tiles.get(layer, z, x, y)
        except tilemod.TileError as error:
            return self.json({"error": str(error)}, error.status)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.send_header("X-Tile-Cache", "hit" if cached else "miss")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_console(self, path):
        """The built console (app/dist): its files, and index.html for any other page path."""
        root = getattr(self.server, "dist", None)
        if root is None or not (root / "index.html").is_file():
            return self.json({"error": "Console not built: run `npm run build` in app/, or app/start.sh."}, 404)
        root = root.resolve()
        relative = unquote(path).lstrip("/") or "index.html"
        file = (root / relative).resolve()
        if not file.is_relative_to(root):
            return self.json({"error": "File not available."}, 404)
        if not file.is_file():
            if "." in Path(relative).name:
                return self.json({"error": "File not available."}, 404)
            file = root / "index.html"
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", STATIC_TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0]
                         or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable"
                         if file.parent.name == "assets" and file.parent.parent == root else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def context(self, run_id):
        ctx = self.server.worker.runs.get(run_id)
        if ctx is None:
            raise KeyError("Run not available in this live session.")
        return ctx

    def stream(self, ctx, after):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            while True:
                events, done = ctx.pending(after)
                for event in events:
                    self.wfile.write(f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
                    after = event["seq"]
                if done:
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    self.wfile.flush()
                    self.close_connection = True
                    return
                if not events:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        try:
            body = self.write_body()
            if body is None:
                return
            url, worker = urlsplit(self.path), self.server.worker
            if url.path == "/api/runs":
                filename, data, size, category, source, special = server.parse_upload(self.headers.get("Content-Type", ""), body)
                ctx = LiveContext(filename, data, category, source, special, size,
                                  question_timeout=getattr(worker.args, "question_timeout", None))
                worker.add(ctx)
                return self.json({"run_id": ctx.run_id}, 201)
            if url.path == "/api/tiles/prefetch":
                return self.prefetch(json.loads(body))
            match = re.fullmatch(r"/api/runs/([\w-]+)/(questions/([\w-]+)/(answer|skip)|cues|submit|priority|skip-remaining)", url.path)
            if not match:
                return self.json({"error": "Route not available."}, 404)
            ctx = self.context(match[1])
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("The action needs a JSON object.")
            if match[4] in ("answer", "skip"):
                if ctx.finished:
                    raise ValueError("This run has finished; its questions are closed.")
                ctx.respond(match[3], payload.get("option_id"), skip=match[4] == "skip")
            elif match[2] == "skip-remaining":
                open_question = ctx.skip_remaining()
                log(f"{ctx.run_id}: skip remaining questions requested"
                    + (f" while {open_question} was open" if open_question else ""))
                return self.json({"accepted": True, "open_question": open_question})
            elif match[2] == "cues":
                return self.json({"error": "Text cues are not supported in live mode yet (T78): the pipeline takes no "
                                           "cue mid-run. Answer or skip its questions instead; nothing was sent or charged."}, 501)
            elif match[2] == "submit":
                return self.json({"error": "Submission is not wired in live mode: copy the coordinates from the answer "
                                           "screen. Nothing was submitted."}, 501)
            elif match[2] == "priority":
                with worker.condition:
                    if ctx in worker.queue:
                        worker.queue.remove(ctx)
                        worker.queue.insert(0, ctx)
            return self.json({"accepted": True})
        except (KeyError, ValueError, RuntimeError, TypeError) as error:
            self.json({"error": str(error).strip("'\"")}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def prefetch(self, payload):
        """Warm the tile cache behind one open question's options, for the layer the console shows."""
        tiles = getattr(self.server, "tiles", None)
        if tiles is None:
            return self.json({"error": "The tile proxy is off (--no-tiles)."}, 404)
        if not isinstance(payload, dict):
            raise ValueError("The action needs a JSON object.")
        ctx = self.context(str(payload.get("run_id")))
        with ctx.condition:
            q = ctx.questions.get(str(payload.get("question_id")))
            options = list(q["option_list"]) if q else None
        if options is None:
            raise KeyError("No such question in this run.")
        try:
            queued = tiles.prefetch(str(payload.get("layer") or "streets"), options)
        except tilemod.TileError as error:
            return self.json({"error": str(error)}, error.status)
        return self.json({"accepted": True, "queued": queued})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--console-port", type=int, default=0,
                        help="also serve the console and /api here (5178 keeps the usual URL); 0: off")
    parser.add_argument("--dist", type=Path, default=server.ROOT / "app/dist", help="built console to serve")
    parser.add_argument("--question-timeout", type=float, default=0,
                        help="skip a question nobody answered after this many seconds (free, logged); 0: wait")
    parser.add_argument("--no-tiles", action="store_true", help="no tile proxy: the map keeps its bundled outlines")
    parser.add_argument("--no-warm", action="store_true", help="load models lazily on the first panorama")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--no-vlm", action="store_true")
    parser.add_argument("--no-retrieval", action="store_true", help="no PE-Core, GeoCLIP, gallery or verifier (no GPU models)")
    parser.add_argument("--no-landmarks", action="store_true", help="skip the Commons gallery and verifier (saves ~2.5 GiB of GPU)")
    parser.add_argument("--ask-anyway", action="store_true", help="ask the first question even below break-even (rehearsal)")
    parser.add_argument("--min-gain", type=float, default=None, help="question gate; -1 asks every scheduled question (rehearsal)")
    parser.add_argument("--max-questions", type=int, default=pipeline.MAX_QUESTIONS)
    args = parser.parse_args()
    if {args.port, args.console_port} & {8000, 8765, 8799}:
        parser.error("ports 8000, 8765 and 8799 are taken on this laptop")
    if args.question_timeout < 0:
        parser.error("--question-timeout must be 0 (off) or a number of seconds")
    http = server.ThreadingHTTPServer(("127.0.0.1", args.port), LiveHandler)
    http.daemon_threads = True
    http.dist = args.dist
    http.tiles = None if args.no_tiles else tilemod.TileProxy(server.ROOT / "runs/app/tiles", log=log)
    http.worker = LiveWorker(args)
    urls = [f"http://127.0.0.1:{args.port}/"]
    if args.console_port and args.console_port != args.port:
        try:
            extra = server.ThreadingHTTPServer(("127.0.0.1", args.console_port), LiveHandler)
            extra.daemon_threads = True
            extra.dist, extra.tiles, extra.worker = http.dist, http.tiles, http.worker
            threading.Thread(target=extra.serve_forever, daemon=True, name="console-port").start()
            urls.insert(0, f"http://127.0.0.1:{args.console_port}/")
        except OSError as exc:
            log(f"console port {args.console_port} unavailable ({exc}); the console is still on port {args.port}")
    built = (args.dist / "index.html").is_file()
    log(f"Aqui live backend on port {args.port} · uploads and run logs in runs/app/ · console "
        + (" and ".join(urls) if built else "not built (npm run build in app/)")
        + (f" · questions auto-skip after {args.question_timeout:g} s" if args.question_timeout else "")
        + (" · tile proxy off" if args.no_tiles else " · map tiles cached in runs/app/tiles/"))
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()


if __name__ == "__main__":
    main()
