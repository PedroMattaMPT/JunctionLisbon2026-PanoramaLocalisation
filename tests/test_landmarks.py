"""Tests for panoloc.landmarks and tools/embed_gallery.py, model-free.
Run: .venv/bin/python -m unittest tests.test_landmarks"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from panoloc import landmarks
from panoloc.candidates import Candidate
from panoloc.retrieval import EMBED_DIM, EMBED_VERSION

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("embed_gallery", ROOT / "tools" / "embed_gallery.py")
embed_gallery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed_gallery)


def fake_meta(qids, extents=None):
    n = len(qids)
    return {"qid": np.array(qids), "lat": np.array([38.7 + i * 0.01 for i in range(n)]),
            "lon": np.array([-9.1] * n), "extent_m": np.array(extents or [100.0] * n),
            "country": np.array(["PT"] * n), "name": np.array([f"Item {q}" for q in qids]),
            "types": np.array(["Q16970|Q210272"] * n), "type_labels": np.array(["church|cultural heritage"] * n),
            "heritage": np.array(["National Monument of Portugal"] * n),
            "commons_file": np.array([f"{q}.jpg" for q in qids]), "photo": np.array([f"PT/{q}.jpg" for q in qids]),
            "type_role": np.array(["landmark"] * n), "extent_rule": np.array(["wikidata type: church"] * n),
            "sitelinks": np.array([3] * n)}


class AggregateTest(unittest.TestCase):
    def test_one_view_orders_by_similarity_and_sums_to_one(self):
        meta = fake_meta(["Q1", "Q2", "Q3"])
        out = landmarks.aggregate(np.array([[0.80, 0.90, 0.70]]), np.array([[0, 1, 2]]), meta, tau=0.05, min_similarity=0)
        self.assertEqual([c.details["qid"] for c in out], ["Q2", "Q1", "Q3"])
        self.assertAlmostEqual(sum(c.weight for c in out), 1.0)
        self.assertGreater(out[0].weight, out[1].weight)

    def test_candidate_fields(self):
        meta = fake_meta(["Q1", "Q2"], extents=[40.0, 2500.0])
        c = landmarks.aggregate(np.array([[0.9, 0.5]]), np.array([[0, 1]]), meta, view_names=["h000"])[0]
        self.assertIsInstance(c, Candidate)
        self.assertEqual((c.role, c.source, c.group), ("landmark", "commons:Q1", "pe-core"))
        self.assertIsNone(c.accuracy_m)
        self.assertEqual(c.extent_m, 40.0)
        self.assertEqual((c.lat, c.lng, c.country), (38.7, -9.1, "PT"))
        d = c.details
        self.assertFalse(d["verified_match"])  # only panoloc.verify may set it
        self.assertEqual(d["qid"], "Q1")
        self.assertEqual(d["types"], ["Q16970", "Q210272"])
        self.assertEqual(d["heritage"], ["National Monument of Portugal"])
        self.assertEqual(d["commons_file"], "Q1.jpg")
        self.assertEqual(d["photo"], "PT/Q1.jpg")
        self.assertEqual(d["views"], ["h000"])
        self.assertEqual(d["similarity"], 0.9)
        self.assertEqual(d["extent_source"], "assumed")
        self.assertIn("Item Q1", c.label)

    def test_one_qid_counts_once_across_views(self):
        meta = fake_meta(["Q1", "Q2", "Q1"])  # row 2 is a second photo of Q1
        sims = np.array([[0.90, 0.85, 0.60], [0.70, 0.95, 0.80]])
        rows = np.array([[0, 1, 2], [0, 1, 2]])
        out = landmarks.aggregate(sims, rows, meta, tau=0.05, view_names=["h000", "h045"])
        self.assertEqual(sorted(c.details["qid"] for c in out), ["Q1", "Q2"])
        q1 = next(c for c in out if c.details["qid"] == "Q1")
        self.assertEqual(q1.details["views"], ["h000", "h045"])
        self.assertEqual(q1.details["n_views"], 2)
        self.assertEqual(q1.details["similarity"], 0.9)  # best over views and photos
        self.assertAlmostEqual(q1.details["mean_similarity"], (0.90 + 0.80) / 2, places=4)
        self.assertAlmostEqual(sum(c.weight for c in out), 1.0)

    def test_average_not_product(self):
        meta = fake_meta(["Q1", "Q2"])
        # Q1 is the only hit of view 0; view 1 sees only Q2: each gets half, nobody is multiplied away
        sims = np.array([[0.9, np.nan], [0.9, np.nan]])
        rows = np.array([[0, -1], [1, -1]])
        out = landmarks.aggregate(sims, rows, meta)
        self.assertEqual({c.details["qid"]: round(c.weight, 6) for c in out}, {"Q1": 0.5, "Q2": 0.5})

    def test_scores_rank_and_similarities_are_reported(self):
        meta = fake_meta(["Q1", "Q2"])
        out = landmarks.aggregate(np.array([[0.30, 0.20]]), np.array([[1, 0]]), meta,
                                  similarities=np.array([[0.70, 0.80]]), beta=1.0)
        self.assertEqual(out[0].details["qid"], "Q2")  # ranked by score, not by cosine
        self.assertEqual((out[0].details["score"], out[0].details["similarity"]), (0.3, 0.7))
        gated = landmarks.aggregate(np.array([[0.30, 0.20]]), np.array([[1, 0]]), meta,
                                    similarities=np.array([[0.70, 0.80]]), min_similarity=0.75)
        self.assertEqual([c.details["qid"] for c in gated], ["Q1"])  # the gate applies to the cosine

    def test_gate_drops_weak_candidates_without_reweighting(self):
        meta = fake_meta(["Q1", "Q2"])
        sims = np.array([[0.70, 0.60], [0.50, 0.68]])
        rows = np.array([[0, 1], [0, 1]])
        everything = {c.details["qid"]: c.weight for c in landmarks.aggregate(sims, rows, meta, tau=0.05, min_similarity=0)}
        gated = landmarks.aggregate(sims, rows, meta, tau=0.05, min_similarity=0.69)
        self.assertEqual([c.details["qid"] for c in gated], ["Q1"])  # Q2's best cosine is 0.68
        self.assertAlmostEqual(gated[0].weight, everything["Q1"])  # its weight is kept, not renormalised
        self.assertLess(sum(c.weight for c in gated), 1.0)
        self.assertEqual(gated[0].details["n_views"], 2)  # the view below the gate still voted
        self.assertEqual(landmarks.aggregate(sims, rows, meta, min_similarity=0.99), [])
        self.assertEqual(landmarks.MIN_SIMILARITY, 0.70)

    def test_k_and_argument_checks(self):
        meta = fake_meta(["Q1", "Q2", "Q3"])
        self.assertEqual(len(landmarks.aggregate(np.array([[0.9, 0.8, 0.7]]), np.array([[0, 1, 2]]), meta, k=2)), 2)
        with self.assertRaises(ValueError):
            landmarks.aggregate(np.array([[0.9]]), np.array([[0]]), meta, view_names=["a", "b"])
        with self.assertRaises(ValueError):
            landmarks.aggregate(np.array([[0.9]]), np.array([[0]]), meta, tau=0)


def unit_rows(n, seed=0):
    rng = np.random.default_rng(seed)
    emb = rng.normal(size=(n, EMBED_DIM)).astype(np.float32)
    return emb / np.linalg.norm(emb, axis=1, keepdims=True)


class GalleryTest(unittest.TestCase):
    def test_search_and_open_roundtrip(self):
        emb = unit_rows(6)
        qids = [f"Q{i}" for i in range(1, 7)]
        rows = [{"key": f"PT/{q}", "qid": q, "country": "PT", "lat": str(38.7 + i / 100), "lon": "-9.1",
                 "types": "Q16970", "type_labels_en": "church", "heritage_labels_en": "", "commons_file": f"{q}.jpg",
                 "commons_page": "", "other_qids": "", "rel": f"PT/{q}.jpg", "sitelinks": "2"}
                for i, q in enumerate(qids)]
        roles = SimpleNamespace(classify=lambda labels, qids: ("landmark", 75, "church"))
        arrays = embed_gallery.shard_arrays(rows, emb, {"Q1": {"pt": "Igreja Um"}}, roles, ("unclassified", "landmark", 100))
        self.assertEqual(str(arrays["version"]), EMBED_VERSION)
        with tempfile.TemporaryDirectory() as d:
            np.savez(Path(d) / "shard_00000.npz", **arrays)  # no hub column yet: filled with the median (0 here: none known)
            g = landmarks.Gallery.open(d)
            self.assertEqual(len(g), 6)
            self.assertEqual(g.countries(), {"PT": 6})
            self.assertTrue(np.all(g.meta["hub"] == 0))
            self.assertEqual(len(landmarks.Gallery.open(d, countries=["ES"])), 0)
            query = np.stack([emb[2], emb[2] * 0.9 + emb[4] * 0.1])
            query /= np.linalg.norm(query, axis=1, keepdims=True)
            out = g.search(query, k=3, view_names=["h000", "h045"])
            self.assertEqual(out[0].details["qid"], "Q3")
            self.assertEqual(out[0].details["n_views"], 2)
            self.assertAlmostEqual(out[0].details["similarity"], 1.0, places=3)
            self.assertEqual(out[0].extent_m, 75.0)
            self.assertEqual(g.photo_path(out[0]), landmarks.COMMONS_DIR / "PT" / "Q3.jpg")
            self.assertEqual(g.photo_path(2), landmarks.COMMONS_DIR / "PT" / "Q3.jpg")
            self.assertEqual(g.meta["name"][0], "Igreja Um")
            np.savez(Path(d) / "shard_00001.npz", **dict(arrays, version=np.array("other-version")))
            with self.assertRaises(ValueError):
                landmarks.Gallery.open(d)

    def test_hub_correction_demotes_generic_photos(self):
        emb = unit_rows(3, seed=1)
        query = emb[0] * 0.7 + emb[1] * 0.71  # nearly as close to Q1 (generic) as to Q2 (distinctive)
        query /= np.linalg.norm(query)
        meta = fake_meta(["Q1", "Q2", "Q3"])
        meta["hub"] = np.array([0.80, 0.55, 0.60])
        g = landmarks.Gallery.from_arrays(emb, meta)
        plain = g.search(query, k=3, beta=0.0, min_similarity=0)
        corrected = g.search(query, k=3, beta=1.0, min_similarity=0)
        self.assertEqual(plain[0].details["qid"], "Q2")  # 0.71 vs 0.70 before the correction ...
        self.assertEqual(corrected[0].details["qid"], "Q2")
        self.assertGreater(corrected[0].weight, plain[0].weight)  # ... and a clearer winner after it
        c = corrected[0].details
        self.assertAlmostEqual(c["score"], c["similarity"] - 0.55, places=4)  # exact: score = cos - beta x hub
        self.assertEqual((c["hub"], c["beta"]), (0.55, 1.0))
        scores, sims, rows = g.neighbours(query[None], per_view_k=3, beta=1.0)
        np.testing.assert_allclose(sims[0], emb[rows[0]] @ query, atol=1e-5)
        np.testing.assert_allclose(scores[0], sims[0] - meta["hub"][rows[0]], atol=1e-5)
        self.assertEqual(g.meta["key"][0], "PT/Q1")
        self.assertIsNone(g.photo_path(SimpleNamespace(details={"qid": "Q99"})))


class EmbedGalleryTest(unittest.TestCase):
    def test_pick_name_prefers_the_country_language(self):
        labels = {"en": "Belem Tower", "pt": "Torre de Belém", "fr": "Tour de Belém"}
        self.assertEqual(embed_gallery.pick_name(labels, "PT"), "Torre de Belém")
        self.assertEqual(embed_gallery.pick_name(labels, "ES"), "Belem Tower")
        self.assertEqual(embed_gallery.pick_name({"mul": "X"}, "FR"), "X")
        self.assertEqual(embed_gallery.pick_name({}, "PT"), "")

    def test_classify_events_take_the_default(self):
        row = {"types": "Q1|Q2", "type_labels_en": "battle"}
        roles = SimpleNamespace(classify=lambda labels, qids: None)
        self.assertEqual(embed_gallery.classify(roles, ("unclassified", "landmark", 100), row),
                         ("landmark", 100.0, "events only: default"))
        seen = {}
        roles = SimpleNamespace(classify=lambda labels, qids: seen.update(labels=labels) or ("area", 3000, "parish"))
        self.assertEqual(embed_gallery.classify(roles, None, row), ("area", 3000.0, "parish"))
        self.assertEqual(seen["labels"], ["battle", ""])  # labels padded to the type QIDs


if __name__ == "__main__":
    unittest.main()
