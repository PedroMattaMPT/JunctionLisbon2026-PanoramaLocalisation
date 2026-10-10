"""Tests for panoloc.candidates (PLAN.md 3.3). Run: python3 -m unittest discover -s tests"""
import tempfile
import unittest

from panoloc.candidates import GLOBAL_FALLBACK, Candidate, Output, coarse_output, distinct, normalise
from panoloc.runlog import Run


def cand(lat, lng, role="area", weight=1.0, **kwargs):
    return Candidate(lat, lng, role, f"test:{lat},{lng}", weight=weight, **kwargs)


class CandidateTest(unittest.TestCase):
    def test_candidates_are_checked(self):
        for bad in (dict(role="spot"), dict(lat=91), dict(lng=float("nan")), dict(source="no-colon"),
                    dict(weight=-1), dict(accuracy_m=0), dict(extent_m=-5)):
            fields = {"lat": 38.7, "lng": -9.1, "role": "area", "source": "test:1", **bad}
            with self.assertRaises(ValueError, msg=bad):
                Candidate(**fields)
        c = Candidate("38.7", -9.1, "camera", "osv5m:1", accuracy_m=5)
        self.assertEqual((c.point, c.accuracy_m, c.extent_m), ((38.7, -9.1), 5, None))
        self.assertEqual(c.to_dict()["role"], "camera")

    def test_output_contract(self):
        with self.assertRaises(ValueError):
            Output(38.7, -9.1, "coarse_candidate", "area", uncertainty_m=None, uncertainty_source="source_estimate")
        with self.assertRaises(ValueError):
            Output(38.7, -9.1, "coarse_candidate", "area", uncertainty_m=50, uncertainty_source="unknown")
        with self.assertRaises(ValueError):
            Output(38.7, -9.1, "reference_camera", "landmark", uncertainty_m=30, uncertainty_source="estimated_offset")
        with self.assertRaises(ValueError):
            Output(38.7, -9.1, "geographic_cell", "area", uncertainty_m=25, uncertainty_source="source_estimate")
        with self.assertRaises(ValueError):
            Output(38.7, -9.1, "magic", "area")
        out = Output(38.7, -9.1, "geographic_cell", "area", ["cell:q2"], 25, "geometric_bound")
        self.assertEqual(out.coordinates(), [(38.7, -9.1)] * 10)

    def test_output_log_records_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Run("IMG_20260115_143012_00_204.jpg", tmp)
            Output(38.7, -9.1, "reference_camera", "camera", ["osv5m:1"], 15, "source_estimate").log(run)
            payload = run.outputs[0]
            self.assertEqual((payload["output_method"], payload["source_role"], payload["sources"]),
                             ("reference_camera", "camera", ["osv5m:1"]))
            self.assertEqual((payload["position_uncertainty_m"], payload["uncertainty_source"]), (15, "source_estimate"))
            self.assertEqual(len(payload["coordinates"]), 10)

    def test_distinct_keeps_the_heaviest_apart(self):
        a = cand(38.70, -9.10, weight=0.5)
        b = cand(38.7001, -9.1001, weight=0.4)  # ~14 m from a
        c = cand(38.80, -9.10, weight=0.1)  # ~11 km from a
        self.assertEqual(distinct([b, c, a], 1000), [a, c])
        self.assertEqual(distinct([b, c, a], 5), [a, b, c])
        landmark = cand(38.7001, -9.1001, role="landmark", weight=0.5)
        self.assertEqual(distinct([a, landmark], 1000), [landmark])  # equal weight: the more specific role

    def test_coarse_output(self):
        area = cand(38.70, -9.10, weight=0.6, extent_m=800, accuracy_m=50)
        camera = cand(41.15, -8.61, role="camera", weight=0.6, accuracy_m=5)
        out = coarse_output([area, camera])
        self.assertEqual((out.source_role, out.uncertainty_m, out.uncertainty_source), ("camera", 5, "source_estimate"))
        out = coarse_output([area, cand(41.15, -8.61, weight=0.2)])
        self.assertEqual((out.lat, out.uncertainty_m, out.method), (38.70, 850, "coarse_candidate"))
        out = coarse_output([cand(38.70, -9.10, role="landmark")])
        self.assertEqual((out.uncertainty_m, out.uncertainty_source), (None, "unknown"))

    def test_global_fallback(self):
        for candidates in ([], [cand(38.7, -9.1, weight=0)]):
            out = coarse_output(candidates)
            self.assertEqual((out.lat, out.lng, out.sources), (GLOBAL_FALLBACK.lat, GLOBAL_FALLBACK.lng, ["fallback:lisbon"]))
            self.assertEqual(out.uncertainty_source, "unknown")
            self.assertIn("fallback", out.note)

    def test_normalise(self):
        a, b = cand(38.7, -9.1, weight=3), cand(38.8, -9.1, weight=1)
        self.assertEqual([c.weight for c in normalise([a, b])], [0.75, 0.25])
        self.assertEqual(a.weight, 3)  # copies, not in place
        self.assertEqual([c.weight for c in normalise([cand(1, 1, weight=0), cand(2, 2, weight=0)])], [0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
