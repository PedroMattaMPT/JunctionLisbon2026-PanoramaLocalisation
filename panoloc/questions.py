"""Agent-generated multiple-choice questions: options, expected gain, answers and the operator loop.

PLAN.md 3.3-3.4, RULES.md. Every answered question multiplies all later outputs by 0.95 (rule 7); a
skipped one costs nothing and must change nothing (partner clarification 2). Code builds each question
and its options from the current candidates; the team only picks one option, or skips. At most 4
options, IDs a-d, three kinds:

  place    up to 3 distinct candidates (panoloc.candidates.distinct) plus an explicit "None of these".
           A place option means "the camera stood within radius_m of this point": min_separation_m / 2,
           widened to the candidate's extent_m, never more than half the way to another listed point,
           so options never overlap. Each says what its point marks (the Candidate role): a landmark or
           area point is not where the camera stood.
  zone     areas that together cover the scope without overlapping, in one of two forms:
           named zones (region_question, a RegionQuestion of ZoneOptions): administrative zones from
             panoloc.zones (countries, districts, municipalities, parishes; communities and provinces;
             regions and departments), the three countries for the whole allowed area, else up to 3
             zones plus an explicit "Elsewhere" / "Outside <zone>";
           cells (zone_question), the fallback without the zone index: latitude/longitude boxes, 4 for
             the whole allowed area (ALLOWED_AREA), or 3 plus an explicit "Outside this area".
           Each area has a representative point (labelled as not a camera position) and bound_m, a
           conservative maximum distance from that point to anywhere in the area.
  feature  an observable feature; the caller says which option each candidate predicts.

Every hypothesis (candidate) belongs to exactly one option, Question.option_for(candidate): the first
option whose disc, cell or zone holds its point, else the "None of these" / "Outside this area" /
"Elsewhere" option. On a whole-area zone question, a point outside ALLOWED_AREA or every country (it
cannot be the answer) goes to the nearest cell or country. Options record the hypotheses they held when
built (covers, support).

Named zones (region_question): the scope is the allowed area, or a zone an earlier answer picked
(chained questions: country, then district, then municipality). The question offers the scope's
subzones, going a level down while one subzone holds at least REGION_DESCEND_SHARE (75%) of the weight
inside and has subzones of its own, so it asks at the coarsest level that splits the weight; a zone
with a single subzone is looked through. If the subzones fit (all three countries, or at most 3 plus
"Outside <zone>") they are all offered; otherwise the 3 heaviest plus "Elsewhere", which holds the rest
of the scope and everything outside it, so an earlier wrong answer stays recoverable. Zones given in
`exclude` (the named zones of an earlier "Elsewhere" answer) are not offered again and their hypotheses
do not count, and with no weight left the largest subzones are offered: the zone fallback of PLAN.md 3.4
when every hypothesis missed. A zone holds a point when panoloc.zones places it there, a snap of up to
1 km outside the coast or a border included (piers, beaches, estuaries); bound_m and the representative
point come from panoloc.zones. Each option also carries map links, including a name search that shows
the zone's outline on Google Maps, its bounding box on OpenStreetMap and a GeoJSON outline to draw.
region_chain(question, option_id, scope, exclude) gives the next question's scope and exclusions: a
named zone becomes the scope; "Elsewhere" excludes the named zones; "Outside <zone>" excludes that zone
and, if the search was inside it, widens the scope back to the allowed area. area_candidate(option)
turns a picked zone or cell into an `area` Candidate (its point, extent_m = bound_m) for T42; while
hypotheses are points, panoloc.zones.Zones.spread(zone) is the way to give a picked zone that holds no
hypothesis weight its next question can split.

Zone cells (zone_question): the scope is cut recursively across its
longer side (in metres) at weighted quantiles of the hypotheses inside it (the median for 2 + 2 cells,
the tercile for 1 + 2), so cells carry similar weight where the hypotheses allow. A cut lies midway
between two neighbouring hypotheses, so none sits on a boundary; where they cannot be split (none, or
all on one line) it falls in the middle of the side. Cells are boxes in WGS84 degrees rather than
projected metres, so containment is exact in the coordinates the team's maps and the scorer use.
bound_m: on a sphere, the farthest point of a latitude/longitude box (at most 90 degrees of longitude
wide, away from the poles) from a point inside it is a corner, so the largest corner Haversine distance
(R = 6371 km, as panoloc.scoring and the scorer) is exact. bound_m adds 0.6% (ellipsoidal geodesics or
another Earth radius differ by less) and 1 m, rounded up.

Expected gain (PLAN.md 3.4): before is the best expected theta now, over the candidates' and options'
points; after averages the best expected theta once the answer is known over the possible answers. The
team picks the right option with probability answer_accuracy and otherwise one of the others at random.
Ask only if 0.95 x after > before: a gain above 1/0.95 - 1 = 5.26%. Approximations: fusion weights stand
in for probabilities, hypotheses are points, time is not counted, and an option holding no hypothesis
matters only through wrong answers, so keep a fallback candidate (PLAN.md 3.2) in the list.

apply_answer is the matching soft update: the chosen option's hypotheses keep their weight and the
others are scaled down, never deleted, so a wrong answer stays recoverable. There is no apply_skip: a
skip leaves every belief as it was. ask_operator waits without a timeout and accepts only an option ID
or s; nothing else (an empty line, end of input) counts as a skip.

Question text comes from TEMPLATES. phrase_fn(question) -> str is the hook for the VLM to reword it
later: it changes the text only, never the options, and wording that gives a skip a meaning is refused
(the template stays). Nothing here calls a model.

  q = place_question(candidates)                       # or zone_question(candidates, scope=cell)
  q = region_question(candidates, zones, scope=None)   # zones = panoloc.zones.Zones.open(); chained:
                                                       # scope, exclude = region_chain(q, option.id, scope, exclude)
  gain = expected_gain(candidates, q, urban_probability=0.5)
  if gain["worth_asking"]:
      q.details["expected_gain"] = gain                # logged with the question
      option = ask_operator(run, q)                    # the team types a-d, or s to skip
      if option is not None:
          candidates = apply_answer(candidates, q, option.id)

Try it by hand: python3 -m panoloc.questions --demo   (invented candidates; log under runs/demo/)
"""
import argparse
import functools
import math
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from panoloc.candidates import ROLES, Candidate, distinct, normalise
from panoloc.runlog import MAX_OPTIONS, QUESTION_FACTOR, SILENCE_RE, Run, coordinate
from panoloc.scoring import EARTH_RADIUS_M, SCALE_M, best_point, haversine_m, theta

KINDS = ("place", "zone", "feature")
OPTION_IDS = "abcd"
BREAK_EVEN = 1 / QUESTION_FACTOR - 1  # an answered question must raise expected theta by more than this
DEFAULT_MIN_SEPARATION_M = 500.0  # places the team can tell apart on a map; pass ~150 m for spots in one town
DEFAULT_ANSWER_ACCURACY = 0.9
BOUND_RELATIVE_MARGIN = 0.006
BOUND_ABSOLUTE_MARGIN_M = 1.0
RESERVED_DETAILS = ("question_id", "text", "options", "kind", "stage")  # Run.ask's own fields

TEMPLATES = {
    "place": "Where was this panorama taken? A place counts only if the camera stood within the distance "
             "given for it.",
    "zone_whole": "Which zone contains the camera position? The four zones do not overlap and together cover "
                  "all of Portugal, Spain and France.",
    "zone_part": "Which zone contains the camera position? The first three zones split the current search area "
                 "without overlapping; the last option is anywhere outside it.",
    "region_whole": "Which of these contains the camera position? They do not overlap and together cover all of "
                    "Portugal, Spain and France.",
    "region_part": "Which zone contains the camera position? The named zones do not overlap; the last option is "
                   "anywhere else in Portugal, Spain or France.",
}
REGION_DESCEND_SHARE = 0.75  # region_question offers a zone's subzones once one zone holds this share
ALLOWED_AREA_TEXT = "Portugal, Spain and France"
ROLE_TEXT = {
    "camera": "The marked point is a camera position: the GPS of a reference photo.",
    "landmark": "The marked point is the landmark itself, not where the camera stood.",
    "area": "The marked point is the centre of an area, not a camera position.",
}
LINK_NAMES = {"google_maps": "Google Maps", "street_view": "Street View", "osm": "OpenStreetMap",
              "osm_cell": "Zone on OpenStreetMap", "google_maps_zone": "Zone's name on Google Maps (shows its outline)",
              "osm_zone": "Zone's extent on OpenStreetMap"}


@dataclass(frozen=True)
class Box:
    """A latitude/longitude box in WGS84 degrees, edges included. It may not cross the antimeridian or
    reach a pole, and is at most 90 degrees of longitude wide (the corner rule of cell_bound_m needs it)."""

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self):
        for name in ("south", "west", "north", "east"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"box {name} is not a number: {value}")
            object.__setattr__(self, name, value)
        if not -90 < self.south < self.north < 90:
            raise ValueError(f"a box needs -90 < south < north < 90, got {self.south}, {self.north}")
        if not -180 <= self.west < self.east <= min(180.0, self.west + 90):
            raise ValueError(f"a box needs west < east, at most 90 degrees apart, got {self.west}, {self.east}")

    @classmethod
    def of(cls, value):
        """A Box from a Box or a {"south", "west", "north", "east"} dict."""
        return value if isinstance(value, Box) else cls(value["south"], value["west"], value["north"], value["east"])

    def contains(self, point):
        lat, lng = point
        return self.south <= lat <= self.north and self.west <= lng <= self.east

    def contains_box(self, other):
        return (self.south <= other.south and other.north <= self.north
                and self.west <= other.west and other.east <= self.east)

    def overlaps(self, other):
        """True when the interiors intersect; boxes that only share an edge do not overlap."""
        return (self.south < other.north and other.south < self.north
                and self.west < other.east and other.west < self.east)

    def clamp(self, point):
        lat, lng = point
        return min(max(lat, self.south), self.north), min(max(lng, self.west), self.east)

    @property
    def centre(self):
        return (self.south + self.north) / 2, (self.west + self.east) / 2

    def corners(self):
        return [(self.south, self.west), (self.south, self.east), (self.north, self.west), (self.north, self.east)]

    @property
    def height_m(self):
        return EARTH_RADIUS_M * math.radians(self.north - self.south)

    @property
    def width_m(self):
        """Along the box's widest parallel, the one nearest the equator."""
        widest = min(max(0.0, self.south), self.north)
        return EARTH_RADIUS_M * math.radians(self.east - self.west) * math.cos(math.radians(widest))

    def split(self, axis, cut):
        if axis == "lat":
            return Box(self.south, self.west, cut, self.east), Box(cut, self.west, self.north, self.east)
        return Box(self.south, self.west, self.north, cut), Box(self.south, cut, self.north, self.east)

    def to_dict(self):
        return {"south": self.south, "west": self.west, "north": self.north, "east": self.east}


# All the allowed countries in one box: mainland Portugal, Spain and France with the Azores, Madeira, the
# Canaries, the Balearics, Corsica, Ceuta and Melilla. Overseas France is assumed out of scope. The box
# also holds sea and slices of neighbouring countries: a superset keeps the zone options exhaustive.
ALLOWED_AREA = Box(south=27.5, west=-31.5, north=51.2, east=9.7)


def cell_bound_m(box, point):
    """Conservative maximum distance in metres from `point` (inside `box`) to anywhere in the box.

    The exact spherical maximum is at a corner: along a meridian, the distance from the point has no
    interior maximum, and along a parallel it grows with the longitude difference (up to 90 degrees
    here). The margins cover ellipsoidal geodesics or another Earth radius (0.6%) and rounding (1 m).
    """
    if not box.contains(point):
        raise ValueError(f"point {point} is outside its cell {box.to_dict()}")
    farthest = max(haversine_m(point, corner) for corner in box.corners())
    return math.ceil((farthest * (1 + BOUND_RELATIVE_MARGIN) + BOUND_ABSOLUTE_MARGIN_M) * 10) / 10


def _url_number(value):
    """A coordinate for a URL: at most 7 decimals (about 1 cm), no exponent, no trailing zeros."""
    text = f"{value:.7f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def map_links(point):
    """Google Maps and Street View links for a (lat, lng) point. Street View coverage there is unchecked:
    the nearest panorama may be far from the point, or there may be none."""
    lat, lng = (_url_number(v) for v in point)
    return {"google_maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
            "street_view": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}"}


def _osm_point_link(point):
    lat, lng = (_url_number(v) for v in point)
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}"


def _osm_box_link(box):
    s, w, n, e = (_url_number(v) for v in (box.south, box.west, box.north, box.east))
    return f"https://www.openstreetmap.org/?minlon={w}&minlat={s}&maxlon={e}&maxlat={n}&box=yes"


@dataclass
class Option:
    """One answer the team can pick. `point` is {"lat", "lng"}, or None for a complement option."""

    id: str
    label: str
    detail: str = ""
    point: dict | None = None
    point_role: str | None = None  # what the point marks: camera, landmark or area
    radius_m: float | None = None  # place: the option means "the camera stood within radius_m of point"
    bbox: Box | None = None  # zone: the cell
    bound_m: float | None = None  # zone: no part of the cell is farther than this from point
    complement: bool = False  # "None of these" / "Outside this area": whatever no other option holds
    covers: list = field(default_factory=list)  # sources of the hypotheses it held when built, heaviest first
    support: float = 0.0  # their share of the total weight when built

    @property
    def latlng(self):
        return None if self.point is None else (self.point["lat"], self.point["lng"])

    def contains(self, point):
        if self.bbox is not None:
            return self.bbox.contains(point)
        if self.radius_m is not None and self.point is not None:
            return haversine_m(self.latlng, point) <= self.radius_m
        return False

    def links(self):
        if self.point is None:
            return {}
        links = map_links(self.latlng)
        if self.bbox is not None:
            links["osm_cell"] = _osm_box_link(self.bbox)
        else:
            links["osm"] = _osm_point_link(self.latlng)
        return links

    def to_dict(self):
        """JSON-ready, in the form Run.ask() takes."""
        d = {"id": self.id, "label": self.label}
        if self.detail:
            d["detail"] = self.detail
        if self.point is not None:
            d.update(point=dict(self.point), point_role=self.point_role, links=self.links(),
                     street_view_coverage="unchecked")
        if self.radius_m is not None:
            d["radius_m"] = self.radius_m
        if self.bbox is not None:
            d["bbox"] = self.bbox.to_dict()
        if self.bound_m is not None:
            d["bound_m"] = self.bound_m
        d.update(complement=self.complement, covers=list(self.covers), support=round(self.support, 6))
        return d


def _check_tiling(scope, cells):
    """Cells inside the scope, with disjoint interiors and areas (in square degrees) adding up to the
    scope's: then their union is the whole scope."""
    if not all(scope.contains_box(c) for c in cells):
        raise ValueError("a zone cell reaches outside the question's scope")
    if any(a.overlaps(b) for i, a in enumerate(cells) for b in cells[i + 1:]):
        raise ValueError("zone cells overlap")
    area = [(b.north - b.south) * (b.east - b.west) for b in [scope, *cells]]
    if abs(sum(area[1:]) - area[0]) > 1e-9 * area[0]:
        raise ValueError("the zone cells leave part of the scope uncovered")


@dataclass
class Question:
    """A multiple-choice question of one kind, with 2-4 options; validated when made."""

    kind: str
    text: str
    options: list
    scope: Box | None = None  # zone: the area the cells cover
    details: dict = field(default_factory=dict)  # JSON-ready extras logged with it, e.g. "expected_gain"
    assign: Callable | None = None  # feature: candidate -> option ID
    question_id: str | None = None  # set by ask_operator from the run log

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if not 2 <= len(self.options) <= MAX_OPTIONS:
            raise ValueError(f"a question has 2 to {MAX_OPTIONS} options, got {len(self.options)}")
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids) or not set(ids) <= set(OPTION_IDS):
            raise ValueError(f"option IDs must be unique letters from {OPTION_IDS!r}, got {ids}")
        if any(not str(o.label).strip() for o in self.options):
            raise ValueError("every option needs a label")
        complements = [o for o in self.options if o.complement]
        if len(complements) > 1:
            raise ValueError("at most one 'None of these' / 'Outside this area' option")
        regions = [o for o in self.options if not o.complement]
        if self.kind == "place":
            if not complements:
                raise ValueError("a place question needs an explicit 'None of these' option")
            if any(o.point is None or not o.radius_m or o.point_role not in ROLES for o in regions):
                raise ValueError("each place option needs a point, its role and a radius")
            if any(a.radius_m + b.radius_m > haversine_m(a.latlng, b.latlng) + 1e-6
                   for i, a in enumerate(regions) for b in regions[i + 1:]):
                raise ValueError("place options overlap")
        elif self.kind == "zone":
            if self.scope is None:
                raise ValueError("a zone question needs its scope")
            for o in regions:
                if o.bbox is None or o.point is None or not o.bbox.contains(o.latlng):
                    raise ValueError(f"zone option {o.id} needs a cell with its point inside")
                if o.bound_m is None or o.bound_m < max(haversine_m(o.latlng, c) for c in o.bbox.corners()):
                    raise ValueError(f"zone option {o.id}: bound_m does not cover its cell")
            _check_tiling(self.scope, [o.bbox for o in regions])
            if not complements and not self.scope.contains_box(ALLOWED_AREA):
                raise ValueError("cells covering only part of the allowed area need an 'Outside this area' option")
        elif self.assign is None:
            raise ValueError("a feature question needs assign(candidate) -> option ID")

    def option(self, option_id):
        for o in self.options:
            if o.id == option_id:
                return o
        raise ValueError(f"the question has no option {option_id!r}")

    def option_for(self, candidate):
        """The one option holding this hypothesis: a Candidate, or for place and zone questions also a
        (lat, lng) or {"lat", "lng"} point."""
        if self.kind == "feature":
            return self.option(self.assign(candidate))
        if isinstance(candidate, Candidate):
            point = candidate.point
        else:
            point = (candidate["lat"], candidate["lng"]) if isinstance(candidate, dict) else tuple(candidate)
        regions = [o for o in self.options if not o.complement]
        for o in regions:
            if o.contains(point):
                return o
        for o in self.options:
            if o.complement:
                return o
        clamped = self.scope.clamp(point)  # whole-area zones only: the cells tile the scope
        return next(o for o in regions if o.contains(clamped))

    def option_dicts(self):
        return [o.to_dict() for o in self.options]

    def log_details(self):
        """The extras for Run.ask(**details): the scope and self.details."""
        clash = [k for k in RESERVED_DETAILS if k in self.details]
        if clash:
            raise ValueError(f"details may not set Run.ask's own fields: {clash}")
        return {**({"scope": self.scope.to_dict()} if self.scope is not None else {}), **self.details}


def _fill_coverage(question, candidates):
    """Record which hypotheses each option holds (heaviest first) and their share of the weight."""
    held = {o.id: [] for o in question.options}
    for c in sorted(candidates, key=lambda c: c.weight, reverse=True):
        held[question.option_for(c).id].append(c)
    total = sum(c.weight for c in candidates)
    for o in question.options:
        o.covers = [c.source for c in held[o.id]]
        o.support = sum(c.weight for c in held[o.id]) / total if total > 0 else 0.0
    return held


def _phrase(question, phrase_fn):
    """Let phrase_fn (later the VLM) reword the question text; the options stay exactly as built."""
    if phrase_fn is None:
        return question
    template, text = question.text, phrase_fn(question)
    text = text.strip() if isinstance(text, str) else ""
    if text and not SILENCE_RE.search(text):
        question.text = text
        question.details.update(phrased=True, template_text=template)
    else:
        question.details.update(phrased=False, phrasing_refused="empty, or it gives a skip a meaning")
    return question


def _fmt_m(metres):
    if metres < 1000:
        return f"{metres:.0f} m"
    if metres < 10_000:
        return f"{metres / 1000:.1f} km"
    return f"{metres / 1000:,.0f} km"


def _deg(value, positive, negative):
    """Degrees for people: up to 6 decimals (about 10 cm) and at least 2, so a cut shows where it is."""
    text = f"{abs(value):.6f}".rstrip("0")
    text += "0" * max(0, 2 - len(text.split(".")[1]))
    return f"{text}° {positive if value >= 0 else negative}"


def _fmt_box(box):
    return (f"latitude {_deg(box.south, 'N', 'S')} to {_deg(box.north, 'N', 'S')}, "
            f"longitude {_deg(box.west, 'E', 'W')} to {_deg(box.east, 'E', 'W')}")


def place_question(candidates, k=3, min_separation_m=DEFAULT_MIN_SEPARATION_M, phrase_fn=None):
    """Up to k (at most 3) distinct supported candidates, heaviest first, plus "None of these".

    Candidates at least min_separation_m apart (non-maximum suppression); see the module docstring for
    what each option's radius means. Candidates with no weight are never offered.
    """
    if not 1 <= k <= MAX_OPTIONS - 1:
        raise ValueError(f"k must be 1 to {MAX_OPTIONS - 1}: 'None of these' takes the last option")
    if not min_separation_m >= 1:
        raise ValueError(f"min_separation_m must be at least 1 m, got {min_separation_m}")
    candidates = list(candidates)
    kept = distinct([c for c in candidates if c.weight > 0], min_separation_m)[:k]
    if not kept:
        raise ValueError("no supported candidate to ask about")
    points = [coordinate(c.point) for c in kept]
    options = []
    for i, (c, point) in enumerate(zip(kept, points)):
        here = (point["lat"], point["lng"])
        halfway = [haversine_m(here, (p["lat"], p["lng"])) / 2 for j, p in enumerate(points) if j != i]
        radius = math.floor(min([max(min_separation_m / 2, c.extent_m or 0.0), *halfway]) * 10) / 10
        detail = (f"{ROLE_TEXT[c.role]} This option means the camera stood within about {_fmt_m(radius)} of it. "
                  f"Source: {c.source}.")
        options.append(Option(OPTION_IDS[i], c.label or c.source, detail, point, c.role, radius_m=radius))
    options.append(Option(OPTION_IDS[len(kept)], "None of these",
                          "The camera stood farther than the stated distance from every place above.",
                          complement=True))
    question = Question("place", TEMPLATES["place"], options, details={"min_separation_m": min_separation_m})
    _fill_coverage(question, candidates)
    return _phrase(question, phrase_fn)


def _quantile_cut(lo, hi, values, fraction):
    """A cut in (lo, hi) with about `fraction` of the weight of `values` [(coordinate, weight)] below it.

    It lies midway between two neighbouring hypotheses; without two distinct coordinates to separate,
    the middle of (lo, hi). Zero total weight balances the count of hypotheses instead.
    """
    if sum(w for _, w in values) <= 0:
        values = [(x, 1.0) for x, _ in values]
    weight = {}
    for x, w in values:
        weight[x] = weight.get(x, 0.0) + w
    xs = sorted(weight)
    if len(xs) < 2:
        left, right = lo, hi
    else:
        target, below, best = fraction * sum(weight.values()), 0.0, None
        for left, right in zip(xs, xs[1:]):
            below += weight[left]
            if best is None or abs(below - target) < best[0]:
                best = (abs(below - target), left, right)
        _, left, right = best
    cut = (left + right) / 2
    tidy = round(cut, 7)  # about 1 cm: a readable log, as long as it still separates the two sides
    return tidy if left < tidy < right else cut


def _split(box, hypotheses, n):
    """n cells covering `box`: cut across its longer side at weighted quantiles, then recurse.

    Listed in the order of the cuts: the north part before the south part, the west before the east.
    """
    if n == 1:
        return [box]
    lower_n = n // 2
    axis, k = ("lat", 0) if box.height_m >= box.width_m else ("lng", 1)
    lo, hi = (box.south, box.north) if axis == "lat" else (box.west, box.east)
    cut = _quantile_cut(lo, hi, [(p[k], w) for p, w in hypotheses], lower_n / n)
    lower, upper = box.split(axis, cut)
    lower = _split(lower, [(p, w) for p, w in hypotheses if p[k] < cut], lower_n)
    upper = _split(upper, [(p, w) for p, w in hypotheses if p[k] >= cut], n - lower_n)
    return upper + lower if axis == "lat" else lower + upper


def _side(lo, hi, lo_is_cut, hi_is_cut, positive, negative, above, below):
    lo_text, hi_text = _deg(lo, positive, negative), _deg(hi, positive, negative)
    if lo_is_cut and hi_is_cut:
        return f"between {lo_text} and {hi_text}"
    return f"{above} {lo_text}" if lo_is_cut else f"{below} {hi_text}" if hi_is_cut else ""


def _cell_label(cell, scope):
    """The side of each cut the cell lies on, e.g. "North of 43.14° N, east of 3.765° W"."""
    parts = [_side(cell.south, cell.north, cell.south > scope.south, cell.north < scope.north, "N", "S",
                   "north of", "south of"),
             _side(cell.west, cell.east, cell.west > scope.west, cell.east < scope.east, "E", "W",
                   "east of", "west of")]
    text = ", ".join(p for p in parts if p) or "the whole area"
    return text[0].upper() + text[1:]


def _cell_detail(option, held):
    names = [c.label or c.source for c in held]
    holds = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    return (f"The zone is {_fmt_box(option.bbox)}, about {_fmt_m(option.bbox.width_m)} east-west by "
            f"{_fmt_m(option.bbox.height_m)} north-south. The marked point is its centre, not a camera "
            f"position; no part of the zone is more than {_fmt_m(option.bound_m)} from it. "
            f"Current candidates in it: {holds or 'none'}.")


def zone_question(candidates, scope=None, phrase_fn=None):
    """Cells covering the scope (a Box or {"south", "west", "north", "east"}; None for ALLOWED_AREA).

    A scope holding the whole allowed area gets 4 cells; a sub-area gets 3 cells plus "Outside this
    area". Cells follow the cuts: the north part before the south part, the west before the east.
    """
    candidates = list(candidates)
    scope = ALLOWED_AREA if scope is None else Box.of(scope)
    whole = scope.contains_box(ALLOWED_AREA)
    inside = [(c.point, c.weight) for c in candidates if scope.contains(c.point)]
    cells = _split(scope, inside, 4 if whole else 3)
    options = []
    for option_id, cell in zip(OPTION_IDS, cells):
        point = coordinate(cell.centre)
        options.append(Option(option_id, _cell_label(cell, scope), point=point, point_role="area", bbox=cell,
                              bound_m=cell_bound_m(cell, (point["lat"], point["lng"]))))
    if not whole:
        options.append(Option(OPTION_IDS[len(cells)], "Outside this area",
                              f"Anywhere else in Portugal, Spain or France: outside {_fmt_box(scope)}.",
                              complement=True))
    question = Question("zone", TEMPLATES["zone_whole" if whole else "zone_part"], options, scope=scope,
                        details={"scope_kind": "allowed_area" if whole else "sub_area"})
    held = _fill_coverage(question, candidates)
    for o in options:
        if not o.complement:
            o.detail = _cell_detail(o, held[o.id])
    return _phrase(question, phrase_fn)


@dataclass
class ZoneOption(Option):
    """A named administrative zone of panoloc.zones (region_question). It holds a point when the zone
    index places the point in that zone, a snap within 1 km of it included: contains_fn(point) -> bool.
    `extent` is the zone's bounding box and `outline` a simplified GeoJSON Polygon, both for display only."""

    zone_id: str | None = None
    zone_level: str | None = None
    zone_name: str | None = None
    search_text: str | None = None  # what to type into a map search to see the zone's outline
    extent: Box | None = None
    area_km2: float | None = None
    outline: dict | None = None
    contains_fn: Callable | None = field(default=None, repr=False, compare=False)

    def contains(self, point):
        return self.contains_fn is not None and bool(self.contains_fn(tuple(point)))

    def links(self):
        if self.point is None:
            return {}
        links = map_links(self.latlng)
        if self.search_text:
            links["google_maps_zone"] = f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.search_text)}"
        if self.extent is not None:
            links["osm_zone"] = _osm_box_link(self.extent)
        return links

    def to_dict(self):
        d = super().to_dict()
        d.update(zone_id=self.zone_id, zone_level=self.zone_level, zone_name=self.zone_name)
        if self.area_km2 is not None:
            d["area_km2"] = round(self.area_km2, 3)
        if self.extent is not None:
            d["extent"] = self.extent.to_dict()
        if self.outline is not None:
            d["zone"] = self.outline  # GeoJSON, [lng, lat]: what the console draws
        return d


@dataclass
class RegionQuestion(Question):
    """A zone question whose options are named zones (region_question), validated when made.

    Its options are ZoneOptions plus, unless they are the three countries, one complement ("Elsewhere"
    or "Outside <zone>") holding the rest of the allowed area. scope_zone is the zone the question was
    asked within (None: the allowed area) and split_zone the zone whose subzones it offers.
    """

    zones: object = field(default=None, repr=False, compare=False)
    scope_zone: object = None
    split_zone: object = None

    def __post_init__(self):
        if self.kind != "zone":
            raise ValueError(f"a region question has kind 'zone', got {self.kind!r}")
        if self.zones is None:
            raise ValueError("a region question needs the zone index")
        if not 2 <= len(self.options) <= MAX_OPTIONS:
            raise ValueError(f"a question has 2 to {MAX_OPTIONS} options, got {len(self.options)}")
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids) or not set(ids) <= set(OPTION_IDS):
            raise ValueError(f"option IDs must be unique letters from {OPTION_IDS!r}, got {ids}")
        if any(not str(o.label).strip() for o in self.options):
            raise ValueError("every option needs a label")
        complements = [o for o in self.options if o.complement]
        if len(complements) > 1:
            raise ValueError("at most one 'Elsewhere' / 'Outside' option")
        regions = [o for o in self.options if not o.complement]
        if not regions:
            raise ValueError("a region question needs at least one named zone")
        for o in regions:
            if not isinstance(o, ZoneOption) or o.zone_id is None or o.contains_fn is None:
                raise ValueError(f"option {o.id} needs its zone and contains_fn")
            if o.point is None or o.point_role != "area" or not o.contains(o.latlng):
                raise ValueError(f"zone option {o.id} needs its representative point inside its zone")
            if o.bound_m is None or not o.bound_m > 0:
                raise ValueError(f"zone option {o.id} needs bound_m")
        zones = [self.zones.get(o.zone_id) for o in regions]
        if len({z.id for z in zones}) != len(zones):
            raise ValueError("a zone is offered twice")
        if len({z.tree for z in zones}) > 1 or any(self.zones.is_within(a, b) for a in zones for b in zones if a != b):
            raise ValueError("zone options overlap: they must be distinct zones of one tree, none inside another")
        if not complements and {z.id for z in zones} != {z.id for z in self.zones.roots()}:
            raise ValueError("zones covering only part of the allowed area need an 'Elsewhere' option")

    def option_for(self, candidate):
        """The one option holding this hypothesis (a Candidate, (lat, lng) or {"lat", "lng"}): the named
        zone the zone index places it in, else the complement. Without a complement the options are the
        countries, and a point outside all of them and beyond the snap (far at sea, overseas; it cannot
        be the answer) goes to the nearest one."""
        if isinstance(candidate, Candidate):
            point = candidate.point
        else:
            point = (candidate["lat"], candidate["lng"]) if isinstance(candidate, dict) else tuple(candidate)
        regions = [o for o in self.options if not o.complement]
        for o in regions:
            if o.contains(point):
                return o
        for o in self.options:
            if o.complement:
                return o
        zone, _ = self.zones.nearest(point, [o.zone_id for o in regions])
        return next(o for o in regions if o.zone_id == zone.id)

    def scope_dict(self):
        def brief(z):
            return None if z is None else {"zone_id": z.id, "label": z.label, "level": z.level}
        return {"zone": brief(self.scope_zone), "label": self.scope_zone.label if self.scope_zone else ALLOWED_AREA_TEXT,
                "split": brief(self.split_zone)}

    def log_details(self):
        """The extras for Run.ask(**details): the scope (zones, not a box) and self.details."""
        clash = [k for k in RESERVED_DETAILS if k in self.details]
        if clash:
            raise ValueError(f"details may not set Run.ask's own fields: {clash}")
        return {"scope": self.scope_dict(), **self.details}


def _fmt_km2(area):
    return f"{area:,.0f} km²" if area >= 10 else f"{area:.1f} km²" if area >= 0.1 else f"{area * 1e6:,.0f} m²"


def _region_detail(zone, option, held):
    names = [c.label or c.source for c in held]
    holds = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    what = zone.description[0].upper() + zone.description[1:]
    return (f"{what}, about {_fmt_km2(zone.area_km2)}. The marked point lies inside the zone and is not a camera "
            f"position; no part of the zone is more than {_fmt_m(option.bound_m)} from it. "
            f"Current candidates in it: {holds or 'none'}.")


def region_question(candidates, zones, scope=None, phrase_fn=None, *, exclude=(), tree="primary",
                    descend_share=REGION_DESCEND_SHARE):
    """Named zones from a panoloc.zones Zones index as a zone question (module docstring).

    scope: None for the allowed area, or a zone (ID or Zone), e.g. the one an earlier answer picked.
    The question offers the scope's subzones (the countries for the allowed area), going down a level
    while one subzone holds at least descend_share of the weight inside (None: never) and has two or
    more subzones of its own. Then: every subzone when they fit (all three countries; at most 3 plus
    "Outside <zone>" otherwise), else the 3 heaviest plus "Elsewhere". Zones in `exclude` (picked
    against before) are not offered and their hypotheses do not count; with no weight left, the
    largest subzones are offered. tree="nuts" walks Portugal's NUTS regions instead of the districts.
    """
    candidates = list(candidates)
    scope_zone = None if scope is None else zones.get(scope)
    excluded = {zones.get(z).id for z in exclude}
    total = sum(c.weight for c in candidates)
    weights = [c.weight if total > 0 else 1.0 for c in candidates]
    located = [zones.locate(*c.point) for c in candidates]

    def mass(zone):
        return sum(w for w, loc in zip(weights, located)
                   if loc is not None and zone.id in loc.ids and not excluded & loc.ids)

    def subzones(zone, keep_excluded=False):
        kids = zones.roots() if zone is None else zones.children(zone, tree=tree)
        while len(kids) == 1 and zones.children(kids[0], tree=tree):  # one subzone asks the same: look through
            kids = zones.children(kids[0], tree=tree)
        return [k for k in kids if keep_excluded or k.id not in excluded]

    node, kids = scope_zone, subzones(scope_zone)
    if not kids:
        raise ValueError(f"{scope_zone.label if scope_zone else ALLOWED_AREA_TEXT} has no subzones to offer: "
                         "split it into cells instead")
    weight = {k.id: mass(k) for k in kids}
    while descend_share is not None:
        inside = sum(weight.values())
        top = max(kids, key=lambda k: (weight[k.id], k.area_km2))
        below = subzones(top) if inside > 0 and weight[top.id] >= descend_share * inside else []
        if len(below) < 2:
            break
        node, kids = top, below
        weight = {k.id: mass(k) for k in kids}
    roots = {z.id for z in zones.roots()}
    if node is None and {k.id for k in kids} == roots and len(kids) <= MAX_OPTIONS:
        named = kids
    elif len(kids) <= MAX_OPTIONS - 1:
        named = kids
    else:
        ranked = sorted(kids, key=lambda k: (-weight[k.id], -k.area_km2, k.id))
        named = ([k for k in ranked if weight[k.id] > 0] or ranked)[:MAX_OPTIONS - 1]
    named = sorted(named, key=lambda k: (-weight[k.id], k.label))
    options = []
    for option_id, z in zip(OPTION_IDS, named):
        point = coordinate(z.rep)
        south, west, north, east = z.bbox
        options.append(ZoneOption(option_id, z.label, point=point, point_role="area",
                                  bound_m=zones.bound_m((point["lat"], point["lng"]), z), zone_id=z.id,
                                  zone_level=z.level, zone_name=z.name, search_text=z.search_text,
                                  extent=Box(south, west, north, east), area_km2=z.area_km2, outline=zones.outline(z),
                                  contains_fn=functools.partial(zones.contains, z.id)))
    whole = {z.id for z in named} == roots
    outside_zone = None
    if not whole:
        same_level = len({z.level for z in named}) == 1
        if len(named) == 1:
            which = f"the {named[0].singular if same_level else 'zone'} above"
        else:
            which = f"the {len(named)} {named[0].plural if same_level else 'zones'} above"
        if node is not None and {z.id for z in named} == {k.id for k in subzones(node, keep_excluded=True)}:
            label, detail = f"Outside {node.label}", f"Anywhere in {ALLOWED_AREA_TEXT} outside {node.label}."
            outside_zone = node.id
        else:
            rest = f": the rest of {node.label}, or outside it" if node is not None else ""
            label = "Elsewhere"
            detail = f"Anywhere in {ALLOWED_AREA_TEXT} that is not in {which}{rest}."
        options.append(Option(OPTION_IDS[len(options)], label, detail, complement=True))
    levels = sorted({z.level for z in named})
    details = {"scope_kind": "allowed_area" if scope_zone is None else "zone", "zone_kind": "named",
               "tree": tree, "level": levels[0] if len(levels) == 1 else levels, "descend_share": descend_share,
               "excluded": sorted(excluded), "outside_zone": outside_zone,
               "weights": "fusion" if total > 0 else "count", "zones_version": getattr(zones, "version", None)}
    question = RegionQuestion("zone", TEMPLATES["region_whole" if whole else "region_part"], options,
                              details=details, zones=zones, scope_zone=scope_zone, split_zone=node)
    held = _fill_coverage(question, candidates)
    for o, z in zip(options, named):
        o.detail = _region_detail(z, o, held[o.id])
    return _phrase(question, phrase_fn)


def region_chain(question, option_id, scope=None, exclude=()):
    """(scope, exclude) for the next region_question once the team picked option_id (chained questions).

    A named zone becomes the scope, with nothing excluded. "Elsewhere" keeps the scope and excludes the
    named zones. "Outside <zone>" excludes that zone; when the search was inside it (the scope), the
    scope widens to the whole allowed area, so the earlier answer is recoverable. A skip has no answer,
    so it never reaches this: the caller keeps scope and exclude as they were.
    """
    option = question.option(option_id)
    zones = question.zones
    if not option.complement:
        return option.zone_id, []
    exclude = set(exclude)
    outside = question.details.get("outside_zone")
    if outside is not None:
        exclude.add(outside)
        if scope is not None and zones.is_within(scope, outside):
            scope = None
    else:
        exclude.update(o.zone_id for o in question.options if not o.complement)
    return scope, sorted(exclude)


def area_candidate(option, weight=1.0):
    """The area a chosen zone or cell option stands for, as an `area` Candidate (PLAN.md 3.3; T42).

    When the team picks an option that holds no hypothesis, add this so later questions and the output
    have that area: the option's representative point, which marks the zone and never a camera
    position, with extent_m = bound_m, a radius around it that covers the whole zone or cell.
    """
    if option.complement or option.point is None or option.bound_m is None:
        raise ValueError("only a zone or cell option with a point and bound_m stands for an area")
    if isinstance(option, ZoneOption):
        source = f"zone:{option.zone_id}"
        extra = {"zone_id": option.zone_id, "level": option.zone_level, "area_km2": option.area_km2}
    elif option.bbox is not None:
        b = option.bbox
        source = "cell:" + ",".join(_url_number(v) for v in (b.south, b.west, b.north, b.east))
        extra = {"cell": b.to_dict()}
    else:
        raise ValueError("only a zone or cell option stands for an area")
    return Candidate(option.point["lat"], option.point["lng"], "area", source, label=option.label, weight=weight,
                     extent_m=option.bound_m,
                     details={**extra, "bound_m": option.bound_m, "extent_source": "geometric_bound",
                              "option_id": option.id, "point": "the zone's representative point, not a camera position"})


# -- polygon cells (panoloc.cells; T42) -------------------------------------------------------------
# Additions only: the geometry is built in panoloc.cells (shapely, .venv); these classes import shapely
# lazily, so this module still imports without it.

TEMPLATES.update({
    "cell_part": "Which area contains the camera position? The first areas split the current search area without "
                 "overlapping, as drawn on the linked map; the last option is anywhere outside it.",
    "cell_whole": "Which area contains the camera position? The four areas do not overlap and together cover all of "
                  "Portugal, Spain and France, as drawn on the linked map.",
})
LINK_NAMES.update({"cell_map": "Cell on a map (geojson.io)"})
CELL_TILING_TOLERANCE = 1e-7  # relative area: the cells' union may differ from the scope by this (floating point)


@dataclass
class CellOption(Option):
    """A polygon cell of panoloc.cells (cell_question). It holds a point when the cell's polygon does,
    edges included: geometry is the cell in WGS84 (shapely, x = longitude), cell the same as GeoJSON
    ([lng, lat], 7 decimals) for the log, the operator console and the simulated operators (simplified to
    2,000 vertices for a very large cell, such as a third of a country). bound_m
    includes deviation_m, the boundary error of the zone the cell was cut from, when the cell reaches
    that zone's boundary. geometry_m is the cell in its scope's metric frame (panoloc.cells.Frame)."""

    cell_id: str | None = None
    cell: dict | None = None
    extent: Box | None = None
    area_m2: float | None = None
    deviation_m: float = 0.0
    map_link: str | None = None  # geojson.io with the cell and its point
    geometry: object = field(default=None, repr=False, compare=False)
    geometry_m: object = field(default=None, repr=False, compare=False)

    def contains(self, point):
        if self.geometry is None:
            return False
        import shapely
        lat, lng = point
        return bool(shapely.intersects_xy(self.geometry, float(lng), float(lat)))

    def links(self):
        if self.point is None:
            return {}
        links = map_links(self.latlng)
        links["osm"] = _osm_point_link(self.latlng)
        if self.map_link:
            links["cell_map"] = self.map_link
        return links

    def to_dict(self):
        d = super().to_dict()
        d.update(cell_id=self.cell_id, deviation_m=self.deviation_m)
        if self.area_m2 is not None:
            d["area_m2"] = round(self.area_m2, 1)
        if self.extent is not None:
            d["extent"] = self.extent.to_dict()
        if self.cell is not None:
            d["cell"] = self.cell  # the exact cell, GeoJSON [lng, lat]
            d["zone"] = _outer_ring(self.cell)  # its largest part's outer ring: what the console draws
        return d


def _outer_ring(geometry):
    """A GeoJSON Polygon of the largest part's outer ring (by its bounding box: display only)."""
    if geometry.get("type") == "Polygon":
        return {"type": "Polygon", "coordinates": [geometry["coordinates"][0]]}

    def size(polygon):
        lngs, lats = [p[0] for p in polygon[0]], [p[1] for p in polygon[0]]
        return (max(lngs) - min(lngs)) * (max(lats) - min(lats))
    largest = max(geometry["coordinates"], key=size)
    return {"type": "Polygon", "coordinates": [largest[0]]}


@dataclass
class CellQuestion(Question):
    """A zone question whose options are polygon cells (panoloc.cells.cell_question), validated when made.

    scope is a panoloc.cells.Scope (geom: its WGS84 area). The cells tile the scope: disjoint, their
    union the scope, each with its representative point strictly inside and bound_m covering it. There
    is one complement, "Outside this area", unless the scope is the whole allowed area (scope.whole):
    then up to 4 cells and none.
    """

    def __post_init__(self):
        import shapely
        if self.kind != "zone":
            raise ValueError(f"a cell question has kind 'zone', got {self.kind!r}")
        if not 2 <= len(self.options) <= MAX_OPTIONS:
            raise ValueError(f"a question has 2 to {MAX_OPTIONS} options, got {len(self.options)}")
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids) or not set(ids) <= set(OPTION_IDS):
            raise ValueError(f"option IDs must be unique letters from {OPTION_IDS!r}, got {ids}")
        if any(not str(o.label).strip() for o in self.options):
            raise ValueError("every option needs a label")
        if len({o.label for o in self.options}) != len(self.options):
            raise ValueError("option labels must differ")
        if self.scope is None or getattr(self.scope, "geom", None) is None:
            raise ValueError("a cell question needs its scope (panoloc.cells.Scope)")
        complements = [o for o in self.options if o.complement]
        cells = [o for o in self.options if not o.complement]
        whole = bool(getattr(self.scope, "whole", False))
        if len(complements) != (0 if whole else 1):
            raise ValueError("a cell question needs exactly one 'Outside this area' option, unless its scope is "
                             "the whole allowed area")
        if not cells:
            raise ValueError("a cell question needs at least one cell")
        for o in cells:
            if not isinstance(o, CellOption) or o.geometry is None:
                raise ValueError(f"option {o.id} needs its cell geometry")
            if o.point is None or o.point_role != "area":
                raise ValueError(f"cell option {o.id} needs its representative point (role area)")
            lat, lng = o.latlng
            if not shapely.contains_xy(o.geometry, lng, lat):
                raise ValueError(f"cell option {o.id}: its point is not strictly inside its cell")
            hull = shapely.get_coordinates(shapely.convex_hull(o.geometry))
            farthest = max(haversine_m(o.latlng, (y, x)) for x, y in hull)
            if o.bound_m is None or o.bound_m < farthest + (o.deviation_m or 0.0):
                raise ValueError(f"cell option {o.id}: bound_m does not cover its cell")
        scope_area = float(shapely.area(self.scope.geom))
        union = shapely.union_all([o.geometry for o in cells])
        if shapely.area(shapely.symmetric_difference(union, self.scope.geom)) > CELL_TILING_TOLERANCE * scope_area:
            raise ValueError("the cells do not cover exactly their scope")
        for i, a in enumerate(cells):
            for b in cells[i + 1:]:
                if shapely.area(shapely.intersection(a.geometry, b.geometry)) > CELL_TILING_TOLERANCE * scope_area:
                    raise ValueError(f"cells {a.id} and {b.id} overlap")

    def option_for(self, candidate):
        """The one option holding this hypothesis (a Candidate, (lat, lng) or {"lat", "lng"}): the first
        cell whose polygon holds its point, edges included, else "Outside this area". Without a
        complement (the whole allowed area), a point outside every cell goes to the nearest one."""
        if isinstance(candidate, Candidate):
            point = candidate.point
        else:
            point = (candidate["lat"], candidate["lng"]) if isinstance(candidate, dict) else tuple(candidate)
        cells = [o for o in self.options if not o.complement]
        for o in cells:
            if o.contains(point):
                return o
        for o in self.options:
            if o.complement:
                return o
        import shapely
        here = shapely.Point(point[1], point[0])
        return min(cells, key=lambda o: shapely.distance(o.geometry, here))

    def log_details(self):
        """The extras for Run.ask(**details): the scope (a summary with its outline) and self.details."""
        clash = [k for k in RESERVED_DETAILS if k in self.details]
        if clash:
            raise ValueError(f"details may not set Run.ask's own fields: {clash}")
        return {"scope": self.scope.to_dict(), **self.details}


def cell_question(candidates, scope, phrase_fn=None, **kwargs):
    """Polygon cells over a panoloc.cells.Scope, plus "Outside this area": panoloc.cells.cell_question (.venv)."""
    from panoloc import cells
    return cells.cell_question(candidates, scope, phrase_fn=phrase_fn, **kwargs)


def cell_chain(question, option_id):
    """The next scope once the team picked option_id of a CellQuestion: panoloc.cells.chain."""
    from panoloc import cells
    return cells.chain(question, option_id)


def cell_area_candidate(option, weight=1.0):
    """The area a picked cell stands for, as an `area` Candidate: its representative point, which is not
    a camera position, with extent_m = bound_m, a radius around it covering the whole cell (T42; the
    cell counterpart of area_candidate)."""
    if option.complement or not isinstance(option, CellOption) or option.point is None or option.bound_m is None:
        raise ValueError("only a cell option with a point and bound_m stands for an area")
    return Candidate(option.point["lat"], option.point["lng"], "area", f"cell:{option.cell_id}", label=option.label,
                     weight=weight, extent_m=option.bound_m,
                     details={"cell_id": option.cell_id, "cell": option.cell, "bound_m": option.bound_m,
                              "extent_source": "geometric_bound", "option_id": option.id,
                              "point": "the cell's representative point, not a camera position"})


def feature_question(candidates, text, labels, assign):
    """A question about an observable feature, with 2-4 option labels written by the agent.

    assign(candidate) -> the index of the label that candidate predicts; it is called again for every
    candidate that expected_gain or apply_answer sees, so it must cover candidates added later too.
    """
    if not 2 <= len(labels) <= MAX_OPTIONS:
        raise ValueError(f"a question has 2 to {MAX_OPTIONS} options, got {len(labels)}")

    def option_id(candidate):
        i = assign(candidate)
        if not (isinstance(i, int) and 0 <= i < len(labels)):
            raise ValueError(f"assign() must give a label index 0 to {len(labels) - 1}, got {i!r}")
        return OPTION_IDS[i]

    question = Question("feature", text, [Option(OPTION_IDS[i], label) for i, label in enumerate(labels)],
                        assign=option_id)
    _fill_coverage(question, candidates)
    return question


def _check_accuracy(answer_accuracy, n_options):
    accuracy = float(answer_accuracy)
    if not 1 / n_options <= accuracy <= 1:
        raise ValueError(f"answer_accuracy must be from 1/{n_options} (a random pick) to 1, got {accuracy}")
    return accuracy


def expected_gain(candidates, question, category=None, urban_probability=None,
                  answer_accuracy=DEFAULT_ANSWER_ACCURACY):
    """PLAN.md 3.4: is the question worth its x0.95? Returns a JSON-ready dict.

      before        best expected theta now (best_point over the candidates' and options' points)
      after         expected best expected theta once the answer is known, over the possible answers
      ratio, gain   after / before, and ratio - 1
      worth_asking  0.95 x after > before, i.e. gain > break_even (5.26%)
      answers       per option: its probability, the point the agent would then output, and its value

    Answer model: the team picks the option holding the true spot with probability answer_accuracy,
    otherwise one of the other options at random; so a wrong answer is part of `after`. Give exactly
    one of category ("urban", "non-urban") and urban_probability; the latter, used while the label is
    unknown, is an assumption and is returned with the result.
    """
    if (category is None) == (urban_probability is None):
        raise ValueError("give exactly one of category and urban_probability")
    if category is not None and category not in SCALE_M:
        raise ValueError(f"category must be one of {tuple(SCALE_M)}, got {category!r}")
    if urban_probability is not None and not 0 <= urban_probability <= 1:
        raise ValueError("urban_probability must be in [0, 1]")
    n = len(question.options)
    accuracy = _check_accuracy(answer_accuracy, n)
    candidates = list(candidates)
    total = sum(c.weight for c in candidates)
    if not total > 0:
        raise ValueError("hypothesis weights must sum to more than 0")
    prior = [c.weight / total for c in candidates]
    holder = [question.option_for(c).id for c in candidates]
    points = [c.point for c in candidates] + [o.latlng for o in question.options if o.point is not None]

    def score(d):
        if category is not None:
            return theta(d, category)
        return urban_probability * theta(d, "urban") + (1 - urban_probability) * theta(d, "non-urban")

    table = [[score(haversine_m(x, c.point)) for c in candidates] for x in points]

    def best(weights):  # scoring.best_point over `points`, with the theta table computed once
        mass = sum(weights)
        values = [sum(w * t for w, t in zip(weights, row)) / mass for row in table]
        i = max(range(len(values)), key=values.__getitem__)
        return coordinate(points[i]), values[i]

    point_before, before = best(prior)
    misclick = (1 - accuracy) / (n - 1)
    after, answers = 0.0, []
    for option in question.options:
        joint = [p * (accuracy if holder[j] == option.id else misclick) for j, p in enumerate(prior)]
        probability = sum(joint)
        if probability > 0:
            point, value = best(joint)
            after += probability * value
        else:  # only when answer_accuracy is 1 and the option holds no hypothesis
            point = value = None
        answers.append({"option_id": option.id, "probability": probability, "point": point,
                        "expected_theta": value})
    ratio = after / before
    return {"before": before, "after": after, "ratio": ratio, "gain": ratio - 1, "break_even": BREAK_EVEN,
            "worth_asking": QUESTION_FACTOR * after > before, "point_before": point_before, "answers": answers,
            "answer_accuracy": accuracy, "category": category, "urban_probability": urban_probability}


def apply_answer(candidates, question, option_id, answer_accuracy=DEFAULT_ANSWER_ACCURACY):
    """The team picked option_id: a soft update, returned as a new list (the input is left untouched).

    The chosen option's hypotheses keep their weight; every other one is multiplied by
    (1 - a) / ((n - 1) a), with a = answer_accuracy and n options: under the expected_gain answer model
    that is the likelihood of this answer if it were wrong relative to right, so the result is the
    posterior up to normalisation. Nothing is deleted, so after a wrong answer later evidence can still
    bring the right hypothesis back. "None of these" or "Outside this area" scales down the hypotheses
    in the listed places or in the cells instead. If nothing lies outside them, normalised beliefs do
    not move: the place options missed, so ask a zone question next (PLAN.md 3.4, zone fallback).

    There is deliberately no apply_skip: a skipped question carries no information (RULES.md, partner
    clarification 2), so after a skip the candidates stay exactly as they were.
    """
    chosen = question.option(option_id).id
    n = len(question.options)
    accuracy = _check_accuracy(answer_accuracy, n)
    if accuracy >= 1:
        raise ValueError("answer_accuracy must be below 1, so that a wrong answer stays recoverable")
    factor = (1 - accuracy) / ((n - 1) * accuracy)
    return [Candidate(**{**asdict(c), "weight": c.weight * (1.0 if question.option_for(c).id == chosen else factor)})
            for c in candidates]


def format_question(question):
    """The question as the operator sees it: options, points and links."""
    lines = [f"Question ({question.kind}): {question.text}"]
    for o in question.options:
        lines.append(f"  {o.id}) {o.label}")
        if o.detail:
            lines.append(f"     {o.detail}")
        if o.point is not None:
            lines.append(f"     Point: {o.point['lat']:.6f}, {o.point['lng']:.6f}")
            for name, url in o.links().items():
                note = " (coverage unchecked)" if name == "street_view" else ""
                lines.append(f"     {LINK_NAMES[name]}: {url}{note}")
    lines.append(f"Answering costs x{QUESTION_FACTOR} on every later output for this panorama, right or wrong. "
                 "Skipping costs nothing and changes nothing.")
    return "\n".join(lines)


def ask_operator(run, question, input_fn=input, print_fn=print):
    """Ask the team, log their choice, and return the chosen Option, or None on a skip.

    The question is logged with run.ask (which refuses wording that gives a skip a meaning) and printed
    with its options, points and links. Then it waits, with no timeout, for an option ID or s: anything
    else, an empty line included, is refused and asked again. A skip is logged with run.skip; it costs
    nothing and the caller changes nothing. End of input or Ctrl-C propagates and leaves the question
    open in the log, neither answered nor skipped.
    """
    question.question_id = run.ask(question.text, question.option_dicts(), kind=question.kind,
                                   **question.log_details())
    print_fn(format_question(question))
    ids = [o.id for o in question.options]
    prompt = f"Type {', '.join(ids)} to answer, or s to skip: "
    while True:
        choice = input_fn(prompt).strip().lower()
        if choice in ids:
            option = question.option(choice)
            run.answer(question.question_id, choice)
            print_fn(f"Answered {choice}: {option.label}. Later outputs are worth x{run.penalties.multiplier:.4f}.")
            return option
        if choice == "s":
            run.skip(question.question_id)
            print_fn(f"Skipped: nothing changes, and the multiplier stays x{run.penalties.multiplier:.4f}.")
            return None
        print_fn(f"{choice!r} is not one of the choices. Type {', '.join(ids)} to answer, or s to skip.")


DEMO_DIR = Path(__file__).resolve().parent.parent / "runs" / "demo"
DEMO_PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented (design_system_prompt.md), not a warm-up file


def demo_candidates():
    """Invented hypotheses: two spots in one city, a district elsewhere and a quarter in a third city."""
    return [
        Candidate(41.1450, -8.6100, "camera", "demo:ref-photo", label="Street corner (reference photo)",
                  weight=0.35, accuracy_m=10),
        Candidate(41.1520, -8.6030, "landmark", "demo:market", label="Old market hall", weight=0.25, extent_m=60),
        Candidate(38.7100, -9.1400, "area", "demo:district", label="Riverside district", weight=0.25, extent_m=900),
        Candidate(37.3900, -5.9900, "area", "demo:quarter", label="Cathedral quarter", weight=0.15, extent_m=1200),
    ]


def demo(runs_dir=DEMO_DIR, input_fn=input, print_fn=print):
    """A place question, then a zone question, with invented candidates; returns the log.json path."""
    run = Run(DEMO_PANORAMA, runs_dir, versions={"demo": "panoloc.questions --demo"})
    candidates = demo_candidates()
    run.candidates([c.to_dict() for c in candidates], stage="demo")
    print_fn(f"Demo run {run.run_id}: invented candidates, Urban label unknown (assumed 50% urban).")
    try:
        for build in (place_question, zone_question):
            question = build(candidates)
            gain = expected_gain(candidates, question, urban_probability=0.5)
            question.details["expected_gain"] = gain
            verdict = "worth asking" if gain["worth_asking"] else "not worth its cost; asked anyway for the demo"
            print_fn(f"\nExpected gain {gain['gain']:+.1%} against the +{BREAK_EVEN:.2%} break-even: {verdict}.")
            option = ask_operator(run, question, input_fn, print_fn)
            if option is not None:
                candidates = apply_answer(candidates, question, option.id)
                run.candidates([c.to_dict() for c in normalise(candidates)], stage="demo")
            print_fn("Support: " + ", ".join(f"{c.label} {c.weight:.1%}" for c in normalise(candidates)))
    except (EOFError, KeyboardInterrupt):
        print_fn("\nStopped. The open question stays open: neither an answer nor a skip is recorded.")
    hypotheses = [(c.point, c.weight) for c in candidates]
    point, _ = best_point([c.point for c in candidates], hypotheses, urban_probability=0.5)
    best = next(c for c in candidates if c.point == point)
    run.output([point] * 10, method="coarse_candidate", source_role=best.role, sources=[best.source],
               note="demo: the candidate with the best expected theta")
    path = run.finish()
    print_fn(f"\nOutput {point[0]:.5f}, {point[1]:.5f} x10 at multiplier x{run.penalties.multiplier:.4f}. Log: {path}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m panoloc.questions",
                                     description="Try the question loop by hand.")
    parser.add_argument("--demo", action="store_true",
                        help="interactive session with invented candidates; the run log goes under runs/demo/")
    parser.add_argument("--runs-dir", default=str(DEMO_DIR), help="folder for the demo run (default: %(default)s)")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.print_help()
        return 2
    demo(args.runs_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
