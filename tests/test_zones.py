"""Tests for panoloc.zones and the named-zone questions of panoloc.questions (T32).

Run from the repo root with the venv (shapely, pyogrio): .venv/bin/python -m unittest discover -s tests

The synthetic tests build an index in memory from invented polygons. The tests on the built file
(Data/index/zones.gpkg, from tools/build_zones.py) skip when it is absent; they use famous public places
only, never a warm-up panorama's location.
"""
import copy
import importlib.util
import json
import math
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import shapely

from panoloc import zones as Z
from panoloc.candidates import Candidate
from panoloc.questions import (MAX_OPTIONS, Option, RegionQuestion, ZoneOption, apply_answer, area_candidate,
                               ask_operator, expected_gain, region_chain, region_question)
from panoloc.runlog import Run
from panoloc.scoring import haversine_m

ROOT = Path(__file__).resolve().parent.parent
PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


def cand(lat, lng, weight=1.0, label=""):
    return Candidate(lat, lng, "camera", f"test:{lat},{lng}", label=label or f"{lat},{lng}", weight=weight)


class Scripted:
    def __init__(self, *lines):
        self.lines = list(lines)

    def __call__(self, prompt=""):
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


def pieces(outline, south, west, north, east, rows, cols):
    """The outline cut by a rows x cols grid over the box: polygons that tile the outline exactly."""
    out = []
    for r in range(rows):
        for c in range(cols):
            cell = shapely.box(west + (east - west) * c / cols, south + (north - south) * r / rows,
                               west + (east - west) * (c + 1) / cols, south + (north - south) * (r + 1) / rows)
            piece = shapely.intersection(outline, cell)
            if not piece.is_empty and piece.area > 0:
                out.append(piece)
    return out


def synthetic():
    """Three invented countries, x = longitude, y = latitude:
      PT  a concave mainland (a bay bites into its west coast) in 2 districts x 2 municipalities x 4
          parishes, plus an autonomous region with one island (one municipality, one parish: a chain)
      ES  east of PT across a 0.002-degree gap (about 175 m), 2 communities x 2 provinces
      FR  north of ES, touching it, 1 region x 3 departments
    """
    mainland = shapely.difference(shapely.box(-9.0, 38.0, -7.0, 40.0),
                                  shapely.Polygon([(-9.01, 38.8), (-8.6, 39.0), (-9.01, 39.2)]))
    leaves, coarse = [], [
        {"zone_id": "PT", "name": "Portugal", "level": "country", "country": "PT", "parent_id": None},
        {"zone_id": "ES", "name": "Spain", "level": "country", "country": "ES", "parent_id": None},
        {"zone_id": "FR", "name": "France", "level": "country", "country": "FR", "parent_id": None},
        {"zone_id": "PT:autonomous_region:2", "name": "Região Autónoma de Teste", "level": "autonomous_region",
         "country": "PT", "parent_id": "PT"},
        {"zone_id": "PT:island:41", "name": "Ilha de Teste", "level": "island", "country": "PT",
         "parent_id": "PT:autonomous_region:2"},
        {"zone_id": "PT:municipality:4101", "name": "Vila Teste", "level": "municipality", "country": "PT",
         "parent_id": "PT:island:41"},
    ]
    for d, (west, east) in enumerate(((-9.0, -8.0), (-8.0, -7.0)), start=1):
        district = f"PT:district:{d:02d}"
        coarse.append({"zone_id": district, "name": ["Porto", "Évora"][d - 1], "level": "district", "country": "PT",
                       "parent_id": "PT"})
        for m, (south, north) in enumerate(((38.0, 39.0), (39.0, 40.0)), start=1):
            muni = f"PT:municipality:{d:02d}{m:02d}"
            coarse.append({"zone_id": muni, "name": f"Município {d}{m}", "level": "municipality", "country": "PT",
                           "parent_id": district})
            region = shapely.intersection(mainland, shapely.box(west, south, east, north))
            for p, geom in enumerate(pieces(region, south, west, north, east, 2, 2), start=1):
                leaves.append({"zone_id": f"PT:parish:{d:02d}{m:02d}{p:02d}", "name": f"Freguesia {d}{m}{p}",
                               "level": "parish", "country": "PT", "parent_id": muni, "geometry": geom})
    island = shapely.Polygon([(-16.9, 32.6), (-16.6, 32.65), (-16.7, 32.85), (-16.95, 32.8)])
    leaves.append({"zone_id": "PT:parish:410101", "name": "Freguesia da Ilha", "level": "parish", "country": "PT",
                   "parent_id": "PT:municipality:4101", "geometry": island})
    for c, (south, north) in enumerate(((38.0, 39.0), (39.0, 40.0)), start=1):
        community = f"ES:community:C{c}"
        coarse.append({"zone_id": community, "name": ["Comunidad de Prueba", "Andalucía"][c - 1],
                       "level": "community", "country": "ES", "parent_id": "ES"})
        for p, (west, east) in enumerate(((-6.998, -5.5), (-5.5, -4.0)), start=1):
            leaves.append({"zone_id": f"ES:province:P{c}{p}", "name": ["Palmas, Las", "Toledo"][p - 1] + f" {c}",
                           "level": "province", "country": "ES", "parent_id": community,
                           "geometry": shapely.box(west, south, east, north)})
    coarse.append({"zone_id": "FR:region:FR-TST", "name": "Région Test", "level": "region", "country": "FR",
                   "parent_id": "FR"})
    for k, (west, east) in enumerate(((-6.998, -6.0), (-6.0, -5.0), (-5.0, -4.0)), start=1):
        leaves.append({"zone_id": f"FR:department:D{k}", "name": f"Département {k}", "level": "department",
                       "country": "FR", "parent_id": "FR:region:FR-TST",
                       "geometry": shapely.box(west, 40.0, east, 41.0)})
    return Z.Zones.from_leaves(leaves, coarse)


ZONES = synthetic()


def boundary_and_interior(geom, step=0.002, n=25):
    """Dense samples of a zone: its boundary every `step` degrees and an n x n grid inside it."""
    coords = shapely.get_coordinates(shapely.segmentize(shapely.boundary(geom), step))
    west, south, east, north = shapely.bounds(geom)
    xs, ys = np.meshgrid(np.linspace(west, east, n), np.linspace(south, north, n))
    inside = shapely.contains_xy(geom, xs.ravel(), ys.ravel())
    return np.vstack([coords, np.column_stack([xs.ravel()[inside], ys.ravel()[inside]])])


class ZonesIndexTest(unittest.TestCase):
    def test_tree_levels_and_labels(self):
        self.assertEqual([z.name for z in ZONES.roots()], ["France", "Portugal", "Spain"])
        self.assertEqual([z.label for z in ZONES.children("PT")],
                         ["Distrito de Évora", "Distrito do Porto", "Região Autónoma de Teste"])
        self.assertEqual(ZONES.children("PT:parish:010101"), [])
        labels = {z.id: z.label for z in ZONES}
        self.assertEqual(labels["PT:district:01"], "Distrito do Porto")
        self.assertEqual(labels["PT:district:02"], "Distrito de Évora")
        self.assertEqual(labels["PT:municipality:0101"], "Município 11 (município)")
        self.assertEqual(labels["PT:parish:010101"], "Freguesia 111 (freguesia, Município 11)")
        self.assertEqual(labels["ES:province:P11"], "Palmas, Las 1 (provincia)")  # not article-last: kept
        self.assertEqual(Z.display_name("Palmas, Las", "province"), "Las Palmas")
        self.assertEqual(labels["ES:community:C1"], "Comunidad de Prueba")
        self.assertEqual(labels["ES:community:C2"], "Andalucía (comunidad autónoma)")
        self.assertEqual(labels["FR:department:D1"], "Département 1 (département)")
        self.assertEqual(ZONES.get("PT:municipality:0101").description,
                         "a municipality of Portugal, in Distrito do Porto")
        self.assertEqual([z.id for z in ZONES.ancestors("PT:parish:410101")],
                         ["PT", "PT:autonomous_region:2", "PT:island:41", "PT:municipality:4101", "PT:parish:410101"])
        self.assertTrue(ZONES.is_within("PT:parish:010101", "PT:district:01"))
        self.assertTrue(ZONES.is_within("PT:parish:010101", "PT"))
        self.assertFalse(ZONES.is_within("PT:parish:010101", "PT:district:02"))
        self.assertEqual(len(ZONES.leaves("PT:district:01")), 8)
        self.assertEqual([z.id for z in ZONES.search("evora")], ["PT:district:02"])
        with self.assertRaises(KeyError):
            ZONES.get("PT:district:99")

    def test_levels_nest_and_tile_exactly(self):
        for zone in ZONES:
            kids = ZONES.children(zone)
            if not kids:
                continue
            geom = ZONES.exact_geometry(zone)
            union = shapely.union_all([ZONES.exact_geometry(k) for k in kids])
            self.assertAlmostEqual(shapely.area(shapely.symmetric_difference(geom, union)), 0.0, places=12)
            for i, a in enumerate(kids):
                for b in kids[i + 1:]:
                    overlap = shapely.area(shapely.intersection(ZONES.exact_geometry(a), ZONES.exact_geometry(b)))
                    self.assertAlmostEqual(overlap, 0.0, places=12)

    def test_representative_points_lie_inside_their_zones(self):
        for zone in ZONES:
            lat, lng = zone.rep
            self.assertTrue(shapely.contains_xy(ZONES.exact_geometry(zone), lng, lat), zone.id)
            loc = ZONES.locate(lat, lng)
            self.assertIn(zone.id, loc, zone.id)
            self.assertEqual(loc.distance_m, 0.0)
        # the concave mainland's rep point avoids the bay; the island chain's points sit on the island
        self.assertFalse(shapely.contains_xy(shapely.Polygon([(-9.01, 38.8), (-8.6, 39.0), (-9.01, 39.2)]),
                                             ZONES.get("PT").rep[1], ZONES.get("PT").rep[0]))
        self.assertEqual(ZONES.get("PT:island:41").rep, ZONES.get("PT:parish:410101").rep)

    def test_bound_covers_the_true_maximum_distance(self):
        for zone in ZONES:
            samples = boundary_and_interior(ZONES.exact_geometry(zone))
            origins = [zone.rep, (zone.bbox[0], zone.bbox[1]), (zone.bbox[2] + 0.5, zone.bbox[3] + 0.5), (39.0, -8.0)]
            for origin in origins:
                true_max = max(haversine_m(origin, (y, x)) for x, y in samples)
                bound = ZONES.bound_m(origin, zone)
                self.assertGreaterEqual(bound, true_max, (zone.id, origin))
                self.assertLessEqual(bound, true_max * 1.01 + 2.0, (zone.id, origin))  # and not wildly loose
        deviated = Z.Zones(*Z.derive([{**{"zone_id": "PT", "name": "P", "level": "country", "country": "PT",
                                          "parent_id": None}, "geometry": shapely.box(-9, 38, -8, 39),
                                       "deviation_m": 40.0}]))
        self.assertGreaterEqual(deviated.bound_m((38.5, -8.5), "PT") - plain_bound(), 40.0)

    def test_locate_snaps_near_misses_and_rejects_far_points(self):
        loc = ZONES.locate(39.5, -8.5)
        self.assertEqual([z.level for z in loc.chain], ["country", "district", "municipality", "parish"])
        self.assertEqual(loc.country, "PT")
        self.assertFalse(loc.snapped)
        lng = -9.0 - 300 / (Z.M_PER_DEG * math.cos(math.radians(38.5)))  # 300 m off the west coast
        loc = ZONES.locate(38.5, lng)
        self.assertTrue(loc.snapped)
        self.assertAlmostEqual(loc.distance_m, 300, delta=3)
        self.assertEqual(loc.leaf.parent_id, "PT:municipality:0101")
        self.assertIsNone(ZONES.locate(38.5, -9.1))  # about 8.7 km out at sea
        self.assertIsNone(ZONES.locate(38.5, lng, snap_m=100))
        gap = ZONES.locate(38.5, -6.9995)  # in the 175 m gap: 44 m from Portugal, 131 m from Spain
        self.assertEqual(gap.country, "PT")
        self.assertAlmostEqual(gap.distance_m, 0.0005 * Z.M_PER_DEG * math.cos(math.radians(38.5)), delta=1)
        bay = ZONES.locate(39.0, -8.75)  # inside the bay, about 13 km from its shores
        self.assertIsNone(bay)
        self.assertTrue(ZONES.contains("PT", (38.5, lng)))
        self.assertFalse(ZONES.contains("ES", (38.5, lng)))
        with self.assertRaises(ValueError):
            ZONES.locate(float("nan"), 0.0)

    def test_locate_is_fast(self):
        rng = np.random.default_rng(7)
        lats, lngs = rng.uniform(37.9, 41.1, 3000), rng.uniform(-9.2, -3.9, 3000)
        t = time.perf_counter()
        for lat, lng in zip(lats, lngs):
            ZONES.locate(lat, lng)
        self.assertLess((time.perf_counter() - t) / len(lats), 0.005)

    def test_zone_candidate_for_an_area_the_team_picked(self):
        c = ZONES.candidate("PT:district:02", weight=0.3)
        self.assertEqual((c.role, c.source, c.weight, c.country), ("area", "zone:PT:district:02", 0.3, "PT"))
        self.assertEqual((c.lat, c.lng), ZONES.get("PT:district:02").rep)
        self.assertEqual(c.extent_m, ZONES.bound_m(ZONES.get("PT:district:02").rep, "PT:district:02"))
        self.assertEqual(c.details["extent_source"], "geometric_bound")

    def test_missing_file_raises_a_catchable_error(self):
        with self.assertRaises(FileNotFoundError) as caught:
            Z.Zones.open(ROOT / "Data" / "index" / "no-such-zones.gpkg")
        self.assertIsInstance(caught.exception, Z.ZonesNotBuilt)
        self.assertIn("tools/build_zones.py", str(caught.exception))

    def test_file_round_trip(self):
        spec = importlib.util.spec_from_file_location("build_zones", ROOT / "tools" / "build_zones.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        rows, geoms = Z.derive(*synthetic_records())
        for r in rows:
            r["outline_deviation_m"] = 0.0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "zones.gpkg"
            builder.write_gpkg(path, rows, geoms, {"schema": Z.SCHEMA, "built_utc": "test"})
            with Z.Zones.open(path) as zones:
                self.assertEqual(len(zones), len(ZONES))
                self.assertEqual(zones.locate(39.5, -8.5).to_dict(), ZONES.locate(39.5, -8.5).to_dict())
                self.assertEqual(zones.get("PT:district:01"), ZONES.get("PT:district:01"))
                self.assertEqual(zones.bound_m((39.0, -8.0), "ES"), ZONES.bound_m((39.0, -8.0), "ES"))
                self.assertIsNone(zones.get("PT").parent_id)
            builder.write_gpkg(path, rows, geoms, {"schema": "other/0"})
            with self.assertRaises(RuntimeError):
                Z.Zones.open(path)


def synthetic_records():
    """The leaves and coarse records of synthetic(), for building a file."""
    leaves, coarse = [], []
    for zone in ZONES:
        rec = {"zone_id": zone.id, "name": zone.name, "level": zone.level, "country": zone.country,
               "parent_id": zone.parent_id}
        if zone.is_leaf:
            leaves.append({**rec, "geometry": ZONES.geometry(zone)})
        else:
            coarse.append(rec)
    return leaves, coarse


def plain_bound():
    plain = Z.Zones(*Z.derive([{"zone_id": "PT", "name": "P", "level": "country", "country": "PT", "parent_id": None,
                                "geometry": shapely.box(-9, 38, -8, 39)}]))
    return plain.bound_m((38.5, -8.5), "PT")


SPREAD = [cand(39.6, -8.6, 0.2, "PT north-west"), cand(38.4, -7.4, 0.2, "PT south-east"),
          cand(38.5, -5.0, 0.2, "ES south"), cand(39.5, -6.5, 0.1, "ES north"), cand(40.5, -5.5, 0.2, "FR"),
          cand(32.7, -16.75, 0.1, "Island")]


class RegionQuestionTest(unittest.TestCase):
    def assert_tiles(self, q):
        """Named zones are disjoint, every hypothesis lands in exactly one option, and without a
        complement the zones tile the whole allowed area."""
        named = [o for o in q.options if not o.complement]
        geoms = [ZONES.exact_geometry(o.zone_id) for o in named]
        for i, a in enumerate(geoms):
            for b in geoms[i + 1:]:
                self.assertAlmostEqual(shapely.area(shapely.intersection(a, b)), 0.0, places=12)
        union = shapely.union_all(geoms)
        self.assertAlmostEqual(shapely.area(union), sum(shapely.area(g) for g in geoms), places=9)
        everything = shapely.union_all([ZONES.exact_geometry(z) for z in ZONES.roots()])
        if not any(o.complement for o in q.options):
            self.assertAlmostEqual(shapely.area(shapely.symmetric_difference(union, everything)), 0.0, places=9)
        if q.split_zone is not None:  # named zones lie in the zone they split
            self.assertAlmostEqual(shapely.area(shapely.difference(union, ZONES.exact_geometry(q.split_zone))), 0.0,
                                   places=12)
        rng = np.random.default_rng(3)
        points = list(zip(rng.uniform(31.0, 42.0, 600), rng.uniform(-18.0, -3.0, 600)))
        points += [(38.5, -6.9995), (38.5, -9.003), (39.0, -8.75), (52.5, 13.4), (32.7, -16.75)]
        for p in points:
            holding = [o for o in named if o.contains(p)]
            self.assertLessEqual(len(holding), 1, p)
            chosen = q.option_for(p)
            self.assertIn(chosen, q.options)
            self.assertIs(chosen, holding[0] if holding else next(o for o in q.options if o.complement)
                          if any(o.complement for o in q.options) else chosen)
            loc = ZONES.locate(*p)
            if holding:
                self.assertIn(holding[0].zone_id, loc)
        for o in named:
            self.assertTrue(o.contains(o.latlng))
            self.assertEqual(o.point_role, "area")
            self.assertGreaterEqual(o.bound_m, max(haversine_m(o.latlng, (y, x)) for x, y in
                                                   boundary_and_interior(ZONES.exact_geometry(o.zone_id))))

    def test_the_whole_area_gets_the_three_countries(self):
        q = region_question(SPREAD, ZONES)
        self.assertIsInstance(q, RegionQuestion)
        self.assertEqual(q.kind, "zone")
        self.assertEqual(len(q.options), 3)
        self.assertFalse(any(o.complement for o in q.options))
        self.assertEqual([o.label for o in q.options], ["Portugal", "Spain", "France"])
        self.assertEqual([round(o.support, 6) for o in q.options], [0.5, 0.3, 0.2])
        self.assert_tiles(q)
        self.assertIs(q.option_for((52.5, 13.4)).zone_id, "FR")  # beyond every zone: the nearest country
        self.assertEqual(q.option_for((31.0, -17.0)).zone_id, "PT")  # at sea near the island

    def test_the_coarsest_level_that_splits_the_weight(self):
        portugal = [cand(39.6, -8.6, 0.4), cand(38.4, -7.4, 0.3), cand(39.4, -7.3, 0.2), cand(38.5, -5.0, 0.1)]
        q = region_question(portugal, ZONES)
        self.assertEqual(q.split_zone.id, "PT")
        self.assertEqual([o.zone_id for o in q.options[:-1]], ["PT:district:02", "PT:district:01",
                                                               "PT:autonomous_region:2"])
        self.assertEqual((q.options[-1].label, q.options[-1].complement), ("Outside Portugal", True))
        self.assertEqual(q.option_for((38.5, -5.0)).id, "d")
        self.assert_tiles(q)
        one_district = [cand(38.2, -8.8, 0.5), cand(39.7, -8.2, 0.3), cand(39.2, -8.3, 0.15), cand(38.5, -5.0, 0.05)]
        q = region_question(one_district, ZONES)
        self.assertEqual(q.split_zone.id, "PT:district:01")
        self.assertEqual({o.zone_level for o in q.options[:-1]}, {"municipality"})
        self.assertEqual(q.options[-1].label, "Outside Distrito do Porto")
        self.assert_tiles(q)
        one_municipality = [cand(38.2, -8.8, 0.5), cand(38.3, -8.2, 0.3), cand(38.8, -8.3, 0.15), cand(38.7, -8.9, 0.04),
                            cand(38.5, -5.0, 0.01)]
        q = region_question(one_municipality, ZONES)
        self.assertEqual(q.split_zone.id, "PT:municipality:0101")
        self.assertEqual(len(q.options), 4)
        self.assertEqual(q.options[-1].label, "Elsewhere")
        self.assertIn("the rest of Município 11 (município), or outside it", q.options[-1].detail)
        self.assertEqual([o.support > 0 for o in q.options[:3]], [True, True, True])
        self.assert_tiles(q)
        q = region_question(one_municipality, ZONES, descend_share=None)
        self.assertEqual([o.label for o in q.options], ["Portugal", "Spain", "France"])

    def test_a_chained_scope_offers_its_subzones(self):
        q = region_question(SPREAD, ZONES, scope="PT:district:01", descend_share=None)
        self.assertEqual(q.scope_zone.id, "PT:district:01")
        self.assertEqual([o.zone_id for o in q.options[:-1]], ["PT:municipality:0102", "PT:municipality:0101"])
        self.assertEqual(q.options[-1].label, "Outside Distrito do Porto")
        self.assertEqual(q.option_for((38.5, -5.0)), q.options[-1])
        self.assertEqual(q.log_details()["scope"]["zone"]["zone_id"], "PT:district:01")
        self.assert_tiles(q)
        deeper = region_question(SPREAD, ZONES, scope="PT:district:01")  # its one hypothesis is in 0102
        self.assertEqual(deeper.split_zone.id, "PT:municipality:0102")
        self.assertEqual([o.zone_id for o in deeper.options[:-1]], ["PT:parish:010203"])
        self.assertEqual(deeper.options[-1].label, "Elsewhere")
        self.assertIn("not in the parish above: the rest of Município 12", deeper.options[-1].detail)
        self.assert_tiles(deeper)
        island = region_question(SPREAD, ZONES, scope="PT:autonomous_region:2")
        self.assertEqual([o.zone_id for o in island.options[:-1]], ["PT:parish:410101"])  # the chain is looked through
        self.assertEqual(island.options[-1].label, "Outside Região Autónoma de Teste")
        with self.assertRaises(ValueError):
            region_question(SPREAD, ZONES, scope="PT:parish:010101")  # a leaf: cells take over (T42)

    def test_excluded_zones_are_not_offered_again(self):
        heavy = [cand(39.6, -8.6, 0.5), cand(38.4, -7.4, 0.5)]
        first = region_question(heavy, ZONES, scope="PT")
        self.assertEqual({o.zone_id for o in first.options[:-1]}, {"PT:district:01", "PT:district:02",
                                                                   "PT:autonomous_region:2"})
        self.assertEqual(first.options[-1].label, "Outside Portugal")
        districts = ["PT:district:01", "PT:district:02"]
        again = region_question(heavy, ZONES, scope="PT", exclude=districts)  # after "Elsewhere" was picked
        self.assertEqual([o.zone_id for o in again.options[:-1]], ["PT:autonomous_region:2"])
        self.assertEqual(again.details["excluded"], districts)
        self.assertEqual(again.options[-1].label, "Elsewhere")
        self.assertIn("not in the autonomous region above: the rest of Portugal, or outside it",
                      again.options[-1].detail)
        for c in heavy:  # their hypotheses still land in exactly one option: the complement
            self.assertIs(again.option_for(c), again.options[-1])
        self.assert_tiles(again)
        root = region_question(heavy, ZONES, exclude=districts)  # no weight left: the whole area again
        self.assertEqual([o.label for o in root.options], ["France", "Portugal", "Spain"])
        self.assert_tiles(root)

    def test_chaining_narrows_the_scope_and_recovers_from_a_wrong_answer(self):
        candidates = [cand(39.6, -8.6, 0.4), cand(38.4, -7.4, 0.3), cand(38.5, -5.0, 0.3)]
        q = region_question(candidates, ZONES)  # Portugal / Spain / France
        scope, exclude = region_chain(q, next(o.id for o in q.options if o.zone_id == "PT"))
        self.assertEqual((scope, exclude), ("PT", []))
        q2 = region_question(candidates, ZONES, scope=scope)  # Évora, Porto, the region, then "Outside Portugal"
        self.assertEqual((q2.options[-1].label, q2.details["outside_zone"]), ("Outside Portugal", "PT"))
        self.assertEqual(region_chain(q2, q2.options[0].id, scope, exclude), (q2.options[0].zone_id, []))
        scope, exclude = region_chain(q2, q2.options[-1].id, scope, exclude)
        self.assertEqual((scope, exclude), (None, ["PT"]))  # "Portugal" was wrong: search everywhere else
        q3 = region_question(candidates, ZONES, scope=scope, exclude=exclude)  # the one hypothesis left is in P12
        self.assertEqual([o.zone_id for o in q3.options[:-1]], ["ES:province:P12", "ES:province:P11"])
        self.assertEqual(q3.options[-1].label, "Outside Comunidad de Prueba")
        self.assertFalse(any(ZONES.is_within(o.zone_id, "PT") for o in q3.options[:-1]))
        self.assert_tiles(q3)
        q3 = region_question(candidates, ZONES, scope=scope, exclude=exclude, descend_share=None)
        self.assertEqual([o.zone_id for o in q3.options[:-1]], ["ES", "FR"])
        self.assertEqual(q3.options[-1].label, "Elsewhere")
        self.assertIn("not in the 2 countries above", q3.options[-1].detail)
        deep = [cand(38.2, -8.8, 0.5), cand(38.3, -8.2, 0.3), cand(38.8, -8.3, 0.15), cand(38.7, -8.9, 0.05)]
        q4 = region_question(deep, ZONES)  # three parishes of one municipality, then "Elsewhere"
        named = sorted(o.zone_id for o in q4.options[:-1])
        self.assertEqual(region_chain(q4, q4.options[-1].id), (None, named))
        self.assertEqual(region_chain(q4, q4.options[-1].id, "PT:district:01", ["ES"]),
                         ("PT:district:01", sorted(["ES", *named])))

    def test_spread_lets_questions_split_a_zone_with_no_hypothesis(self):
        spread = ZONES.spread("PT:district:02", weight=0.6)
        self.assertEqual(sorted(c.details["zone_id"] for c in spread), ["PT:municipality:0201", "PT:municipality:0202"])
        self.assertAlmostEqual(sum(c.weight for c in spread), 0.6)
        for c in spread:
            self.assertEqual((c.role, c.details["spread_of"]), ("area", "PT:district:02"))
            self.assertIn(c.details["zone_id"], ZONES.locate(*c.point))
        q = region_question(spread + [cand(39.6, -8.6, 0.01)], ZONES, scope="PT:district:02")
        self.assertEqual(sorted(o.zone_id for o in q.options[:-1]), ["PT:municipality:0201", "PT:municipality:0202"])
        self.assertEqual(q.options[-1].label, "Outside Distrito de Évora")
        self.assertTrue(expected_gain(spread, q, urban_probability=0.5)["worth_asking"])
        self.assertEqual(ZONES.spread("PT:parish:010101"), [ZONES.candidate("PT:parish:010101")])
        self.assertEqual([c.details["zone_id"] for c in ZONES.spread("PT:autonomous_region:2")], ["PT:parish:410101"])

    def test_options_say_what_their_point_is_and_link_to_maps(self):
        q = region_question([cand(38.2, -8.8, 0.6), cand(39.7, -7.5, 0.4)], ZONES, scope="PT")
        o = q.options[0]
        self.assertIsInstance(o, ZoneOption)
        self.assertIn("not a camera position", o.detail)
        self.assertIn("A district of Portugal, about", o.detail)
        d = o.to_dict()
        json.dumps(q.option_dicts())
        for key in ("zone_id", "zone_level", "zone_name", "area_km2", "extent", "bound_m", "links", "point"):
            self.assertIn(key, d)
        self.assertEqual(d["zone"]["type"], "Polygon")
        self.assertTrue(d["links"]["google_maps_zone"].startswith("https://www.google.com/maps/search/?api=1&query="))
        self.assertIn("osm_zone", d["links"])
        self.assertEqual(d["point_role"], "area")
        self.assertTrue(q.options[-1].to_dict()["complement"])

    def test_a_skip_changes_nothing(self):
        candidates = [cand(38.2, -8.8, 0.5), cand(38.5, -5.0, 0.5)]
        q = region_question(candidates, ZONES)
        before, options_before = copy.deepcopy(candidates), q.option_dicts()
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp)
            self.assertIsNone(ask_operator(run, q, Scripted("s"), lambda *_: None))
            self.assertEqual(run.penalties.multiplier, 1.0)
            self.assertEqual([e["type"] for e in run.events][-1], "question.skipped")
            self.assertEqual(run.events[1]["payload"]["scope"]["label"], "Portugal, Spain and France")
        self.assertEqual(candidates, before)
        self.assertEqual(q.option_dicts(), options_before)

    def test_expected_gain_and_apply_answer_work_unchanged(self):
        candidates = [cand(38.2, -8.8, 0.5), cand(38.5, -5.0, 0.5)]
        q = region_question(candidates, ZONES)
        gain = expected_gain(candidates, q, urban_probability=0.5)
        self.assertTrue(gain["worth_asking"])
        self.assertAlmostEqual(sum(a["probability"] for a in gain["answers"]), 1.0)
        after = apply_answer(candidates, q, "b")  # Spain
        self.assertEqual(after[1].weight, 0.5)
        self.assertAlmostEqual(after[0].weight, 0.5 * 0.1 / (2 * 0.9))
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp)
            option = ask_operator(run, q, Scripted("b"), lambda *_: None)
            self.assertEqual(option.zone_id, "ES")
            self.assertAlmostEqual(run.penalties.multiplier, 0.95)

    def test_area_candidate_for_a_zone_holding_no_hypothesis(self):
        q = region_question([cand(39.6, -8.6, 1.0)], ZONES, scope="PT", descend_share=None)
        empty = next(o for o in q.options if not o.complement and not o.covers)
        c = area_candidate(empty, weight=0.2)
        self.assertEqual((c.role, c.source, c.extent_m, c.weight), ("area", f"zone:{empty.zone_id}", empty.bound_m, 0.2))
        self.assertEqual(c.point, empty.latlng)
        self.assertEqual(q.option_for(c), empty)
        with self.assertRaises(ValueError):
            area_candidate(q.options[-1])

    def test_region_rules_are_enforced(self):
        q = region_question(SPREAD, ZONES, scope="PT")
        named, outside = q.options[:-1], q.options[-1]
        with self.assertRaises(ValueError):  # part of the allowed area needs its complement
            RegionQuestion("zone", "Which zone?", named, zones=ZONES)
        with self.assertRaises(ValueError):  # a zone and a zone inside it overlap
            inner = copy.copy(named[0])
            inner.id, inner.zone_id = "c", ZONES.children(named[0].zone_id)[0].id
            RegionQuestion("zone", "Which zone?", [named[0], copy.copy(named[1]), inner, outside], zones=ZONES)
        with self.assertRaises(ValueError):  # a point outside its zone
            moved = copy.copy(named[0])
            moved.point = {"lat": 38.5, "lng": -5.0}
            RegionQuestion("zone", "Which zone?", [moved, *named[1:], outside], zones=ZONES)
        with self.assertRaises(ValueError):
            RegionQuestion("zone", "Which zone?", [Option("a", "A"), outside], zones=ZONES)
        with self.assertRaises(ValueError):
            RegionQuestion("zone", "Which zone?", list(q.options))  # no zone index
        self.assertLessEqual(len(q.options), MAX_OPTIONS)


ZONES_FILE = Z.DEFAULT_PATH


@unittest.skipUnless(ZONES_FILE.is_file(), "Data/index/zones.gpkg is not built (tools/build_zones.py)")
class BuiltZonesTest(unittest.TestCase):
    """On the built file, with famous public places only."""

    @classmethod
    def setUpClass(cls):
        cls.zones = Z.Zones.open(ZONES_FILE)

    def names(self, lat, lng):
        loc = self.zones.locate(lat, lng)
        self.assertIsNotNone(loc, (lat, lng))
        return {z.level: z.name for z in (*loc.chain, *loc.also)}

    def test_counts(self):
        levels = {}
        for z in self.zones:
            levels[(z.country, z.level)] = levels.get((z.country, z.level), 0) + 1
        self.assertEqual(levels[("PT", "district")], 18)
        self.assertEqual(levels[("PT", "autonomous_region")], 2)
        self.assertEqual(levels[("PT", "municipality")], 308)
        self.assertEqual(levels[("PT", "parish")], 3259)
        self.assertEqual(levels[("ES", "community")], 19)
        self.assertEqual(levels[("ES", "province")], 52)
        self.assertEqual(levels[("FR", "region")], 13)
        self.assertEqual(levels[("FR", "department")], 96)

    def test_portugal(self):
        lisbon = self.names(38.7076, -9.1365)  # Praça do Comércio
        self.assertEqual((lisbon["country"], lisbon["district"], lisbon["municipality"], lisbon["parish"]),
                         ("Portugal", "Lisboa", "Lisboa", "Santa Maria Maior"))
        self.assertEqual(lisbon["nuts2"], "Grande Lisboa")
        porto = self.names(41.1496, -8.6110)  # Avenida dos Aliados
        self.assertEqual((porto["district"], porto["municipality"]), ("Porto", "Porto"))
        funchal = self.names(32.6481, -16.9087)  # Sé do Funchal
        self.assertEqual((funchal["autonomous_region"], funchal["municipality"]),
                         ("Região Autónoma da Madeira", "Funchal"))
        ponta_delgada = self.names(37.7398, -25.6686)  # Portas da Cidade
        self.assertEqual((ponta_delgada["autonomous_region"], ponta_delgada["island"], ponta_delgada["municipality"]),
                         ("Região Autónoma dos Açores", "Ilha de São Miguel", "Ponta Delgada"))

    def test_spain_and_france(self):
        sol = self.names(40.4169, -3.7035)  # Puerta del Sol
        self.assertEqual((sol["country"], sol["community"], sol["province"]), ("Spain", "Comunidad de Madrid", "Madrid"))
        notre_dame = self.names(48.8530, 2.3499)
        self.assertEqual((notre_dame["country"], notre_dame["region"], notre_dame["department"]),
                         ("France", "Île-de-France", "Paris"))
        ajaccio = self.names(41.9192, 8.7386)
        self.assertEqual((ajaccio["region"], ajaccio["department"]), ("Corse", "Corse-du-Sud"))
        llivia = self.names(42.4644, 1.9786)  # the Spanish exclave inside France
        self.assertEqual(llivia["country"], "Spain")

    def test_sea_and_neighbours_are_nowhere(self):
        for lat, lng in ((40.0, -15.0), (45.0, -5.0), (42.5063, 1.5218)):  # Atlantic, Bay of Biscay, Andorra la Vella
            self.assertIsNone(self.zones.locate(lat, lng), (lat, lng))

    def test_a_point_just_off_the_quay_snaps_to_lisbon(self):
        loc = self.zones.locate(38.7040, -9.1365)  # about 400 m into the Tagus from Praça do Comércio
        self.assertIsNotNone(loc)
        self.assertEqual(loc.level("municipality").name, "Lisboa")
        self.assertLessEqual(loc.distance_m, 1000)

    def test_locate_and_questions_are_fast_enough(self):
        rng = np.random.default_rng(11)
        points = list(zip(rng.uniform(36.9, 43.8, 2000), rng.uniform(-9.5, 3.3, 2000)))
        t = time.perf_counter()
        for p in points:
            self.zones.locate(*p)
        self.assertLess((time.perf_counter() - t) / len(points), 0.005)
        candidates = [cand(38.7076, -9.1365, 0.4), cand(41.1496, -8.6110, 0.3), cand(40.4169, -3.7035, 0.2),
                      cand(48.8530, 2.3499, 0.1)]
        t = time.perf_counter()
        q = region_question(candidates, self.zones)
        self.assertLess(time.perf_counter() - t, 2.0)
        self.assertEqual([o.label for o in q.options], ["Portugal", "Spain", "France"])
        lisbon = [cand(38.7076, -9.1365, 0.5), cand(38.7139, -9.1334, 0.3), cand(38.6979, -9.2064, 0.2)]
        q = region_question(lisbon, self.zones)
        self.assertEqual(q.split_zone.name, "Lisboa")
        self.assertEqual(q.split_zone.level, "municipality")
        self.assertEqual({o.zone_level for o in q.options if not o.complement}, {"parish"})
        q = region_question(lisbon, self.zones, scope="PT", descend_share=None)
        self.assertEqual(q.options[0].label, "Distrito de Lisboa")
        self.assertIn("Distrito de Lisboa", q.options[0].to_dict()["links"]["google_maps_zone"].replace("+", " "))


if __name__ == "__main__":
    unittest.main()
