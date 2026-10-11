#!/usr/bin/env python3
"""Drive panoramas through the live app API with a simulated operator (TASKS.md T26, T29; evaluation only).

Uploads each panorama to the live backend (app/dev/live_server.py), follows its event stream, and
answers every question as the nominal operator would: the option holding the reference point, else the
complement ("None of these" / "Outside"), else a skip. References come only from panoloc.evaluate
(load_set), and only this process sees them. The app receives the image and option IDs, nothing else.
A reference wider than 1 km (an estimate) gets skips only. Per case, results.jsonl records the run ID,
stage times, questions answered and skipped, and errors, never reference coordinates.

  .venv/bin/python -I app/dev/drive_warmup.py [--set warmup] [--only 141,681] [--operator nominal|human|skip]
  then score the run folders: .venv/bin/python -I app/dev/drive_warmup.py score runs/app/batch-<time>
"""
import argparse
import http.client
import json
import math
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from panoloc import evaluate  # noqa: E402
from panoloc.scoring import haversine_m  # noqa: E402

HOST, PORT = "127.0.0.1", 8788
ORIGIN = f"http://{HOST}:{PORT}"
COARSE_M = 1000.0
RUN_TIMEOUT_S = 20 * 60
STICKY_SKIP = None  # --sticky-skip


def request(method, path, body=None, headers=None, timeout=30):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, json.loads(data or b"{}")


def upload(token, image):
    boundary = uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{image.name}\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n".encode() + image.read_bytes() + b"\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"special_one\"\r\n\r\nfalse\r\n".encode(),
        f"--{boundary}--\r\n".encode(),
    ]
    status, doc = request("POST", "/api/runs", b"".join(parts),
                          {"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Aqui-Token": token,
                           "Origin": ORIGIN}, timeout=120)
    if status != 201:
        raise RuntimeError(f"upload refused: {status} {doc}")
    return doc["run_id"]


def act(token, run_id, question_id, option_id):
    path = f"/api/runs/{run_id}/questions/{question_id}/" + ("skip" if option_id is None else "answer")
    body = json.dumps({} if option_id is None else {"option_id": option_id}).encode()
    status, doc = request("POST", path, body, {"Content-Type": "application/json", "X-Aqui-Token": token,
                                               "Origin": ORIGIN})
    if status >= 300:
        raise RuntimeError(f"{path}: {status} {doc}")


def events(run_id):
    """Yield the run's events from its SSE stream until the server says it ended."""
    conn = http.client.HTTPConnection(HOST, PORT, timeout=RUN_TIMEOUT_S)
    conn.request("GET", f"/api/runs/{run_id}/events?after=0", headers={"Accept": "text/event-stream"})
    resp = conn.getresponse()
    kind = None
    while True:
        line = resp.readline()
        if not line:
            return
        line = line.decode("utf-8").rstrip("\r\n")
        if line.startswith("event:"):
            kind = line[6:].strip()
        elif line.startswith("data:"):
            if kind == "end":
                return
            yield json.loads(line[5:])
            kind = None


class Nominal:
    """The option holding the reference point; else the complement; else a skip (panoloc.oracle 'nominal')."""

    def __init__(self, ref, zones):
        self.point = (ref.lat, ref.lng)
        self.coarse = ref.error_radius_m is not None and ref.error_radius_m > COARSE_M  # None: camera GPS (val)
        self.zones = zones
        self._loc = None

    def location(self):
        if self._loc is None and self.zones is not None:
            self._loc = self.zones.locate(*self.point) or False
        return self._loc or None

    def holds(self, o):
        lat, lng = self.point
        if o.get("cell"):
            import shapely.geometry
            return shapely.geometry.shape(o["cell"]).covers(shapely.geometry.Point(lng, lat))
        if o.get("zone_id"):
            loc = self.location()
            return loc is not None and o["zone_id"] in loc
        if o.get("point") is not None and o.get("radius_m") is not None:
            p = o["point"]
            return haversine_m(self.point, (p["lat"], p["lng"])) <= o["radius_m"]
        if o.get("bbox"):
            b = o["bbox"]
            return b["south"] <= lat <= b["north"] and b["west"] <= lng <= b["east"]
        return None  # no geometry: unknown

    def choose(self, payload):
        if self.coarse:
            return None, "coarse reference: skip"
        named = [o for o in payload["options"] if not o.get("complement")]
        complement = [o for o in payload["options"] if o.get("complement")]
        verdicts = [(o["id"], self.holds(o)) for o in named]
        if any(v is None for _, v in verdicts):
            return None, "an option without geometry: skip"
        inside = [oid for oid, v in verdicts if v]
        if inside:
            return inside[0], "holds the reference"
        if complement:
            return complement[0]["id"], "complement"
        return None, "no option holds it and no complement: skip"


class Human(Nominal):
    """panoloc.oracle's "human" mode over the app's JSON options: seeded per panorama, the nominal answer
    with probability 0.70, a uniformly random other option with 0.10, a skip otherwise (EVALUATION.md).
    sticky_skip p (oracle's T79 option, used for Gate C): a question identical to one skipped before (same
    kind and option labels) is skipped again with probability p, else answered at the same right/wrong odds."""

    def __init__(self, ref, zones, sticky_skip=None):
        super().__init__(ref, zones)
        from panoloc.oracle import HUMAN_RATES, HUMAN_SEED, human_seed
        import random
        self.rates = HUMAN_RATES
        self.rng = random.Random(human_seed(ref.key, HUMAN_SEED))
        self.sticky_skip = sticky_skip
        self.skipped = set()  # signatures of the questions skipped so far

    def choose(self, payload):
        correct, why = super().choose(payload)
        draw, pick = self.rng.random(), self.rng.random()
        right, wrong, _ = self.rates
        signature = (payload.get("kind"), tuple(str(o.get("label")) for o in payload["options"]))
        again = self.sticky_skip is not None and signature in self.skipped
        if again:
            if correct is not None and draw >= self.sticky_skip:
                draw = (draw - self.sticky_skip) / (1 - self.sticky_skip) * (right + wrong)
            else:
                draw = 1.0
        if correct is None or draw >= right + wrong:
            self.skipped.add(signature)
            return None, why if correct is None else "simulated skip again" if again else "simulated skip"
        if draw >= right:
            others = [o["id"] for o in payload["options"] if o["id"] != correct]
            return others[min(int(pick * len(others)), len(others) - 1)], "simulated mistake"
        return correct, why


def run_case(token, ref, path, operator_kind, zones):
    started = time.time()
    run_id = upload(token, path)
    if operator_kind == "nominal":
        operator = Nominal(ref, zones)
    elif operator_kind == "human":
        operator = Human(ref, zones, sticky_skip=STICKY_SKIP)
    else:
        operator = None
    record = {"key": ref.key, "run_id": run_id, "answered": 0, "skipped": 0, "decisions": [], "stages": {},
              "first_output_s": None, "error": None}
    for event in events(run_id):
        kind, p = event["type"], event["payload"]
        if kind == "stage.finished":
            record["stages"][event["stage"]] = p.get("elapsed_s")
        elif kind in ("stage.failed", "stage.timed_out"):
            record["stages"][event["stage"]] = f"{kind.split('.')[1]}: {p.get('error') or p.get('message')}"
        elif kind == "output.produced" and record["first_output_s"] is None:
            record["first_output_s"] = event["t"]
        elif kind == "question.asked":
            try:
                option_id, why = operator.choose(p) if operator else (None, "operator skips")
            except Exception as exc:  # never leave the single worker waiting
                option_id, why = None, f"operator error {type(exc).__name__}: {exc}"
            act(token, run_id, p["question_id"], option_id)
            record["answered" if option_id else "skipped"] += 1
            record["decisions"].append({"question": p["question_id"], "kind": p.get("kind"),
                                        "option": option_id, "why": why})
        elif kind == "run.finished":
            record["duration_s"] = p.get("duration_s")
    record["wall_s"] = round(time.time() - started, 1)
    return record


def drive(args):
    refs = evaluate.load_set(args.set)
    only = set(args.only.split(",")) if args.only else None
    cases = [r for r in refs.references if not only or r.key.rsplit("_", 1)[-1].split(".")[0] in only]
    out = Path(args.out or f"runs/app/batch-{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)
    try:
        from panoloc.zones import Zones
        zones = Zones.open()
    except Exception as exc:
        print(f"zones unavailable ({exc}); zone options fall back to skips", flush=True)
        zones = None
    status, doc = request("GET", "/api/status")
    token = doc["csrf_token"]
    print(f"{len(cases)} panoramas -> {out} (operator {args.operator}, sticky_skip {STICKY_SKIP})", flush=True)
    for i, ref in enumerate(cases, 1):
        path = ROOT / (ref.path or f"Data/Panorama Warm-Up/{ref.key}")
        try:
            record = run_case(token, ref, path, args.operator, zones)
        except Exception as exc:
            record = {"key": ref.key, "error": f"{type(exc).__name__}: {exc}"}
        with open(out / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        print(f"[{i}/{len(cases)}] {ref.key}: wall {record.get('wall_s')} s, first output "
              f"{record.get('first_output_s')} s, answered {record.get('answered')}, skipped "
              f"{record.get('skipped')}, error {record.get('error')}", flush=True)


def score(args):
    out = Path(args.out)
    records = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines() if line.strip()]
    folders = [p for r in records if r.get("run_id") for p in (ROOT / "runs/app").glob(f"*/{r['run_id']}")]
    refs = evaluate.load_set(args.set)
    report = evaluate.evaluate(refs, evaluate.load_predictions([str(f) for f in folders]))
    evaluate.write_report(report, out / "report.json")
    print(evaluate.format_table(report))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="drive", choices=("drive", "score"))
    ap.add_argument("out", nargs="?", help="batch folder (score), or where to write (drive)")
    ap.add_argument("--set", default="warmup")
    ap.add_argument("--only", help="comma-separated three-digit suffixes, e.g. 141,681")
    ap.add_argument("--operator", default="nominal", choices=("nominal", "human", "skip"))
    ap.add_argument("--sticky-skip", type=float, default=None, help="human mode: re-skip probability for a "
                    "question identical to one skipped before (Gate C uses 0.75)")
    args = ap.parse_args()
    global STICKY_SKIP
    STICKY_SKIP = args.sticky_skip
    (score if args.command == "score" else drive)(args)


if __name__ == "__main__":
    main()
