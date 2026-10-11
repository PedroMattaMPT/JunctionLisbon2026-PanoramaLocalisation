"""Tests for panoloc.verify, model-free (the models are replaced by stubs).
Run: .venv/bin/python -m unittest tests.test_verify"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc import verify
from panoloc.candidates import Candidate


def two_views(n=200, n_outliers=60, seed=0):
    """Projections of random 3D points into two cameras a few metres apart, plus random outliers."""
    rng = np.random.default_rng(seed)
    pts = np.c_[rng.uniform(-5, 5, n), rng.uniform(-3, 3, n), rng.uniform(8, 20, n)]
    K = np.array([[500.0, 0, 512], [0, 500.0, 512], [0, 0, 1]])
    a = np.radians(10)
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    t = np.array([1.5, 0.2, 0.5])
    p0 = (K @ pts.T).T
    p1 = (K @ (R @ pts.T + t[:, None])).T
    p0, p1 = p0[:, :2] / p0[:, 2:], p1[:, :2] / p1[:, 2:]
    o0, o1 = rng.uniform(0, 1024, (n_outliers, 2)), rng.uniform(0, 1024, (n_outliers, 2))
    return np.r_[p0, o0], np.r_[p1, o1], n


class GeometryTest(unittest.TestCase):
    def test_ransac_keeps_the_rigid_scene(self):
        p0, p1, n = two_views()
        mask = verify.ransac_inliers(p0, p1)
        self.assertGreater(mask[:n].mean(), 0.9)
        self.assertLess(mask[n:].mean(), 0.1)

    def test_ransac_needs_eight_matches(self):
        p0, p1, _ = two_views(n=7, n_outliers=0)
        self.assertFalse(verify.ransac_inliers(p0, p1).any())

    def test_ransac_survives_degenerate_sets(self):
        same = np.tile([[100.0, 200.0]], (20, 1))  # every match on one point
        line = np.c_[np.linspace(0, 500, 20), np.zeros(20)]  # every match on one line
        for p0, p1 in ((same, same), (line, line * 1.5)):
            mask = verify.ransac_inliers(p0, p1)
            self.assertEqual(mask.shape, (20,))

    def test_grid_spread(self):
        self.assertEqual(verify.grid_spread([], 100, 100), 0.0)
        self.assertEqual(verify.grid_spread([[1, 1], [2, 2]], 100, 100), 1 / 16)
        corners = [[1, 1], [99, 1], [1, 99], [99, 99]]
        self.assertEqual(verify.grid_spread(corners, 100, 100), 4 / 16)
        self.assertEqual(verify.grid_spread([[150, -3]], 100, 100), 1 / 16)  # clipped to the image

    def test_match_rule(self):
        m = verify.Match(matches=120, confident=100, inliers=50, raw_inliers=90, spread=0.25, thickness=0.05, ms=3.0)
        self.assertEqual(m.inlier_ratio, 0.5)
        self.assertTrue(m.verified(min_inliers=50, min_thickness=0.05))
        self.assertFalse(m.verified(min_inliers=51))
        self.assertFalse(m.verified(min_inliers=10, min_thickness=0.06))
        self.assertEqual(verify.Match(0, 0, 0, 0, 0.0, 0.0, 1.0).inlier_ratio, 0.0)
        self.assertEqual(verify.match_summary(m)["inlier_ratio"], 0.5)

    def test_thickness(self):
        line = np.c_[np.linspace(0, 1000, 50), np.full(50, 300.0)]
        self.assertAlmostEqual(verify.thickness(line, 1000), 0.0, places=6)
        rng = np.random.default_rng(0)
        square = rng.uniform(0, 1000, (2000, 2))
        self.assertAlmostEqual(verify.thickness(square, 1000), 1 / np.sqrt(12), delta=0.01)
        self.assertEqual(verify.thickness(square[:2], 1000), 0.0)

    def test_rgb_array(self):
        gray = np.zeros((4, 5), np.uint8)
        self.assertEqual(verify.rgb_array(gray).shape, (4, 5, 3))
        self.assertEqual(verify.rgb_array(Image.new("L", (5, 4))).shape, (4, 5, 3))
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGB", (6, 3), "red").save(Path(d) / "x.png")
            self.assertEqual(verify.rgb_array(Path(d) / "x.png")[0, 0].tolist(), [255, 0, 0])
        with self.assertRaises(ValueError):
            verify.rgb_array(np.zeros((4, 5, 2)))


class StubVerifier(verify.Verifier):
    """No models. MegaLoc: view i is axis i, and every photo looks most like view 2 (h090), then view 3
    (h135). Matching gives `inliers[(view name, photo id)]`."""

    def __init__(self, inliers, megaloc=True):
        self.inliers, self.calls, self.megaloc = inliers, [], (object() if megaloc else None)

    def global_descriptors(self, images, batch_size=16):
        d = np.zeros((len(images), 8), np.float32)
        for i, im in enumerate(images):
            if im.shape[0] == 4:  # views are 4 px tall, their first pixel holds their index
                d[i, int(im[0, 0, 0])] = 1.0
            else:  # photos are 6 px tall
                d[i, 2], d[i, 3], d[i, 0] = 1.0, 0.5, 0.1
        return d / np.linalg.norm(d, axis=1, keepdims=True)

    def features(self, image, size=None):
        return {"id": int(image[0, 0, 0]), "size": size}

    def match_features(self, f0, f1, view=None):
        self.calls.append((view, f1["id"], f1["size"]))
        n = self.inliers.get((view, f1["id"], f1["size"]), self.inliers.get((view, f1["id"]), 0))
        return verify.Match(matches=n * 3, confident=n * 2, inliers=n, raw_inliers=n, spread=0.5, thickness=0.1,
                            ms=1.0, view=view)


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        for i in (101, 102):
            Image.fromarray(np.full((6, 6, 3), i, np.uint8)).save(d / f"{i}.png")
        self.views = [np.full((4, 4, 3), i, np.uint8) for i in range(8)]
        self.names = [f"h{45 * i:03d}" for i in range(8)]
        self.cands = [Candidate(38.7, -9.1, "landmark", f"commons:Q{i}", details={"qid": f"Q{i}", "verified_match": False})
                      for i in (101, 102, 103)]
        self.path = lambda c: d / f"{c.details['qid'][1:]}.png" if c.details["qid"] != "Q103" else None

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_marks_only_matches_above_the_rule(self):
        ver = StubVerifier({("h090", 101): 80, ("h135", 101): 30, ("h090", 102): 12})
        out = ver.verify(self.views, self.cands, self.path, views_per_candidate=2, min_inliers=40,
                         view_names=self.names)
        self.assertEqual([c.source for c in out], [c.source for c in self.cands])  # order kept
        self.assertTrue(out[0].details["verified_match"])
        self.assertEqual((out[0].details["inliers"], out[0].details["verify_view"]), (80, "h090"))
        self.assertFalse(out[1].details["verified_match"])
        self.assertEqual(out[1].details["inliers"], 12)
        self.assertNotIn("inliers", out[2].details)  # no photo: left as it was
        self.assertFalse(self.cands[0].details["verified_match"])  # inputs untouched
        self.assertEqual(out[0].role, "landmark")  # a verified landmark still marks the landmark
        self.assertIn("megaloc_similarity", out[0].details)
        # MegaLoc picks the two views most like the photos: h090, then h135; each at both photo scales
        self.assertEqual(sorted({v for v, _, _ in ver.calls}), ["h090", "h135"])
        self.assertEqual({size for _, _, size in ver.calls}, set(verify.PHOTO_SCALES))

    def test_small_scale_match_is_kept(self):
        ver = StubVerifier({("h090", 101, 400): 30, ("h090", 101, 1024): 5})
        out = ver.verify(self.views, self.cands[:1], self.path, view_names=self.names)
        self.assertTrue(out[0].details["verified_match"])
        self.assertEqual((out[0].details["inliers"], out[0].details["verify_scale"]), (30, 400))

    def test_without_megaloc_every_view_is_matched_and_top_limits(self):
        ver = StubVerifier({("h315", 101): 99}, megaloc=False)
        out = ver.verify(self.views, self.cands, self.path, top=1, view_names=self.names)
        self.assertEqual(len(ver.calls), 8 * len(verify.PHOTO_SCALES))
        self.assertTrue(out[0].details["verified_match"])
        self.assertNotIn("inliers", out[1].details)  # beyond `top`
        self.assertNotIn("megaloc_similarity", out[0].details)


if __name__ == "__main__":
    unittest.main()
