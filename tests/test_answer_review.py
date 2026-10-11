"""Answer review state, model decisions and penalties, with invented data and no model/network calls."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from panoloc import answer_review as review, pipeline
from panoloc.candidates import Candidate


def decision(action="keep", kind="", probabilities=None):
    return {"action": action, "explanation": "Check the visible street plate.",
            "question": "Can the street plate distinguish these places?", "question_kind": kind,
            "probabilities": probabilities or []}


class AnswerReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "IMG_20260115_143012_00_204.jpg"
        Image.fromarray(np.zeros((128, 256, 3), dtype=np.uint8)).save(self.path)
        self.models = pipeline.Models(ocr=False, vlm=False, retrieval=False)
        self.models.zones = lambda: None
        self.result = pipeline.run_panorama(self.path, self.models, runs_dir=Path(self.temp.name) / "runs",
                                            print_fn=lambda *a: None)
        self.run = self.result.review_state["run"]
        self.result.review_state["hypotheses"] = [
            Candidate(38.70, -9.14, "area", "invented:a", label="Invented A", weight=.7, extent_m=1000),
            Candidate(41.14, -8.61, "area", "invented:b", label="Invented B", weight=.3, extent_m=1000)]
        self.models.use["vlm"] = True
        def chat(system, text, schema, *, images=(), num_predict=0, timeout_s=None):
            raise AssertionError("Tests never call a model")
        self.models.vlm = lambda: SimpleNamespace(model="test:local", chat=chat)
        self.models.vlm_name = lambda: "test:local"
        self.images = patch.object(review.reason, "_images", return_value=(["invented-base64"], ["original"]))
        self.images.start()

    def tearDown(self):
        self.images.stop()
        self.temp.cleanup()

    def reopen(self):
        self.run.reopen(self.run.outputs[-1]["output_id"])

    def human_decision(self):
        offered = review._offered(self.result.review_state, None)
        kind = "place" if "place" in offered else "zone"
        options = offered[kind][0].options
        return decision("human", kind, [{"option_id": o.id, "probability": 1 / len(options)} for o in options])

    def test_keep_preserves_history_answer_and_penalty(self):
        original = self.result.output
        before = list(self.run.events)
        self.reopen()
        with patch.object(review, "_chat", return_value=decision()):
            review.continue_review(self.result, self.models, lambda q: self.fail("No question expected"))
        self.assertEqual(self.run.events[:len(before)], before)
        self.assertIs(self.result.output, original)
        self.assertEqual(len(self.run.outputs), 1)
        self.assertEqual(self.run.penalties.multiplier, 1)
        self.assertIsNotNone(self.run.finished_at)
        self.assertEqual(self.run.events[-1]["type"], "run.finished")

    def test_self_question_is_a_separate_photo_request_and_costs_nothing(self):
        self.reopen()
        replies = [decision("self"), {"places": [], "misleading_texts": [], "country": "unknown"}, decision()]
        with patch.object(review, "_chat", side_effect=replies) as chat:
            review.continue_review(self.result, self.models, lambda q: self.fail("A self-check must not ask a human"))
        self.assertEqual(chat.call_count, 3)
        self.assertIn("Examine this unresolved clue", chat.call_args_list[1].args[2])
        self.assertEqual(chat.call_args_list[1].args[4], ["invented-base64"])
        self.assertEqual(self.run.penalties.answered_questions, 0)
        self.assertFalse(self.run.questions)
        self.assertEqual(len(self.run.outputs), 1)

    def test_human_question_displays_model_probabilities_and_charges_only_on_answer(self):
        human = self.human_decision()
        self.reopen()
        before = self.run.outputs[0]["penalty"]
        with patch.object(review, "_chat", side_effect=[human, decision()]):
            review.continue_review(self.result, self.models, lambda q: q.options[0].id)
        asked = next(e["payload"] for e in self.run.events if e["type"] == "question.asked")
        self.assertAlmostEqual(sum(asked["agent_probabilities"].values()), 1)
        self.assertEqual(set(asked["agent_probabilities"]), {o["id"] for o in asked["options"]})
        self.assertEqual(before["multiplier"], 1)
        self.assertAlmostEqual(self.run.outputs[-1]["penalty"]["multiplier"], .95)
        self.assertEqual(self.run.penalties.answered_questions, 1)
        self.assertEqual(len(self.result.review_state["answers"]), 1)

    def test_self_check_uses_resolved_places_and_drops_extra_model_fields(self):
        from panoloc.fusion import Clue
        self.reopen()
        replies = [decision("self"), {"places": [{"name": "Invented station", "kind": "station", "country": "PT",
            "municipality": "Invented town", "probability": .9, "evidence": "Readable station sign",
            "private_reasoning": "This field must never reach the log."}], "misleading_texts": [], "country": "PT"}, decision()]
        clue = Clue("vlm:reason:1", "vlm_landmark", "vlm", .9,
                     [Candidate(38.71, -9.13, "landmark", "invented:station", country="PT", extent_m=100, weight=1)])
        with patch.object(review, "_chat", side_effect=replies), patch.object(pipeline, "_apply_reasoning", return_value=[clue]) as apply:
            review.continue_review(self.result, self.models, lambda q: self.fail("A self-check must be free"))
        self.assertIs(apply.call_args.args[0], self.result.review_state["base_clues"])
        self.assertNotIn("private_reasoning", apply.call_args.args[1]["places"][0])
        self.assertEqual(self.run.penalties.multiplier, 1)
        self.assertEqual(len(self.run.outputs), 2)
        self.assertAlmostEqual(self.result.output.lat, 38.71)
        self.assertNotIn("private_reasoning", self.run.log_path.read_text())

    def test_skip_is_neutral_and_stops_this_review(self):
        original = self.result.output
        human = self.human_decision()
        self.reopen()
        with patch.object(review, "_chat", return_value=human) as chat:
            review.continue_review(self.result, self.models, lambda q: None)
        self.assertEqual(chat.call_count, 1)
        self.assertIs(self.result.output, original)
        self.assertEqual(self.run.penalties.multiplier, 1)
        self.assertEqual(self.result.review_state["answers"], [])
        self.assertEqual(list(self.run.questions.values())[0]["status"], "skipped")

    def test_confirming_an_area_keeps_a_refined_camera_that_fits(self):
        from panoloc.candidates import Output
        precise = Output(38.7001, -9.1401, "coarse_candidate", "camera", ["refine:high"], 10, "source_estimate")
        self.reopen()
        precise.log(self.run)
        self.result.output = precise
        self.run.finish()
        human = self.human_decision()
        self.reopen()
        with patch.object(review, "_chat", side_effect=[human, decision()]):
            review.continue_review(self.result, self.models, lambda q: q.options[0].id)
        self.assertIs(self.result.output, precise)
        self.assertAlmostEqual(self.run.outputs[-1]["penalty"]["multiplier"], .95)

    def test_later_self_check_cannot_overrule_an_earlier_human_answer(self):
        human = self.human_decision()
        self.reopen()
        with patch.object(review, "_chat", side_effect=[human, decision()]):
            review.continue_review(self.result, self.models, lambda q: q.options[0].id)
        answered = self.result.output
        def contradictory_check(*args):
            self.result.review_state["hypotheses"] = [Candidate(48.85, 2.35, "area", "invented:far", weight=1)]
            return True
        self.reopen()
        with patch.object(review, "_chat", side_effect=[decision("self"), decision()]), patch.object(review, "_self_check", side_effect=contradictory_check):
            review.continue_review(self.result, self.models, lambda q: self.fail("No human question"))
        self.assertEqual((self.result.output.lat, self.result.output.lng), (answered.lat, answered.lng))
        self.assertAlmostEqual(self.run.penalties.multiplier, .95)

    def test_failed_model_keeps_the_answer_and_closes_the_run(self):
        original = self.result.output
        self.reopen()
        with patch.object(review, "_chat", side_effect=TimeoutError("model timed out")):
            review.continue_review(self.result, self.models, lambda q: self.fail("No human question"))
        self.assertIs(self.result.output, original)
        self.assertEqual(len(self.run.outputs), 1)
        self.assertIsNotNone(self.run.finished_at)
        self.assertTrue(any(e["type"] == "stage.failed" for e in self.run.events))
        self.assertTrue(any(e["payload"].get("kind") == "review_failed" for e in self.run.events))
        self.assertEqual(json.loads(self.run.log_path.read_text())["events"][-1]["type"], "run.finished")

    def test_failure_after_a_paid_answer_refreshes_its_receipt(self):
        original = self.result.output
        human = self.human_decision()
        self.reopen()
        with patch.object(review, "_chat", return_value=human), patch.object(pipeline, "_select_and_log", side_effect=ValueError("Invented selection failure")):
            review.continue_review(self.result, self.models, lambda q: q.options[0].id)
        self.assertIs(self.result.output, original)
        self.assertAlmostEqual(self.run.outputs[-1]["penalty"]["multiplier"], .95)
        self.assertEqual(self.run.penalties.answered_questions, 1)
        self.assertIsNotNone(self.run.finished_at)

    def test_invalid_probabilities_and_repeat_self_checks_fail_closed(self):
        offered = review._offered(self.result.review_state, None)
        valid = self.human_decision()
        for values in ([1, 1, 1, 1], [float("nan"), 0, 0, 0], [-1, 1, 1, 0]):
            bad = {**valid, "probabilities": [{**row, "probability": values[i]} for i, row in enumerate(valid["probabilities"])]}
            with self.assertRaises(ValueError):
                review.validate_decision(bad, offered, True)
        with self.assertRaises(ValueError):
            review.validate_decision(decision("self"), offered, False)

    def test_stale_and_duplicate_reopen_requests_are_rejected(self):
        with self.assertRaises(ValueError):
            self.run.reopen("old-output")
        self.reopen()
        with self.assertRaises(ValueError):
            self.run.reopen(self.run.outputs[-1]["output_id"])
