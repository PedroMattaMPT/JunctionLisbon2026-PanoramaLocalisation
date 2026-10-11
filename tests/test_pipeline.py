"""Tests for panoloc.pipeline with every model stage disabled. Run from the repo root:
.venv/bin/python -m unittest discover -s tests

The panorama is random noise under an invented filename; nothing here comes from the warm-up set.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc import pipeline
from panoloc.candidates import Candidate
from panoloc.pipeline import Models, run_panorama
from panoloc.runlog import Run

os.environ["PANOLOC_VLM"] = "local"  # tests never call a VLM plugin's remote API

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


def events(result):
    return json.loads(Path(result.log_path).read_text())["events"]


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / PANORAMA
        rng = np.random.default_rng(0)
        Image.fromarray(rng.integers(0, 255, (512, 1024, 3), dtype=np.uint8)).save(self.path)
        self.models = Models(ocr=False, vlm=False, retrieval=False)

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, **kwargs):
        return run_panorama(self.path, self.models, runs_dir=Path(self.tmp.name) / "runs", print_fn=lambda *a: None,
                            **kwargs)

    def test_autonomous_run_outputs_ten_coordinates(self):
        result = self.run_it(operator="never")
        self.assertEqual(len(result.output.coordinates()), 10)
        types = [e["type"] for e in events(result)]
        self.assertEqual(types.count("output.produced"), 1)
        self.assertNotIn("question.asked", types)
        self.assertEqual([e["stage"] for e in events(result) if e["type"] == "stage.skipped"],
                         ["read", "describe", "retrieve", "geoclip", "landmarks"])

    def test_skips_change_nothing(self):
        result = self.run_it(operator="skip", ask_anyway=True)
        ev = events(result)
        self.assertGreaterEqual(sum(e["type"] == "question.skipped" for e in ev), 1)
        self.assertEqual(sum(e["type"] == "output.produced" for e in ev), 1)
        self.assertEqual(ev[-1]["payload"]["penalty"]["multiplier"], 1.0)

    def test_answer_reselects_with_penalty(self):
        result = self.run_it(operator=lambda q: q.options[0].id, ask_anyway=True, max_questions=1)
        ev = events(result)
        outputs = [e["payload"] for e in ev if e["type"] == "output.produced"]
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0]["penalty"]["multiplier"], 1.0)
        self.assertAlmostEqual(outputs[1]["penalty"]["multiplier"], 0.95)

    def test_perception_cache_skips_the_models(self):
        cache = Path(self.tmp.name) / "cache"
        entry = cache / f"{self.path.name}-{self.path.stat().st_size}"
        entry.mkdir(parents=True)
        item = {"item_id": "i1", "sign_id": "s1", "kind": "language", "value": "french", "countries": ["FR"],
                "regions": [], "strength": "strong", "source": "reading"}
        (entry / "ocr.json").write_text(json.dumps({"signs": [{"sign_id": "s1", "confidence": 0.9}], "items": [item]}))
        landmark = {"name": "Invented Tower", "kind": "building", "confidence": "low", "views": ["h000"], "support": 1}
        (entry / "vlm.json").write_text(json.dumps({"model": "test", "landmarks": [landmark], "hints": []}))
        # OCR and VLM on, but nothing asked of either: the local VLM (the cache key names the model, D4)
        models = Models(retrieval=False, perception_cache=cache, vlm_model="qwen3.5:9b")
        result = run_panorama(self.path, models, runs_dir=Path(self.tmp.name) / "runs", print_fn=lambda *a: None)
        self.assertIsNone(models._ocr)
        self.assertFalse([e for e in events(result) if e["payload"].get("kind") == "vlm_checklist"])
        self.assertGreater(result.fused.country["FR"], 0.5)
        kinds = [e["payload"].get("kind") for e in events(result) if e["type"] == "evidence.added"]
        self.assertEqual(kinds.count("perception_cache"), 2)
        lm = next(e["payload"] for e in events(result) if e["payload"].get("kind") == "landmark_hypothesis")
        self.assertEqual(lm["place_kind"], "building")
        self.assertFalse([e for e in events(result) if e["type"] == "stage.failed"])

    def test_none_of_these_moves_to_zones(self):
        def none_of_these(q):  # a whole-area zone question has no complement: take its first cell
            return next((o.id for o in q.options if o.complement), q.options[0].id)

        result = self.run_it(operator=none_of_these, ask_anyway=True, max_questions=4)
        asked = [e["payload"] for e in events(result) if e["type"] == "question.asked"]
        self.assertEqual(asked[0]["kind"], "place")
        for first, second in zip(asked, asked[1:]):  # never the same place question twice in a row
            if first["kind"] == second["kind"] == "place":
                self.assertNotEqual([o["label"] for o in first["options"]], [o["label"] for o in second["options"]])
        if len(asked) > 1:
            self.assertEqual(asked[1]["kind"], "zone")

    def test_on_event_streams_every_event(self):
        seen = []
        result = run_panorama(self.path, self.models, runs_dir=Path(self.tmp.name) / "runs", print_fn=lambda *a: None,
                              on_event=seen.append)
        self.assertEqual([e["seq"] for e in seen], [e["seq"] for e in events(result)])

    def test_run_id_is_used(self):
        result = self.run_it(operator="never", run_id="r-console-123")
        self.assertEqual(result.run_id, "r-console-123")

    def test_output_fits_the_answer(self):
        # Three listed places and one unlisted: after "None of these", the output must be the unlisted one,
        # never a place the answer ruled out (T79 containment check)
        hyps = [Candidate(38.70, -9.14, "area", "t:a", label="A", weight=0.6, extent_m=500),
                Candidate(41.15, -8.61, "area", "t:b", label="B", weight=0.25, extent_m=500),
                Candidate(37.02, -7.93, "area", "t:c", label="C", weight=0.14, extent_m=500),
                Candidate(40.20, -8.41, "area", "t:d", label="D", weight=0.01, extent_m=500)]
        run = Run(PANORAMA, Path(self.tmp.name) / "runs")
        none_of_these = lambda q: next(o.id for o in q.options if o.complement)
        _, outputs = pipeline._ask_loop(run, hyps, none_of_these, category=None, urban_probability=0.5,
                                        max_questions=1, ask_anyway=True, print_fn=lambda *a: None)
        run.finish()
        self.assertEqual(len(outputs), 1)
        self.assertEqual((outputs[-1].lat, outputs[-1].lng), (40.20, -8.41))

    def test_outside_points_are_never_output(self):
        hyps = [Candidate(37.98, 13.67, "landmark", "t:sicily", label="Sicily", weight=0.9, extent_m=50),
                Candidate(38.70, -9.14, "area", "t:lisbon", label="Lisbon", weight=0.1, extent_m=500)]
        run = Run(PANORAMA, Path(self.tmp.name) / "runs")
        out, _ = pipeline._select_and_log(run, hyps, category=None, urban_probability=0.5, note="test")
        run.finish()
        self.assertEqual((out.lat, out.lng), (38.70, -9.14))

    def test_constraints_reach_cells_only_when_accepted(self):
        def new_style(hyps, constraints=None):
            return constraints

        def old_style(hyps):
            return "ok"

        answers = [("q1", "a"), ("q2", "d")]
        self.assertEqual(pipeline._constrained(new_style, [], answers=answers), answers)
        self.assertIsNone(pipeline._constrained(new_style, [], answers=[]))
        self.assertEqual(pipeline._constrained(old_style, [], answers=answers), "ok")

    def test_place_misses_hand_over_to_zones(self):
        # 24 landmarks with slowly falling weights (without the cap: six place questions in a row). An operator
        # that always answers "None of these" gets at most MAX_PLACE_MISSES in a row before zones take over
        hyps = [Candidate(37.2 + 0.25 * (i // 4), -8.8 + 0.3 * (i % 4), "landmark", f"t:{i}", label=f"P{i}",
                          weight=1.0 / (1 + 0.1 * i), extent_m=40) for i in range(24)]
        run = Run(PANORAMA, Path(self.tmp.name) / "runs")
        kinds = []

        def op(q):
            kinds.append(q.kind)
            return next((o.id for o in q.options if o.complement), q.options[0].id)

        pipeline._ask_loop(run, hyps, op, category="urban", urban_probability=0.5, max_questions=6, ask_anyway=True,
                           print_fn=lambda *a: None)
        run.finish()
        self.assertIn("zone", kinds)
        streak = max((len(r) for r in "".join("p" if k == "place" else "z" for k in kinds).split("z")), default=0)
        self.assertLessEqual(streak, pipeline.MAX_PLACE_MISSES)

    def test_point_built_inside_every_answer(self):
        # Only the three listed places exist and the team answers "None of these": the output must be a point
        # built inside the allowed area and outside every listed disc, not one of the ruled-out places
        try:
            from panoloc.zones import Zones
            zones = Zones.open()
        except Exception as exc:
            self.skipTest(f"zone index not built: {exc}")
        hyps = [Candidate(38.7223, -9.1393, "area", "t:lisbon", label="Lisbon", weight=0.5, extent_m=500),
                Candidate(41.1579, -8.6291, "area", "t:porto", label="Porto", weight=0.3, extent_m=500),
                Candidate(37.0194, -7.9304, "area", "t:faro", label="Faro", weight=0.2, extent_m=500)]
        run = Run(PANORAMA, Path(self.tmp.name) / "runs")
        asked = []

        def none_of_these(q):
            asked.append(q)
            return next(o.id for o in q.options if o.complement)

        _, outputs = pipeline._ask_loop(run, hyps, none_of_these, category=None, urban_probability=0.5,
                                        max_questions=1, ask_anyway=True, print_fn=lambda *a: None, zones=zones)
        run.finish()
        out = outputs[-1]
        self.assertIsNotNone(zones.locate(out.lat, out.lng))
        q = asked[0]
        self.assertTrue(q.option_for(Candidate(out.lat, out.lng, "area", "t:out")).complement)

    def test_operator_is_checked(self):
        with self.assertRaises(ValueError):
            self.run_it(operator="maybe")


if __name__ == "__main__":
    unittest.main()
