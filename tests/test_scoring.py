"""Tests for panoloc.scoring against the figures in RULES.md and PLAN.md. Run: python3 -m unittest discover -s tests"""
import math
import tempfile
import unittest

from panoloc.runlog import Run
from panoloc.scoring import (EARTH_RADIUS_M, best_point, entry_score, expected_theta, haversine_m, list_score,
                             max_score, score_output, theta)

TRUTH = (38.7, -9.1)


def north_of(point, metres):
    """A point `metres` due north of `point` (exact on the Haversine sphere)."""
    return (point[0] + math.degrees(metres / EARTH_RADIUS_M), point[1])


class ScoringTest(unittest.TestCase):
    def test_maxima(self):
        self.assertAlmostEqual(max_score(), 16_050.52, places=2)
        self.assertAlmostEqual(max_score(special=True), 48_151.57, places=2)

    def test_plan_distance_table(self):
        # PLAN.md 1.2: score as % of the maximum, for urban and non-urban
        table = {25: (80.0, 99.8), 100: (50.0, 99.0), 1000: (9.1, 90.9), 5000: (2.0, 66.7), 10000: (1.0, 50.0)}
        for d, (urban, non_urban) in table.items():
            self.assertEqual(round(theta(d, "urban") / 2 * 100, 1), urban, d)
            self.assertEqual(round(theta(d, "non-urban") / 2 * 100, 1), non_urban, d)

    def test_under_ten_metres_counts_as_zero(self):
        self.assertEqual(theta(9.99, "urban"), 2.0)
        self.assertLess(theta(10.0, "urban"), 2.0)

    def test_plan_question_examples(self):
        # PLAN.md 3.4: ten repeated guesses, urban
        cases = [(0.95, 5, 15_248.00), (0.95, 20, 12_706.66), (1.0, 1500, 1_003.16), (0.95 ** 15, 5, 7_436.07)]
        for multiplier, d, expected in cases:
            guesses = [north_of(TRUTH, d)] * 10
            self.assertAlmostEqual(list_score(guesses, TRUTH, "urban", multiplier), expected, places=1)

    def test_haversine(self):
        self.assertAlmostEqual(haversine_m((38.7223, -9.1393), (41.1579, -8.6291)) / 1000, 274.3, delta=0.5)
        self.assertAlmostEqual(haversine_m(TRUTH, north_of(TRUTH, 123.4)), 123.4, places=6)
        self.assertEqual(haversine_m(TRUTH, TRUTH), 0.0)

    def test_ranks_multipliers_and_limits(self):
        self.assertAlmostEqual(entry_score(2, 0, "urban"), 1900.0)
        self.assertAlmostEqual(entry_score(1, 0, "urban", special=True), 6000.0)
        for rank in (0, 11):
            with self.assertRaises(ValueError):
                entry_score(rank, 0, "urban")
        per_entry = list_score([TRUTH, TRUTH], TRUTH, "urban", [1.0, 0.95])
        self.assertAlmostEqual(per_entry, 2000 + 1900 * 0.95)
        with self.assertRaises(ValueError):
            list_score([TRUTH] * 11, TRUTH, "urban")
        with self.assertRaises(ValueError):
            list_score([TRUTH] * 2, TRUTH, "urban", [1.0])

    def test_score_output_uses_the_logged_penalty(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Run("IMG_20260115_143012_00_204.jpg", tmp)
            run.answer(run.ask("Which one?", ["A", "B"]), "a")
            run.output([north_of(TRUTH, 20)] * 10)
            logged = [(c["lat"], c["lng"]) for c in run.outputs[0]["coordinates"]]
            score = score_output(run.outputs[0], TRUTH, "urban")
            self.assertAlmostEqual(score, list_score(logged, TRUTH, "urban", 0.95))
            # the log keeps 7 decimals (~1 cm): at 20 m urban that moves the score by under 1 point
            self.assertAlmostEqual(score, 12_706.66, delta=1)

    def test_expected_theta(self):
        self.assertEqual(expected_theta(TRUTH, [(TRUTH, 1.0)], "urban"), 2.0)
        far = north_of(TRUTH, 100)
        self.assertAlmostEqual(expected_theta(TRUTH, [(TRUTH, 1), (far, 1)], "urban"), (2 + 1) / 2)
        mixed = expected_theta(TRUTH, [(far, 1)], urban_probability=0.25)
        self.assertAlmostEqual(mixed, 0.25 * theta(100, "urban") + 0.75 * theta(100, "non-urban"))
        with self.assertRaises(ValueError):
            expected_theta(TRUTH, [(TRUTH, 1)])
        with self.assertRaises(ValueError):
            expected_theta(TRUTH, [(TRUTH, 1)], "urban", 0.5)
        with self.assertRaises(ValueError):
            expected_theta(TRUTH, [(TRUTH, 0)], "urban")

    def test_best_point_is_not_always_the_most_likely_spot(self):
        # PLAN.md 1.1: two close hypotheses can beat a single, slightly more likely one
        lone, near_a = TRUTH, north_of(TRUTH, 5000)
        near_b = north_of(near_a, 50)
        hypotheses = [(lone, 0.4), (near_a, 0.3), (near_b, 0.3)]
        point, value = best_point([lone, near_a, near_b], hypotheses, "urban")
        self.assertIn(point, (near_a, near_b))
        self.assertGreater(value, expected_theta(lone, hypotheses, "urban"))
        with self.assertRaises(ValueError):
            best_point([], hypotheses, "urban")


if __name__ == "__main__":
    unittest.main()
