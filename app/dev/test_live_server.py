"""Smoke checks for the live backend with a stand-in pipeline: no models, no GPU.

.venv/bin/python -m unittest discover -s app/dev -p 'test_*.py'   (skipped under a Python without numpy)
The stand-in follows run_panorama's contract: its own Run, on_event, a blocking operator. Coordinates are invented.
"""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server

try:
    import live_server
    from panoloc import pipeline
except ImportError as exc:  # the mock's tests still run under system Python
    raise unittest.SkipTest(f"live backend needs the .venv: {exc}")


def stand_in(path, models=None, *, runs_dir="runs", operator="never", category=None, category_source=None,
             special_one=False, max_questions=4, ask_anyway=False, min_gain=0.05, print_fn=print, on_event=None):
    name = Path(path).name
    if name.startswith("early"):
        raise RuntimeError("stand-in failure before any Run")
    run = pipeline.Run(name, runs_dir, special_one=special_one, category=category, category_source=category_source,
                       on_event=on_event)
    try:
        with run.stage("prepare"):
            run.evidence("filename", {"valid": False, "observation": "stand-in"}, stage="prepare", actor="agent")
            run.progress("prepare", "Preparing stand-in panorama views.", completed=0, total=2)
        run.output([(38.7, -9.1)] * 10, method="coarse_candidate", source_role="area", sources=["stand-in"])
        if name.startswith("boom"):
            raise RuntimeError("stand-in failure outside a stage")
        places = [{"label": "Invented A", "point": {"lat": 38.70, "lng": -9.10}, "radius_m": 800},
                  {"label": "Invented B", "point": {"lat": 38.72, "lng": -9.14}, "radius_m": 600},
                  {"label": "None of these", "complement": True}]
        for text in ("First stand-in question?", "Second stand-in question?"):
            options = places if name.startswith("place") else ["Yes", "No"]
            q = SimpleNamespace(question_id=run.ask(text, options, kind="place" if name.startswith("place") else "feature"))
            option = operator(q)
            run.skip(q.question_id) if option is None else run.answer(q.question_id, option)
    finally:
        log_path = run.finish()
    return SimpleNamespace(timings={"total_s": 0.0}, log_path=log_path)


class Quiet(live_server.LiveHandler):
    def log_message(self, *args):
        pass


class LiveTests(unittest.TestCase):
    question_timeout = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aqui-live-check-")
        self.saved = server.ROOT, pipeline.run_panorama, pipeline.Run
        server.ROOT = Path(self.temp.name)
        pipeline.run_panorama = stand_in
        args = SimpleNamespace(no_ocr=True, no_vlm=True, no_retrieval=True, no_warm=True, ask_anyway=False,
                               min_gain=None, max_questions=4, question_timeout=self.question_timeout)
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
        self.http.daemon_threads = True
        self.http.worker = live_server.LiveWorker(args)
        self.http.dist = server.ROOT / "dist"
        self.http.tiles = None
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        self.image = Path(__file__).with_name("upload-test.jpg").read_bytes()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        server.ROOT, pipeline.run_panorama, pipeline.Run = self.saved
        self.temp.cleanup()

    def request(self, path, payload=None, token=True):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", **({"X-Aqui-Token": server.TOKEN} if token else {})}
        try:
            with urlopen(Request(self.base + path, data=body, headers=headers), timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def raw(self, path):
        """(status, headers, body bytes) of one GET."""
        try:
            with urlopen(self.base + path, timeout=10) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def upload(self, filename):
        boundary = "aqui-live-boundary"
        body = bytearray()
        for key, value in (("category", ""), ("category_source", "unknown"), ("special_one", "false")):
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body.extend(self.image + f"\r\n--{boundary}--\r\n".encode())
        request = Request(self.base + "/api/runs", data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Aqui-Token": server.TOKEN})
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 201)
            return json.load(response)["run_id"]

    def events(self, run_id, on_event=lambda e: None):
        """Read the SSE stream to its end; on_event may answer questions as they arrive."""
        received = []
        with urlopen(self.base + f"/api/runs/{run_id}/events?after=0", timeout=10) as response:
            while True:
                line = response.readline().decode().strip()
                if line.startswith("data: ") and line != "data: {}":
                    received.append(json.loads(line[6:]))
                    on_event(received[-1])
                if line == "event: end":
                    return received

    def test_answer_skip_log_and_cue(self):
        run_id = self.upload("IMG_stand_in.jpg")
        def respond(e):
            if e["type"] == "question.asked":
                q = e["payload"]["question_id"]
                if q == "q1":
                    self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q1/answer", {"option_id": "zz"})[0], 400)
                    self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q1/answer", {"option_id": "a"})[0], 200)
                    self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q1/skip", {})[0], 400)  # already resolved
                    status, body = self.request(f"/api/runs/{run_id}/cues", {"text": "The sign has blue lettering."})
                    self.assertEqual(status, 501)
                    self.assertIn("T78", body["error"])
                else:
                    self.assertEqual(self.request(f"/api/runs/{run_id}/questions/{q}/skip", {})[0], 200)
        events = self.events(run_id, respond)
        self.assertTrue(all(e["run_id"] == run_id for e in events))
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))
        types = [e["type"] for e in events]
        self.assertIn("stage.progress", types)
        self.assertIn("question.answered", types)
        self.assertIn("question.skipped", types)
        self.assertNotIn("cue.sent", types)
        self.assertEqual(types[-1], "run.finished")
        self.assertEqual(events[-1]["payload"]["penalty"]["multiplier"], 0.95)  # one answer; the skip is free
        status, log = self.request(f"/api/runs/{run_id}/log.json")
        self.assertEqual((status, log["run_id"], len(log["events"])), (200, run_id, len(events)))
        self.assertTrue((server.ROOT / "runs/app" / run_id / "IMG_stand_in.jpg").read_bytes() == self.image)
        self.assertEqual(self.request("/api/runs")[1][0]["status"], "finished")

    def test_failures_stay_visible_and_server_stays_up(self):
        for name in ("boom.jpg", "early.jpg"):
            run_id = self.upload(name)
            events = self.events(run_id)
            failed = [e for e in events if e["type"] == "stage.failed"]
            self.assertEqual([e["stage"] for e in failed], ["pipeline"], name)
            self.assertIn("stand-in failure", failed[0]["payload"]["message"])
            runs = {r["run_id"]: r for r in self.request("/api/runs")[1]}
            self.assertEqual(runs[run_id]["status"], "failed")
        self.assertEqual(self.request("/api/status")[0], 200)
        run_id = self.upload("IMG_after_failure.jpg")
        events = self.events(run_id, lambda e: e["type"] == "question.asked" and self.request(
            f"/api/runs/{run_id}/questions/{e['payload']['question_id']}/skip", {}))
        self.assertEqual(events[-1]["payload"]["penalty"]["multiplier"], 1)

    def test_skip_remaining_unblocks_the_worker(self):
        run_id = self.upload("IMG_stuck.jpg")
        queued = self.upload("IMG_queued.jpg")
        seen = {}
        def respond(e):
            if e["type"] == "question.asked" and e["payload"]["question_id"] == "q1":
                for _ in range(50):  # the operator marks the wait just after the event
                    status = self.request("/api/status")[1]
                    if status["current_question"]:
                        break
                    time.sleep(0.02)
                seen["status"] = status
                seen["runs"] = {r["run_id"]: r for r in self.request("/api/runs")[1]}
                self.assertEqual(self.request(f"/api/runs/{run_id}/skip-remaining", {}, token=False)[0], 403)
                seen["skip"] = self.request(f"/api/runs/{run_id}/skip-remaining", {})
        events = self.events(run_id, respond)
        self.assertEqual(seen["status"]["current"], run_id)
        self.assertEqual(seen["status"]["current_question"]["question_id"], "q1")
        self.assertEqual(seen["status"]["current_question"]["text"], "First stand-in question?")
        self.assertEqual(seen["status"]["queue"], [queued])
        self.assertEqual(seen["runs"][queued]["position"], 1)
        self.assertEqual(seen["runs"][run_id]["question"]["question_id"], "q1")
        self.assertEqual(seen["skip"], (200, {"accepted": True, "open_question": "q1"}))
        types = [e["type"] for e in events]
        self.assertEqual(types.count("question.skipped"), 2)
        self.assertNotIn("question.answered", types)
        audit = [e["payload"] for e in events if e["type"] == "operator.auto_skip"]
        self.assertEqual([(a["question_id"], a["reason"]) for a in audit], [("q1", "skip_remaining"), ("q2", "skip_remaining")])
        self.assertLess(types.index("operator.auto_skip"), types.index("question.skipped"))  # the reason comes first
        self.assertEqual(events[-1]["payload"]["penalty"]["multiplier"], 1)  # skips are free
        self.assertEqual(self.request(f"/api/runs/{run_id}/skip-remaining", {})[0], 400)  # finished
        self.assertTrue(self.request("/api/runs")[1][0]["skip_remaining"])
        # The queued upload then runs with its own questions open, untouched by the other run's skip.
        later = self.events(queued, lambda e: e["type"] == "question.asked" and self.request(
            f"/api/runs/{queued}/questions/{e['payload']['question_id']}/answer", {"option_id": "a"}))
        self.assertEqual([e["type"] for e in later].count("question.answered"), 2)
        self.assertNotIn("operator.auto_skip", [e["type"] for e in later])

    def test_console_is_served_with_the_api(self):
        dist = server.ROOT / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<!doctype html><title>Aqui</title>")
        (dist / "assets" / "app-1234.js").write_text("console.log('aqui')")
        status, headers, body = self.raw("/")
        self.assertEqual((status, headers["Content-Type"], body), (200, "text/html; charset=utf-8", b"<!doctype html><title>Aqui</title>"))
        status, headers, _ = self.raw("/assets/app-1234.js")
        self.assertEqual((status, headers["Content-Type"]), (200, "text/javascript; charset=utf-8"))
        self.assertIn("immutable", headers["Cache-Control"])
        self.assertEqual(self.raw("/queue")[2], b"<!doctype html><title>Aqui</title>")  # page paths load the app
        self.assertEqual(self.raw("/missing.js")[0], 404)
        self.assertEqual(self.raw("/%2e%2e/%2e%2e/etc/passwd")[0], 404)
        self.assertEqual(self.request("/api/status")[0], 200)  # same origin as the page


class TimeoutTests(LiveTests):
    """The same server with --question-timeout: an unanswered question becomes a logged, free skip."""
    question_timeout = 0.4

    def test_unanswered_questions_time_out(self):
        run_id = self.upload("IMG_nobody_home.jpg")
        start = time.monotonic()
        events = self.events(run_id)
        self.assertLess(time.monotonic() - start, 5)
        audit = [e["payload"] for e in events if e["type"] == "operator.auto_skip"]
        self.assertEqual([(a["question_id"], a["reason"], a["timeout_s"]) for a in audit], [("q1", "timeout", 0.4), ("q2", "timeout", 0.4)])
        self.assertEqual([e["type"] for e in events].count("question.skipped"), 2)
        self.assertEqual(events[-1]["payload"]["penalty"]["multiplier"], 1)
        self.assertEqual(self.request("/api/status")[1]["question_timeout_s"], 0.4)

    # Inherited tests answer at once, well inside the timeout; skip-remaining is covered above.
    test_console_is_served_with_the_api = None


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Upstream(BaseHTTPRequestHandler):
    """A stand-in tile server: a PNG for every path, and it records the User-Agent it saw."""
    seen = []

    def do_GET(self):
        Upstream.seen.append((self.path, self.headers.get("User-Agent")))
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PNG)))
        self.end_headers()
        self.wfile.write(PNG)

    def log_message(self, *args):
        pass


class TileTests(LiveTests):
    """The caching tile proxy: miss then hit, a polite User-Agent, prefetch, and a fast clean failure offline."""

    def setUp(self):
        super().setUp()
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        layers = {"streets": {**live_server.tilemod.LAYERS["streets"], "url": f"http://127.0.0.1:{self.upstream.server_port}/{{z}}/{{x}}/{{y}}.png"},
                  "satellite": {**live_server.tilemod.LAYERS["satellite"], "url": "http://127.0.0.1:9/{z}/{y}/{x}"}}  # nothing listens on port 9
        self.http.tiles = live_server.tilemod.TileProxy(server.ROOT / "tiles", layers=layers, timeout=2, log=lambda *a: None)
        Upstream.seen = []

    def tearDown(self):
        self.upstream.shutdown()
        self.upstream.server_close()
        super().tearDown()

    def test_tiles_are_cached_prefetched_and_fail_fast(self):
        status = self.request("/api/status")[1]
        self.assertEqual([l["id"] for l in status["tile_layers"]], ["streets", "satellite"])
        self.assertEqual(status["tile_source"], "/api/tiles/streets/{z}/{x}/{y}")
        code, headers, body = self.raw("/api/tiles/streets/12/1950/1548")
        self.assertEqual((code, headers["X-Tile-Cache"], headers["Content-Type"], body), (200, "miss", "image/png", PNG))
        code, headers, body = self.raw("/api/tiles/streets/12/1950/1548.png")
        self.assertEqual((code, headers["X-Tile-Cache"], body), (200, "hit", PNG))
        self.assertEqual(len(Upstream.seen), 1)  # the second came from runs/app/tiles
        self.assertIn("JunctionX Lisbon 2026", Upstream.seen[0][1])
        self.assertEqual(self.raw("/api/tiles/streets/3/9/0")[0], 404)  # outside the zoom-3 grid
        self.assertEqual(self.raw("/api/tiles/nope/1/0/0")[0], 404)
        hotlink = Request(self.base + "/api/tiles/streets/12/1950/1548", headers={"Sec-Fetch-Site": "cross-site"})
        with self.assertRaises(HTTPError) as refused:
            urlopen(hotlink, timeout=5)
        self.assertEqual(refused.exception.code, 403)  # another web page can't use the proxy
        # Offline layer: a clean JSON error within the timeout, then the breaker answers at once.
        start = time.monotonic()
        for y in range(4):
            code, _, body = self.raw(f"/api/tiles/satellite/12/1950/{1548 + y}")
            self.assertEqual(code, 504)
            self.assertIn("unavailable", json.loads(body)["error"])
        code, _, body = self.raw("/api/tiles/satellite/12/1950/1600")
        self.assertEqual(code, 503)
        self.assertLess(time.monotonic() - start, 3)
        # A cached tile is served even while its layer is unreachable.
        cached = server.ROOT / "tiles/satellite/12/1950/1700.jpg"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)
        code, headers, _ = self.raw("/api/tiles/satellite/12/1950/1700")
        self.assertEqual((code, headers["X-Tile-Cache"], headers["Content-Type"]), (200, "hit", "image/jpeg"))
        # Prefetch: the tiles behind an open place question, for the layer on screen; token required.
        run_id = self.upload("place_question.jpg")
        result = {}
        def respond(e):
            if e["type"] == "question.asked" and e["payload"]["question_id"] == "q1":
                body = {"run_id": run_id, "question_id": "q1", "layer": "streets"}
                self.assertEqual(self.request("/api/tiles/prefetch", body, token=False)[0], 403)
                result["prefetch"] = self.request("/api/tiles/prefetch", body)
                for _ in range(100):
                    if self.http.tiles.jobs.empty() and len(Upstream.seen) > 1:
                        break
                    time.sleep(0.05)
            if e["type"] == "question.asked":
                self.request(f"/api/runs/{run_id}/questions/{e['payload']['question_id']}/skip", {})
        self.events(run_id, respond)
        code, body = result["prefetch"]
        self.assertEqual(code, 200)
        self.assertGreater(body["queued"], 4)
        self.assertLessEqual(body["queued"], live_server.tilemod.PREFETCH_CAP)
        time.sleep(0.3)
        self.assertTrue(all(int(path.split("/")[1]) <= 16 for path, _ in Upstream.seen[1:]))
        self.assertGreater(len(list((server.ROOT / "tiles/streets").rglob("*.png"))), 4)

    test_answer_skip_log_and_cue = test_failures_stay_visible_and_server_stays_up = None
    test_skip_remaining_unblocks_the_worker = test_console_is_served_with_the_api = None


if __name__ == "__main__":
    unittest.main()
