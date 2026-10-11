"""Standard-library checks for the mock HTTP boundary and real Run ledger.

Run from the repo: python3 -m unittest discover -s app/dev -p 'test_*.py'
All JPEGs and coordinates in these tests are invented.
"""
import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server

class QuietHandler(server.Handler):
    def log_message(self, *args):
        pass


class ValidationTests(unittest.TestCase):
    def test_cues(self):
        self.assertEqual(server.validate_cue("The sign has blue lettering."), "The sign has blue lettering.")
        for text in ("", "x" * 1001, "Porto", "big wave surfing", "41.14, -8.61"):
            with self.assertRaises(ValueError):
                server.validate_cue(text)

    def test_jpeg_frame(self):
        image = Path(__file__).with_name("upload-test.jpg").read_bytes()
        self.assertEqual(server.jpeg_size(image), (32, 16))
        for invalid in (b"not jpeg", image[:-2]):
            with self.assertRaises(ValueError):
                server.jpeg_size(invalid)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aqui-mock-check-")
        self.old_root = server.ROOT
        server.ROOT = Path(self.temp.name)
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.http.daemon_threads = True
        self.http.worker = server.Worker(0.002)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        self.image = Path(__file__).with_name("upload-test.jpg").read_bytes()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        server.ROOT = self.old_root
        self.temp.cleanup()

    def request(self, path, payload=None, token=True, origin=None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Aqui-Token"] = server.TOKEN
        if origin:
            headers["Origin"] = origin
        request = Request(self.base + path, data=body, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def start_run(self):
        boundary = "aqui-test-boundary"
        body = bytearray()
        for key, value in (("category", "urban"), ("category_source", "inferred"), ("special_one", "false")):
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="invented.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body.extend(self.image)
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        with urlopen(Request(self.base + "/api/runs", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Aqui-Token": server.TOKEN}), timeout=5) as response:
            self.assertEqual(response.status, 201)
            return json.load(response)["run_id"]

    def wait_for(self, run_id, predicate):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            log = self.request(f"/api/runs/{run_id}/log.json")[1]
            if predicate(log):
                return log
            time.sleep(0.01)
        self.fail("The scripted worker did not reach the expected logged state.")

    def finish_neutrally(self, run_id):
        for q in ("q1", "q2"):
            self.wait_for(run_id, lambda log: any(e["type"] == "question.asked" and e["payload"]["question_id"] == q for e in log["events"]))
            self.assertEqual(self.request(f"/api/runs/{run_id}/questions/{q}/skip", {})[0], 200)
        self.wait_for(run_id, lambda log: len([e for e in log["events"] if e["type"] == "output.produced"]) == 2)
        self.assertEqual(self.request(f"/api/runs/{run_id}/submit", {"output_id": "o2"})[0], 200)

    def test_run_ledger_and_sse_resume(self):
        run_id = self.start_run()
        before = self.wait_for(run_id, lambda log: any(e["type"] == "question.asked" for e in log["events"]))
        candidates = [e for e in before["events"] if e["type"] == "candidates.updated"][-1]["payload"]
        self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q1/skip", {})[0], 200)
        self.wait_for(run_id, lambda log: any(e["type"] == "question.asked" and e["payload"]["question_id"] == "q2" for e in log["events"]))
        self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q2/answer", {"option_id": "invalid"})[0], 400)
        self.assertEqual(self.request(f"/api/runs/{run_id}/cues", {"text": "The sign has blue lettering."})[0], 200)
        self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q2/answer", {"option_id": "a"})[0], 200)
        self.assertEqual(self.request(f"/api/runs/{run_id}/questions/q2/answer", {"option_id": "b"})[0], 400)
        log = self.wait_for(run_id, lambda log: len([e for e in log["events"] if e["type"] == "output.produced"]) == 2)
        outputs = [e for e in log["events"] if e["type"] == "output.produced"]
        self.assertEqual([e["payload"]["penalty"]["multiplier"] for e in outputs], [1, 0.76])
        self.assertEqual([e for e in log["events"] if e["type"] == "candidates.updated"][-1]["payload"], candidates)
        self.assertEqual(self.request(f"/api/runs/{run_id}/submit", {"output_id": "o1"})[0], 400)
        self.assertEqual(self.request(f"/api/runs/{run_id}/submit", {"output_id": "o2"})[0], 200)
        log = self.request(f"/api/runs/{run_id}/log.json")[1]
        self.assertEqual(log["events"][-1]["type"], "run.finished")
        self.assertEqual([e["seq"] for e in log["events"]], list(range(1, len(log["events"]) + 1)))
        actual = server.ROOT / "runs/mock" / run_id / "invented.jpg"
        self.assertEqual(hashlib.sha256(actual.read_bytes()).digest(), hashlib.sha256(self.image).digest())
        after = log["events"][-1]["seq"] - 1
        with urlopen(Request(self.base + f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(after)}), timeout=5) as response:
            received = []
            while True:
                line = response.readline().decode().strip()
                if line.startswith("data: ") and line != "data: {}":
                    received.append(json.loads(line[6:]))
                if line == "event: end":
                    break
            self.assertEqual([e["seq"] for e in received], [after + 1])

    def test_local_write_boundary(self):
        self.assertEqual(self.request("/api/runs", {}, token=False)[0], 403)
        self.assertEqual(self.request("/api/runs", {}, origin="https://untrusted.invalid")[0], 403)
        self.assertEqual(self.request("/api/files/%2e%2e/%2e%2e/README.md")[0], 404)

    def test_one_worker_and_queue_priority(self):
        first = self.start_run()
        self.wait_for(first, lambda log: any(e["type"] == "question.asked" for e in log["events"]))
        second, third = self.start_run(), self.start_run()
        self.assertEqual(self.request(f"/api/runs/{third}/priority", {})[0], 200)
        self.assertEqual(self.http.worker.current, first)
        self.assertEqual([ctx.run.run_id for ctx in self.http.worker.queue], [third, second])
        self.finish_neutrally(first)
        self.wait_for(third, lambda log: any(e["type"] == "question.asked" for e in log["events"]))
        self.assertEqual(self.http.worker.current, third)
        self.finish_neutrally(third)
        self.finish_neutrally(second)


if __name__ == "__main__":
    unittest.main()
