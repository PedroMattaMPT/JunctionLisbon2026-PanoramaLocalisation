"""Tests for panoloc.retrieval and tools/bank_partitions.py, model-free.
Run: .venv/bin/python -m unittest tests.test_retrieval"""
import importlib.util
import math
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from panoloc import retrieval
from panoloc.candidates import Candidate
from panoloc.scoring import haversine_m

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bank_partitions", ROOT / "tools" / "bank_partitions.py")
bank_partitions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bank_partitions)


def fake_bank(groups, lats=None, countries=None):
    n = len(groups)
    return SimpleNamespace(ids=np.array([f"id{i}" for i in range(n)]),
                           lat=np.array(lats if lats is not None else [40.0 + i * 0.1 for i in range(n)]),
                           lon=np.array([-5.0] * n), country=np.array(countries or ["ES"] * n),
                           region=np.array(["Madrid"] * n), ref_group=np.array(groups),
                           partition=np.array(["train"] * n))


class PartitionTest(unittest.TestCase):
    def test_blocks_are_about_10_km(self):
        self.assertEqual(bank_partitions.block_key(40.0, -3.0), bank_partitions.block_key(40.0, -3.0))
        a = bank_partitions.block_key(40.0001, -3.0001)
        far = [bank_partitions.block_key(40.0 + d, -3.0) for d in (0.2, -0.2)]
        self.assertTrue(all(f != a for f in far))  # 22 km away
        # points inside one block are never more than ~15 km apart (10 km x 10 km diagonal)
        rng = np.random.default_rng(0)
        pts = [(40 + rng.uniform(-1, 1), -3 + rng.uniform(-1, 1)) for _ in range(2000)]
        by = {}
        for p in pts:
            by.setdefault(bank_partitions.block_key(*p), []).append(p)
        worst = max(haversine_m(p, q) for ps in by.values() for p in ps for q in ps)
        self.assertLess(worst, 15_000)

    def test_val_is_per_region_and_whole_groups(self):
        groups = [f"g{i // 5}" for i in range(500)] + [f"h{i}" for i in range(30)]  # 100 groups of 5, 30 singletons
        regions = ["A"] * 500 + ["B"] * 30
        val = bank_partitions.assign_val(groups, regions, 0.1, seed=0)
        n_a = sum(1 for g in groups[:500] if g in val)
        n_b = sum(1 for g in groups[500:] if g in val)
        self.assertTrue(50 <= n_a < 60 and 3 <= n_b < 5, (n_a, n_b))  # >= 10% per region, small region too
        self.assertEqual(val, bank_partitions.assign_val(groups, regions, 0.1, seed=0))  # deterministic

    def test_build_partitions(self):
        meta = pd.DataFrame({
            "id": ["1", "2", "3", "4", "5"], "country": ["PT", "PT", "ES", "ES", "FR"],
            "region": ["Lisbon", "Lisbon", "Ceuta", "Madrid", "Alsace"], "lat": [38.7, 38.7, 35.9, 40.4, 48.6],
            "lon": [-9.1, -9.1, -5.3, -3.7, 7.7], "sequence": ["s1", "s1", None, None, None],
            "subdir": ["train_PT", "train_PT", "train_ESFR", "train_ESFR", "test"],
            "source": ["train", "train", "train", "train", "test"]})
        p = bank_partitions.build(meta, val_fraction=0.5, seed=0).set_index("id")
        self.assertEqual(p.loc["1", "group"], "seq:s1")
        self.assertTrue(p.loc["4", "group"].startswith("blk:"))
        self.assertEqual(p.loc["3", "partition"], "dropped")
        self.assertEqual(p.loc["5", "partition"], "test")
        self.assertEqual(p.loc["1", "partition"], p.loc["2", "partition"])  # one sequence, one side
        self.assertEqual(list(p.reset_index().columns), bank_partitions.COLUMNS)


class AggregateTest(unittest.TestCase):
    def test_one_view_orders_by_similarity_and_dedups_groups(self):
        bank = fake_bank(["seq:a", "seq:a", "seq:b", "blk:1:1"])
        sims = np.array([[0.90, 0.89, 0.80, 0.70]])
        rows = np.array([[0, 1, 2, 3]])
        out = retrieval.aggregate(sims, rows, bank, k=10, tau=0.05)
        self.assertEqual([c.details["ref_group"] for c in out], ["seq:a", "seq:b", "blk:1:1"])
        self.assertEqual(out[0].source, "osv5m:id0")  # the group's best image
        self.assertEqual(out[0].details["n_images"], 2)
        self.assertAlmostEqual(sum(c.weight for c in out), 1.0)
        # the duplicate frame in seq:a does not add support: weights follow one kernel per group
        w = [math.exp((s - 0.9) / 0.05) for s in (0.90, 0.80, 0.70)]
        for c, expect in zip(out, w):
            self.assertAlmostEqual(c.weight, expect / sum(w))

    def test_views_are_averaged_not_multiplied(self):
        bank = fake_bank(["seq:a", "seq:b", "seq:c"])
        sims = np.array([[0.9, 0.5, -1], [0.9, 0.5, -1]])
        rows = np.array([[0, 1, -1], [2, 1, -1]])  # a only in view 0, c only in view 1, b in both
        out = {c.details["ref_group"]: c for c in retrieval.aggregate(sims, rows, bank, tau=0.1)}
        self.assertAlmostEqual(out["seq:a"].weight, out["seq:c"].weight)
        self.assertGreater(out["seq:a"].weight, 0.4)  # a product would zero a, b and c alike
        self.assertEqual(out["seq:b"].details["n_views"], 2)
        self.assertAlmostEqual(sum(c.weight for c in out.values()), 1.0)
        self.assertEqual(out["seq:a"].details["views"], ["v0"])

    def test_candidate_fields(self):
        bank = fake_bank(["blk:1:2"], lats=[41.15], countries=["PT"])
        (c,) = retrieval.aggregate(np.array([[0.8]]), np.array([[0]]), bank, view_names=["h090"])
        self.assertIsInstance(c, Candidate)
        self.assertEqual((c.role, c.source, c.group, c.country), ("camera", "osv5m:id0", "pe-core", "PT"))
        self.assertIsNone(c.accuracy_m)
        self.assertIsNone(c.extent_m)
        self.assertEqual(c.point, (41.15, -5.0))
        d = c.details
        self.assertEqual((d["similarity"], d["views"], d["group_kind"], d["region"], d["rank"]),
                         (0.8, ["h090"], "block", "Madrid", 1))
        self.assertIn("not a verified match", d["note"])

    def test_k_limits_and_empty_hits(self):
        bank = fake_bank([f"seq:{i}" for i in range(5)])
        out = retrieval.aggregate(np.array([[0.9, 0.8, 0.7, 0.6, 0.5]]), np.array([[0, 1, 2, 3, 4]]), bank, k=2)
        self.assertEqual(len(out), 2)
        self.assertEqual(retrieval.aggregate(np.array([[0.1]]), np.array([[-1]]), bank), [])
        with self.assertRaises(ValueError):
            retrieval.aggregate(np.array([[0.9]]), np.array([[0]]), bank, view_names=["a", "b"])


class BankTest(unittest.TestCase):
    def test_faiss_bank_search(self):
        import faiss
        rng = np.random.default_rng(0)
        emb = rng.normal(size=(6, retrieval.EMBED_DIM)).astype(np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True)
        index = faiss.IndexFlatIP(retrieval.EMBED_DIM)
        index.add(emb)
        meta = {"id": list("abcdef"), "lat": [38.7, 38.71, 41.1, 40.4, 43.3, 48.8], "lon": [-9.1] * 6,
                "country": ["PT", "PT", "PT", "ES", "ES", "FR"], "region": ["Lisbon"] * 6,
                "group": ["seq:x", "seq:x", "seq:y", "blk:0:0", "blk:0:1", "blk:9:9"], "partition": ["train"] * 6}
        bank = retrieval.Bank.from_arrays(index, meta)
        out = bank.search(np.stack([emb[0], emb[1]]), k=3, view_names=["h000", "h045"])
        self.assertEqual(out[0].details["ref_group"], "seq:x")
        self.assertEqual(out[0].details["n_views"], 2)
        self.assertEqual(len({c.details["ref_group"] for c in out}), len(out))

    def test_test_partition_is_never_a_gallery(self):
        with self.assertRaises(ValueError):
            retrieval.Bank.open(partitions=("train", "test"))


class RegionHeadTest(unittest.TestCase):
    def head(self):
        W = np.zeros((3, 4), np.float32)
        W[0, 0] = W[1, 1] = W[2, 2] = 5
        classes = [{"name": f"PT:R{i}", "country": "PT", "region": f"R{i}", "n_train": 10,
                    "lat": 38 + i, "lon": -8.0, "extent_m": 20_000} for i in range(3)]
        return retrieval.RegionHead(W, np.zeros(3, np.float32), 1.0, classes)

    def test_views_are_averaged(self):
        head = self.head()
        x = np.eye(4, dtype=np.float32)[[0, 1]]  # view 0 says R0, view 1 says R1
        p = head.probs(x)
        np.testing.assert_allclose(p.sum(axis=1), 1, rtol=1e-6)
        ranked = head.predict(x)
        self.assertEqual({r for r, _, _ in ranked[:2]}, {"R0", "R1"})
        self.assertAlmostEqual(ranked[0][2], ranked[1][2], places=6)
        self.assertAlmostEqual(sum(pr for _, _, pr in ranked), 1, places=6)
        self.assertEqual(len(head.predict(x, top=1)), 1)

    def test_temperature_flattens(self):
        head = self.head()
        sharp = head.probs(np.eye(4, dtype=np.float32)[:1]).max()
        head.temperature = 3.0
        self.assertLess(head.probs(np.eye(4, dtype=np.float32)[:1]).max(), sharp)

    def test_candidates(self):
        (c,) = self.head().candidates(np.eye(4, dtype=np.float32)[[2]], k=1)
        self.assertEqual((c.role, c.group, c.country, c.source, c.extent_m), ("area", "pe-core", "PT", "regionhead:PT:R2", 20_000))
        self.assertEqual(c.point, (40.0, -8.0))
        self.assertIn("not a camera position", c.details["note"])


class GeoCLIPClusterTest(unittest.TestCase):
    def test_cluster_merges_nearby_mass(self):
        from panoloc.geoclip_gen import cluster
        lat = np.array([40.0, 40.05, 41.0, 38.0])
        lon = np.array([-4.0, -4.0, -4.0, -9.0])
        prob = np.array([0.4, 0.3, 0.2, 0.1])
        out = cluster(lat, lon, prob, cluster_m=25_000)
        self.assertEqual([c for c, _, _ in out], [0, 2, 3])
        self.assertAlmostEqual(out[0][1], 0.7)
        self.assertGreater(out[0][2], 1000)  # the 5.6 km member spreads it beyond the 1 km floor
        self.assertEqual(out[1][2], 1000)


class ViewImageTest(unittest.TestCase):
    def test_crop(self):
        img = np.zeros((512, 512, 3), np.uint8)
        self.assertEqual(retrieval.view_image(img, "4:3").size, (512, 384))
        self.assertEqual(retrieval.view_image(SimpleNamespace(image=img), "square").size, (512, 512))
        with self.assertRaises(ValueError):
            retrieval.view_image(img, "16:9")


if __name__ == "__main__":
    unittest.main()
