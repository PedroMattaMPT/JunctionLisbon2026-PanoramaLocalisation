"""Simulated operators for paired assisted validation: nominal, radius-aware, seeded human (PLAN.md 3.4; T40).

EVALUATION CODE ONLY: the pipeline must never import this module. Every operator here is built from
one panorama's reference, which only the evaluator may see (RULES.md, PLAN.md 4.6). Get the reference
through panoloc.evaluate.load_set, build one operator per panorama with make_operator(mode, reference),
and pass it as operator= to pipeline.run_panorama. The pipeline calls operator(question) with the
panoloc.questions.Question it just logged and gets back an option ID, or None for a skip: nothing
else crosses over. Each decision is also kept on the operator (operator.decisions) for the report,
with option IDs, distances and statuses, never the reference coordinates or option labels.

Option geometry is read from the Option's fields when the question arrives, because zone options are
changing (T32: district and region outlines instead of latitude/longitude boxes):
  complement  "None of these" / "Outside this area": holds whatever no other option holds
  callable    a contains_fn (questions.ZoneOption): the zone index's own test, unsimplified leaves
              plus its 1 km snap, used through option.contains. It wins over the option's outline,
              which is simplified for display only
  polygon     any field holding GeoJSON (Polygon, MultiPolygon, Feature, collections; positions
              [lng, lat]), an object with __geo_interface__ (shapely), or raw rings of points read as
              (lat, lng) or (lng, lat), whichever fits the allowed area. Even-odd rule over a
              polygon's rings, so holes count. Checked before bbox, which may then be just the
              polygon's bounding box
  box         bbox: a questions.Box or {"south", "west", "north", "east"} dict, edges included
  disc        point + radius_m (place options): "the camera stood within radius_m of the point"
  unknown     none of these (e.g. a zone ID only): question.option_for(point) decides, as the
              pipeline itself would; if it refuses a plain point, the operator skips
Containment is planar in degrees (as a box or a GeoJSON polygon is drawn on the team's maps). A point
outside every drawn region goes to the region option question.option_for gives, if any (panoloc.zones
snaps a pier or a beach to the zone within 1 km), before the complement. The nominal answer is also
compared with question.option_for (option_for_agrees in the decision).

Modes (EVALUATION.md, "Operator policy"):
  nominal  the option holding the reference point; else the complement; else a skip. Place tolerance:
           the option's own stated radius_m, no extra slack. Feature questions: a skip (the reference
           says nothing about features).
  radius   only when the whole reference disc (radius error_radius_m) supports one option: a place
           option with d + r <= radius_m (exact disc-in-disc), every place option with d - r > radius_m
           (then the complement), or for zones the centre and EDGE_SAMPLES points on the disc's edge all
           in one option (the complement counts as one). Anything else is a skip.
  human    seeded per panorama (sha256("<seed>:<filename>")): the nominal answer with probability
           right, a uniformly random other option with probability wrong, a skip otherwise (default
           0.70 / 0.10 / 0.20). When the nominal oracle would skip, it skips. Two draws per question,
           whatever happens, so one question's outcome never shifts the next one's draws.
           sticky_skip p (T79, the conservative reading of skip retries): a question identical (kind and
           option labels) to one this operator skipped is skipped again with probability p, otherwise
           answered with the right / wrong rates renormalised; a teammate who could not tell usually
           still cannot. None: every question is drawn independently.
           sticky_mistake p (T79, the conservative reading of wrong-answer recovery): when the right option
           lies outside a region this operator picked by mistake earlier, a would-be right answer repeats the
           mistake with probability p: an option inside that earlier region, else the complement, else a skip.

  from panoloc.evaluate import load_set
  from panoloc.oracle import make_operator
  ref = next(r for r in load_set("warmup").references if r.key == name)
  op = make_operator("radius", ref)
  result = pipeline.run_panorama(ref.path, models, operator=op)
  op.decisions          # [{question_id, kind, correct, answer, outcome, options: [...]}, ...]
"""
import hashlib
import math
import random
from dataclasses import dataclass, field, fields, is_dataclass

from panoloc.scoring import EARTH_RADIUS_M, haversine_m

MODES = ("nominal", "radius", "human")
EDGE_SAMPLES = 72
HUMAN_RATES = (0.70, 0.10, 0.20)  # right, wrong, skip
HUMAN_SEED = 2026
# Option fields that never hold zone geometry (the place disc is read from point + radius_m)
PLAIN_FIELDS = {"id", "label", "detail", "point", "point_role", "radius_m", "bbox", "bound_m", "complement",
                "covers", "support"}
# The allowed area's latitude and longitude ranges (questions.ALLOWED_AREA); they do not overlap, so a
# raw ring's coordinate order can be told from its values
LAT_RANGE = (27.5, 51.2)
LNG_RANGE = (-31.5, 9.7)


# -- geometry ------------------------------------------------------------------------------------

def destination(point, bearing_deg, distance_m):
    """The (lat, lng) reached from `point` along `bearing_deg` after `distance_m` on the sphere."""
    lat1, lng1 = map(math.radians, point)
    b, d = math.radians(bearing_deg), distance_m / EARTH_RADIUS_M
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lng2 = lng1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lng2) + 540.0) % 360.0 - 180.0


def disc_points(point, radius_m, n=EDGE_SAMPLES):
    """The centre, then n points on the edge of the disc (none when the radius is 0 or unknown)."""
    if not radius_m:
        return [tuple(point)]
    return [tuple(point)] + [destination(point, 360.0 * i / n, radius_m) for i in range(n)]


def _number_pair(p):
    return (isinstance(p, (list, tuple)) and len(p) >= 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p[:2]))


def _in(value, bounds):
    return bounds[0] <= value <= bounds[1]


def _raw_ring(ring):
    """A ring of raw points as [(lat, lng)], or None when it is not one or its order is unclear."""
    if not isinstance(ring, (list, tuple)) or len(ring) < 3 or not all(_number_pair(p) for p in ring):
        return None
    if all(_in(p[0], LAT_RANGE) and _in(p[1], LNG_RANGE) for p in ring):
        return [(float(p[0]), float(p[1])) for p in ring]
    if all(_in(p[1], LAT_RANGE) and _in(p[0], LNG_RANGE) for p in ring):
        return [(float(p[1]), float(p[0])) for p in ring]
    return None


def _geojson_polygons(value):
    """[[outer ring, *holes], ...] with rings as [(lat, lng)], from GeoJSON or __geo_interface__; else None."""
    if hasattr(value, "__geo_interface__"):
        value = value.__geo_interface__
    if not isinstance(value, dict):
        return None
    kind = value.get("type")
    if kind == "Feature":
        return _geojson_polygons(value.get("geometry"))
    if kind in ("FeatureCollection", "GeometryCollection"):
        members = value.get("features") or value.get("geometries") or []
        polygons = [p for m in members for p in (_geojson_polygons(m) or [])]
        return polygons or None
    coords = value.get("coordinates")
    if kind == "Polygon":
        coords = [coords]
    elif kind != "MultiPolygon":
        return None
    try:
        return [[[(float(p[1]), float(p[0])) for p in ring] for ring in polygon] for polygon in coords if polygon]
    except (TypeError, ValueError, IndexError):
        return None


def _raw_polygons(value):
    """Raw rings: one ring, a list of rings (outer + holes) or a list of such polygons; else None."""
    ring = _raw_ring(value)
    if ring:
        return [[ring]]
    if not isinstance(value, (list, tuple)) or not value:
        return None
    rings = [_raw_ring(r) for r in value]
    if all(rings):
        return [rings]
    polygons = []
    for polygon in value:
        rings = [_raw_ring(r) for r in polygon] if isinstance(polygon, (list, tuple)) and polygon else [None]
        if not all(rings):
            return None
        polygons.append(rings)
    return polygons


def _field_values(option):
    if is_dataclass(option):
        return [(f.name, getattr(option, f.name, None)) for f in fields(option)]
    return list(vars(option).items())


def option_geometry(option):
    """("complement",) | ("callable", contains) | ("polygon", polygons) | ("box", (s, w, n, e))
    | ("disc", (lat, lng), r) | ("unknown",)."""
    if getattr(option, "complement", False):
        return ("complement",)
    if callable(getattr(option, "contains_fn", None)):
        return ("callable", option.contains)
    for name, value in _field_values(option):
        if name in PLAIN_FIELDS or value is None or isinstance(value, (str, bytes, int, float, bool)):
            continue
        polygons = _geojson_polygons(value) or _raw_polygons(value)
        if polygons:
            return ("polygon", polygons)
    bbox = getattr(option, "bbox", None)
    if bbox is not None:
        get = bbox.get if isinstance(bbox, dict) else lambda k: getattr(bbox, k)
        return ("box", tuple(float(get(k)) for k in ("south", "west", "north", "east")))
    point, radius = getattr(option, "point", None), getattr(option, "radius_m", None)
    if point is not None and radius:
        return ("disc", (float(point["lat"]), float(point["lng"])), float(radius))
    return ("unknown",)


def _ring_contains(ring, point):
    """Even-odd ray casting in degrees; a point on an edge counts as inside."""
    lat, lng = point
    inside = False
    for (lat1, lng1), (lat2, lng2) in zip(ring, ring[1:] + ring[:1]):
        if _on_segment(point, (lat1, lng1), (lat2, lng2)):
            return True
        if (lat1 > lat) != (lat2 > lat):
            cross = lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1)
            if lng < cross:
                inside = not inside
    return inside


def _on_segment(p, a, b, eps=1e-12):
    (y, x), (y1, x1), (y2, x2) = p, a, b
    if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > eps * max(1.0, abs(x2 - x1) + abs(y2 - y1)):
        return False
    return min(x1, x2) - eps <= x <= max(x1, x2) + eps and min(y1, y2) - eps <= y <= max(y1, y2) + eps


def _polygons_contain(polygons, point):
    """Even-odd over each polygon's rings: a hole inside its outer ring, or a raw list whose rings are
    separate parts, both come out right."""
    return any(sum(_ring_contains(ring, point) for ring in rings) % 2 == 1 for rings in polygons)


def geometry_contains(geometry, point):
    """True or False for a known geometry; None for complement or unknown (the question decides)."""
    kind = geometry[0]
    if kind == "callable":
        return bool(geometry[1](tuple(point)))
    if kind == "polygon":
        return _polygons_contain(geometry[1], point)
    if kind == "box":
        s, w, n, e = geometry[1]
        return s <= point[0] <= n and w <= point[1] <= e
    if kind == "disc":
        return haversine_m(geometry[1], point) <= geometry[2]
    return None


# -- the answer rules ------------------------------------------------------------------------------

def _option_for(question, point):
    """question.option_for(point), or None if it refuses a plain point: then the operator skips
    rather than break the run."""
    try:
        return question.option_for(point)
    except Exception:
        return None


def _holder(question, geometries, point):
    """The option holding `point`: the first region option that contains it; else the region option the
    question's own option_for gives (named zones snap a pier or a beach to the zone within 1 km), else
    the complement. Unknown geometry: question.option_for. None when no option holds it."""
    regions = [(o, g) for o, g in zip(question.options, geometries) if g[0] != "complement"]
    if any(g[0] == "unknown" for _, g in regions):
        return _option_for(question, point)
    for o, g in regions:
        if geometry_contains(g, point):
            return o
    snapped = _option_for(question, point)
    if snapped is not None and not getattr(snapped, "complement", False):
        return snapped
    return next((o for o, g in zip(question.options, geometries) if g[0] == "complement"), None)


def _option_report(option, geometry, point, radius_m):
    entry = {"id": option.id, "geometry": geometry[0]}
    if geometry[0] == "disc":
        d = haversine_m(geometry[1], point)
        entry.update(radius_m=geometry[2], distance_m=round(d, 1), holds_reference=d <= geometry[2],
                     disc=("inside" if d + radius_m <= geometry[2] else "outside" if d - radius_m > geometry[2]
                           else "boundary"))
    elif geometry[0] in ("box", "polygon", "callable"):
        entry["holds_reference"] = bool(geometry_contains(geometry, point))
    return entry


def nominal_choice(question, point):
    """(option ID or None, why): the option holding the reference point."""
    if question.kind == "feature":
        return None, "feature question: the reference says nothing about features"
    geometries = [option_geometry(o) for o in question.options]
    option = _holder(question, geometries, point)
    if option is None:
        return None, "no option holds the reference and there is no complement"
    return option.id, "holds the reference" if not option.complement else "no listed option holds the reference"


def radius_choice(question, point, radius_m):
    """(option ID or None, why): an answer only when the whole reference disc supports one option."""
    if question.kind == "feature":
        return None, "feature question: the reference says nothing about features"
    r = float(radius_m or 0.0)
    geometries = [option_geometry(o) for o in question.options]
    regions = [(o, g) for o, g in zip(question.options, geometries) if g[0] != "complement"]
    complement = next((o for o, g in zip(question.options, geometries) if g[0] == "complement"), None)
    if regions and all(g[0] == "disc" for _, g in regions):  # place options: exact disc-in-disc
        status = {o.id: _option_report(o, g, point, r)["disc"] for o, g in regions}
        inside = [k for k, s in status.items() if s == "inside"]
        if len(inside) == 1:
            return inside[0], "the whole reference disc lies in this option"
        if all(s == "outside" for s in status.values()):
            if complement is not None:
                return complement.id, "the whole reference disc lies outside every listed place"
            return None, "outside every option and no complement"
        return None, "the reference disc crosses an option's edge"
    held = {getattr(_holder(question, geometries, p), "id", None) for p in disc_points(point, r)}
    if len(held) == 1 and None not in held:
        return held.pop(), "the reference disc lies in one option"
    return None, "the reference disc crosses a zone boundary" if len(held) > 1 else "no option holds the reference"


# -- operators ------------------------------------------------------------------------------------

def human_seed(key, seed=HUMAN_SEED):
    return int.from_bytes(hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()[:8], "big")


@dataclass
class Operator:
    """A simulated operator for one panorama. Call it with a Question; it returns an option ID or None.

    The reference stays on the evaluator side: repr() leaves it out, and decisions hold option IDs,
    distances and statuses only.
    """

    mode: str
    key: str
    point: tuple = field(repr=False)
    radius_m: float | None = field(default=None, repr=False)
    rates: tuple = HUMAN_RATES
    seed: int = HUMAN_SEED
    sticky_skip: float | None = None
    sticky_mistake: float | None = None
    decisions: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        right, wrong, skip = (float(x) for x in self.rates)
        if min(right, wrong, skip) < 0 or abs(right + wrong + skip - 1) > 1e-9:
            raise ValueError(f"human rates (right, wrong, skip) must be >= 0 and add up to 1, got {self.rates}")
        self.point = (float(self.point[0]), float(self.point[1]))
        if self.sticky_skip is not None and not 0 <= self.sticky_skip <= 1:
            raise ValueError(f"sticky_skip must be in [0, 1], got {self.sticky_skip}")
        self._rng = random.Random(human_seed(self.key, self.seed))
        self._skipped = set()  # signatures of the questions this operator skipped
        self._wrong = []  # geometries of the options this operator picked by mistake

    def __call__(self, question):
        correct, why = nominal_choice(question, self.point)
        answer, outcome = correct, "right" if correct is not None else "skip"
        if self.mode == "radius":
            answer, why = radius_choice(question, self.point, self.radius_m)
            outcome = "skip" if answer is None else "right" if answer == correct else "wrong"
        elif self.mode == "human":
            draw, pick = self._rng.random(), self._rng.random()
            right, wrong, _ = self.rates
            signature = (question.kind, tuple(str(o.label) for o in question.options))
            again = self.sticky_skip is not None and signature in self._skipped
            if again:  # the same question once more: skipped again with probability sticky_skip
                if correct is not None and draw >= self.sticky_skip:
                    draw = (draw - self.sticky_skip) / (1 - self.sticky_skip) * (right + wrong)
                else:
                    draw = 1.0  # a skip again
            repeat = (self.sticky_mistake is not None and correct is not None and draw < right
                      and pick < self.sticky_mistake and self._contradicts_mistake(question, correct))
            if repeat:  # the right option lies outside an earlier mistake: the operator sticks to that mistake
                answer = self._as_before(question)
                outcome = "skip" if answer is None else "right" if answer == correct else "wrong"
                why = "simulated repeated mistake"
                if answer is None:
                    self._skipped.add(signature)
            elif correct is None or draw >= right + wrong:
                answer, outcome = None, "skip"
                why = why if correct is None else "simulated skip again" if again else "simulated skip"
                self._skipped.add(signature)
            elif draw >= right:
                others = [o.id for o in question.options if o.id != correct]
                answer = others[min(int(pick * len(others)), len(others) - 1)]
                outcome, why = "wrong", "simulated mistake"
        if self.mode == "human" and outcome == "wrong":
            g = option_geometry(question.option(answer))
            if g[0] not in ("complement", "unknown"):
                self._wrong.append(g)
        self.decisions.append(self._record(question, correct, answer, outcome, why))
        return answer

    def _contradicts_mistake(self, question, option_id):
        point = getattr(question.option(option_id), "latlng", None)
        return point is not None and any(geometry_contains(g, point) is False for g in self._wrong)

    def _as_before(self, question):
        """The option an operator sticking to its earlier mistake picks: one inside a wrongly picked region,
        else the complement, else None (a skip)."""
        for o in question.options:
            point = getattr(o, "latlng", None)
            if not o.complement and point is not None and any(geometry_contains(g, point) for g in self._wrong):
                return o.id
        return next((o.id for o in question.options if o.complement), None)

    def _record(self, question, correct, answer, outcome, why):
        r = float(self.radius_m or 0.0)
        geometries = [option_geometry(o) for o in question.options]
        options = [_option_report(o, g, self.point, r) for o, g in zip(question.options, geometries)]
        for entry, o in zip(options, question.options):
            entry["complement"] = bool(getattr(o, "complement", False))
        record = {"question_id": question.question_id, "kind": question.kind, "n_options": len(question.options),
                  "correct": correct, "answer": answer, "outcome": outcome, "why": why, "options": options}
        if question.kind != "feature":
            holder = _option_for(question, self.point)
            record["option_for_agrees"] = None if holder is None else holder.id == correct
        if question.kind == "place":
            record["place_recall"] = place_recall(question, self.point)
        return record


def make_operator(mode, reference, *, rates=HUMAN_RATES, seed=HUMAN_SEED, sticky_skip=None, sticky_mistake=None):
    """An Operator for one panorama from its panoloc.evaluate.Reference."""
    return Operator(mode, reference.key, (reference.lat, reference.lng), reference.error_radius_m,
                    rates=tuple(rates), seed=seed, sticky_skip=sticky_skip, sticky_mistake=sticky_mistake)


def place_recall(question, point):
    """For a place question: whether any listed place (not "None of these") holds the reference point
    within its stated radius. None for other kinds."""
    if question.kind != "place":
        return None
    for o in question.options:
        g = option_geometry(o)
        if g[0] != "complement" and geometry_contains(g, point):
            return True
    return False


def summarise(decisions):
    """Counts over decisions: questions, answered, skipped, right, wrong, place questions and recall."""
    place = [d for d in decisions if d["kind"] == "place"]
    return {"questions": len(decisions),
            "answered": sum(d["answer"] is not None for d in decisions),
            "skipped": sum(d["answer"] is None for d in decisions),
            "right": sum(d["outcome"] == "right" for d in decisions),
            "wrong": sum(d["outcome"] == "wrong" for d in decisions),
            "place_questions": len(place),
            "place_recall": sum(bool(d.get("place_recall")) for d in place),
            "option_for_disagrees": sum(d.get("option_for_agrees") is False for d in decisions)}
