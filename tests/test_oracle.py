"""Tests for panoloc.oracle, the simulated operators of T40. Model-free: synthetic questions only."""
import re
import unittest
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from panoloc import oracle, questions
from panoloc.candidates import Candidate
from panoloc.oracle import destination, make_operator, nominal_choice, option_geometry, radius_choice
from panoloc.scoring import haversine_m

REPO = Path(__file__).resolve().parent.parent
A, B, C = (40.0, -8.0), (40.1, -8.0), (41.0, -7.0)


def candidates():
    return [Candidate(*A, "camera", "t:a", label="A", weight=0.5, accuracy_m=10),
            Candidate(*B, "landmark", "t:b", label="B", weight=0.3),
            Candidate(*C, "area", "t:c", label="C", weight=0.2, extent_m=900)]


def reference(point, radius_m=8.0, key="IMG_TEST_00_001.jpg"):
    return SimpleNamespace(key=key, lat=point[0], lng=point[1], error_radius_m=radius_m)


def step_m(point, metres, axis):
    """A point `metres` north (axis "lat") or east (axis "lng") of `point`."""
    return destination(point, 0.0 if axis == "lat" else 90.0, metres)


@dataclass
class ZoneOption:  # a stand-in for the polygon options T32 is adding
    id: str
    label: str
    outline: object = None
    complement: bool = False


@dataclass
class FakeQuestion:
    kind: str
    options: list
    question_id: str = "q1"
    holder: object = None  # option_for(point) -> option ID, the agent's own rule

    def option_for(self, point):
        wanted = self.holder(point)
        return next(o for o in self.options if o.id == wanted)


def square(south, west, north, east):
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


class GeoInterface:  # what a shapely geometry exposes
    def __init__(self, mapping):
        self.__geo_interface__ = mapping


class PlaceQuestionTest(unittest.TestCase):
    def setUp(self):
        self.q = questions.place_question(candidates())
        self.q.question_id = "q1"
        self.radius = self.q.option("a").radius_m

    def test_reference_inside_a_place(self):
        point = step_m(A, 100, "lng")
        self.assertEqual(nominal_choice(self.q, point)[0], "a")
        self.assertEqual(radius_choice(self.q, point, 8.0)[0], "a")
        self.assertEqual(self.q.option_for(point).id, "a")

    def test_none_of_these(self):
        point = (38.0, -9.0)
        none = next(o.id for o in self.q.options if o.complement)
        self.assertEqual(nominal_choice(self.q, point)[0], none)
        self.assertEqual(radius_choice(self.q, point, 8.0)[0], none)

    def test_radius_aware_skips_at_the_edge(self):
        point = step_m(A, self.radius - 3, "lng")  # inside, but the 8 m disc crosses the edge
        self.assertEqual(nominal_choice(self.q, point)[0], "a")
        self.assertIsNone(radius_choice(self.q, point, 8.0)[0])
        self.assertEqual(radius_choice(self.q, point, 1.0)[0], "a")
        outside = step_m(A, self.radius + 3, "lng")  # just outside: nominal says none, radius-aware skips
        self.assertTrue(self.q.option(nominal_choice(self.q, outside)[0]).complement)
        self.assertIsNone(radius_choice(self.q, outside, 8.0)[0])

    def test_tolerance_is_the_stated_radius(self):
        edge = destination(A, 90.0, self.radius - 0.05)
        self.assertEqual(nominal_choice(self.q, edge)[0], "a")
        self.assertTrue(oracle.place_recall(self.q, edge))
        self.assertFalse(oracle.place_recall(self.q, (38.0, -9.0)))

    def test_decision_record(self):
        op = make_operator("nominal", reference(step_m(B, 50, "lat")))
        self.assertEqual(op(self.q), "b")
        d = op.decisions[0]
        self.assertEqual((d["question_id"], d["kind"], d["correct"], d["answer"], d["outcome"]),
                         ("q1", "place", "b", "b", "right"))
        self.assertTrue(d["option_for_agrees"])
        self.assertTrue(d["place_recall"])
        self.assertEqual([o["geometry"] for o in d["options"]], ["disc", "disc", "disc", "complement"])
        self.assertAlmostEqual(d["options"][1]["distance_m"], 50, delta=0.2)
        self.assertNotIn("lat", repr(op).lower())  # the reference stays out of repr
        self.assertNotIn(str(round(op.point[0], 4)), repr(op))


class BoxZoneTest(unittest.TestCase):
    def test_whole_area_cells(self):
        q = questions.zone_question(candidates())
        q.question_id = "q2"
        self.assertTrue(all(oracle.option_geometry(o)[0] == "box" for o in q.options))
        for point in (A, C, (37.0, -5.0), (48.8, 2.3), (28.1, -15.4)):
            self.assertEqual(nominal_choice(q, point)[0], q.option_for(point).id)
            self.assertEqual(radius_choice(q, point, 8.0)[0], q.option_for(point).id)

    def test_radius_aware_skips_near_a_cut(self):
        q = questions.zone_question(candidates())
        scope = q.scope
        cell = next(o.bbox for o in q.options if o.bbox.south > scope.south)  # a cell whose south edge is a cut
        mid_lng = (cell.west + cell.east) / 2
        near = step_m((cell.south, mid_lng), 3, "lat")
        self.assertEqual(nominal_choice(q, near)[0], q.option_for(near).id)
        self.assertIsNone(radius_choice(q, near, 8.0)[0])
        self.assertEqual(radius_choice(q, near, 1.0)[0], q.option_for(near).id)

    def test_outside_this_area(self):
        scope = questions.Box(39.5, -8.5, 40.5, -7.5)
        q = questions.zone_question(candidates(), scope=scope)
        outside = next(o.id for o in q.options if o.complement)
        self.assertEqual(nominal_choice(q, (45.0, 0.0))[0], outside)
        self.assertEqual(radius_choice(q, (45.0, 0.0), 8.0)[0], outside)
        inside_edge = step_m((40.5, -8.0), -3, "lat")  # 3 m inside the scope's north edge
        self.assertNotEqual(nominal_choice(q, inside_edge)[0], outside)
        self.assertIsNone(radius_choice(q, inside_edge, 8.0)[0])


class PolygonZoneTest(unittest.TestCase):
    def setUp(self):
        west = {"type": "Polygon", "coordinates": [square(39.5, -8.5, 40.5, -8.0)]}
        ring_with_hole = {"type": "Polygon", "coordinates": [square(39.5, -8.0, 40.5, -7.5),
                                                             square(39.9, -7.9, 40.1, -7.7)]}
        hole = GeoInterface({"type": "MultiPolygon", "coordinates": [[square(39.9, -7.9, 40.1, -7.7)]]})
        self.options = [ZoneOption("a", "West", west), ZoneOption("b", "East", ring_with_hole),
                        ZoneOption("c", "Hole", hole), ZoneOption("d", "Outside this area", complement=True)]
        self.q = FakeQuestion("zone", self.options, holder=self.holder)

    def holder(self, point):
        lat, lng = point
        if not (39.5 <= lat <= 40.5 and -8.5 <= lng <= -7.5):
            return "d"
        if lng <= -8.0:
            return "a"
        return "c" if 39.9 <= lat <= 40.1 and -7.9 <= lng <= -7.7 else "b"

    def test_geometry_is_read_from_the_fields(self):
        self.assertEqual([option_geometry(o)[0] for o in self.options], ["polygon", "polygon", "polygon", "complement"])

    def test_nominal_and_holes(self):
        for point, want in (((40.3, -8.3), "a"), ((40.3, -7.6), "b"), ((40.0, -7.8), "c"), ((42.0, -3.0), "d")):
            self.assertEqual(nominal_choice(self.q, point)[0], want, point)
            self.assertEqual(radius_choice(self.q, point, 8.0)[0], want, point)
        op = make_operator("nominal", reference((40.0, -7.8)))
        self.assertEqual(op(self.q), "c")
        self.assertTrue(op.decisions[0]["option_for_agrees"])

    def test_radius_aware_skips_at_a_polygon_edge(self):
        near_hole = step_m((40.1, -7.8), 3, "lat")  # 3 m north of the hole, in the ring
        self.assertEqual(nominal_choice(self.q, near_hole)[0], "b")
        self.assertIsNone(radius_choice(self.q, near_hole, 8.0)[0])
        near_split = step_m((40.0, -8.0), -4, "lng")  # 4 m west of the line between a and b
        self.assertEqual(nominal_choice(self.q, near_split)[0], "a")
        self.assertIsNone(radius_choice(self.q, near_split, 8.0)[0])
        self.assertEqual(radius_choice(self.q, near_split, 2.0)[0], "a")

    def test_raw_rings_in_either_order(self):
        latlng = [(39.5, -8.5), (39.5, -8.0), (40.5, -8.0), (40.5, -8.5)]
        lnglat = [(lng, lat) for lat, lng in latlng]
        for ring in (latlng, lnglat, [latlng]):
            kind, polygons = option_geometry(ZoneOption("a", "West", ring))
            self.assertEqual(kind, "polygon")
            self.assertTrue(oracle.geometry_contains((kind, polygons), (40.0, -8.25)))
            self.assertFalse(oracle.geometry_contains((kind, polygons), (40.0, -7.75)))

    def test_raw_parts_are_not_holes(self):
        parts = [[(39.0, -9.0), (39.0, -8.9), (39.1, -8.9), (39.1, -9.0)],
                 [(41.0, -7.0), (41.0, -6.9), (41.1, -6.9), (41.1, -7.0)]]
        g = option_geometry(ZoneOption("a", "Islands", parts))
        self.assertTrue(oracle.geometry_contains(g, (39.05, -8.95)))
        self.assertTrue(oracle.geometry_contains(g, (41.05, -6.95)))
        self.assertFalse(oracle.geometry_contains(g, (40.0, -8.0)))

    def test_polygon_wins_over_its_bounding_box(self):
        @dataclass
        class Both:
            id: str
            label: str
            bbox: dict = None
            region: object = None
            complement: bool = False
        triangle = {"type": "Polygon", "coordinates": [[[-8.0, 40.0], [-7.0, 40.0], [-8.0, 41.0], [-8.0, 40.0]]]}
        option = Both("a", "Triangle", bbox={"south": 40.0, "west": -8.0, "north": 41.0, "east": -7.0}, region=triangle)
        self.assertEqual(option_geometry(option)[0], "polygon")
        in_box_not_triangle = (40.9, -7.1)
        self.assertFalse(oracle.geometry_contains(option_geometry(option), in_box_not_triangle))

    def test_a_point_outside_every_polygon_follows_the_snap(self):
        pier = (40.3, -8.5005)  # ~40 m west of the west zone's edge: the zones' snap puts it in zone a
        q = FakeQuestion("zone", self.options, holder=lambda p: "a" if p == pier else self.holder(p))
        self.assertEqual(nominal_choice(q, pier)[0], "a")
        far = (40.3, -9.5)  # no snap: outside this area
        self.assertEqual(nominal_choice(self.q, far)[0], "d")

    def test_the_zone_index_test_wins_over_the_display_outline(self):
        @dataclass
        class Named:  # questions.ZoneOption: a simplified outline for display, contains_fn decides
            id: str
            label: str
            outline: dict = None
            contains_fn: object = None
            complement: bool = False

            def contains(self, point):
                return bool(self.contains_fn(tuple(point)))
        outline = {"type": "Polygon", "coordinates": [square(39.5, -8.5, 40.5, -8.0)]}
        north = Named("a", "North", outline, contains_fn=lambda p: p[0] >= 40.0)
        south = Named("b", "South", outline, contains_fn=lambda p: p[0] < 40.0)
        q = FakeQuestion("zone", [north, south], holder=lambda p: "a" if p[0] >= 40.0 else "b")
        self.assertEqual(option_geometry(north)[0], "callable")
        self.assertEqual(nominal_choice(q, (39.7, -8.2))[0], "b")  # inside both outlines: the index decides
        self.assertEqual(radius_choice(q, (39.7, -8.2), 8.0)[0], "b")
        self.assertIsNone(radius_choice(q, step_m((40.0, -8.2), 3, "lat"), 8.0)[0])
        op = make_operator("radius", reference((40.3, -8.2)))
        self.assertEqual(op(q), "a")
        self.assertEqual(op.decisions[0]["options"][0], {"id": "a", "geometry": "callable", "holds_reference": True,
                                                         "complement": False})

    def test_unknown_geometry_uses_option_for(self):
        opts = [ZoneOption("a", "North"), ZoneOption("b", "South"),
                ZoneOption("c", "Outside this area", complement=True)]
        q = FakeQuestion("zone", opts, holder=lambda p: "a" if p[0] >= 40.0 else "b")
        self.assertEqual(option_geometry(opts[0]), ("unknown",))
        self.assertEqual(nominal_choice(q, (40.5, -8.0))[0], "a")
        self.assertEqual(radius_choice(q, (40.5, -8.0), 8.0)[0], "a")
        self.assertIsNone(radius_choice(q, step_m((40.0, -8.0), 3, "lat"), 8.0)[0])


class HumanSimulationTest(unittest.TestCase):
    def setUp(self):
        self.q = questions.place_question(candidates())
        self.ref = reference(step_m(A, 30, "lat"))

    def outcomes(self, op, n):
        return [op(self.q) for _ in range(n)]

    def test_seeded_and_repeatable(self):
        first = self.outcomes(make_operator("human", self.ref), 50)
        again = self.outcomes(make_operator("human", self.ref), 50)
        other = self.outcomes(make_operator("human", reference(self.ref_point(), key="IMG_OTHER_00_002.jpg")), 50)
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def ref_point(self):
        return self.ref.lat, self.ref.lng

    def test_rates(self):
        op = make_operator("human", self.ref)
        answers = Counter("skip" if a is None else "right" if a == "a" else "wrong" for a in self.outcomes(op, 4000))
        self.assertAlmostEqual(answers["right"] / 4000, 0.70, delta=0.03)
        self.assertAlmostEqual(answers["wrong"] / 4000, 0.10, delta=0.02)
        self.assertAlmostEqual(answers["skip"] / 4000, 0.20, delta=0.03)
        wrong = {d["answer"] for d in op.decisions if d["outcome"] == "wrong"}
        self.assertEqual(wrong, {"b", "c", "d"})  # never the correct option, every other one

    def test_extreme_rates(self):
        self.assertEqual(set(self.outcomes(make_operator("human", self.ref, rates=(1, 0, 0)), 20)), {"a"})
        self.assertEqual(set(self.outcomes(make_operator("human", self.ref, rates=(0, 0, 1)), 20)), {None})
        self.assertNotIn("a", self.outcomes(make_operator("human", self.ref, rates=(0, 1, 0)), 20))
        with self.assertRaises(ValueError):
            make_operator("human", self.ref, rates=(0.5, 0.5, 0.5))

    def test_sticky_skip(self):
        def run(sticky):
            outcomes = Counter()
            for i in range(800):
                op = make_operator("human", reference(self.ref_point(), key=f"IMG_{i}_00_001.jpg"), sticky_skip=sticky)
                while op(self.q) is not None:  # until the first skip
                    pass
                answer = op(self.q)  # the identical question again
                outcomes["skip" if answer is None else "right" if answer == "a" else "wrong"] += 1
            return outcomes
        sticky, independent = run(0.75), run(None)
        self.assertAlmostEqual(sticky["skip"] / 800, 0.75, delta=0.05)
        self.assertAlmostEqual(sticky["right"] / max(1, sticky["right"] + sticky["wrong"]), 0.875, delta=0.07)
        self.assertAlmostEqual(independent["skip"] / 800, 0.20, delta=0.05)
        op = make_operator("human", self.ref, sticky_skip=0.75)  # a fresh question is drawn as usual
        self.assertEqual([op(self.q) for _ in range(3)][:1], [make_operator("human", self.ref)(self.q)])

    def test_sticky_mistake(self):
        q = questions.place_question(candidates())  # a holds the reference
        wrong_region = oracle.option_geometry(q.option("b"))  # as if b had been picked by mistake earlier
        sticky = make_operator("human", self.ref, rates=(1, 0, 0), sticky_mistake=1.0)
        sticky._wrong.append(wrong_region)
        self.assertEqual(sticky(q), "b")  # sticks to the earlier mistake
        self.assertEqual(sticky.decisions[-1]["why"], "simulated repeated mistake")
        plain = make_operator("human", self.ref, rates=(1, 0, 0), sticky_mistake=0.0)
        plain._wrong.append(wrong_region)
        self.assertEqual(plain(q), "a")
        fresh = make_operator("human", self.ref, rates=(1, 0, 0), sticky_mistake=1.0)
        self.assertEqual(fresh(q), "a")  # no earlier mistake: nothing to stick to
        wrong_once = make_operator("human", self.ref, rates=(0, 1, 0), sticky_mistake=1.0)
        wrong_once(q)
        self.assertEqual(len(wrong_once._wrong), 1 if wrong_once.decisions[-1]["answer"] != "d" else 0)

    def test_two_draws_per_question(self):
        feature = questions.feature_question(candidates(), "Which side of the road do cars drive on?",
                                             ["Right", "Left"], lambda c: 0)
        op1, op2 = make_operator("human", self.ref), make_operator("human", self.ref)
        self.assertIsNone(op1(feature))  # the nominal oracle cannot answer a feature: a skip
        op2(self.q)
        self.assertEqual([op1(self.q) for _ in range(10)], [op2(self.q) for _ in range(10)])


class OperatorTest(unittest.TestCase):
    def test_feature_questions_are_skipped(self):
        feature = questions.feature_question(candidates(), "Is there a tram line?", ["Yes", "No"], lambda c: 0)
        for mode in oracle.MODES:
            op = make_operator(mode, reference(A))
            self.assertIsNone(op(feature))
            self.assertEqual(op.decisions[0]["outcome"], "skip")

    def test_option_for_failure_means_a_skip(self):
        def refuse(point):
            raise TypeError("wants a Candidate")
        opts = [ZoneOption("a", "North"), ZoneOption("b", "South")]
        q = FakeQuestion("zone", opts, holder=refuse)
        for mode in oracle.MODES:
            op = make_operator(mode, reference(A))
            self.assertIsNone(op(q))
            self.assertIsNone(op.decisions[0]["option_for_agrees"])

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            make_operator("psychic", reference(A))

    def test_summarise(self):
        q = questions.place_question(candidates())
        op = make_operator("radius", reference(step_m(A, q.option("a").radius_m - 2, "lng")))
        op(q)
        op.radius_m = 0.0
        op(q)
        s = oracle.summarise(op.decisions)
        self.assertEqual((s["questions"], s["answered"], s["skipped"], s["right"]), (2, 1, 1, 1))
        self.assertEqual((s["place_questions"], s["place_recall"], s["option_for_disagrees"]), (2, 2, 0))

    def test_disc_points(self):
        pts = oracle.disc_points(A, 10.0)
        self.assertEqual(len(pts), 1 + oracle.EDGE_SAMPLES)
        self.assertTrue(all(abs(haversine_m(A, p) - 10.0) < 1e-6 for p in pts[1:]))
        self.assertEqual(oracle.disc_points(A, None), [A])

    def test_the_pipeline_never_imports_the_oracle(self):
        pattern = re.compile(rb"^\s*(from\s+panoloc(\.oracle|\s+import\s+[^\n]*\boracle\b)|import\s+panoloc\.oracle"
                             rb"|from\s+\.\s+import\s+[^\n]*\boracle\b|from\s+\.oracle)", re.M)
        offenders = [p.name for p in sorted((REPO / "panoloc").glob("*.py"))
                     if p.name != "oracle.py" and pattern.search(p.read_bytes())]
        self.assertEqual(offenders, [], "panoloc.oracle is evaluation code: the pipeline must never import it")


if __name__ == "__main__":
    unittest.main()
