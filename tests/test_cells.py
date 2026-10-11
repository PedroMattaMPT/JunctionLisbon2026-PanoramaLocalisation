"""Tests for panoloc.cells and the cell questions of panoloc.questions (T42).

Run from the repo root with the venv (shapely, pyproj): .venv/bin/python -m unittest discover -s tests

The synthetic tests use invented geometry and invented candidates only. The tests on the built zone file
(Data/index/zones.gpkg, tools/build_zones.py) skip when it is absent; they use a famous public square,
never a warm-up panorama's location.
"""
import copy
import json
import math
import tempfile
import time
import unittest

import numpy as np
import shapely

from panoloc import cells
from panoloc import questions as Q
from panoloc import zones as Z
from panoloc.candidates import Candidate
from panoloc.runlog import Run
from panoloc.scoring import MAX_ENTRIES, haversine_m

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file
LAT, LNG = 40.2, -8.41  # an invented spot; every candidate below is made up
TOL = Q.CELL_TILING_TOLERANCE  # cells are snapped to a 1 micrometre grid: their union is the scope to ~1e-8 of its area


def shop(lat=LAT, lng=LNG, weight=1.0, label="Pastelaria Inventada", source="osm:n1"):
    return Candidate(lat, lng, "landmark", source, label=label, weight=weight, extent_m=15.0,
                     details={"osm_type": "shop=bakery", "extent_source": "assumed", "fusion": {"clues": ["ocr:i1"]}})


def camera(lat, lng, weight=1.0):
    return Candidate(lat, lng, "camera", f"test:{lat},{lng}", label=f"photo {lat},{lng}", weight=weight)


def offset(point, north_m, east_m):
    lat, lng = point
    return (lat + north_m / cells.M_PER_DEG, lng + east_m / (cells.M_PER_DEG * math.cos(math.radians(lat))))


def polygon_scope(coords, scope_id="test:polygon", **kwargs):
    """A scope from (lat, lng) offsets in metres around (LAT, LNG)."""
    ring = [offset((LAT, LNG), n, e) for n, e in coords]
    return cells.Scope(shapely.Polygon([(lng, lat) for lat, lng in ring]), scope_id, label="test area", **kwargs)


def samples(geom, step=0.5):
    """Dense points of a WGS84 polygon: its boundary about every `step` metres and a grid inside it."""
    degrees = step / cells.M_PER_DEG
    boundary = shapely.get_coordinates(shapely.segmentize(shapely.boundary(geom), degrees))
    west, south, east, north = shapely.bounds(geom)
    xs, ys = np.meshgrid(np.linspace(west, east, 30), np.linspace(south, north, 30))
    inside = shapely.contains_xy(geom, xs.ravel(), ys.ravel())
    return np.vstack([boundary, np.column_stack([xs.ravel()[inside], ys.ravel()[inside]])])


class Scripted:
    def __init__(self, *lines):
        self.lines = list(lines)

    def __call__(self, prompt=""):
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


SQUARE = [(-200, -300), (-200, 300), (200, 300), (200, -300)]
L_SHAPE = [(0, 0), (0, 400), (100, 400), (100, 100), (300, 100), (300, 0)]
NOTCH = [(0, 0), (0, 300), (300, 300), (300, 0), (150, 0), (150, 140), (140, 140), (140, 0)]  # a narrow slot


def scopes():
    """A landmark disc, a rectangle, a concave L, a slotted square, a square with a hole and two islands."""
    hole_outer = [offset((LAT, LNG), n, e) for n, e in [(0, 0), (0, 300), (300, 300), (300, 0)]]
    hole_inner = [offset((LAT, LNG), n, e) for n, e in [(100, 100), (100, 200), (200, 200), (200, 100)]]
    holed = cells.Scope(shapely.Polygon([(g, t) for t, g in hole_outer], [[(g, t) for t, g in hole_inner]]),
                        "test:holed", label="a square with a courtyard")
    islands = cells.Scope(shapely.MultiPolygon([
        shapely.Polygon([(g, t) for t, g in (offset((LAT, LNG), n, e) for n, e in [(0, 0), (0, 80), (80, 80), (80, 0)])]),
        shapely.Polygon([(g, t) for t, g in (offset((LAT, LNG), n, e)
                                             for n, e in [(0, 200), (0, 260), (60, 260), (60, 200)])])]),
        "test:islands", label="two islands")
    return [cells.Scope.around(shop()), polygon_scope(SQUARE, "test:square"), polygon_scope(L_SHAPE, "test:L"),
            polygon_scope(NOTCH, "test:notch"), holed, islands]


class CellGeometryTest(unittest.TestCase):
    def assert_tiles(self, q):
        cells_ = [o for o in q.options if not o.complement]
        scope = q.scope
        union = shapely.union_all([o.geometry for o in cells_])
        area = shapely.area(scope.geom)
        self.assertLessEqual(shapely.area(shapely.symmetric_difference(union, scope.geom)), TOL * area)
        for i, a in enumerate(cells_):
            for b in cells_[i + 1:]:
                self.assertLessEqual(shapely.area(shapely.intersection(a.geometry, b.geometry)), TOL * area)
        self.assertEqual(len(cells_), 4 if scope.whole else 3)
        self.assertEqual(sum(o.complement for o in q.options), 0 if scope.whole else 1)

    def test_cells_tile_every_kind_of_scope(self):
        for scope in scopes():
            with self.subTest(scope=scope.scope_id):
                q = cells.cell_question([], scope)
                self.assertIsInstance(q, Q.CellQuestion)
                self.assertEqual(q.kind, "zone")
                self.assert_tiles(q)
                self.assertEqual(len({o.label for o in q.options}), len(q.options))
                self.assertTrue(q.options[-1].complement)
                self.assertEqual(q.options[-1].label, "Outside this area")

    def test_a_landmark_disc_is_cut_into_sectors_around_it(self):
        q = cells.cell_question([], cells.Scope.around(shop()))
        self.assertEqual(q.details["family"], "sectors")
        self.assertEqual([o.label for o in q.options[:3]], ["North of Pastelaria Inventada",
                                                            "South-east of Pastelaria Inventada",
                                                            "South-west of Pastelaria Inventada"])
        self.assertIn("Bearings 300° to 60° as seen from Pastelaria Inventada", q.options[0].detail)
        radius = q.scope.details["search_radius_m"]
        for o in q.options[:3]:  # three equal discs cover a disc with radius 0.866 R at best
            self.assertLess(o.bound_m, 0.9 * radius + 2)
            self.assertGreater(o.bound_m, 0.85 * radius)

    def test_representative_points_lie_strictly_inside_their_cells(self):
        for scope in scopes():
            q = cells.cell_question([camera(*offset((LAT, LNG), 20, 30), 0.5)], scope)
            for o in q.options[:-1]:
                with self.subTest(scope=scope.scope_id, option=o.id):
                    lat, lng = o.latlng
                    self.assertTrue(shapely.contains_xy(o.geometry, lng, lat))
                    edge = shapely.boundary(o.geometry_m)
                    x, y = scope.frame.xy(lat, lng)
                    self.assertGreaterEqual(shapely.distance(edge, shapely.Point(float(x), float(y))), 0.2)
                    self.assertEqual(o.point_role, "area")
                    self.assertIn("not a camera position", o.detail)

    def test_bound_covers_the_true_maximum_distance(self):
        for scope in scopes():
            q = cells.cell_question([], scope)
            for o in q.options[:-1]:
                with self.subTest(scope=scope.scope_id, option=o.id):
                    points = samples(o.geometry)
                    true_max = max(haversine_m(o.latlng, (y, x)) for x, y in points)
                    self.assertGreaterEqual(o.bound_m, true_max)
                    self.assertLessEqual(o.bound_m, true_max * 1.01 + 2.0)  # and not wildly loose
                    self.assertEqual(o.bound_m, cells.bound_m(o.latlng, o.geometry))

    def test_every_candidate_maps_to_exactly_one_option(self):
        rng = np.random.default_rng(42)
        for scope in scopes():
            q = cells.cell_question([], scope)
            west, south, east, north = shapely.bounds(scope.geom)
            pad_lat, pad_lng = (north - south) * 0.3, (east - west) * 0.3
            points = list(zip(rng.uniform(south - pad_lat, north + pad_lat, 400),
                              rng.uniform(west - pad_lng, east + pad_lng, 400)))
            for p in points:
                holding = [o for o in q.options if not o.complement and shapely.contains_xy(o.geometry, p[1], p[0])]
                self.assertLessEqual(len(holding), 1, p)
                chosen = q.option_for(p)
                inside = scope.contains(p)
                if holding:
                    self.assertIs(chosen, holding[0])
                self.assertEqual(chosen.complement, not inside, (scope.scope_id, p))
                self.assertIs(q.option_for(Candidate(p[0], p[1], "camera", "test:p")), chosen)
                self.assertIs(q.option_for({"lat": p[0], "lng": p[1]}), chosen)

    def test_the_outside_option_covers_the_rest_of_the_allowed_area(self):
        q = cells.cell_question([], cells.Scope.around(shop()))
        outside = q.options[-1]
        for p in [(38.7, -9.1), (40.4, -3.7), (48.85, 2.35), offset((LAT, LNG), 70, 0), offset((LAT, LNG), 0, -100)]:
            self.assertIs(q.option_for(p), outside)
        self.assertIn("outside the 3 areas above", outside.detail)

    def test_whole_area_gets_four_cells_and_no_outside(self):
        whole = cells.Scope(shapely.box(-31.5, 27.5, 9.7, 51.2), "test:allowed", label="the allowed area", whole=True)
        q = cells.cell_question([], whole)
        self.assert_tiles(q)
        self.assertFalse(any(o.complement for o in q.options))
        self.assertIs(q.option_for((60.0, 20.0)), min(q.options, key=lambda o: shapely.distance(
            o.geometry, shapely.Point(20.0, 60.0))))  # beyond every cell: the nearest one

    def test_cuts_balance_the_weight_of_spread_hypotheses(self):
        scope = polygon_scope(SQUARE, "test:square")
        crowd = [camera(*offset((LAT, LNG), n, e), 1.0) for n in (-150, -120, -90) for e in (-250, -220, -190)]
        crowd += [camera(*offset((LAT, LNG), 150, 250), 1.0)]
        q = cells.cell_question(crowd, scope)
        self.assertEqual(q.details["balance"], "weight")
        self.assertGreaterEqual(len({q.option_for(c).id for c in crowd[:9]}), 2)  # the crowd in one corner is split
        self.assertLess(max(o.support for o in q.options[:3]), 0.75)
        for c in crowd:  # no hypothesis sits on a cut
            for o in q.options[:3]:
                x, y = scope.frame.xy(c.lat, c.lng)
                d = shapely.distance(shapely.boundary(o.geometry_m), shapely.Point(float(x), float(y)))
                if shapely.contains_xy(o.geometry_m, float(x), float(y)):
                    self.assertGreater(d, 0.5)


class ChainAndRouteTest(unittest.TestCase):
    def test_chaining_shrinks_the_bound_and_recovery_restores_the_parent(self):
        root = cells.Scope.around(shop())
        q = cells.cell_question([], root)
        child = cells.chain(q, "a")
        self.assertIs(child.parent, root)
        self.assertEqual(child.kind, "cell")
        self.assertLess(child.rep[2], root.rep[2])
        q2 = cells.cell_question([], child)
        grandchild = cells.chain(q2, "b")
        self.assertLess(grandchild.rep[2], child.rep[2])
        self.assertEqual(grandchild.sources[0], "osm:n1")
        rest = cells.chain(cells.cell_question([], grandchild), "d")  # Outside: the camera is not in it
        self.assertEqual(rest.kind, "remainder")
        self.assertIs(rest.parent, root)  # the remainder's own outside option reaches past its parent
        union = shapely.union(rest.geom, grandchild.geom)
        self.assertLessEqual(shapely.area(shapely.symmetric_difference(union, child.geom)), TOL * shapely.area(child.geom))
        restored = cells.chain(cells.cell_question([], rest), "d")  # not there either: the root minus the child
        self.assertLessEqual(shapely.area(shapely.symmetric_difference(shapely.union(restored.geom, rest.geom),
                                                                      root.geom)), TOL * shapely.area(root.geom))
        self.assertIsNone(restored.parent)
        self.assertIsNone(cells.chain(cells.cell_question([], root), "d"))  # outside the root: the route ends
        self.assertIsNone(cells.chain(cells.cell_question([], restored), "d"))

    def test_the_route_reaches_the_target_and_outputs_a_geographic_cell(self):
        spot = offset((LAT, LNG), 31, -17)
        route = cells.CellRoute.start([shop(weight=0.7), shop(41.0, -8.0, 0.3, "Elsewhere", "osm:n2")],
                                      cells.Scope.around(shop()), category="urban")
        self.assertIsNone(route.output())  # the search disc is an assumption, not a picked cell
        while not route.done():
            q = route.question()
            self.assertTrue(math.isclose(sum(a["probability"] for a in route.gain(q)["answers"]), 1.0))
            route = route.answer(q, q.option_for(spot).id)
        self.assertLessEqual(route.answered, 6)
        out = route.output()
        self.assertEqual((out.method, out.source_role, out.uncertainty_source),
                         ("geographic_cell", "area", "geometric_bound"))
        self.assertLessEqual(out.uncertainty_m, cells.target_bound_m("urban"))
        self.assertTrue(route.scope.contains((out.lat, out.lng)))
        self.assertEqual(out.uncertainty_m, cells.bound_m((out.lat, out.lng), route.scope.geom))
        self.assertLessEqual(haversine_m(spot, (out.lat, out.lng)), out.uncertainty_m)
        self.assertEqual(out.coordinates(), [(out.lat, out.lng)] * MAX_ENTRIES)
        self.assertEqual(out.sources[0], "osm:n1")
        self.assertIn("category urban", out.note)
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp, category="urban", category_source="inferred")
            cells.log_cell_output(run, out, route)
            kinds = [e["type"] for e in run.events]
            self.assertIn("output.produced", kinds)
            evidence = next(e for e in run.events if e["type"] == "evidence.added")["payload"]
            self.assertEqual(evidence["kind"], "cell_output")
            self.assertEqual(evidence["bound_m"], out.uncertainty_m)
            self.assertEqual(evidence["category_assumption"], "urban")
            json.dumps(run.events, default=str)

    def test_the_route_update_matches_apply_answer(self):
        hyps = [shop(weight=0.6), camera(*offset((LAT, LNG), 30, 5), 0.2), shop(41.0, -8.0, 0.2, "Far", "osm:n2")]
        route = cells.CellRoute.start(hyps, cells.Scope.around(shop()), urban_probability=0.5)
        self.assertEqual([h.source for h in route.spread], ["osm:n1"])
        self.assertEqual(sorted(h.source for h in route.others), ["osm:n2", f"test:{hyps[1].lat},{hyps[1].lng}"])
        q = route.question()
        before = route.hypotheses()
        self.assertAlmostEqual(sum(h.weight for h in before), 1.0)
        after = route.answer(q, "a")
        a, n = Q.DEFAULT_ANSWER_ACCURACY, len(q.options)
        factor = (1 - a) / ((n - 1) * a)
        points = sum(h.weight * (1.0 if q.option_for(h).id == "a" else factor) for h in route.others)
        spread = sum(0.6 * shapely.area(o.geometry_m) / route.root.area_m2 * (1.0 if o.id == "a" else factor)
                     for o in q.options[:3])  # the landmark's weight, spread uniformly over its disc
        self.assertAlmostEqual(sum(h.weight for h in after.hypotheses()), points + spread, places=6)
        self.assertAlmostEqual(sum(p.weight for p in after.pieces), spread, places=7)
        self.assertEqual([h.weight for h in after.others], [h.weight for h in Q.apply_answer(route.others, q, "a")])

    def test_a_wrong_answer_is_recovered(self):
        spot = offset((LAT, LNG), 34, 1)
        route = cells.CellRoute.start([shop()], cells.Scope.around(shop()), category="urban")
        q = route.question()
        right = q.option_for(spot).id
        wrong = next(o.id for o in q.options[:3] if o.id != right)
        route = route.answer(q, wrong)
        q = route.question()
        self.assertTrue(q.option_for(spot).complement)
        route = route.answer(q, q.option_for(spot).id)  # Outside: back to the disc minus the wrong sector
        self.assertEqual(route.scope.kind, "remainder")
        self.assertTrue(route.scope.contains(spot))
        while not route.done():
            q = route.question()
            route = route.answer(q, q.option_for(spot).id)
        out = route.output()
        self.assertLessEqual(haversine_m(spot, (out.lat, out.lng)), out.uncertainty_m)

    def test_a_skip_changes_nothing(self):
        route = cells.CellRoute.start([shop(weight=0.8), shop(41.0, -8.0, 0.2, "Far", "osm:n2")],
                                      cells.Scope.around(shop()), urban_probability=0.5)
        q = route.question()
        before, options_before = copy.deepcopy(route.hypotheses()), q.option_dicts()
        state = (route.scope, len(route.pieces), [p.weight for p in route.pieces], route.history)
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(PANORAMA, tmp)
            self.assertIsNone(Q.ask_operator(run, q, Scripted("s"), lambda *_: None))
            self.assertEqual(run.penalties.multiplier, 1.0)
            self.assertEqual(run.events[-1]["type"], "question.skipped")
            asked = next(e for e in run.events if e["type"] == "question.asked")["payload"]
            self.assertEqual(asked["scope"]["scope_id"], route.scope.scope_id)
            self.assertEqual(asked["options"][0]["zone"]["type"], "Polygon")
        self.assertEqual(route.hypotheses(), before)
        self.assertEqual(q.option_dicts(), options_before)
        self.assertEqual((route.scope, len(route.pieces), [p.weight for p in route.pieces], route.history), state)
        self.assertIs(route.question(), q)  # nothing moved: the same question

    def test_a_picked_cell_with_no_hypothesis_keeps_weight_to_split(self):
        far = shop(41.0, -8.0, 1.0, "Far", "osm:n2")
        zone = polygon_scope(SQUARE, "test:square", picked=True)
        route = cells.CellRoute.start([far], zone, urban_probability=0.5)  # nothing inside: the default weight
        self.assertEqual(len(route.pieces), 1)
        q = route.question()
        empty = q.options[1]
        self.assertEqual(empty.covers, [])
        route = route.answer(q, empty.id)
        inside = [h for h in route.hypotheses() if route.scope.contains(h.point)]
        self.assertGreaterEqual(len(inside), cells.MIN_PIECE_SAMPLES)
        self.assertTrue(all(h.role == "area" and h.details["cell_sample"] for h in inside))
        nxt = route.question()  # the picked cell splits like any other
        self.assertTrue(all(o.support > 0 for o in nxt.options[:3]))
        area = Q.cell_area_candidate(empty, weight=0.4)
        self.assertEqual((area.role, area.source, area.extent_m, area.weight), ("area", f"cell:{empty.cell_id}",
                                                                              empty.bound_m, 0.4))
        self.assertIs(q.option_for(area), empty)
        with self.assertRaises(ValueError):
            Q.cell_area_candidate(q.options[-1])
        spread = cells.spread_candidates(route.scope, weight=0.5, n=9)
        self.assertAlmostEqual(sum(c.weight for c in spread), 0.5)
        self.assertTrue(all(route.scope.contains(c.point) for c in spread))
        out = route.exit_hypotheses()
        cell = next(h for h in out if h.source == f"cell:{route.scope.scope_id}")
        self.assertEqual(cell.extent_m, route.bound()[2])
        self.assertAlmostEqual(sum(h.weight for h in out), sum(h.weight for h in route.hypotheses()), places=6)

    def test_validation_rejects_bad_cells(self):
        q = cells.cell_question([], cells.Scope.around(shop()))
        a, b, c, outside = q.options
        with self.assertRaises(ValueError):  # no outside option for part of the allowed area
            Q.CellQuestion("zone", q.text, [a, b, c], scope=q.scope)
        with self.assertRaises(ValueError):  # a cell missing: the scope is not covered
            Q.CellQuestion("zone", q.text, [a, b, outside], scope=q.scope)
        big = copy.copy(a)
        big.id, big.label, big.geometry = "c", "Overlapping", shapely.union(a.geometry, c.geometry)
        big.bound_m = cells.bound_m(big.latlng, big.geometry)
        with self.assertRaises(ValueError):  # overlapping cells
            Q.CellQuestion("zone", q.text, [a, b, big, outside], scope=q.scope)
        moved = copy.copy(a)
        moved.point = b.point
        with self.assertRaises(ValueError):  # a point outside its cell
            Q.CellQuestion("zone", q.text, [moved, b, c, outside], scope=q.scope)
        short = copy.copy(a)
        short.bound_m = a.bound_m / 2
        with self.assertRaises(ValueError):  # a bound that does not cover the cell
            Q.CellQuestion("zone", q.text, [short, b, c, outside], scope=q.scope)
        Q.CellQuestion("zone", q.text, [a, b, c, outside], scope=q.scope)

    def test_options_serialise_with_geojson_and_map_links(self):
        q = cells.cell_question([shop()], cells.Scope.around(shop()))
        dicts = q.option_dicts()
        json.dumps(dicts)
        json.dumps(q.log_details())
        d = dicts[0]
        for key in ("cell_id", "cell", "zone", "bound_m", "point", "point_role", "links", "area_m2", "extent"):
            self.assertIn(key, d)
        self.assertEqual(d["zone"]["type"], "Polygon")
        self.assertIn(d["cell"]["type"], ("Polygon", "MultiPolygon"))
        lng, lat = d["zone"]["coordinates"][0][0]
        self.assertAlmostEqual(lat, LAT, delta=0.01)  # GeoJSON keeps [lng, lat]
        links = d["links"]
        self.assertTrue(links["cell_map"].startswith("https://geojson.io/#data=data:application/json,"))
        self.assertIn("street_view", links)
        self.assertTrue(q.details["cells_map"].startswith("https://geojson.io/#data="))
        self.assertIn("Cell on a map", Q.format_question(q))
        self.assertTrue(dicts[-1]["complement"])

    def test_expected_gain_and_apply_answer_work_unchanged(self):
        monument = Candidate(LAT, LNG, "landmark", "osm:n9", label="Monumento", extent_m=40.0,
                             details={"fusion": {"clues": ["vlm:landmark:1"]}})
        route = cells.CellRoute.start([monument], cells.Scope.around(monument), category="urban")
        self.assertEqual(route.root.details["evidence"], "vlm_landmark")
        q = route.question()
        gain = route.gain(q)
        self.assertTrue(gain["worth_asking"])  # a 340 m urban search disc is worth splitting
        self.assertAlmostEqual(sum(a["probability"] for a in gain["answers"]), 1.0)
        hyps = route.hypotheses()
        updated = Q.apply_answer(hyps, q, "b")
        self.assertEqual(len(updated), len(hyps))


class SearchExtentAndGlueTest(unittest.TestCase):
    def test_search_extents_per_evidence_type(self):
        cases = [
            (shop(), "ocr_sign", 65.0),
            (Candidate(LAT, LNG, "landmark", "osm:w5", label="Igreja", extent_m=30.0,
                       details={"osm_type": "historic=church", "extent_source": "source",
                                "fusion": {"clues": ["ocr:i3"]}}), "ocr_landmark", 150.0),
            (Candidate(LAT, LNG, "landmark", "wikidata:Q1", label="Torre", extent_m=20.0,
                       details={"fusion": {"clues": ["vlm:landmark:1"]}}), "vlm_landmark", 320.0),
            (Candidate(LAT, LNG, "area", "osm:w7", label="Rua Inventada", extent_m=180.0,
                       details={"osm_type": "highway=residential", "fusion": {"clues": ["ocr:i4"]}}), "street", 205.0),
            (Candidate(LAT, LNG, "area", "osm-postcode:PT:3000-001", label="3000-001", extent_m=60.0), "area", 85.0),
            (Candidate(LAT, LNG, "camera", "osv5m:1", accuracy_m=8.0, details={"verified_match": True}), "camera", 48.0),
        ]
        for c, kind, radius in cases:
            with self.subTest(kind=kind):
                self.assertEqual(cells.evidence_kind(c), kind)
                r, info = cells.search_radius(c)
                self.assertAlmostEqual(r, radius)
                self.assertIn("not where the camera stood", info["assumption"])
                scope = cells.Scope.around(c)
                self.assertAlmostEqual(scope.rep[2], radius, delta=0.01 * radius + 1.5)
                self.assertEqual(scope.details["evidence"], kind)
                self.assertEqual(scope.anchor, (c.lat, c.lng))
        self.assertEqual(cells.search_radius(shop(), evidence="vlm_landmark")[0], 315.0)
        tiny = Candidate(LAT, LNG, "landmark", "osm:n8", details={"osm_type": "shop=kiosk"})
        self.assertEqual(cells.search_radius(tiny)[0], 50.0)
        self.assertEqual(cells.Scope.around(shop(), max_radius_m=30.0).details["clamped_to_m"], 30.0)
        with self.assertRaises(ValueError):
            cells.search_radius(shop(), evidence="guess")

    def test_route_scope_finds_a_dominant_unique_landmark(self):
        unique = shop(weight=0.6)
        unique.details.update(tier=0, ambiguity=1)
        rest = [shop(41.0, -8.0, 0.25, "Far", "osm:n2"), Candidate(38.72, -9.14, "area", "fallback:PT", weight=0.15,
                                                                  extent_m=150_000.0, details={"residual": True})]
        scope, why = cells.route_scope([unique, *rest])
        self.assertEqual(scope.sources, ("osm:n1",))
        self.assertIn("60%", why)
        ambiguous = shop(weight=0.6)
        ambiguous.details.update(tier=0, ambiguity=14, chain=True)
        scope, why = cells.route_scope([ambiguous, *rest])
        self.assertIsNone(scope)
        scope, _ = cells.route_scope([shop(weight=0.85), shop(41.0, -8.0, 0.15, "Far", "osm:n2")])
        self.assertIsNotNone(scope)  # strong enough without a unique name
        self.assertIsNone(cells.route_scope([camera(LAT, LNG)])[0])

    def test_route_scope_after_a_place_answer(self):
        hyps = [shop(weight=0.4), shop(41.0, -8.0, 0.35, "Far", "osm:n2"), shop(38.0, -7.9, 0.25, "South", "osm:n3")]
        q = Q.place_question(hyps)
        scope, why = cells.route_scope(hyps, place_question=q, place_option_id="a")
        self.assertEqual(scope.sources, ("osm:n1",))
        self.assertIn("Pastelaria Inventada", why)
        self.assertLessEqual(scope.details["search_radius_m"], q.options[0].radius_m)
        confirmed = scope.parent  # the sign's disc first, inside the disc the team confirmed
        self.assertTrue(confirmed.picked)
        self.assertAlmostEqual(confirmed.details["radius_m"], q.options[0].radius_m)
        spot = offset((LAT, LNG), 0, 100)  # beyond the sign's 65 m, inside the confirmed 250 m
        route = cells.CellRoute.start(hyps, scope, category="urban")
        question = route.question()
        self.assertTrue(question.option_for(spot).complement)
        route = route.answer(question, question.option_for(spot).id)
        self.assertEqual(route.scope.kind, "remainder")  # recovered into the confirmed disc, not out of the route
        self.assertTrue(route.scope.contains(spot))
        residual = [*hyps, Candidate(36.5, -6.0, "area", "fallback:ES", weight=0.5, extent_m=150_000.0,
                                     details={"residual": True})]
        rq = Q.place_question(residual)
        pick = rq.option_for((36.5, -6.0)).id
        self.assertIsNone(cells.route_scope(residual, place_question=rq, place_option_id=pick)[0])
        none_of_these = q.options[-1].id  # the places missed, and no hypothesis dominates: no cell route
        self.assertIsNone(cells.route_scope(hyps, place_question=q, place_option_id=none_of_these)[0])

    def test_route_scope_for_a_leaf_zone(self):
        zones = synthetic_zones()
        scope, why = cells.route_scope([], zones=zones, zone_scope="PT:parish:0101")
        self.assertEqual((scope.kind, scope.zone_id, scope.deviation_m), ("zone", "PT:parish:0101", 12.0))
        self.assertTrue(scope.picked)
        self.assertIsNone(cells.route_scope([], zones=zones, zone_scope="PT:municipality:01")[0])  # 2 parishes: named
        leaves = [{"zone_id": f"PT:parish:02{k}", "name": f"Freguesia {k}", "level": "parish", "country": "PT",
                   "parent_id": "PT:municipality:02", "geometry": shapely.box(-8.4 + 0.01 * k, 40.0, -8.39 + 0.01 * k, 40.01)}
                  for k in range(5)]
        coarse = [{"zone_id": "PT", "name": "Portugal", "level": "country", "country": "PT", "parent_id": None},
                  {"zone_id": "PT:municipality:02", "name": "Vila Grande", "level": "municipality", "country": "PT",
                   "parent_id": "PT"}]
        five = Z.Zones.from_leaves(leaves, coarse)
        scope, why = cells.route_scope([], zones=five, zone_scope="PT:municipality:02")  # 5 parishes, no hypothesis
        self.assertEqual((scope.kind, scope.zone_id), ("zone", "PT:municipality:02"))
        self.assertIn("5 subzones", why)
        held = [camera(40.005, -8.385)]  # a real hypothesis inside: named subzones split it instead
        self.assertIsNone(cells.route_scope(held, zones=five, zone_scope="PT:municipality:02")[0])


def synthetic_zones():
    """One invented municipality of two parishes (one with a 12 m boundary deviation)."""
    west = shapely.Polygon([(g, t) for t, g in (offset((LAT, LNG), n, e) for n, e in
                                                [(0, 0), (0, 1200), (900, 1200), (900, 0)])])
    east = shapely.Polygon([(g, t) for t, g in (offset((LAT, LNG), n, e) for n, e in
                                                [(0, 1200), (0, 2000), (900, 2000), (900, 1200)])])
    leaves = [{"zone_id": "PT:parish:0101", "name": "Freguesia Oeste", "level": "parish", "country": "PT",
               "parent_id": "PT:municipality:01", "geometry": west, "deviation_m": 12.0},
              {"zone_id": "PT:parish:0102", "name": "Freguesia Leste", "level": "parish", "country": "PT",
               "parent_id": "PT:municipality:01", "geometry": east, "deviation_m": 3.0}]
    coarse = [{"zone_id": "PT", "name": "Portugal", "level": "country", "country": "PT", "parent_id": None},
              {"zone_id": "PT:municipality:01", "name": "Vila Inventada", "level": "municipality", "country": "PT",
               "parent_id": "PT"}]
    return Z.Zones.from_leaves(leaves, coarse)


class ZoneScopeTest(unittest.TestCase):
    def test_the_zone_deviation_is_added_only_on_its_boundary(self):
        zones = synthetic_zones()
        scope = cells.Scope.from_zone(zones, "PT:parish:0101")
        self.assertEqual(scope.label, "Freguesia Oeste (freguesia, Vila Inventada)")
        q = cells.cell_question([], scope)
        for o in q.options[:3]:  # every first-level cell reaches the parish boundary
            self.assertEqual(o.deviation_m, 12.0)
            self.assertGreaterEqual(o.bound_m - cells.bound_m(o.latlng, o.geometry), 11.9)
            self.assertIn("12 m of it for the mapped boundary", o.detail)
        interior = shapely.Polygon([(g, t) for t, g in (offset((LAT, LNG), n, e) for n, e in
                                                        [(300, 400), (300, 800), (600, 800), (600, 400)])])
        inner = cells.Scope(interior, "test:inner", frame=scope.frame, parent=scope, deviation_m=12.0,
                            root_boundary_m=scope.root_boundary_m)
        for o in cells.cell_question([], inner).options[:3]:
            self.assertEqual(o.deviation_m, 0.0)
        out = cells.cell_output(scope)
        self.assertGreaterEqual(out.uncertainty_m, cells.bound_m((out.lat, out.lng), scope.geom) + 12.0 - 0.1)

    def test_outside_a_root_zone_ends_the_route(self):
        zones = synthetic_zones()
        route = cells.CellRoute.start([], cells.Scope.from_zone(zones, "PT:parish:0101"), urban_probability=0.5)
        self.assertIsNotNone(route.output())  # the team picked the parish: its rep point and bound
        q = route.question()
        route = route.answer(q, "d")
        self.assertIsNone(route.scope)
        self.assertTrue(route.done())
        self.assertIsNone(route.output())
        out = route.exit_hypotheses()
        self.assertEqual([h.source for h in out], ["cell:zone:PT:parish:0101"])


def coast_zones(coast_deviation_m=0.0):
    """Two invented countries: a Portuguese leaf with the sea west of -8.42 and a Spanish leaf east of
    the border at -8.40 (both 40.19-40.21 N). coast_deviation_m: the Portuguese leaf's stored outline is
    that far from the true one (a simplified coastline)."""
    leaves = [{"zone_id": "PT:parish:01", "name": "Freguesia da Costa", "level": "parish", "country": "PT",
               "parent_id": "PT", "geometry": shapely.box(-8.42, 40.19, -8.40, 40.21),
               "deviation_m": coast_deviation_m},
              {"zone_id": "ES:province:01", "name": "Provincia Vecina", "level": "province", "country": "ES",
               "parent_id": "ES", "geometry": shapely.box(-8.40, 40.19, -8.38, 40.21)}]
    coarse = [{"zone_id": "PT", "name": "Portugal", "level": "country", "country": "PT", "parent_id": None},
              {"zone_id": "ES", "name": "Spain", "level": "country", "country": "ES", "parent_id": None}]
    return Z.Zones.from_leaves(leaves, coarse)


class ConstraintTest(unittest.TestCase):
    """The route keeps to earlier answers and to land (the coordinator's containment recheck, T42)."""

    @classmethod
    def setUpClass(cls):
        cls.zones = coast_zones()

    def country_answer(self, country="PT"):
        q = Q.region_question([camera(40.2, -8.41), camera(40.2, -8.39)], self.zones)
        return q, next(o.id for o in q.options if o.zone_id == country)

    def walk(self, route, spot, steps=4):
        """Every option point and output the route offers on the way, the ideal operator answering."""
        points = []
        for _ in range(steps):
            if route.done():
                break
            q = route.question()
            points += [o.latlng for o in q.options if not o.complement]
            route = route.answer(q, q.option_for(spot).id)
            out = route.output()
            if out is not None:
                points.append((out.lat, out.lng))
        return route, points

    def test_a_coastal_scope_offers_no_point_at_sea(self):
        coastal = shop(40.2, -8.4198, source="osm:n7", label="Bar da Praia")  # 17 m from the shore
        pq = Q.place_question([coastal, shop(40.205, -8.385, 0.3, "Far", "osm:n8")], min_separation_m=150)
        picked = pq.option_for(coastal.point).id
        plain = cells.CellRoute.start([coastal], cells.Scope.around(coastal), category="urban")
        land = shapely.buffer(plain.root.frame.to_m(shapely.box(-8.42, 40.19, -8.40, 40.21)), 26.0)  # metres
        self.assertGreater(shapely.area(shapely.difference(plain.root.geom_m, land)), 100.0)  # the disc reaches the sea
        route = cells.CellRoute.start([coastal], cells.Scope.around(coastal), category="urban",
                                      constraints=[(pq, picked)], zones=self.zones)
        self.assertLessEqual(shapely.area(shapely.difference(route.root.geom_m, land)), 1e-6)
        route, points = self.walk(route, (40.2001, -8.4196))
        self.assertGreaterEqual(len(points), 6)
        for point in points:
            self.assertTrue(self.zones.on_land(point, cells.LAND_TOLERANCE_M), point)

    def test_a_disc_ruled_out_by_none_of_these_stays_out(self):
        ruled = [shop(40.2050, -8.4150, 0.4, "Café A", "osm:a"), shop(40.1950, -8.4050, 0.3, "Café B", "osm:b"),
                 shop(40.2000, -8.3850, 0.3, "Café C", "osm:c")]
        pq = Q.place_question(ruled, min_separation_m=300)
        none = next(o for o in pq.options if o.complement)
        discs = [(o.latlng, o.radius_m) for o in pq.options if not o.complement]
        zone = cells.Scope.from_zone(self.zones, "PT:parish:01")
        scope, _ = cells.route_scope([], zones=self.zones, zone_scope="PT:parish:01", constraints=[(pq, none.id)])
        self.assertLess(scope.area_m2, zone.area_m2)  # the discs are cut out
        route = cells.CellRoute.start([], scope, category="urban", constraints=[(pq, none.id)])
        route, points = self.walk(route, (40.1990, -8.4170), steps=5)
        self.assertGreaterEqual(len(points), 6)
        for point in points:
            for centre, radius in discs:
                self.assertGreater(haversine_m(point, centre), radius, (point, centre))

    def test_an_answered_border_is_never_crossed(self):
        rq, portugal = self.country_answer("PT")
        border = shop(40.2000, -8.4003, 0.9, "Posto da Fronteira", "osm:n9")  # 26 m from Spain
        border.details.update(tier=0, ambiguity=1)
        scope, why = cells.route_scope([border], constraints=[(rq, portugal)])
        spain = shapely.box(-8.40, 40.19, -8.38, 40.21)
        self.assertLessEqual(shapely.area(shapely.intersection(scope.geom, spain)), 1e-12)
        route = cells.CellRoute.start([border], scope, category="urban", constraints=[(rq, portugal)])
        route, points = self.walk(route, (40.2002, -8.4006))
        self.assertGreaterEqual(len(points), 6)
        for point in points:
            self.assertEqual(self.zones.locate(*point, snap_m=cells.LAND_TOLERANCE_M).country, "PT", point)
        rq_es, spain_id = self.country_answer("ES")
        far = shop(40.2000, -8.4150, 0.9, "Loja Portuguesa", "osm:n10")
        far.details.update(tier=0, ambiguity=1)
        self.assertIsNone(cells.route_scope([far], constraints=[(rq_es, spain_id)])[0])  # wholly ruled out

    def test_sub_cells_cover_every_allowed_point_of_the_picked_cell(self):
        zones = coast_zones(coast_deviation_m=60.0)
        coastal = shop(40.2, -8.4198, source="osm:n7", label="Bar da Praia")
        pq = Q.place_question([coastal, shop(40.205, -8.385, 0.3, "Far", "osm:n8")], min_separation_m=150)
        beach = offset((40.2, -8.42), 0, -40)  # 40 m off the stored coast: true land within its 60 m error
        self.assertTrue(zones.on_land(beach, cells.LAND_TOLERANCE_M))
        self.assertFalse(zones.on_land(offset((40.2, -8.42), 0, -120), cells.LAND_TOLERANCE_M))  # open sea
        route = cells.CellRoute.start([coastal], cells.Scope.around(coastal), category="urban",
                                      constraints=[(pq, pq.option_for(coastal.point).id)], zones=zones)
        self.assertTrue(route.scope.contains(beach) and route.scope.allows(beach))
        for _ in range(4):
            q = route.question()
            west, south, east, north = shapely.bounds(route.scope.geom)
            grid = [(lat, lng) for lat in np.linspace(south, north, 25) for lng in np.linspace(west, east, 25)]
            allowed = [g for g in grid if route.scope.contains(g) and route.scope.allows(g)] + [beach]
            self.assertGreater(len(allowed), 20)
            for g in allowed:  # every allowed point of the picked cell is in one of its sub-cells
                self.assertFalse(q.option_for(g).complement, g)
            union = shapely.union_all([o.geometry for o in q.options if not o.complement])
            self.assertLessEqual(shapely.area(shapely.symmetric_difference(union, route.scope.geom)),
                                 TOL * shapely.area(route.scope.geom))
            route = route.answer(q, q.option_for(beach).id)
        self.assertTrue(route.scope.contains(beach))

    def test_no_constraints_is_the_behaviour_before(self):
        scope = cells.Scope.around(shop())
        for empty in (None, []):
            self.assertIs(cells.constrain(scope, empty, self.zones), scope)
            self.assertIs(cells.route_scope([shop(weight=0.9)], constraints=empty)[0].geom.equals(scope.geom), True)
            a, b = cells.cell_question([], scope), cells.cell_question([], scope, constraints=empty)
            self.assertEqual([o.latlng for o in a.options[:3]], [o.latlng for o in b.options[:3]])
            r1 = cells.CellRoute.start([shop()], scope, category="urban")
            r2 = cells.CellRoute.start([shop()], scope, category="urban", constraints=empty)
            self.assertIs(r2.root, r1.root)


class SpeedTest(unittest.TestCase):
    def median_ms(self, build, reps=3):
        """The fastest of `reps` builds: the machine is often loaded by other work."""
        times = []
        for _ in range(reps):
            t = time.perf_counter()
            build()
            times.append((time.perf_counter() - t) * 1000)
        return min(times)

    def test_a_cell_question_builds_in_under_50_ms(self):
        disc = cells.Scope.around(shop())
        self.assertLess(self.median_ms(lambda: cells.cell_question([shop()], disc)), 50)
        rng = np.random.default_rng(5)  # a ragged 600-vertex parish-like polygon of about 4 km2
        angles = np.sort(rng.uniform(0, 2 * math.pi, 600))
        radii = 1100 + 250 * np.sin(5 * angles) + rng.uniform(-40, 40, 600)
        ring = [offset((LAT, LNG), r * math.cos(a), r * math.sin(a)) for a, r in zip(angles, radii)]
        parish = cells.Scope(shapely.Polygon([(g, t) for t, g in ring]), "test:ragged", label="a ragged parish")
        self.assertLess(self.median_ms(lambda: cells.cell_question([], parish)), 50)


ZONES_FILE = Z.DEFAULT_PATH


@unittest.skipUnless(ZONES_FILE.is_file(), "Data/index/zones.gpkg is not built (tools/build_zones.py)")
class BuiltZonesTest(unittest.TestCase):
    """On the built file, with a famous public square only."""

    @classmethod
    def setUpClass(cls):
        cls.zones = Z.Zones.open(ZONES_FILE)

    def test_cells_inside_santa_maria_maior(self):
        praca = (38.7076, -9.1365)  # Praça do Comércio
        leaf = self.zones.locate(*praca).leaf
        self.assertEqual(leaf.name, "Santa Maria Maior")
        scope, _ = cells.route_scope([], zones=self.zones, zone_scope=leaf.id)
        self.assertEqual(scope.deviation_m, leaf.deviation_m)
        times = []
        for _ in range(3):
            t = time.perf_counter()
            q = cells.cell_question([], scope)
            times.append((time.perf_counter() - t) * 1000)
        self.assertLess(min(times), 50)
        union = shapely.union_all([o.geometry for o in q.options[:3]])
        self.assertLessEqual(shapely.area(shapely.symmetric_difference(union, self.zones.exact_geometry(leaf))),
                             TOL * shapely.area(scope.geom))
        for o in q.options[:3]:
            self.assertEqual(o.deviation_m, leaf.deviation_m)
            self.assertGreaterEqual(o.bound_m, max(haversine_m(o.latlng, (y, x)) for x, y in samples(o.geometry, 5.0)))
        route = cells.CellRoute.start([], scope, category="urban")
        while not route.done() and route.answered < 12:
            q = route.question()
            route = route.answer(q, q.option_for(praca).id)
        out = route.output()
        self.assertLessEqual(out.uncertainty_m, 25.0)
        self.assertLessEqual(haversine_m(praca, (out.lat, out.lng)), out.uncertainty_m)
        self.assertLessEqual(route.answered, 10)


if __name__ == "__main__":
    unittest.main()
