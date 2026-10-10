"""Tests for panoloc.runlog. Run from the repo root: python3 -m unittest discover -s tests"""
import json
import tempfile
import unittest

from panoloc.runlog import Run, StageTimeout

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def tick(self, seconds):
        self.now += seconds


class RunLogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.clock = FakeClock()

    def new_run(self, **kwargs):
        return Run(PANORAMA, self.dir, clock=self.clock, **kwargs)

    def test_answers_and_cues_cost_points_but_skips_do_not(self):
        run = self.new_run()
        q1 = run.ask("Which bank of the river is this?", ["North bank", "South bank"])
        q2 = run.ask("Is the pavement black and white stone?", ["Yes", "No"])
        run.skip(q1)
        self.assertEqual(run.penalties.multiplier, 1.0)
        run.answer(q2, "a")
        run.cue("The camera was held at head height.")
        self.assertAlmostEqual(run.penalties.multiplier, 0.95 * 0.8)
        run.conversion("Praça do Comércio", (38.7078, -9.1366))
        self.assertAlmostEqual(run.penalties.multiplier, 0.95 * 0.8 * 0.5)

    def test_each_output_keeps_the_penalty_in_force_when_it_was_produced(self):
        run = self.new_run()
        run.output([(38.7078, -9.1366)] * 10, method="coarse_candidate")
        q = run.ask("Which side of the square?", ["East", "West", "None of these"])
        run.answer(q, "b")
        run.output([(38.7080, -9.1370)] * 10, method="geographic_cell", uncertainty_m=25)
        self.assertEqual([o["penalty"]["multiplier"] for o in run.outputs], [1.0, 0.95])
        self.assertEqual(len(run.outputs[1]["coordinates"]), 10)

    def test_a_skip_is_final_and_carries_no_answer(self):
        run = self.new_run()
        q = run.ask("Which group of districts?", ["North", "Centre", "South", "Islands"], kind="zone")
        run.skip(q)
        self.assertEqual(run.events[-1]["type"], "question.skipped")
        self.assertEqual(run.events[-1]["payload"], {"question_id": q})
        self.assertEqual(run.questions[q]["answer"], None)
        with self.assertRaises(ValueError):
            run.answer(q, "a")

    def test_question_rules(self):
        run = self.new_run()
        for options in (["a", "b", "c", "d", "e"], ["only one"]):
            with self.assertRaises(ValueError):
                run.ask("How many options?", options)
        for text in ("Skip this if you are not sure: is it a church?", "If unsure, don't answer.",
                     "No reply means none of these. Which town?"):
            with self.assertRaises(ValueError):
                run.ask(text, ["Yes", "No"])
        with self.assertRaises(ValueError):
            run.ask("Duplicate IDs?", [{"id": "x", "label": "A"}, {"id": "x", "label": "B"}])
        q = run.ask("Which one?", ["A", {"label": "B", "links": {"maps": "https://maps.google.com/?q=38.7,-9.1"}}])
        self.assertEqual([o["id"] for o in run.questions[q]["options"]], ["a", "b"])
        with self.assertRaises(ValueError):
            run.answer(q, "z")
        run.answer(q, "a")
        with self.assertRaises(ValueError):
            run.answer(q, "b")
        with self.assertRaises(KeyError):
            run.skip("q99")
        self.assertEqual(run.penalties.answered_questions, 1)

    def test_cue_length_limit(self):
        run = self.new_run()
        with self.assertRaises(ValueError):
            run.cue("x" * 1001)
        run.cue("x" * 1000)
        self.assertEqual(run.penalties.cues, 1)

    def test_outputs_are_checked_lat_first(self):
        run = self.new_run()
        for bad in ([(38.7, -9.1)] * 11, [(-9.1, 238.7)], [], [(float("nan"), 0)]):
            with self.assertRaises(ValueError):
                run.output(bad)
        run.output([{"lat": 38.7, "lng": -9.1}, (40.4168, -3.7038)])
        self.assertEqual(run.outputs[0]["coordinates"],
                         [{"rank": 1, "lat": 38.7, "lng": -9.1}, {"rank": 2, "lat": 40.4168, "lng": -3.7038}])

    def test_a_failed_optional_stage_is_logged_and_the_run_goes_on(self):
        run = self.new_run()
        with run.stage("detect", optional=True, model="YOLOE-26-L"):
            raise RuntimeError("weights missing")
        with run.stage("geo", optional=True):
            raise StageTimeout("Overpass did not answer in 5 s")
        with self.assertRaises(RuntimeError):
            with run.stage("views"):
                raise RuntimeError("unreadable panorama")
        stage_types = [e["type"] for e in run.events if e["type"].startswith("stage.")]
        self.assertEqual(stage_types, ["stage.started", "stage.failed", "stage.started", "stage.timed_out",
                                       "stage.started", "stage.failed"])
        self.assertEqual(run.events[2]["payload"]["error"], "RuntimeError")

    def test_stage_timing_and_deadline(self):
        run = self.new_run()
        with run.stage("read", deadline_s=1):
            self.clock.tick(2.5)
        self.assertEqual(run.events[-1]["payload"], {"elapsed_s": 2.5, "over_deadline": True})
        self.assertEqual(run.events[-1]["t"], 2.5)

    def test_runs_share_nothing(self):
        a, b = self.new_run(), self.new_run()
        a.answer(a.ask("Which one?", ["A", "B"]), "a")
        self.assertNotEqual(a.run_id, b.run_id)
        self.assertNotEqual(a.dir, b.dir)
        self.assertEqual(b.penalties.multiplier, 1.0)
        self.assertEqual(b.questions, {})
        self.assertEqual([e["type"] for e in b.events], ["run.started"])
        with self.assertRaises(FileExistsError):
            Run("other.jpg", self.dir, run_id=a.run_id)

    def test_log_files(self):
        run = self.new_run(category="urban")
        run.evidence("postcode", {"text": "1100-148", "confidence": 0.9}, stage="read", model="PP-OCRv6-medium")
        run.output([(38.71, -9.13)] * 10, method="coarse_candidate")
        path = run.finish()
        lines = run.events_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["seq"] for line in lines], list(range(1, len(run.events) + 1)))
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["category"], {"value": "urban", "source": "inferred"})
        self.assertEqual(doc["final_output"]["output_id"], "o1")
        self.assertEqual((doc["events"][0]["type"], doc["events"][-1]["type"]), ("run.started", "run.finished"))
        self.assertEqual(doc["events"][1]["payload"]["evidence_id"], "e1")

    def test_nothing_is_logged_or_charged_after_finish(self):
        run = self.new_run()
        q = run.ask("Which one?", ["A", "B"])
        run.finish()
        with self.assertRaises(RuntimeError):
            run.cue("too late")
        with self.assertRaises(RuntimeError):
            run.answer(q, "a")
        self.assertEqual(run.penalties.snapshot()["multiplier"], 1.0)
        self.assertEqual(run.questions[q]["status"], "open")

    def test_category_source_must_match(self):
        with self.assertRaises(ValueError):
            self.new_run(category="urban", category_source="unknown")
        with self.assertRaises(ValueError):
            self.new_run(category="city")
        self.assertEqual(self.new_run().category, {"value": None, "source": "unknown"})
        self.assertEqual(self.new_run(category="non-urban", category_source="official").category,
                         {"value": "non-urban", "source": "official"})


if __name__ == "__main__":
    unittest.main()
