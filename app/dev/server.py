#!/usr/bin/env python3
"""Loopback-only Aqui mock, using the actual panoloc Run and penalty rules.

python3 app/dev/server.py [--port 8788] [--pace 0.12]
This is a scripted demonstration, not a geolocation model. Evidence is invented.
One worker takes queued, sealed runs. Questions pause their script until an answer
or neutral skip arrives. Outputs remain reviewable until an audited submission.
"""
import argparse
import hmac
import json
import mimetypes
import re
import secrets
import struct
import sys
import threading
import time
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from panoloc.runlog import Run  # noqa: E402

MAX_UPLOAD = 40 * 1024 * 1024
TOKEN = secrets.token_urlsafe(32)
PLACE_RE = re.compile(r"\b(porto|lisboa|lisbon|douro|gaia|ribeira|alentejo|évora|evora|nazaré|nazare|galicia|madrid|paris|extremadura|braga|sintra|portugal|spain|france|santiago)\b", re.I)
HINT_RE = re.compile(r"big[- ]wave surf|port wine|cellars|tram 28|camino|pilgrim", re.I)
COORD_RE = re.compile(r"[−+-]?\d{1,3}(?:[.,]\d+)?\s*(?:°|[NSWE]|[,;]\s*[−+-]?\d{1,3}\.\d+)", re.I)


def validate_cue(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A cue needs text.")
    if len(text) > 1000:
        raise ValueError("A cue is at most 1000 characters.")
    if PLACE_RE.search(text) or HINT_RE.search(text) or COORD_RE.search(text):
        raise ValueError("Cues must not name or hint at a place, or give coordinates.")
    # The real pipeline needs a complete gazetteer / semantic check; see CONTRACT.md.
    return text.strip()


def jpeg_size(data):
    """Read JPEG frame dimensions without dependencies; the browser also decodes it."""
    if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        raise ValueError("The upload is not a complete JPEG.")
    i = 2
    while i < len(data):
        if data[i] != 255:
            raise ValueError("Invalid JPEG marker stream.")
        while i < len(data) and data[i] == 255:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i:i + 2])[0]
        if length < 2 or i + length > len(data):
            raise ValueError("Invalid JPEG segment length.")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if length < 8:
                raise ValueError("Invalid JPEG frame.")
            height, width = struct.unpack(">HH", data[i + 3:i + 7])
            if width == 0 or height == 0 or width != 2 * height:
                raise ValueError(f"Decoded frame {width}×{height} is not 2:1.")
            if width * height > 48_000_000:
                raise ValueError("JPEG exceeds the local pixel limit.")
            return width, height
        i += length
    raise ValueError("No JPEG frame was found.")


def parse_upload(content_type, body):
    """A multipart intake -> (filename, data, (width, height), category, category_source, special_one).

    Raises ValueError before anything is written. Shared by the mock and app/dev/live_server.py.
    """
    if not content_type.startswith("multipart/form-data;"):
        raise ValueError("A multipart JPEG upload is required.")
    message = BytesParser(policy=default).parsebytes(f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body)
    fields, filename, data = {}, None, None
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        value = part.get_payload(decode=True)
        if name == "file":
            filename = Path(part.get_filename() or "panorama.jpg").name
            data = value
        elif name in ("category", "category_source", "special_one"):
            fields[name] = value.decode("utf-8")
    if data is None or not filename or not re.search(r"\.jpe?g$", filename, re.I) or len(data) > MAX_UPLOAD:
        raise ValueError("Choose a JPEG file within the 40 MB limit.")
    size = jpeg_size(data)
    category = fields.get("category") or None
    source = fields.get("category_source", "unknown")
    special = fields.get("special_one") == "true"
    if category not in (None, "urban", "non-urban") or source not in ("official", "inferred", "unknown") or (category is None) != (source == "unknown"):
        raise ValueError("Category source must be unknown exactly when category is unknown.")
    return filename, data, size, category, source, special


class Context:
    def __init__(self, filename, data, category, source, special, size):
        self.condition = threading.Condition(threading.RLock())
        self.changed = threading.Event()
        self.events = []
        self.state = "waiting"
        self.run = Run(filename, ROOT / "runs/mock", category=category, category_source=source,
                       special_one=special, versions={"mock": True, "schema": "panoloc.log/1"},
                       on_event=self.on_event)
        self.image = self.run.dir / Path(filename).name
        self.image.write_bytes(data)  # original upload, unchanged
        self.size = size

    def on_event(self, event):
        # Run may invoke its hook while holding its own lock. Never acquire the
        # question lock here: HTTP answers acquire that lock before calling Run.
        self.events.append(event)
        self.changed.set()

    def wait_question(self, qid):
        with self.condition:
            self.state = "question waiting"
            while self.run.questions[qid]["status"] == "open":
                self.condition.wait()
            self.state = "processing"
            return self.run.questions[qid]


class Worker:
    def __init__(self, pace):
        self.pace = pace
        self.condition = threading.Condition()
        self.runs = {}
        self.queue = []
        self.current = None
        threading.Thread(target=self.work, daemon=True).start()

    def add(self, context):
        with self.condition:
            self.runs[context.run.run_id] = context
            self.queue.append(context)
            self.condition.notify()

    def work(self):
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                context = self.queue.pop(0)
                self.current = context.run.run_id
            try:
                self.script(context)
            except Exception as error:
                # Use the Run hook for every event, including mock failures.
                if context.run.finished_at is None:
                    context.run._emit("stage.failed", {"optional": True, "elapsed_s": 0,
                                                      "message": str(error), "error": type(error).__name__}, stage="mock")
                    context.run.finish()
                context.state = "finished"
            finally:
                with self.condition:
                    self.current = None

    def sleep(self, seconds):
        time.sleep(seconds * self.pace)

    def script(self, ctx):
        run = ctx.run
        ctx.state = "processing"
        with run.stage("intake"):
            run.evidence("input_validation", {"width": ctx.size[0], "height": ctx.size[1],
                                               "unchanged_upload": True,
                                               "warning": None if ctx.size == (6080, 3040) else "Accepted 2:1 size differs from 6080×3040."},
                         stage="intake", actor="agent")
        with run.stage("views", model="py360convert", deadline_s=10):
            self.sleep(2)
            run.evidence("views", {"count": 8, "sky": True, "ground": True, "photographer_masked": 0.18}, stage="views", actor="agent")
        with run.stage("detect", model="YOLOE-26-L", optional=True, deadline_s=10):
            self.sleep(1)
            raise RuntimeError("Mock detector unavailable; the OCR stage runs on the full panorama instead.")
        with run.stage("read", model="PP-OCRv6-medium", deadline_s=30):
            self.sleep(4)
            if run.category["value"] != "non-urban":
                postcode = run.evidence("postcode", {"text": "4050-253", "country": "PT", "confidence": 0.94,
                                                     "box": {"yaw": 212.5, "pitch": -3.1, "w": 4.2, "h": 1.6},
                                                     "inference": "Invented Portuguese postcode observation for this mock."}, stage="read", model="PP-OCRv6-medium")
            else:
                postcode = run.evidence("text", {"text": "", "observation": "No text found in this mock"}, stage="read", model="PP-OCRv6-medium")
        with run.stage("describe", model="qwen3.5:9b", deadline_s=45):
            for i, item in enumerate(["Masonry visible", "River visible", "Licence plates readable"]):
                self.sleep(3)
                run.evidence("checklist", {"item": item, "answer": "yes" if i < 2 else "not_visible", "answered": i + 1, "total": 3}, stage="describe", model="qwen3.5:9b")
        candidates = [
            {"candidate_id": "c1", "lat": 41.1407, "lng": -8.6131, "role": "area", "source": "fixture:ribeira", "label": "Porto · Ribeira (invented)", "weight": 0.55, "accuracy_m": None, "extent_m": 1500, "country": "PT", "evidence": [postcode], "supports": [postcode], "contradicts": [], "details": {"invented": True}},
            {"candidate_id": "c2", "lat": 38.57, "lng": -7.91, "role": "area", "source": "fixture:alentejo", "label": "Alentejo (invented)", "weight": 0.30, "accuracy_m": None, "extent_m": None, "country": "PT", "evidence": [], "details": {"invented": True}},
            {"candidate_id": "c3", "lat": 38.90, "lng": -6.40, "role": "area", "source": "fixture:dehesa", "label": "Extremadura (invented)", "weight": 0.15, "accuracy_m": None, "extent_m": None, "country": "ES", "evidence": [], "details": {"invented": True}},
        ]
        with run.stage("fuse"):
            run.candidates(candidates)
        run.output([(41.1407, -8.6131)] * 10, method="coarse_candidate", uncertainty_m=1500,
                   uncertainty_source="source_estimate", source_role="area", sources=["fixture:ribeira"], note="Initial invented mock estimate, before any team interaction.")
        q1 = run.ask("Which part of the search area contains the camera?",
                     [{"label": "North half", "reason": "Covers the northern part of the agent's scope."},
                      {"label": "South half", "reason": "Covers the southern part of the agent's scope."},
                      {"label": "None of these: outside the area", "none": True}], kind="zone", gain=0.12,
                     scope=["Portugal · Spain · France", "Mock search area"])
        response = ctx.wait_question(q1)
        if response["status"] == "answered":
            # This is deliberately a soft update, never a hard exclusion.
            chosen = {"a": 0, "b": 1, "c": 2}[response["answer"]]
            candidates = [{**c, "weight": c["weight"] + (0.25 if i == chosen else 0)} for i, c in enumerate(candidates)]
            run.candidates(candidates)
        q2 = run.ask("Is there a broad arch visible in the scene?", ["Yes", "No", "Can't tell from here"], kind="feature")
        ctx.wait_question(q2)
        # Leave a real interval for a cue; the live timer shows this actual wait.
        with run.stage("spot", optional=True, model="ALIKED + LightGlue", deadline_s=60):
            self.sleep(30)
            run.skip_stage("reference_match", "The mock has no verified camera reference for the uploaded JPEG.")
        run.output([(41.1407, -8.6131)] * 10, method="coarse_candidate", uncertainty_m=1500,
                   uncertainty_source="source_estimate", source_role="area", sources=["fixture:ribeira"],
                   note="Invented mock output; no image match ran, so the uncertainty remains coarse.")
        run.export()
        ctx.state = "answer ready"
        with ctx.condition:
            ctx.condition.notify_all()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Do not print cues or uploaded contents.
        if "/events" not in str(args[0]):
            super().log_message(fmt, *args)

    def allowed_host(self):
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def context(self, run_id):
        ctx = self.server.worker.runs.get(run_id)
        if ctx is None:
            raise KeyError("Run not available in this mock session.")
        return ctx

    def do_GET(self):
        try:
            if not self.allowed_host():
                return self.json({"error": "Local host required."}, 403)
            url = urlsplit(self.path)
            if url.path == "/api/status":
                return self.json({"worker": "online", "mock": True, "gpu": {"used_gb": None, "total_gb": 16}, "models": [], "tile_source": None, "csrf_token": TOKEN})
            if url.path == "/api/runs":
                return self.json([{"run_id": run_id, "status": ctx.state, "special_one": ctx.run.special_one} for run_id, ctx in self.server.worker.runs.items()])
            match = re.fullmatch(r"/api/runs/([\w-]+)/(events|log\.json)", url.path)
            if match:
                ctx = self.context(match[1])
                if match[2] == "log.json":
                    ctx.run.export()
                    return self.json(json.loads(ctx.run.log_path.read_text()))
                after = int(self.headers.get("Last-Event-ID") or parse_qs(url.query).get("after", ["0"])[0])
                return self.stream(ctx, max(0, after))
            if url.path.startswith("/api/files/"):
                return self.send_file(ROOT / "runs/mock", unquote(url.path.removeprefix("/api/files/")))
            return self.json({"error": "Route not available."}, 404)
        except (KeyError, ValueError) as error:
            self.json({"error": str(error)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, root, relative):
        """One local run asset (JPEG, PNG or JSON) under root; nothing outside it."""
        file = (root / relative).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file() or file.suffix.lower() not in (".jpg", ".jpeg", ".png", ".json"):
            return self.json({"error": "File not available."}, 404)
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def write_body(self):
        """The body of an allowed local write, or None once an error response is sent (token, Origin, size)."""
        if not self.allowed_host() or not hmac.compare_digest(self.headers.get("X-Aqui-Token", ""), TOKEN):
            self.json({"error": "A local write token is required."}, 403)
            return None
        origin = self.headers.get("Origin")
        if origin and origin not in ("http://localhost:5178", "http://127.0.0.1:5178", f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            self.json({"error": "Origin is not the local operator console."}, 403)
            return None
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_UPLOAD + 65536:
            self.json({"error": "Request exceeds the local upload limit."}, 413)
            return None
        return self.rfile.read(length)

    def stream(self, ctx, after):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            while True:
                ctx.changed.clear()
                with ctx.run._lock:
                    pending = [event for event in ctx.run.events if event["seq"] > after]
                    finished = ctx.run.finished_at is not None
                    total = len(ctx.run.events)
                for event in pending:
                    self.wfile.write(f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
                    after = event["seq"]
                if finished and after >= total:
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    self.wfile.flush()
                    self.close_connection = True
                    return
                self.wfile.flush()
                if not pending:
                    ctx.changed.wait(timeout=15)
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        try:
            body = self.write_body()
            if body is None:
                return
            url = urlsplit(self.path)
            if url.path == "/api/runs":
                # Validated before creating a folder or starting the worker.
                filename, data, size, category, source, special = parse_upload(self.headers.get("Content-Type", ""), body)
                ctx = Context(filename, data, category, source, special, size)
                self.server.worker.add(ctx)
                return self.json({"run_id": ctx.run.run_id}, 201)
            match = re.fullmatch(r"/api/runs/([\w-]+)/(questions/([\w-]+)/(answer|skip)|cues|submit|priority)", url.path)
            if not match:
                return self.json({"error": "Route not available."}, 404)
            ctx = self.context(match[1])
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("The action needs a JSON object.")
            with ctx.condition:
                if ctx.run.finished_at is not None:
                    raise ValueError("This case is locked after submission.")
                if match[4] == "answer":
                    ctx.run.answer(match[3], payload.get("option_id"))
                elif match[4] == "skip":
                    ctx.run.skip(match[3])
                elif match[2] == "cues":
                    ctx.run.cue(validate_cue(payload.get("text")))
                    if ctx.state == "answer ready":
                        last = ctx.run.outputs[-1]
                        ctx.run.output([(c["lat"], c["lng"]) for c in last["coordinates"]], method=last["output_method"], uncertainty_m=last["position_uncertainty_m"], uncertainty_source=last["uncertainty_source"], source_role=last["source_role"], sources=last["sources"], note="The mock reissued the same estimate with the newly logged penalty snapshot.")
                elif match[2] == "submit":
                    if ctx.state != "answer ready" or not ctx.run.outputs:
                        raise ValueError("Wait for the worker's answer before submitting.")
                    last = ctx.run.outputs[-1]
                    if payload.get("output_id") != last["output_id"]:
                        raise ValueError("The current output changed; review the latest coordinate and snapshot.")
                    ctx.run._emit("run.submitted", {"output_id": last["output_id"], "coordinates": last["coordinates"], "penalty": last["penalty"]}, actor="team")
                    ctx.run.finish()
                    ctx.state = "submitted"
                elif match[2] == "priority":
                    with self.server.worker.condition:
                        if ctx in self.server.worker.queue:
                            self.server.worker.queue.remove(ctx)
                            self.server.worker.queue.insert(0, ctx)
                            ctx.run._emit("run.prioritised", {}, actor="agent")
                ctx.condition.notify_all()
                ctx.run.export()
            return self.json({"accepted": True})
        except (KeyError, ValueError, RuntimeError, TypeError) as error:
            self.json({"error": str(error)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--pace", type=float, default=0.12, help="Scale only scripted compute sleeps, never log timestamps.")
    args = parser.parse_args()
    if args.port in (8000, 8765, 8799) or not 0 < args.pace <= 10:
        parser.error("Choose an unused port and a pace above zero, at most 10.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.worker = Worker(args.pace)
    print(f"Aqui scripted mock: http://127.0.0.1:{args.port} · original uploads and real Run logs in runs/mock/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
