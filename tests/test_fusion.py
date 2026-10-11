"""Tests for panoloc.fusion. Run from the repo root: .venv/bin/python -m unittest discover -s tests

Every coordinate and name here is invented or generic; none comes from the warm-up set. A fake name
index stands in for Data/index/names.sqlite, so these tests need no downloaded data.
"""
import json
import tempfile
import unittest
from unittest import mock

from panoloc import fusion
from panoloc.candidates import Candidate
from panoloc.fusion import (COUNTRY_FALLBACKS, COUNTRY_FLOOR, MAX_GROUP_RATIO, OFFICE_FACTOR, Clue, Hint,
                            clean_name_candidates, clues_from_ocr, clues_from_vlm, confident_countries, country_prior,
                            fuse, hints_from_ocr, hints_from_vlm, log_fusion, select, spread_m)
from panoloc.runlog import Run
from panoloc.scoring import haversine_m

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


def name_cand(lat, lng, label, role="landmark", weight=0.9, extent_m=50.0, country="PT", prior=0.9, **details):
    return Candidate(lat, lng, role, f"test:{label}:{lat},{lng}", label=label, weight=weight, extent_m=extent_m,
                     country=country, details={"prior": prior, "name_kind": "label", **details})


TOWN_A = (40.2000, -8.4000)
TOWN_B = (37.0000, -7.9000)


def near(point, dn_m=0.0, de_m=0.0):
    return (point[0] + dn_m / 111_320.0, point[1] + de_m / 85_000.0)


class FakeNames:
    """lookup / postcode from a dict; records the queries."""

    def __init__(self, table=None, postcodes=None):
        self.table, self.postcodes, self.queries = table or {}, postcodes or {}, []

    def lookup(self, text, countries=None, limit=10, **kwargs):
        self.queries.append((text, countries))
        found = self.table.get(text, [])
        if countries:
            found = [c for c in found if c.country in countries]
        return found[:limit]

    def postcode(self, code, country=None):
        return self.postcodes.get(code, [])


def clue(clue_id, group, candidates, reliability=0.5, scale=fusion.LOOKUP_SCALE):
    return Clue(clue_id, "ocr_name", group, reliability, candidates, scale)


class CountryPriorTest(unittest.TestCase):
    def test_uniform_without_hints(self):
        p = country_prior([])
        for c in ("PT", "ES", "FR"):
            self.assertAlmostEqual(p[c], 1 / 3)

    def test_one_group_is_capped(self):
        hints = [Hint(f"vlm:{i}", "vlm", ("FR",), "strong") for i in range(5)]  # 4^5 inside one group
        p = country_prior(hints)
        self.assertAlmostEqual(p["FR"] / p["ES"], MAX_GROUP_RATIO, places=6)

    def test_groups_multiply_and_floor_holds(self):
        hints = [Hint(f"ocr:s{i}", f"ocr:s{i}", ("PT",), "strong") for i in range(6)]
        p = country_prior(hints)
        self.assertGreater(p["PT"], 0.9)
        self.assertGreaterEqual(min(p["ES"], p["FR"]), COUNTRY_FLOOR - 1e-9)
        self.assertAlmostEqual(sum(p.values()), 1.0)

    def test_hint_naming_every_country_says_nothing(self):
        p = country_prior([Hint("x", "g", ("PT", "ES", "FR"), "strong")])
        self.assertAlmostEqual(p["PT"], 1 / 3)


class FuseTest(unittest.TestCase):
    def test_empty_gives_a_residual_answer(self):
        f = fuse([], [])
        self.assertEqual({h.source for h in f.hypotheses}, {c.source for c in COUNTRY_FALLBACKS.values()})
        self.assertEqual(f.output.method, "coarse_candidate")
        self.assertEqual(len(f.output.coordinates()), 10)

    def test_country_hint_moves_the_residual(self):
        f = fuse([], [Hint("vlm:lang", "vlm", ("FR",), "strong"), Hint("ocr:i1", "ocr:s1", ("FR",), "strong")])
        self.assertEqual(f.output.sources[0], "fallback:FR")

    def test_weights_are_normalised_and_sorted(self):
        f = fuse([clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Cafe A"), name_cand(*TOWN_B, "Cafe B", weight=0.3)])])
        self.assertAlmostEqual(sum(h.weight for h in f.hypotheses), 1.0)
        self.assertEqual([h.weight for h in f.hypotheses], sorted((h.weight for h in f.hypotheses), reverse=True))

    def test_agreement_across_groups_lifts_the_shared_town(self):
        # Sign 1 is ambiguous between town A and town B; sign 2 names a street in town A only
        sign1 = clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Igreja A", weight=0.5),
                                      name_cand(*TOWN_B, "Igreja B", weight=0.6)])
        sign2 = clue("c2", "ocr:s2", [name_cand(*near(TOWN_A, 300, 200), "Rua X", role="area", extent_m=250)])
        alone = fuse([sign1])
        both = fuse([sign1, sign2])
        weight = lambda f, label: next(h.weight for h in f.hypotheses if h.label == label)
        self.assertGreater(weight(alone, "Igreja B"), weight(alone, "Igreja A"))
        self.assertGreater(weight(both, "Igreja A"), weight(both, "Igreja B"))
        a = next(h for h in both.hypotheses if h.label == "Igreja A")
        self.assertIn("ocr:s2", a.details["fusion"]["agreeing_groups"])

    def test_one_group_never_confirms_itself(self):
        # Two clues from the same sign (one group) close together: no agreement bonus
        c1 = clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Name 1")])
        c2 = clue("c2", "ocr:s1", [name_cand(*near(TOWN_A, 100), "Name 2")])
        f = fuse([c1, c2])
        for h in f.hypotheses:
            if not h.details.get("residual"):
                self.assertEqual(h.details["fusion"]["agreement"], 1.0)

    def test_same_source_from_two_groups_merges_and_agrees(self):
        cand = name_cand(*TOWN_A, "Monument")
        f = fuse([clue("c1", "ocr:s1", [cand]), clue("c2", "vlm", [cand], reliability=0.3)])
        hits = [h for h in f.hypotheses if h.label == "Monument"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(sorted(hits[0].details["fusion"]["clues"]), ["c1", "c2"])
        self.assertGreater(hits[0].details["fusion"]["agreement"], 1.0)

    def test_ambiguous_lookup_shares_its_reliability(self):
        unique = fuse([clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Unique")])])
        many = fuse([clue("c1", "ocr:s1", [name_cand(TOWN_A[0] + i * 0.3, TOWN_A[1], f"Same {i}") for i in range(15)])])
        own = lambda f: max(h.details["fusion"]["own"] for h in f.hypotheses if "fusion" in h.details)
        self.assertGreater(own(unique), 5 * own(many))

    def test_distribution_clue_is_normalised(self):
        cands = [Candidate(TOWN_A[0] + i * 0.1, TOWN_A[1], "camera", f"osv5m:{i}", weight=50.0 + i) for i in range(4)]
        f = fuse([Clue("knn", "knn", "pe-core", 0.5, cands, scale=None)])
        total_own = sum(h.details["fusion"]["own"] for h in f.hypotheses if "fusion" in h.details)
        self.assertAlmostEqual(total_own, 0.5)

    def test_wrong_country_keeps_a_residual(self):
        f = fuse([clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Somewhere")])],
                 [Hint("vlm:lang", "vlm", ("ES",), "strong")])
        self.assertTrue(any(h.source == "fallback:ES" and h.weight > 0 for h in f.hypotheses))

    def test_payload_is_json_ready(self):
        sign1 = clue("c1", "ocr:s1", [name_cand(*TOWN_A, "A")])
        sign2 = clue("c2", "ocr:s2", [name_cand(*near(TOWN_A, 100), "B")])
        f = fuse([sign1, sign2])
        json.dumps(f.summary())
        json.dumps([h.to_dict() for h in f.hypotheses])


class NameCleaningTest(unittest.TestCase):
    def test_overseas_and_short_fuzzy_dropped_office_damped(self):
        keep = name_cand(*TOWN_A, "Cafe Central", match_type="exact")
        overseas = name_cand(-17.5, -149.5, "Faraway", overseas=True)
        fuzzy = name_cand(*TOWN_B, "Ealo", match_type="fuzzy")
        office = name_cand(*TOWN_B, "Energy office", osm_type="office=government")
        out = clean_name_candidates([keep, overseas, fuzzy, office], query="EALA")
        self.assertEqual([c.label for c in out], ["Cafe Central", "Energy office"])
        self.assertAlmostEqual(out[1].weight, office.weight * OFFICE_FACTOR)
        long_fuzzy = clean_name_candidates([fuzzy], query="Rua Augustaa")
        self.assertEqual(len(long_fuzzy), 1)

    def test_confident_countries(self):
        self.assertEqual(confident_countries({"PT": 0.9, "ES": 0.05, "FR": 0.05}), ["PT"])
        self.assertIsNone(confident_countries({"PT": 0.6, "ES": 0.3, "FR": 0.1}))

    def test_lookups_get_the_confident_country(self):
        names = FakeNames(table={"Avec Moi": [name_cand(*TOWN_A, "Avec Moi shop", country="ES")]})
        item = {"item_id": "i1", "sign_id": "s1", "kind": "name", "value": "Avec Moi", "details": {"query": "Avec Moi"},
                "countries": [], "regions": [], "strength": "weak", "source": "reading"}
        self.assertEqual(clues_from_ocr([item], names, countries=["FR"]), [])
        self.assertEqual(names.queries[-1], ("Avec Moi", ["FR"]))

    def test_shared_names_lend_less_agreement(self):
        unique = clue("c2", "ocr:s2", [name_cand(*near(TOWN_A, 200), "Unique shop", ambiguity=1)])
        generic = clue("c2", "ocr:s2", [name_cand(*near(TOWN_A, 200), "Tapas bar", occurrences=25)])
        target = clue("c1", "ocr:s1", [name_cand(*TOWN_A, "Target")])
        bonus = lambda f: next(h for h in f.hypotheses if h.label == "Target").details["fusion"]["agreement"]
        self.assertGreater(bonus(fuse([target, unique])), bonus(fuse([target, generic])))


class SelectTest(unittest.TestCase):
    def test_precise_beats_heavier_vague_when_urban(self):
        # A wide area with more weight against a small landmark: urban scoring wants the landmark
        vague = Candidate(*TOWN_A, "area", "test:region", label="Region", weight=0.55, extent_m=40_000)
        precise = Candidate(*TOWN_B, "landmark", "test:spot", label="Spot", weight=0.45, extent_m=20)
        s = select([vague, precise], category="urban")
        self.assertEqual(s["source"], "test:spot")

    def test_category_scenarios_are_recorded(self):
        hyps = [Candidate(*TOWN_A, "area", "test:a", weight=0.6, extent_m=3000),
                Candidate(*TOWN_B, "landmark", "test:b", weight=0.4, extent_m=20)]
        s = select(hyps, urban_probability=0.5)
        self.assertEqual(set(s["per_category"]), {"urban", "non-urban"})
        self.assertIn("categories_differ", s)
        self.assertEqual(s["urban_probability"], 0.5)

    def test_spread(self):
        self.assertEqual(spread_m(Candidate(*TOWN_A, "camera", "t:c")), fusion.ROLE_SPREAD_M["camera"])
        self.assertEqual(spread_m(Candidate(*TOWN_A, "landmark", "t:l", extent_m=100)), 100 + fusion.LANDMARK_VIEW_M)
        self.assertEqual(spread_m(Candidate(*TOWN_A, "area", "t:a", extent_m=1000, accuracy_m=50)), 1050)


class OutputTest(unittest.TestCase):
    def test_unverified_camera_is_coarse(self):
        f = fuse([Clue("knn", "knn", "pe-core", 0.9, [Candidate(*TOWN_A, "camera", "osv5m:1", weight=1.0)],
                       scale=None)])
        self.assertEqual(f.output.method, "coarse_candidate")
        self.assertEqual(f.output.source_role, "camera")

    def test_verified_camera_is_reference_camera(self):
        cand = Candidate(*TOWN_A, "camera", "osv5m:1", weight=1.0, accuracy_m=8, details={"verified_match": True})
        f = fuse([Clue("match", "match", "megaloc", 1.0, [cand], scale=None)])
        self.assertEqual(f.output.method, "reference_camera")

    def test_unknown_extent_stays_unknown(self):
        cand = Candidate(*TOWN_A, "camera", "osv5m:1", weight=1.0)
        f = fuse([Clue("knn", "knn", "pe-core", 1.0, [cand], scale=None)])
        self.assertIsNone(f.output.uncertainty_m)
        self.assertEqual(f.output.uncertainty_source, "unknown")


class PerceptionAdaptersTest(unittest.TestCase):
    @mock.patch.object(fusion, "REGION_CLUES", True)  # region clues are off by default since T39
    def test_ocr_items(self):
        names = FakeNames(
            table={"Rua Nova": [name_cand(*TOWN_A, "Rua Nova", role="area", extent_m=300)],
                   "Coimbra": [name_cand(*TOWN_A, "Coimbra district", role="area", extent_m=40_000),
                               name_cand(*TOWN_A, "Coimbra shop", extent_m=20)]},
            postcodes={"3000-123": [name_cand(*TOWN_A, "3000-123", role="area", extent_m=600)]})
        items = [
            {"item_id": "i1", "sign_id": "s1", "kind": "name", "value": "Rua Nova", "details": {"query": "Rua Nova"},
             "countries": [], "regions": [], "strength": "weak", "source": "reading"},
            {"item_id": "i2", "sign_id": "s2", "kind": "postcode", "value": "3000-123", "countries": ["PT"],
             "regions": [{"country": "PT", "level": "municipality", "name": "Coimbra"}], "strength": "strong",
             "source": "reading"},
            {"item_id": "i3", "sign_id": "s3", "kind": "phone", "value": "239 000 000", "countries": ["PT"],
             "regions": [{"country": "PT", "level": "district", "name": "Coimbra"}], "strength": "medium",
             "source": "alternative"},
        ]
        clues = clues_from_ocr(items, names, {"s1": 0.9, "s2": 0.95})
        kinds = sorted(c.kind for c in clues)
        self.assertEqual(kinds, ["ocr_name", "ocr_postcode", "ocr_region"])
        region = next(c for c in clues if c.kind == "ocr_region")
        self.assertEqual([c.label for c in region.candidates], ["Coimbra district"])  # the shop is too small
        self.assertAlmostEqual(region.reliability, fusion.REGION_RELIABILITY["medium"] * fusion.ALTERNATIVE_READING_FACTOR)
        self.assertEqual({c.group for c in clues}, {"ocr:s1", "ocr:s2", "ocr:s3"})
        hints = hints_from_ocr(items)
        self.assertEqual([(h.group, h.strength) for h in hints], [("ocr:s2", "strong"), ("ocr:s3", "weak")])

    @mock.patch.object(fusion, "REGION_CLUES", True)  # region clues are off by default since T39
    def test_region_clue_splits_over_uncovered_country(self):
        names = FakeNames(table={"Toledo": [name_cand(39.86, -4.02, "Toledo", role="area", extent_m=45_000,
                                                      country="ES")]})
        item = {"item_id": "i1", "sign_id": "s2", "kind": "phone", "value": "925450732", "countries": ["PT", "ES"],
                "regions": [{"country": "ES", "level": "province", "name": "Toledo"}], "strength": "medium",
                "source": "reading"}
        clue = clues_from_ocr([item], names)[0]
        self.assertEqual(sorted(c.source.split(":")[0] for c in clue.candidates), ["country", "test"])
        f = fuse([clue], [Hint("vlm:x", "vlm", ("PT",), "strong")])
        toledo = next(h for h in f.hypotheses if h.label == "Toledo")
        anywhere = next(h for h in f.hypotheses if h.source == "country:PT")
        self.assertGreater(anywhere.weight, toledo.weight)
        self.assertEqual(anywhere.details["fusion"]["agreement"], 1.0)

    def test_sign_words_are_not_places(self):
        names = FakeNames(table={"FOGO": [name_cand(*TOWN_B, "Fogo", role="area", extent_m=5000)],
                                 "Praia da Rocha": [name_cand(*TOWN_B, "Praia da Rocha", role="area", extent_m=800)]})
        item = lambda text: {"item_id": "i1", "sign_id": "s1", "kind": "name", "value": text,
                             "details": {"query": text}, "countries": [], "regions": [], "strength": "weak",
                             "source": "reading"}
        self.assertEqual(clues_from_ocr([item("FOGO")], names), [])
        self.assertEqual(len(clues_from_ocr([item("Praia da Rocha")], names)), 1)

    def test_region_clues_off_by_default(self):
        names = FakeNames(table={"Coimbra": [name_cand(*TOWN_A, "Coimbra district", role="area", extent_m=40_000)]})
        item = {"item_id": "i1", "sign_id": "s1", "kind": "phone", "value": "239000000", "countries": ["PT"],
                "regions": [{"country": "PT", "level": "district", "name": "Coimbra"}], "strength": "medium",
                "source": "reading"}
        self.assertEqual(clues_from_ocr([item], names), [])
        self.assertEqual([h.countries for h in hints_from_ocr([item])], [("PT",)])  # still a country hint

    @mock.patch.object(fusion, "REGION_CLUES", True)  # region clues are off by default since T39
    def test_vlm(self):
        names = FakeNames(table={"Old Bridge": [name_cand(*TOWN_B, "Old Bridge")],
                                 "Lisbon": [name_cand(*TOWN_A, "Lisbon", role="area", extent_m=10_000)]})
        landmarks = [{"name": "Old Bridge", "confidence": "high", "support": 2, "views": ["h000", "h045"],
                      "digits_unverified": False},
                     {"name": "Unknown Tower", "confidence": "low", "support": 1, "views": ["h090"]}]
        vlm_hints = [{"key": "street_plaque", "value": "blue_on_white_azulejo", "countries": ["PT"],
                      "regions": ["Lisbon"], "strength": "medium", "views": ["h000"], "support": 1, "share": 1.0,
                      "majority": True, "conflict": False, "hard": False},
                     {"key": "post_box", "value": "yellow_logo_unclear", "countries": ["ES", "FR"], "regions": [],
                      "strength": "medium", "views": ["h090"], "support": 1, "share": 0.5, "majority": False,
                      "conflict": True, "hard": False}]
        clues = clues_from_vlm(landmarks, vlm_hints, names)
        self.assertEqual([c.kind for c in clues], ["vlm_landmark", "vlm_region"])  # no match for the tower
        self.assertTrue(all(c.group == "vlm" for c in clues))
        hints = hints_from_vlm(vlm_hints)
        self.assertEqual([h.strength for h in hints], ["medium", "weak"])


class LogTest(unittest.TestCase):
    def test_log_fusion_and_output(self):
        f = fuse([clue("c1", "ocr:s1", [name_cand(*TOWN_A, "A")])], [Hint("vlm:x", "vlm", ("PT",), "medium")])
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp)
            evidence_id = log_fusion(run, f)
            f.output.log(run)
            path = run.finish()
            log = json.loads(path.read_text())
        types = [e["type"] for e in log["events"]]
        self.assertIn("candidates.updated", types)
        self.assertIn("output.produced", types)
        cands = next(e for e in log["events"] if e["type"] == "candidates.updated")["payload"]["candidates"]
        self.assertEqual(cands[0]["candidate_id"], "h1")
        self.assertTrue(evidence_id.startswith("e"))
        out = next(e for e in log["events"] if e["type"] == "output.produced")["payload"]
        self.assertEqual(len(out["coordinates"]), 10)
        self.assertLess(haversine_m((out["coordinates"][0]["lat"], out["coordinates"][0]["lng"]), TOWN_A), 1)


if __name__ == "__main__":
    unittest.main()
