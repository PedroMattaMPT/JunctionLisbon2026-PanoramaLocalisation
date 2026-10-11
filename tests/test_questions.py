"""Tests for panoloc.questions. Run from the repo root: python3 -m unittest discover -s tests

Every coordinate here is invented; none comes from the warm-up set.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from panoloc import questions
from panoloc.candidates import Candidate
from panoloc.questions import (ALLOWED_AREA, Box, Option, Question, apply_answer, ask_operator, cell_bound_m,
                               expected_gain, feature_question, place_question, zone_question)
from panoloc.runlog import Run
from panoloc.scoring import best_point, haversine_m

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


def cand(lat, lng, weight=1.0, role="camera", label="", **kwargs):
    return Candidate(lat, lng, role, f"test:{lat},{lng}", label=label, weight=weight, **kwargs)


# Spread over Iberia and France; no two share a latitude or a longitude, so every cut can split them.
SPREAD = [cand(40.10, -8.20), cand(41.52, -6.93), cand(39.21, -7.44), cand(42.33, -3.12),
          cand(37.64, -4.41), cand(43.95, 2.27), cand(46.43, 4.96), cand(38.76, -1.58)]


def far_apart(west_weight, east_weight):
    """Two hypotheses about 490 km apart."""
    return [cand(40.10, -8.20, west_weight, label="West spot"), cand(42.33, -3.12, east_weight, label="East spot")]


def grid(box, n=11):
    """n x n points over a box, edges and corners included (interpolated so the far edges stay exact)."""
    steps = [i / (n - 1) for i in range(n)]
    return [(box.south * (1 - s) + box.north * s, box.west * (1 - t) + box.east * t) for s in steps for t in steps]


def square_degrees(box):
    return (box.north - box.south) * (box.east - box.west)


class Scripted:
    """An input_fn that replays the team's keystrokes, then reaches end of input."""

    def __init__(self, *lines):
        self.lines, self.prompts = list(lines), []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


class PlaceQuestionTest(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            cand(40.1000, -8.2000, 0.30, "landmark", "Old bridge"),
            cand(40.1020, -8.2000, 0.20, "camera", "Bridge photo"),  # 222 m from the bridge: the same place
            cand(41.5200, -6.9300, 0.15, "area", "Hill town", extent_m=900),
            cand(39.2100, -7.4400, 0.12, "camera", "Roadside photo"),
            cand(42.3300, -3.1200, 0.10, "landmark", "Chapel"),
            cand(37.6400, -4.4100, 0.0, "area", "Unsupported town"),
        ]

    def test_up_to_three_distinct_places_and_none_of_these(self):
        q = place_question(self.candidates, min_separation_m=500)
        self.assertEqual([o.id for o in q.options], ["a", "b", "c", "d"])
        self.assertEqual([o.label for o in q.options], ["Old bridge", "Hill town", "Roadside photo", "None of these"])
        self.assertTrue(q.options[-1].complement)
        self.assertIsNone(q.options[-1].point)
        places = q.options[:-1]
        for i, a in enumerate(places):
            for b in places[i + 1:]:
                distance = haversine_m(a.latlng, b.latlng)
                self.assertGreaterEqual(distance, 500)
                self.assertLessEqual(a.radius_m + b.radius_m, distance)  # the options never overlap
        self.assertEqual([o.radius_m for o in places], [250.0, 900.0, 250.0])
        self.assertEqual(len(place_question(self.candidates, k=1).options), 2)
        for k in (0, 4):
            with self.assertRaises(ValueError):
                place_question(self.candidates, k=k)
        with self.assertRaises(ValueError):
            place_question([cand(40.0, -8.0, 0.0)])  # nothing supported to offer

    def test_each_place_says_what_its_point_marks(self):
        a, b, c = place_question(self.candidates).options[:3]
        self.assertEqual((a.point_role, b.point_role, c.point_role), ("landmark", "area", "camera"))
        self.assertIn("not where the camera stood", a.detail)
        self.assertIn("not a camera position", b.detail)
        self.assertIn("a camera position: the GPS of a reference photo", c.detail)
        self.assertIn("within about 900 m", b.detail)
        self.assertEqual(a.to_dict()["point_role"], "landmark")

    def test_every_hypothesis_falls_in_exactly_one_option(self):
        q = place_question(self.candidates)
        places = q.options[:-1]
        for c in self.candidates:
            holding = [o for o in places if haversine_m(o.latlng, c.point) <= o.radius_m]
            self.assertLessEqual(len(holding), 1)
            self.assertIs(q.option_for(c), holding[0] if holding else q.options[-1])
        self.assertEqual(q.option_for(self.candidates[1]).id, "a")
        self.assertEqual(q.option_for({"lat": 40.1015, "lng": -8.2}).id, "a")
        self.assertEqual(q.option_for((44.0, 1.0)).id, "d")
        self.assertEqual(q.options[0].covers, ["test:40.1,-8.2", "test:40.102,-8.2"])
        self.assertEqual(sum(len(o.covers) for o in q.options), len(self.candidates))
        self.assertAlmostEqual(q.options[0].support, 0.5 / 0.87)
        self.assertAlmostEqual(sum(o.support for o in q.options), 1.0)

    def test_options_serialise_to_what_run_ask_takes_with_links(self):
        q = place_question(far_apart(0.5, 0.5))
        options = q.option_dicts()
        json.dumps(options)
        self.assertEqual(options[0]["point"], {"lat": 40.1, "lng": -8.2})
        self.assertEqual(options[0]["links"]["google_maps"],
                         "https://www.google.com/maps/search/?api=1&query=40.1,-8.2")
        self.assertEqual(options[0]["links"]["street_view"],
                         "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=40.1,-8.2")
        self.assertEqual(options[0]["street_view_coverage"], "unchecked")
        self.assertNotIn("links", options[-1])
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp)
            question_id = run.ask(q.text, options, kind=q.kind, **q.log_details())
            self.assertEqual(run.questions[question_id]["options"][1]["label"], "East spot")


class ZoneQuestionTest(unittest.TestCase):
    def assert_cells_cover_the_scope(self, q):
        cells = [o for o in q.options if not o.complement]
        for o in cells:
            self.assertTrue(q.scope.contains_box(o.bbox))
            self.assertTrue(o.bbox.contains(o.latlng))
            for p in o.bbox.corners() + grid(o.bbox):
                self.assertGreaterEqual(o.bound_m, haversine_m(o.latlng, p))
        for i, a in enumerate(cells):
            for b in cells[i + 1:]:
                self.assertFalse(a.bbox.overlaps(b.bbox))
        self.assertAlmostEqual(sum(square_degrees(o.bbox) for o in cells), square_degrees(q.scope))
        for p in grid(q.scope, 23):
            self.assertTrue(any(o.bbox.contains(p) for o in cells))
        self.assertEqual(len({o.label for o in q.options}), len(q.options))

    def test_whole_area_gets_four_cells_with_equal_weight(self):
        q = zone_question(SPREAD)
        self.assertEqual(q.scope, ALLOWED_AREA)
        self.assertEqual(len(q.options), 4)
        self.assertFalse(any(o.complement for o in q.options))
        self.assert_cells_cover_the_scope(q)
        for c in SPREAD:
            holding = [o for o in q.options if o.bbox.contains(c.point)]
            self.assertEqual(len(holding), 1)
            self.assertIs(q.option_for(c), holding[0])
        self.assertEqual([o.support for o in q.options], [0.25] * 4)

    def test_sub_area_gets_three_cells_and_outside(self):
        scope = {"south": 37.0, "west": -9.6, "north": 43.0, "east": -1.0}
        inside = [c for c in SPREAD if Box.of(scope).contains(c.point)]
        self.assertEqual(len(inside), 6)
        q = zone_question(SPREAD, scope=scope)
        self.assertEqual(len(q.options), 4)
        outside = q.options[-1]
        self.assertEqual((outside.id, outside.label, outside.complement), ("d", "Outside this area", True))
        self.assert_cells_cover_the_scope(q)
        for c in SPREAD:
            holding = [o for o in q.options[:3] if o.bbox.contains(c.point)]
            self.assertEqual(len(holding), 1 if c in inside else 0)
            self.assertIs(q.option_for(c), holding[0] if holding else outside)
        self.assertEqual([o.support for o in q.options], [0.25] * 4)  # 2 of the 8 in each cell, 2 outside

    def test_a_hypothesis_outside_the_allowed_area_still_lands_in_one_cell(self):
        stray = cand(52.5, 13.4, 0.1)  # a model guess beyond the allowed area
        q = zone_question(SPREAD + [stray])
        self.assertIn(q.option_for(stray), q.options)
        self.assertEqual(sum(len(o.covers) for o in q.options), len(SPREAD) + 1)

    def test_cells_without_hypotheses_split_in_the_middle(self):
        scope = Box(40.0, -8.0, 40.01, -7.99)  # about 1.1 x 0.85 km
        q = zone_question([], scope=scope)
        self.assert_cells_cover_the_scope(q)
        self.assertEqual(q.options[2].bbox.north, 40.005)
        self.assertLess(max(o.bound_m for o in q.options[:3]), 700)

    def test_bound_covers_a_small_cell_conservatively(self):
        cell = Box(38.7000, -9.1400, 38.7003, -9.1397)  # about 33 x 26 m
        centre = cell.centre
        exact = max(haversine_m(centre, corner) for corner in cell.corners())
        bound = cell_bound_m(cell, centre)
        self.assertGreater(bound, exact)
        self.assertLess(bound, exact * 1.01 + 1.2)
        self.assertLessEqual(bound, 25)
        with self.assertRaises(ValueError):
            cell_bound_m(cell, (38.8, -9.1))

    def test_zone_rules_are_enforced(self):
        q = zone_question(SPREAD, scope=Box(37.0, -9.6, 43.0, -2.5))
        cells = q.options[:3]
        with self.assertRaises(ValueError):  # a sub-area needs its "Outside this area" option
            Question("zone", "Which zone?", cells, scope=q.scope)
        with self.assertRaises(ValueError):  # cells that leave a gap
            Question("zone", "Which zone?", cells[:2] + [q.options[3]], scope=q.scope)
        shrunk = copy.copy(cells[0])
        shrunk.bound_m = 1.0
        with self.assertRaises(ValueError):
            Question("zone", "Which zone?", [shrunk] + cells[1:] + [q.options[3]], scope=q.scope)
        with self.assertRaises(ValueError):
            Question("place", "Which place?", [Option("a", "A", point={"lat": 40.0, "lng": -8.0},
                                                      point_role="camera", radius_m=100),
                                               Option("b", "B", point={"lat": 41.0, "lng": -8.0},
                                                      point_role="camera", radius_m=100)])
        with self.assertRaises(ValueError):
            Question("feature", "Which?", [Option(i, i.upper()) for i in "abcde"], assign=lambda c: "a")
        with self.assertRaises(ValueError):  # IDs are a-d, so "s" only ever means skip
            Question("feature", "Which?", [Option("a", "Yes"), Option("s", "No")], assign=lambda c: "a")


class ExpectedGainTest(unittest.TestCase):
    SCENARIOS = ({"category": "urban"}, {"category": "non-urban"}, {"urban_probability": 0.5})

    def test_two_equally_likely_far_candidates_are_worth_asking(self):
        candidates = far_apart(0.5, 0.5)
        for build in (place_question, zone_question):
            q = build(candidates)
            for scenario in self.SCENARIOS:
                gain = expected_gain(candidates, q, **scenario)
                self.assertTrue(gain["worth_asking"], (build.__name__, scenario))
                self.assertGreater(0.95 * gain["after"], gain["before"])
                self.assertGreater(gain["gain"], gain["break_even"])
                self.assertAlmostEqual(sum(a["probability"] for a in gain["answers"]), 1.0)

    def test_one_dominant_candidate_is_not_worth_asking(self):
        candidates = far_apart(0.97, 0.03)
        q = place_question(candidates)
        for scenario in self.SCENARIOS:
            gain = expected_gain(candidates, q, **scenario)
            self.assertFalse(gain["worth_asking"], scenario)
            self.assertAlmostEqual(gain["ratio"], 1.0)  # no answer changes the output: nothing to gain
            self.assertEqual(gain["point_before"], {"lat": 40.1, "lng": -8.2})

    def test_before_is_best_point_over_candidates_and_option_points(self):
        q = zone_question(SPREAD)
        points = [c.point for c in SPREAD] + [o.latlng for o in q.options]
        hypotheses = [(c.point, c.weight) for c in SPREAD]
        for scenario in self.SCENARIOS:
            _, value = best_point(points, hypotheses, **scenario)
            self.assertAlmostEqual(expected_gain(SPREAD, q, **scenario)["before"], value)

    def test_wrong_answers_lower_the_gain(self):
        candidates = far_apart(0.5, 0.5)
        q = place_question(candidates)
        ratios = [expected_gain(candidates, q, category="urban", answer_accuracy=a)["ratio"] for a in (1.0, 0.9, 0.6)]
        self.assertGreater(ratios[0], ratios[1])
        self.assertGreater(ratios[1], ratios[2])
        d = haversine_m(candidates[0].point, candidates[1].point)
        self.assertAlmostEqual(ratios[0], 2 / (0.5 * 2 + 0.5 * 2 / (1 + d / 100)))  # a perfect answer: exact spot

    def test_category_and_urban_probability_are_exclusive(self):
        candidates = far_apart(0.5, 0.5)
        q = place_question(candidates)
        for bad in ({}, {"category": "urban", "urban_probability": 0.5}, {"category": "city"},
                    {"urban_probability": 1.5}, {"category": "urban", "answer_accuracy": 0.2}):
            with self.assertRaises(ValueError):
                expected_gain(candidates, q, **bad)
        with self.assertRaises(ValueError):
            expected_gain(far_apart(0.0, 0.0), q, category="urban")


class ApplyAnswerTest(unittest.TestCase):
    def setUp(self):
        self.candidates = [cand(40.10, -8.20, 0.5), cand(42.33, -3.12, 0.3), cand(37.64, -4.41, 0.2)]
        self.q = place_question(self.candidates, k=2)  # a, b, then c = "None of these" holding the third
        self.factor = 0.1 / (2 * 0.9)

    def test_the_chosen_option_keeps_its_weight_and_nothing_is_deleted(self):
        before = copy.deepcopy(self.candidates)
        after = apply_answer(self.candidates, self.q, "a")
        self.assertEqual([c.source for c in after], [c.source for c in self.candidates])
        self.assertEqual(after[0].weight, 0.5)
        self.assertAlmostEqual(after[1].weight, 0.3 * self.factor)
        self.assertAlmostEqual(after[2].weight, 0.2 * self.factor)
        self.assertTrue(all(c.weight > 0 for c in after))
        self.assertEqual(self.candidates, before)  # the input list is untouched
        self.assertIsNot(after[0].details, self.candidates[0].details)

    def test_none_of_these_scales_down_the_listed_places(self):
        after = apply_answer(self.candidates, self.q, "c")
        self.assertAlmostEqual(after[0].weight, 0.5 * self.factor)
        self.assertAlmostEqual(after[1].weight, 0.3 * self.factor)
        self.assertEqual(after[2].weight, 0.2)

    def test_outside_this_area_scales_down_the_cells(self):
        q = zone_question(SPREAD, scope=Box(37.0, -9.6, 43.0, -2.5))
        after = apply_answer(SPREAD, q, "d")
        for old, new in zip(SPREAD, after):
            inside = q.scope.contains(old.point)
            self.assertAlmostEqual(new.weight, old.weight * (0.1 / (3 * 0.9) if inside else 1.0))

    def test_answers_are_checked(self):
        for option_id, accuracy in (("z", 0.9), ("a", 1.0), ("a", 0.2)):
            with self.assertRaises(ValueError):
                apply_answer(self.candidates, self.q, option_id, answer_accuracy=accuracy)

    def test_there_is_no_skip_update(self):
        self.assertFalse(hasattr(questions, "apply_skip"))


class AskOperatorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.run = Run(PANORAMA, self.dir)
        self.candidates = far_apart(0.5, 0.5)
        self.q = place_question(self.candidates)  # a, b, c = "None of these"
        self.printed = []

    def event_types(self):
        return [e["type"] for e in self.run.events]

    def test_an_answer_is_logged_and_costs_0_95(self):
        self.q.details["expected_gain"] = expected_gain(self.candidates, self.q, urban_probability=0.5)
        option = ask_operator(self.run, self.q, Scripted("b"), self.printed.append)
        self.assertEqual(option.id, "b")
        self.assertEqual(self.event_types(), ["run.started", "question.asked", "question.answered"])
        self.assertAlmostEqual(self.run.penalties.multiplier, 0.95)
        asked = self.run.events[1]["payload"]
        self.assertEqual((asked["question_id"], asked["kind"]), (self.q.question_id, "place"))
        self.assertTrue(asked["expected_gain"]["worth_asking"])
        text = "\n".join(self.printed)
        for expected in ("Google Maps: https://www.google.com/maps/search/", "Street View: ", "coverage unchecked",
                         "None of these", "Skipping costs nothing"):
            self.assertIn(expected, text)

    def test_a_skip_is_free_and_changes_nothing(self):
        candidates_before, options_before = copy.deepcopy(self.candidates), self.q.option_dicts()
        self.assertIsNone(ask_operator(self.run, self.q, Scripted("s"), self.printed.append))
        self.assertEqual(self.event_types(), ["run.started", "question.asked", "question.skipped"])
        self.assertEqual(self.run.penalties.multiplier, 1.0)
        self.assertEqual(self.run.questions[self.q.question_id]["answer"], None)
        self.assertEqual(self.candidates, candidates_before)
        self.assertEqual(self.q.option_dicts(), options_before)

    def test_invalid_input_is_asked_again_and_never_read_as_a_skip(self):
        keys = Scripted("", "   ", "x", "d", "skip if", "B")
        option = ask_operator(self.run, self.q, keys, self.printed.append)
        self.assertEqual(option.id, "b")
        self.assertEqual(len(keys.prompts), 6)
        self.assertEqual(self.event_types(), ["run.started", "question.asked", "question.answered"])
        self.assertEqual(sum("is not one of the choices" in line for line in self.printed), 5)

    def test_end_of_input_leaves_the_question_open(self):
        with self.assertRaises(EOFError):
            ask_operator(self.run, self.q, Scripted(), self.printed.append)
        self.assertEqual(self.event_types(), ["run.started", "question.asked"])
        self.assertEqual(self.run.questions[self.q.question_id]["status"], "open")
        self.assertEqual(self.run.penalties.multiplier, 1.0)

    def test_phrase_fn_rewords_the_text_only(self):
        template = place_question(self.candidates)
        reworded = place_question(self.candidates, phrase_fn=lambda q: "Which of these spots is it?")
        self.assertEqual(reworded.text, "Which of these spots is it?")
        self.assertEqual(reworded.details["template_text"], template.text)
        self.assertEqual(reworded.option_dicts(), template.option_dicts())
        refused = place_question(self.candidates, phrase_fn=lambda q: "Skip this if you are unsure: which spot?")
        self.assertEqual(refused.text, template.text)
        self.assertFalse(refused.details["phrased"])
        ask_operator(self.run, refused, Scripted("s"), self.printed.append)  # still askable

    def test_feature_question(self):
        candidates = [cand(40.10, -8.20, 0.5, country="PT"), cand(42.33, -3.12, 0.5, country="ES")]
        q = feature_question(candidates, "Is the street-name sign text in Portuguese?", ["Yes", "No"],
                             lambda c: 0 if c.country == "PT" else 1)
        self.assertEqual([o.covers for o in q.options], [[candidates[0].source], [candidates[1].source]])
        self.assertTrue(expected_gain(candidates, q, category="non-urban")["worth_asking"])
        option = ask_operator(self.run, q, Scripted("a"), self.printed.append)
        after = apply_answer(candidates, q, option.id)
        self.assertEqual(after[0].weight, 0.5)
        self.assertAlmostEqual(after[1].weight, 0.5 * 0.1 / 0.9)

    def test_demo_runs_with_scripted_answers(self):
        path = questions.demo(self.dir, Scripted("a", "s"), self.printed.append)
        log = json.loads(Path(path).read_text(encoding="utf-8"))
        types = [e["type"] for e in log["events"]]
        self.assertEqual(types.count("question.answered"), 1)
        self.assertEqual(types.count("question.skipped"), 1)
        self.assertEqual(log["final_output"]["penalty"]["multiplier"], 0.95)
        self.assertEqual(len(log["final_output"]["coordinates"]), 10)


if __name__ == "__main__":
    unittest.main()
