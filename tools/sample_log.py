#!/usr/bin/env python3
"""Write a sample run log with panoloc.runlog, to show the organisers our JSON format (TASKS.md T12).

Everything in it is invented: the panorama name comes from design_system_prompt.md and is not a
warm-up file, and no warm-up reference goes into it. The run covers every interaction type the
rules mention: an optional stage that fails, evidence, candidates, an initial output, a skipped
question, an answered question (x0.95), a cue (x0.8) and a refined output with its penalty snapshot.
Stage times are simulated (the sample does no real work), so t and elapsed_s look like a real run's.

Usage (from the repo root):  python3 tools/sample_log.py [--out runs/sample]
Prints the path of log.json; events.jsonl sits next to it.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from panoloc.runlog import Run  # noqa: E402


class SimulatedClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="runs/sample", help="folder for the run (default: runs/sample)")
    args = ap.parse_args()

    clock = SimulatedClock()
    run = Run("IMG_20260115_143012_00_204.jpg", args.out, category=None,
              versions={"vlm": "qwen3.5:9b", "ocr": "PP-OCRv6-medium"}, clock=clock)
    with run.stage("views"):
        clock.wait(3.1)
    with run.stage("read", model="PP-OCRv6-medium"):
        clock.wait(11.8)
        run.evidence("postcode", {"text": "1100-148", "country": "PT", "confidence": 0.94,
                                  "box": {"yaw": 212.5, "pitch": -3.1, "w": 4.2, "h": 1.6}},
                     stage="read", model="PP-OCRv6-medium")
    with run.stage("detect", optional=True, model="YOLOE-26-L"):
        clock.wait(0.4)
        raise RuntimeError("detector weights not loaded (sample of a failed optional stage)")
    with run.stage("describe", model="qwen3.5:9b"):
        clock.wait(38.5)
        run.evidence("landmark_hypothesis", {"name": "arcaded square by a river", "not_visible": ["plates"]},
                     stage="describe", model="qwen3.5:9b")
    run.candidates([
        {"candidate_id": "c1", "lat": 38.7078, "lng": -9.1366, "weight": 0.55, "role": "area", "source": "geonames:postcode"},
        {"candidate_id": "c2", "lat": 41.1414, "lng": -8.6110, "weight": 0.30, "role": "area", "source": "knn:osv5m"},
        {"candidate_id": "c3", "lat": 37.0194, "lng": -7.9304, "weight": 0.15, "role": "area", "source": "knn:osv5m"},
    ])
    run.output([(38.7078, -9.1366)] * 10, method="coarse_candidate", uncertainty_m=1500,
               uncertainty_source="source_estimate", note="initial answer, before any question")

    zone = run.ask("Which part of the search area is the camera in?",
                   [{"label": "North half", "detail": "north of 38.7078 N"},
                    {"label": "South half", "detail": "south of 38.7078 N"},
                    {"label": "None of these: outside the area"}], kind="zone")
    clock.wait(45.0)
    run.skip(zone)
    feature = run.ask("Is there a large arch on the north side of the square?",
                      ["Yes", "No", "Can't tell from here"], kind="feature")
    clock.wait(30.0)
    run.answer(feature, "a")
    clock.wait(20.0)
    run.cue("The camera was held at head height.")
    clock.wait(6.2)
    run.candidates([
        {"candidate_id": "c1", "lat": 38.7076, "lng": -9.1365, "weight": 0.9, "role": "camera", "source": "cell:q2"},
    ])
    run.output([(38.7076, -9.1365)] * 10, method="geographic_cell", uncertainty_m=25,
               uncertainty_source="geometric_bound", note="refined after the answered question")
    print(run.finish())


if __name__ == "__main__":
    main()
