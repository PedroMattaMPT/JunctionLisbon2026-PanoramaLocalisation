"""Exhaustive polygon cells in metres: the landmark and cell route to a camera coordinate (PLAN.md 3.3, 3.4; T42).

A place the agent found (a shop sign OCR read, a monument the VLM recognised, a street, a postcode) or a
zone the team picked (a parish) says where to look, not where the camera stood. This module cuts that
area into cells the team can check on a map, asks which one holds the camera, cuts the picked cell
again, and outputs the representative point of the last cell with a geometric bound. A click picks a
cell; the agent computes the coordinate. It needs shapely, so it runs in .venv.

Scopes (Scope): the area a question splits, as a WGS84 polygon (x = longitude) with its parent chain.
  landmark / area  Scope.around(candidate): a geodesic disc around a typed candidate. Its radius is a
                   search extent chosen per evidence type (SEARCH_RULES), recorded in details as an
                   assumption, never as the camera position: the object's own extent (an OSM way's
                   footprint, or the type's assumed radius) plus how far that evidence is usually seen:
                     ocr_sign      +50 m   shop, café, office signs: 20-40 cm letters stay legible at
                                           16.9 px per degree (6080 px for 360°) to about 25-50 m
                     ocr_landmark  +120 m  big lettering on a church, museum, station or monument
                     vlm_landmark  +300 m  a façade or tower the VLM recognised: seen from across squares
                     street        +25 m   a street plate: the camera is on the street (its extent
                                           covers the street's length)
                     area          +25 m   a postcode, square, park or place: the camera is in it or at its edge
                     camera        +40 m   a verified reference photo: its GPS plus viewpoint displacement
                   at least MIN_SCOPE_RADIUS_M. evidence_kind() reads it from the candidate (its OSM type,
                   role, and the fusion clues that proposed it: ocr:... or vlm:...).
  zone             Scope.from_zone(zones, zone): a zone of panoloc.zones, usually a leaf (parish,
                   province, department), with zones.exact_geometry(zone). Its deviation_m (the
                   stored boundary's largest distance from the source boundary) is added to the bound
                   of every cell that reaches the zone's boundary; cells inside it need none.
  cell / remainder chain(): the picked cell, or the parent minus this scope after "Outside this area".
Every scope of a chain shares the root's metric Frame: x east and y north in metres, the equirectangular
projection scaled by cos(latitude) at the root's centre. It is an affine map of longitude/latitude, so
straight edges, containment and tiling are the same in both, and its scale error stays below 0.1% within
10 km. It places the cuts and measures areas; no bound depends on it.

Partition (cell_question): 3 disjoint cells whose union is the scope, plus "Outside this area"; 4 cells
and no outside option only for the whole allowed area (scope.whole). The candidate families, all cut at
weighted quantiles so that the cells carry similar weight:
  sectors   three 120° sectors around the landmark when it lies inside the scope ("North of X",
            bearings 300° to 60° from it). Three equal discs cover a disc at best with radius 0.866 R,
            which these sectors reach
  rings     within r of the landmark, then the rest split in two by a line through it (a sector's
            apex is the landmark): "Within 35 m of X", "35 m or more from X, west side"
  parallel  a cut across one of 4 compass directions at a third of the weight, then the larger part cut
            in half across its longest direction (zone_question's rule, in metres), or three strips
The cuts balance an even mix (AREA_SHARE) of the hypotheses' weight inside the scope and its area (a
lattice of AREA_POINTS points), or the area alone when the weight is not spread (fewer than 3 distinct
points, or one holding half): pure weight balancing let a small heavy landmark disc draw every cut while
the camera's cell kept 857 km2. The family with the lowest mass-weighted mean minimax radius of its
cells wins (the expected bound after the answer); sectors and rings around a named landmark win when
within FAMILY_SLACK (10%) of it, being easiest to check. Cuts avoid real hypotheses. Labels give bearings or distances from the landmark, or
the cell's compass position in its scope; each option carries its GeoJSON polygon and a geojson.io link.

Representative point: strictly inside its cell, at least MARGIN_M (0.25 m) from its edge. With weight in
the cell (hypotheses, or the route's samples of spread weight; country-wide residuals do not count),
the best expected-score point (PLAN.md 1.1) over that weight, among the cell's minimax point, the
hypotheses and the samples; otherwise the point minimising the maximum distance to the cell: the centre
of its smallest enclosing circle, or, when that is outside or too near the edge, the best point of the
cell shrunk by the margin. Spread weight is rarely uniform (a landmark's disc inside a parish), so the
minimax point alone can sit kilometres from where the weight is. The point marks the cell, never a
camera position.

Bound (bound_m): the largest Haversine distance (R = 6371 km) from the point to the vertices of the
cell's convex hull (the farthest point of a region is one of them), plus the deviation for a cell on a
zone's boundary, then 0.6% and 1 m as panoloc.questions.cell_bound_m, rounded up to 0.1 m. It is
recomputed for the point actually output. Targets (TARGET_BOUND_M): stop refining at a bound of 25 m for
an urban or unknown category, 1 km for a known non-urban one, or earlier when
panoloc.questions.expected_gain says the next question is not worth x0.95. Both assume the team picked
the right cell: geometric targets, not guarantees.

The route (CellRoute): hypotheses are points, but a landmark says "somewhere around here". So the route
spreads every non-camera hypothesis inside the root scope (the landmark itself, areas, zone points) over
its own search disc clipped to the root: pieces of uniform weight, split along the cells at every answer
and multiplied by the answer likelihood of panoloc.questions.apply_answer (the chosen option keeps its
weight, the others take (1 - a) / ((n - 1) a)). Unless one of those discs covers the whole root, the
root also gets a uniform piece (the camera may be anywhere in it). Camera hypotheses and everything
outside the root stay points and get apply_answer itself. hypotheses() samples the pieces: SAMPLES lattice points over the
current scope and a few for each piece outside it, as area Candidates ("cellmass:..."), so
expected_gain, apply_answer and option_for work unchanged and a picked cell always holds weight to
split. A skip changes nothing: the route only moves on answer(). exit_hypotheses() gives the pipeline
its hypotheses back: the current cell as an area Candidate (cell_area_candidate) and the rest of each
spread hypothesis's weight on the hypothesis itself.

Glue: route_scope(hypotheses, ...) says where the route starts: a zone the team picked down to a leaf;
the landmark or area a place answer picked; or a dominant landmark or area hypothesis (at least
STRONG_SHARE of the weight within its search disc, or DOMINANT_SHARE with a unique exact name match).

  from panoloc import cells, questions
  scope, why = cells.route_scope(hypotheses, zones=zones, zone_scope=leaf_id)   # or Scope.around(c)
  route = cells.CellRoute.start(hypotheses, scope, urban_probability=0.5)
  while not route.done():
      q = route.question()                              # a questions.CellQuestion, kind "zone"
      gain = route.gain(q)                              # questions.expected_gain over route.hypotheses()
      if not gain["worth_asking"]:
          break
      option = questions.ask_operator(run, q)           # the team types a-d, or s to skip
      if option is None:
          break                                         # a skip: nothing changes
      route = route.answer(q, option.id)                # soft update; picked cell or parent minus this
      if route.scope is None:
          break                                         # "Outside" the root: back to zone or place questions
  output = route.output()                               # geographic_cell, or None before any picked cell
  if output is not None:
      cells.log_cell_output(run, output, route)

Speed: a cell question builds in a few milliseconds for a landmark disc and under 50 ms for a parish; a
province of ES/FR (thousands of vertices) is cut on a simplified copy and rebuilt exactly once.
"""
import math
import json
from dataclasses import dataclass, field
from urllib.parse import quote

import numpy as np
import shapely

from panoloc import questions as Q
from panoloc.candidates import Candidate, Output
from panoloc.runlog import coordinate
from panoloc.scoring import EARTH_RADIUS_M, SCALE_M, ZERO_DISTANCE_M

M_PER_DEG = EARTH_RADIUS_M * math.pi / 180.0  # metres per degree of latitude on the scorer's sphere
TARGET_BOUND_M = {"urban": 25.0, "non-urban": 1000.0, None: 25.0}  # None: category unknown
N_CELLS, N_CELLS_WHOLE = 3, 4
DISC_VERTICES = 64  # a 64-gon inside the circle: at most 0.12% of the radius short of it
AREA_POINTS = 1024  # lattice points standing for area when the cut balances area
SAMPLES = 64  # route: weight samples over the current scope
OUTSIDE_SAMPLES = 2  # route: samples per piece of weight outside the current scope
MIN_PIECE_SAMPLES = 4
MARGIN_M = 0.25  # a representative point stays this far inside its cell (and coordinates round to ~1 cm)
GRID_M = 1e-6  # cells are snapped to a 1 micrometre grid, so the transform to degrees cannot fold a sliver
LAND_TOLERANCE_M = 25.0  # with a zone index, cells and points stay within this (+ the leaf's deviation_m) of land
MIN_ALLOWED_M2 = 1.0  # an area the answers leave smaller than this is no area
LOG_MAX_VERTICES = 2000  # logged cell and scope outlines (a whole country has about 100,000 vertices)
KEEP_OFF_M = 1.0  # cuts keep this far from real hypotheses where they can
FAMILY_SLACK = 0.10  # sectors and rings around the landmark win within 10% of the best expected size
AREA_SHARE = 0.5  # the cuts balance this share of area besides the hypotheses' weight (module docstring)
DIRECTIONS = (0.0, 90.0, 45.0, 135.0)  # bearings of the axis a parallel cut crosses (cardinal ones first)
SECTOR_STEP = 5.0
LATTICE_ROTATION = math.radians(17.0)  # so lattice rows never line up with a cut direction
DESIGN_MAX_VERTICES = 200  # larger scopes choose their cuts on a simplified copy, then are cut exactly
DOMINANT_SHARE = 0.5
STRONG_SHARE = 0.8
MIN_SCOPE_RADIUS_M = 40.0
DIFFUSE_FACTOR = 20.0  # an area hypothesis wider than 20 x the scope says nothing about where in it
SCOPE_KINDS = ("landmark", "area", "camera", "zone", "cell", "remainder", "custom")
COMPASS8 = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
COMPASS16 = ("north", "north-north-east", "north-east", "east-north-east", "east", "east-south-east", "south-east",
             "south-south-east", "south", "south-south-west", "south-west", "west-south-west", "west",
             "west-north-west", "north-west", "north-north-west")
COLOURS = ("#d7263d", "#1b998b", "#3f51b5", "#f49d37")

# evidence: (metres added to the object's own extent, why). See the module docstring.
SEARCH_RULES = {
    "ocr_sign": (50.0, "a shop, café, office or service sign read by OCR: 20-40 cm letters stay legible at the "
                       "panorama's 16.9 px per degree to about 25-50 m, from across the street; the OSM point sits on "
                       "the building"),
    "ocr_landmark": (120.0, "a large name read by OCR (church, museum, station, monument, named building): big "
                            "lettering is legible from across a square, about 100-150 m"),
    "vlm_landmark": (300.0, "a landmark the VLM recognised: a façade or tower filling a view is usually seen from "
                            "50-300 m; farther views are left to the Outside option"),
    "street": (25.0, "a street read on a name plate (legible to about 15-20 m): the camera is on the street or at "
                     "its edge, and the extent covers the street's length"),
    "area": (25.0, "an area (postcode, square, park, place): the camera is inside it or at its edge"),
    "camera": (40.0, "a verified reference photo: its GPS plus the viewpoint displacement of a matched scene"),
    "landmark": (100.0, "a landmark whose evidence type is unknown"),
}
SIGN_KEYS = {"shop", "amenity", "craft", "office", "healthcare", "leisure"}
SIGN_AMENITY_LANDMARKS = {"place_of_worship", "monastery", "townhall", "courthouse", "university", "college",
                          "library", "hospital", "theatre", "cinema", "arts_centre", "marketplace", "bus_station",
                          "ferry_terminal", "fountain"}


# -- geometry helpers --------------------------------------------------------------------------------

def _haversine(lat, lng, lats, lngs):
    """Metres from (lat, lng) to arrays of points (panoloc.scoring.haversine_m, vectorised)."""
    lat1, lng1 = math.radians(lat), math.radians(lng)
    lat2, lng2 = np.radians(np.asarray(lats, dtype=float)), np.radians(np.asarray(lngs, dtype=float))
    h = np.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def _haversine_matrix(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = (np.radians(np.asarray(a, dtype=float)) for a in (lat1, lng1, lat2, lng2))
    h = (np.sin((lat2[None, :] - lat1[:, None]) / 2) ** 2
         + np.cos(lat1)[:, None] * np.cos(lat2)[None, :] * np.sin((lng2[None, :] - lng1[:, None]) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def _theta(d, category, urban_probability):
    d = np.where(d < ZERO_DISTANCE_M, 0.0, d)
    if category is not None:
        return 2.0 / (1.0 + d / SCALE_M[category])
    return (urban_probability * 2.0 / (1.0 + d / SCALE_M["urban"])
            + (1 - urban_probability) * 2.0 / (1.0 + d / SCALE_M["non-urban"]))


def destination(lat, lng, bearings_deg, distance_m):
    """(lats, lngs) reached from (lat, lng) along each bearing after distance_m on the scorer's sphere."""
    lat1, lng1 = math.radians(lat), math.radians(lng)
    b = np.radians(np.asarray(bearings_deg, dtype=float))
    d = distance_m / EARTH_RADIUS_M
    lat2 = np.arcsin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * np.cos(b))
    lng2 = lng1 + np.arctan2(np.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * np.sin(lat2))
    return np.degrees(lat2), (np.degrees(lng2) + 540.0) % 360.0 - 180.0


def geodesic_disc(lat, lng, radius_m, n=DISC_VERTICES):
    """A WGS84 polygon (x = longitude) with n vertices at radius_m from (lat, lng)."""
    lats, lngs = destination(lat, lng, np.arange(n) * 360.0 / n, radius_m)
    return shapely.Polygon(np.column_stack([lngs, lats]))


def _polygonal(geom):
    """The polygonal part of an overlay result (lines and points where cells touch are dropped)."""
    if geom is None or shapely.is_empty(geom):
        return shapely.Polygon()
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [p for p in shapely.get_parts(geom) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else shapely.Polygon()


def _clean(geom):
    """A valid polygonal geometry: snapped to GRID_M when that is metric, repaired if needed."""
    geom = _polygonal(geom)
    if not shapely.is_valid(geom):
        geom = _polygonal(shapely.make_valid(geom))
    return geom


def _to_deg(frame, cell_m):
    """A metric cell in WGS84, valid."""
    return _clean(frame.to_deg(cell_m))


def geojson(geom, decimals=7):
    """A GeoJSON geometry dict ([lng, lat]) rounded to `decimals` (7: about 1 cm)."""
    def walk(value):
        if isinstance(value, (list, tuple)):
            if value and isinstance(value[0], (int, float)):
                return [round(float(v), decimals) for v in value]
            return [walk(v) for v in value]
        return value
    mapping = geom.__geo_interface__
    return {"type": mapping["type"], "coordinates": walk(mapping["coordinates"])}


def bound_m(point, geom, deviation_m=0.0):
    """Conservative maximum distance in metres from `point` (lat, lng) to anywhere in the WGS84 polygon
    `geom`: Haversine to its convex hull's vertices, plus deviation_m, 0.6% and 1 m, rounded up."""
    hull = shapely.get_coordinates(shapely.convex_hull(geom))
    farthest = float(_haversine(point[0], point[1], hull[:, 1], hull[:, 0]).max())
    value = (farthest + deviation_m) * (1 + Q.BOUND_RELATIVE_MARGIN) + Q.BOUND_ABSOLUTE_MARGIN_M
    return math.ceil(value * 10) / 10


def target_bound_m(category=None):
    """The terminal bound to refine to: 25 m urban or unknown, 1 km for a known non-urban category."""
    return TARGET_BOUND_M[category]


def _compass(bearing, names=COMPASS8):
    step = 360.0 / len(names)
    return names[int(((bearing % 360.0) + step / 2) // step) % len(names)]


def _bearing(dx, dy):
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _fmt_m(metres):
    return Q._fmt_m(metres)


def _fmt_area(m2):
    return f"{m2 / 1e6:,.2f} km²" if m2 >= 1e6 else f"{m2:,.0f} m²"


@dataclass(frozen=True)
class Frame:
    """A local metric frame: x east and y north in metres from (lat0, lng0) (module docstring)."""

    lat0: float
    lng0: float

    @property
    def kx(self):
        return M_PER_DEG * math.cos(math.radians(self.lat0))

    def to_m(self, geom):
        k, o = np.array([self.kx, M_PER_DEG]), np.array([self.lng0, self.lat0])
        return shapely.transform(geom, lambda c: (c - o) * k)

    def to_deg(self, geom):
        k, o = np.array([self.kx, M_PER_DEG]), np.array([self.lng0, self.lat0])
        return shapely.transform(geom, lambda c: c / k + o)

    def xy(self, lats, lngs):
        return ((np.asarray(lngs, dtype=float) - self.lng0) * self.kx,
                (np.asarray(lats, dtype=float) - self.lat0) * M_PER_DEG)

    def latlng(self, x, y):
        return (np.asarray(y, dtype=float) / M_PER_DEG + self.lat0,
                np.asarray(x, dtype=float) / self.kx + self.lng0)


def _lattice(geom_m, n, rotation=LATTICE_ROTATION):
    """About n points of a rotated hexagonal lattice inside a metric polygon, as (x, y) arrays."""
    area = float(shapely.area(geom_m))
    if area <= 0 or n <= 0:
        return np.zeros(0), np.zeros(0)
    xmin, ymin, xmax, ymax = shapely.bounds(geom_m)
    cx, cy, half = (xmin + xmax) / 2, (ymin + ymax) / 2, math.hypot(xmax - xmin, ymax - ymin) / 2
    x = y = np.zeros(0)
    for attempt in range(5):
        s = math.sqrt(2 * area / (math.sqrt(3) * n)) / (1.7 ** attempt)
        m = int(math.ceil(half / s * 1.2)) + 2
        if (2 * m + 1) ** 2 > 400_000:  # a sliver: too thin for a lattice
            break
        i, j = np.meshgrid(np.arange(-m, m + 1), np.arange(-m, m + 1))
        i, j = i.ravel() + 0.37, j.ravel() + 0.21  # an offset, so no point sits on the frame's axes
        a1 = (s * math.cos(rotation), s * math.sin(rotation))
        a2 = (s * math.cos(rotation + math.pi / 3), s * math.sin(rotation + math.pi / 3))
        px, py = cx + i * a1[0] + j * a2[0], cy + i * a1[1] + j * a2[1]
        keep = (px >= xmin) & (px <= xmax) & (py >= ymin) & (py <= ymax)
        px, py = px[keep], py[keep]
        inside = shapely.contains_xy(geom_m, px, py)
        x, y = px[inside], py[inside]
        if len(x) >= max(1, n // 2):
            break
    if len(x) > 1.5 * n:
        take = np.linspace(0, len(x) - 1, n).round().astype(int)
        x, y = x[take], y[take]
    if len(x) == 0:
        p = shapely.point_on_surface(geom_m)
        x, y = np.array([p.x]), np.array([p.y])
    return x, y


def _quantile(values, weights, fraction):
    """A cut with about `fraction` of the weight below it, midway between two neighbouring values."""
    order = np.argsort(values, kind="stable")
    v, w = np.asarray(values)[order], np.asarray(weights)[order]
    c = np.cumsum(w)
    total = c[-1] if len(c) else 0.0
    if total <= 0 or len(v) < 2:
        return None
    i = int(np.searchsorted(c, fraction * total))
    i = min(max(i, 1), len(v) - 1)
    return float((v[i - 1] + v[i]) / 2)


def _keep_off(t, values, keep):
    """Move a cut position t at least `keep` away from every value (real hypotheses), as little as possible."""
    values = np.asarray(values, dtype=float)
    if len(values) == 0 or np.all(np.abs(values - t) >= keep):
        return t
    options = sorted({t, *(values - keep), *(values + keep)}, key=lambda c: abs(c - t))
    return next((c for c in options if np.all(np.abs(values - c) >= keep - 1e-9)), t)


def _halfplane(phi_deg, t, reach):
    """The half-plane {p : p . u <= t}, u the unit vector at bearing phi (a big rectangle)."""
    phi = math.radians(phi_deg)
    ux, uy, vx, vy = math.sin(phi), math.cos(phi), math.cos(phi), -math.sin(phi)
    cx, cy = t * ux, t * uy
    return shapely.Polygon([(cx + vx * reach, cy + vy * reach), (cx - vx * reach, cy - vy * reach),
                            (cx - vx * reach - ux * reach, cy - vy * reach - uy * reach),
                            (cx + vx * reach - ux * reach, cy + vy * reach - uy * reach)])


def _wedge(ax, ay, start, end, reach):
    """The sector of bearings [start, end] (clockwise, end > start) from (ax, ay), out to `reach`."""
    steps = max(2, int(math.ceil((end - start) / 10.0)) + 1)
    bearings = np.radians(np.linspace(start, end, steps))
    ring = [(ax, ay)] + [(ax + reach * math.sin(b), ay + reach * math.cos(b)) for b in bearings]
    return shapely.Polygon(ring)


def _metric_disc(ax, ay, r, n=DISC_VERTICES):
    a = np.arange(n) * 2 * math.pi / n
    return shapely.Polygon(np.column_stack([ax + r * np.sin(a), ay + r * np.cos(a)]))


def _reach(geom_m):
    xmin, ymin, xmax, ymax = shapely.bounds(geom_m)
    return 4.0 * (max(abs(xmin), abs(xmax), abs(ymin), abs(ymax)) + math.hypot(xmax - xmin, ymax - ymin)) + 100.0


def _extent_along(geom_m, phi_deg):
    hull = shapely.get_coordinates(shapely.convex_hull(geom_m))
    phi = math.radians(phi_deg)
    proj = hull[:, 0] * math.sin(phi) + hull[:, 1] * math.cos(phi)
    return float(proj.max() - proj.min())


def _minimax(geom_m, margin):
    """(x, y, radius): the point inside geom_m (at least `margin` from its edge) closest to minimising the
    maximum distance to it, and that distance (to its convex hull's vertices)."""
    hull = shapely.get_coordinates(shapely.convex_hull(geom_m))

    def radius(x, y):
        return np.sqrt((hull[:, 0][None, :] - np.atleast_1d(x)[:, None]) ** 2
                       + (hull[:, 1][None, :] - np.atleast_1d(y)[:, None]) ** 2).max(axis=1)

    centre = shapely.centroid(shapely.minimum_bounding_circle(geom_m))
    cx, cy = centre.x, centre.y
    edge = shapely.boundary(geom_m)
    if shapely.contains_xy(geom_m, cx, cy) and shapely.distance(edge, centre) >= margin:
        return cx, cy, float(radius(cx, cy)[0])
    inset = _polygonal(shapely.buffer(geom_m, -margin))
    if shapely.is_empty(inset):
        inset = _polygonal(shapely.buffer(geom_m, -margin / 10))
    if shapely.is_empty(inset):
        p = shapely.point_on_surface(geom_m)
        return p.x, p.y, float(radius(p.x, p.y)[0])
    near = shapely.get_coordinates(shapely.shortest_line(inset, centre))[0]
    lx, ly = _lattice(inset, 150)
    xs, ys = np.concatenate([[near[0]], lx]), np.concatenate([[near[1]], ly])
    ok = shapely.contains_xy(geom_m, xs, ys)
    xs, ys = xs[ok], ys[ok]
    if len(xs) == 0:
        p = shapely.point_on_surface(geom_m)
        return p.x, p.y, float(radius(p.x, p.y)[0])
    r = radius(xs, ys)
    k = int(np.argmin(r))
    return float(xs[k]), float(ys[k]), float(r[k])


# -- search extents ----------------------------------------------------------------------------------

def evidence_kind(candidate):
    """What kind of evidence put this candidate on the list (SEARCH_RULES key), from its role, its OSM
    type and the fusion clues that proposed it (ocr:..., vlm:...)."""
    d = candidate.details or {}
    if candidate.role == "camera":
        return "camera"
    clues = [str(c) for c in (d.get("fusion") or {}).get("clues") or []]
    from_ocr = any(c.startswith("ocr:") for c in clues)
    from_vlm = any(c.startswith("vlm:") for c in clues)
    osm_type = str(d.get("osm_type") or "")
    key, _, value = osm_type.partition("=")
    if candidate.role == "area":
        if key == "highway" or str(d.get("role_rule") or "").endswith("street"):
            return "street"
        return "area"
    if from_vlm and not from_ocr:
        return "vlm_landmark"
    if key in SIGN_KEYS and not (key == "amenity" and value in SIGN_AMENITY_LANDMARKS):
        return "ocr_sign"
    if from_ocr or osm_type or str(candidate.source).startswith(("wikidata:", "osm:")):
        return "ocr_landmark"
    return "landmark"


def search_radius(candidate, evidence=None):
    """(radius_m, details): the search disc around a candidate for the camera (module docstring)."""
    kind = evidence or evidence_kind(candidate)
    if kind not in SEARCH_RULES:
        raise ValueError(f"evidence must be one of {tuple(SEARCH_RULES)}, got {kind!r}")
    view, why = SEARCH_RULES[kind]
    d = candidate.details or {}
    if kind == "camera":
        own = candidate.accuracy_m or 10.0
    else:
        own = (candidate.extent_m or 0.0) + (candidate.accuracy_m or 0.0)
    radius = max(MIN_SCOPE_RADIUS_M, own + view)
    return radius, {"search_radius_m": round(radius, 1), "evidence": kind, "own_extent_m": round(own, 1),
                    "extent_source": d.get("extent_source") or ("source" if candidate.extent_m else "none"),
                    "view_distance_m": view, "rule": why,
                    "assumption": "an externally chosen search extent around the candidate's coordinate; the "
                                  "coordinate marks the " + candidate.role + ", not where the camera stood"}


# -- scopes ------------------------------------------------------------------------------------------

@dataclass(eq=False)
class Scope:
    """An area to split (module docstring). geom is the WGS84 polygon (x = longitude); geom_m the same in
    the chain's metric frame. parent is the scope it was cut from (None for a root)."""

    geom: object
    scope_id: str
    kind: str = "custom"
    label: str = ""
    frame: Frame | None = None
    sources: tuple = ()
    parent: "Scope | None" = None
    anchor: tuple | None = None  # (lat, lng) of the named point the cuts may refer to
    anchor_label: str | None = None
    deviation_m: float = 0.0  # the root zone's boundary deviation: added for cells reaching that boundary
    zone_id: str | None = None
    whole: bool = False  # the whole allowed area: 4 cells and no Outside option
    picked: bool = False  # the team picked this area (a cell, a remainder, a zone): it may be output
    details: dict = field(default_factory=dict)
    root_boundary_m: object = field(default=None, repr=False)
    geom_m: object = field(default=None, repr=False)
    constraints: tuple = field(default=(), repr=False)  # answered (question, option ID) pairs points must fit
    land: object = field(default=None, repr=False)  # a panoloc.zones Zones: points must be on land (LAND_TOLERANCE_M)

    def __post_init__(self):
        geom = _polygonal(self.geom)
        if not shapely.is_valid(geom):
            geom = _polygonal(shapely.make_valid(geom))
        if shapely.is_empty(geom) or not shapely.area(geom) > 0:
            raise ValueError(f"scope {self.scope_id} has no area")
        if self.kind not in SCOPE_KINDS:
            raise ValueError(f"kind must be one of {SCOPE_KINDS}, got {self.kind!r}")
        self.geom = geom
        if self.frame is None:
            west, south, east, north = shapely.bounds(geom)
            self.frame = Frame((south + north) / 2, (west + east) / 2)
        if self.geom_m is None:
            self.geom_m = _clean(self.frame.to_m(geom))
        self.sources = tuple(self.sources)
        self.constraints = tuple(self.constraints or ())
        if self.root_boundary_m is None and self.deviation_m > 0 and self.parent is None:
            self.root_boundary_m = shapely.boundary(self.geom_m)
        for g in (self.geom, self.geom_m, self.root_boundary_m):
            if g is not None:
                shapely.prepare(g)
        self._rep = None

    # -- constructors --------------------------------------------------------------------------------

    @classmethod
    def disc(cls, lat, lng, radius_m, *, scope_id=None, label=None, kind="area", sources=(), anchor_label=None,
             details=None, picked=False, parent=None):
        """A geodesic disc of radius_m around (lat, lng); the point becomes the anchor of the cuts. With a
        parent (an area the team picked), the disc is clipped to it and "Outside" recovers into it."""
        if not radius_m > 0:
            raise ValueError(f"radius_m must be > 0, got {radius_m}")
        lat, lng = float(lat), float(lng)
        scope_id = scope_id or f"disc:{Q._url_number(lat)},{Q._url_number(lng)}@{radius_m:.0f}m"
        name = anchor_label or f"{lat:.5f}, {lng:.5f}"
        geom, frame, geom_m = geodesic_disc(lat, lng, radius_m), Frame(lat, lng), None
        if parent is not None:
            frame = parent.frame
            geom_m = _clean(shapely.intersection(frame.to_m(geom), parent.geom_m))
            geom = _to_deg(frame, geom_m)
        return cls(geom, scope_id, kind=kind, label=label or f"within {_fmt_m(radius_m)} of {name}", frame=frame,
                   sources=sources, parent=parent, anchor=(lat, lng), anchor_label=name, picked=picked,
                   details={"radius_m": round(float(radius_m), 1), **(details or {})},
                   root_boundary_m=parent.root_boundary_m if parent is not None else None,
                   deviation_m=parent.deviation_m if parent is not None else 0.0, geom_m=geom_m,
                   constraints=parent.constraints if parent is not None else (),
                   land=parent.land if parent is not None else None)

    @classmethod
    def around(cls, candidate, *, evidence=None, radius_m=None, max_radius_m=None, picked=False, parent=None):
        """The search disc around a typed candidate: its radius from search_radius() unless given."""
        rule_radius, info = search_radius(candidate, evidence)
        radius = float(radius_m or rule_radius)
        if max_radius_m is not None and radius > max_radius_m:
            radius = float(max_radius_m)
            info["clamped_to_m"] = radius
        name = candidate.label or candidate.source
        kind = candidate.role if candidate.role in ("landmark", "area", "camera") else "custom"
        return cls.disc(candidate.lat, candidate.lng, radius, scope_id=f"{candidate.source}@{radius:.0f}m",
                        label=f"within {_fmt_m(radius)} of {name}", kind=kind, sources=(candidate.source,),
                        anchor_label=name, picked=picked, parent=parent,
                        details={**info, "candidate": {"source": candidate.source, "role": candidate.role,
                                                       "label": candidate.label, "lat": candidate.lat,
                                                       "lng": candidate.lng, "extent_m": candidate.extent_m}})

    @classmethod
    def from_zone(cls, zones, zone, *, picked=True):
        """A panoloc.zones zone (usually a leaf the team picked): its exact geometry and deviation_m."""
        z = zones.get(zone)
        geom = zones.exact_geometry(z)
        lat0, lng0 = z.rep
        return cls(geom, f"zone:{z.id}", kind="zone", label=z.label, frame=Frame(lat0, lng0),
                   sources=(f"zone:{z.id}",), deviation_m=float(z.deviation_m), zone_id=z.id, picked=picked,
                   details={"zone_level": z.level, "area_km2": round(z.area_km2, 4), "is_leaf": z.is_leaf,
                            "deviation_m": round(float(z.deviation_m), 1),
                            "zones_version": getattr(zones, "version", None)})

    def child(self, option):
        """The scope of a picked cell option of a question asked on this scope."""
        return Scope(option.geometry, option.cell_id, kind="cell", label=option.label, frame=self.frame,
                     sources=(*self.sources, f"cell:{option.cell_id}"), parent=self, anchor=self.anchor,
                     anchor_label=self.anchor_label, deviation_m=self.deviation_m, zone_id=self.zone_id,
                     picked=True, details={"option_id": option.id, "cut_from": self.scope_id},
                     root_boundary_m=self.root_boundary_m, geom_m=option.geometry_m,
                     constraints=self.constraints, land=self.land)

    def remainder(self):
        """The parent minus this scope, whose parent is the grandparent; None for a root or when empty."""
        parent = self.parent
        if parent is None:
            return None
        rest_m = _polygonal(shapely.difference(parent.geom_m, self.geom_m))
        if shapely.is_empty(rest_m) or shapely.area(rest_m) <= 1e-9 * max(shapely.area(parent.geom_m), 1.0):
            return None
        rest = _polygonal(shapely.difference(parent.geom, self.geom))
        tail = self.scope_id.rsplit("/", 1)[-1]
        return Scope(rest, f"{parent.scope_id}-{tail}", kind="remainder",
                     label=f"{parent.label}, outside {self.label}", frame=self.frame,
                     sources=(*parent.sources, f"cell:{parent.scope_id}-{tail}"), parent=parent.parent,
                     anchor=self.anchor, anchor_label=self.anchor_label, deviation_m=self.deviation_m,
                     zone_id=self.zone_id, picked=True,
                     details={"excluded": self.scope_id, "from": parent.scope_id},
                     root_boundary_m=self.root_boundary_m, geom_m=rest_m,
                     constraints=self.constraints, land=self.land)

    # -- properties ----------------------------------------------------------------------------------

    @property
    def depth(self):
        return 0 if self.parent is None else self.parent.depth + 1

    @property
    def root(self):
        return self if self.parent is None else self.parent.root

    @property
    def area_m2(self):
        return float(shapely.area(self.geom_m))

    def contains(self, point):
        """True when (lat, lng) lies in the scope, edges included."""
        return bool(shapely.intersects_xy(self.geom, float(point[1]), float(point[0])))

    def contains_many(self, lats, lngs):
        return shapely.intersects_xy(self.geom, np.asarray(lngs, dtype=float), np.asarray(lats, dtype=float))

    def deviation_for(self, geom_m):
        """The boundary deviation a part of this scope carries: the root zone's, when it reaches its boundary."""
        if self.root_boundary_m is None or not self.deviation_m:
            return 0.0
        return self.deviation_m if shapely.distance(geom_m, self.root_boundary_m) <= 0.01 else 0.0

    @property
    def checked(self):
        """True when points must pass allows(): answers to fit, or land to stay on."""
        return bool(self.constraints) or self.land is not None

    def allows(self, point):
        """True when (lat, lng) fits every earlier answer, as that question's own option_for() decides
        (feature questions carry no geometry and are not checked), and, with a zone index, lies on land:
        in a leaf zone or within LAND_TOLERANCE_M of one (a pier, a beach), not the 1 km snap."""
        point = (float(point[0]), float(point[1]))
        if self.land is not None and not self.land.on_land(point, LAND_TOLERANCE_M):
            return False
        for question, option_id in self.constraints:
            if question.kind == "feature":
                continue
            if question.option_for(point).id != option_id:
                return False
        return True

    @property
    def rep(self):
        """(lat, lng, bound_m): the scope's own minimax point (an allowed one when checked) and the bound."""
        if self._rep is None:
            point, _ = _representative(self, self.geom_m, self.geom, None, None)
            if point is None:  # no allowed point (logs only: outputs never use it)
                p = shapely.point_on_surface(self.geom)
                point = (p.y, p.x)
            self._rep = (*point, bound_m(point, self.geom, self.deviation_for(self.geom_m)))
        return self._rep

    def to_dict(self, outline=True):
        """JSON-ready summary for logs: identity, chain, size, bound, assumptions and outline."""
        lat, lng, bound = self.rep
        chain, s = [], self.parent
        while s is not None:
            chain.append(s.scope_id)
            s = s.parent
        d = {"scope_id": self.scope_id, "kind": self.kind, "label": self.label, "sources": list(self.sources),
             "parents": chain, "depth": self.depth, "area_m2": round(self.area_m2, 1),
             "rep": coordinate((lat, lng)), "bound_m": bound, "deviation_m": round(self.deviation_m, 1),
             "zone_id": self.zone_id, "picked": self.picked, "whole": self.whole, "details": self.details}
        if self.anchor is not None:
            d["anchor"] = {**coordinate(self.anchor), "label": self.anchor_label}
        if outline:
            d["outline"], tolerance = _log_geojson(self.geom, self.frame)
            if tolerance:
                d["outline_simplified_m"] = tolerance
        return d


# -- earlier answers -------------------------------------------------------------------------------------

def _zones_of(constraints, zones=None):
    """The zone index for the land rule: the one given, else the first a RegionQuestion answer carries."""
    if zones is not None:
        return zones
    return next((q.zones for q, _ in constraints if getattr(q, "zones", None) is not None), None)


def _option_region_m(question, option, frame, window_m, land_m=None):
    """The area a non-complement option stands for, in `frame` metres within the window, or None when
    it has no geometry (then only the membership test of Scope.allows applies)."""
    west, south, east, north = (float(v) for v in shapely.bounds(frame.to_deg(window_m)))
    geometry = getattr(option, "geometry", None)
    if geometry is not None and getattr(option, "cell_id", None) is not None:  # a cell
        return _clean(shapely.intersection(frame.to_m(geometry), window_m))
    zone_id, zones = getattr(option, "zone_id", None), getattr(question, "zones", None)
    if zone_id is not None and zones is not None:  # a named zone, with its own coast (LAND_TOLERANCE_M)
        zone_m = _clean(frame.to_m(_clean(shapely.clip_by_rect(zones.exact_geometry(zone_id), west, south, east,
                                                               north))))
        deviation = float(getattr(zones.get(zone_id), "deviation_m", 0.0) or 0.0)
        band = (_polygonal(shapely.buffer(zone_m, LAND_TOLERANCE_M + deviation)) if not shapely.is_empty(zone_m)
                else zone_m)
        if land_m is not None and not shapely.is_empty(band):  # the band never reaches another zone's land
            band = _polygonal(shapely.difference(band, shapely.difference(land_m, zone_m)))
        return _clean(shapely.intersection(band, window_m))
    if getattr(option, "radius_m", None) and option.point is not None:  # a place: its disc
        disc = frame.to_m(geodesic_disc(option.point["lat"], option.point["lng"], option.radius_m))
        return _clean(shapely.intersection(disc, window_m))
    box = getattr(option, "bbox", None)
    if box is not None:  # a latitude/longitude box cell
        return _clean(shapely.intersection(frame.to_m(shapely.box(box.west, box.south, box.east, box.north)),
                                           window_m))
    return None


def _allowed_m(root, constraints, land):
    """What the answers (and the land rule) allow around the root, in its frame's metres."""
    xmin, ymin, xmax, ymax = (float(v) for v in shapely.bounds(root.geom_m))
    pad = LAND_TOLERANCE_M + 1.0
    window = shapely.box(xmin - pad, ymin - pad, xmax + pad, ymax + pad)
    allowed, land_m = window, None
    if land is not None and root.kind != "zone":  # a zone is land already; a disc may reach the sea
        parts = land.land_parts(root.frame.to_deg(window))
        metric = [(_clean(root.frame.to_m(part)), deviation) for part, deviation in parts]
        land_m = _clean(shapely.union_all([m for m, _ in metric])) if metric else shapely.Polygon()
        # each leaf with LAND_TOLERANCE_M plus its own simplification error: the true coast lies within it
        band = shapely.union_all([shapely.buffer(m, LAND_TOLERANCE_M + d) for m, d in metric]) if metric \
            else shapely.Polygon()
        allowed = _polygonal(shapely.intersection(allowed, band))
    for question, option_id in constraints:
        if question.kind == "feature" or shapely.is_empty(allowed):
            continue
        option = question.option(option_id)
        if option.complement:  # "None of these" / "Outside" / "Elsewhere": not in any sibling
            regions = [_option_region_m(question, o, root.frame, window, land_m)
                       for o in question.options if not o.complement]
            if regions and all(r is not None for r in regions):
                allowed = _polygonal(shapely.difference(allowed, shapely.union_all(regions)))
        else:
            region = _option_region_m(question, option, root.frame, window, land_m)
            if region is not None:
                allowed = _polygonal(shapely.intersection(allowed, region))
    return _clean(allowed)


def _same_constraints(a, b):
    return len(a) == len(b) and all(qa is qb and oa == ob for (qa, oa), (qb, ob) in zip(a, b))


def constrain(scope, constraints=None, zones=None):
    """The scope (and its chain) cut down to what the earlier answers allow, or None when nothing is left.

    constraints: [(question, option_id), ...], every answered place or zone question, in answer order.
    Each option's area is built where it has one (a place disc, a named zone and its coast, a cell, a
    box; a complement is its question's scope minus the other options) and the scope keeps only their
    intersection; with a zone index (zones, or one an answered RegionQuestion carries), a scope that is
    not a zone also keeps only land and LAND_TOLERANCE_M around it. Every point the route offers or
    outputs must also pass Scope.allows (each question's own option_for), so an answer with no buildable
    area still holds. Without constraints (None or []), the scope itself, zones or not: the behaviour
    before this fix. zones only supplies the land index when no answered RegionQuestion carries one.
    """
    constraints = tuple(constraints or ())
    if not constraints:  # no answers yet: exactly the scope as before
        return scope
    land = _zones_of(constraints, zones)
    if _same_constraints(scope.constraints, constraints) and scope.land is land:
        return scope  # already cut to these answers
    chain, s = [], scope
    while s is not None:
        chain.append(s)
        s = s.parent
    chain.reverse()
    allowed = _allowed_m(chain[0], constraints, land)
    summary = [{"question_id": getattr(q, "question_id", None), "kind": q.kind, "option_id": o,
                "label": q.option(o).label} for q, o in constraints]
    parent = None
    for s in chain:
        keep = allowed if parent is None else parent.geom_m
        geom_m = _clean(shapely.set_precision(_polygonal(shapely.intersection(s.geom_m, keep)), GRID_M))
        if shapely.is_empty(geom_m) or shapely.area(geom_m) < MIN_ALLOWED_M2:
            return None
        share = float(shapely.area(geom_m)) / max(float(shapely.area(s.geom_m)), 1e-9)
        parent = Scope(_to_deg(s.frame, geom_m), s.scope_id, kind=s.kind, label=s.label, frame=s.frame,
                       sources=s.sources, parent=parent, anchor=s.anchor, anchor_label=s.anchor_label,
                       deviation_m=s.deviation_m, zone_id=s.zone_id, whole=s.whole, picked=s.picked,
                       details={**s.details, "constrained_by": summary, "allowed_share": round(share, 4),
                                "land_rule_m": LAND_TOLERANCE_M if land is not None else None},
                       root_boundary_m=s.root_boundary_m, geom_m=geom_m, constraints=constraints, land=land)
    return parent


# -- partition -----------------------------------------------------------------------------------------

def _mass_points(scope, design_m, px, py, pw):
    """(x, y, w, mode): what the cuts balance. With the hypotheses spread (3 or more distinct points, none
    holding half the weight), an even mix of their weight and the area (AREA_SHARE); otherwise the area.

    Pure weight balancing goes wrong when the camera is away from the hypotheses: a small heavy
    landmark disc inside a province drew every cut, and the camera's cell kept 857 km2 for a dozen
    answers. With half the balance on area, a cell holding no weight has at most 2/3 of the area.
    """
    lx, ly = _lattice(design_m, AREA_POINTS)
    la = np.full(len(lx), 1.0 / max(len(lx), 1))
    ok = pw > 0
    px, py, pw = px[ok], py[ok], pw[ok]
    distinct = len({(round(float(x), 2), round(float(y), 2)) for x, y in zip(px, py)})
    if len(pw) and distinct >= 3 and pw.max() <= 0.5 * pw.sum():
        return (np.concatenate([px, lx]), np.concatenate([py, ly]),
                np.concatenate([(1 - AREA_SHARE) * pw / pw.sum(), AREA_SHARE * la]), "weight")
    return lx, ly, la, "area"


def _assign(cells, mx, my):
    """Index of the first cell holding each point (-1 for none)."""
    owner = np.full(len(mx), -1)
    for i, c in enumerate(cells):
        free = owner < 0
        if not free.any():
            break
        hit = shapely.contains_xy(c, mx[free], my[free])
        idx = np.flatnonzero(free)[hit]
        owner[idx] = i
    return owner


def _fit_sectors(anchor, mx, my, mw):
    bearings = np.degrees(np.arctan2(mx - anchor[0], my - anchor[1])) % 360.0
    best = None
    for beta in np.arange(0.0, 120.0, SECTOR_STEP):
        rel = (bearings - beta) % 360.0
        m = np.array([mw[(rel >= 120 * k) & (rel < 120 * (k + 1))].sum() for k in range(3)])
        imbalance = float(np.abs(m - mw.sum() / 3).max())
        nice = min(abs(beta - 60.0), 120 - abs(beta - 60.0)) / 60.0  # boundaries at 60/180/300: N, SE, SW
        score = imbalance + 0.03 * nice  # a 3% imbalance is worth bearings that read as N, SE and SW
        if best is None or score < best[0]:
            best = (score, float(beta))
    return {"beta": best[1]}


def _build_sectors(geom, anchor, params):
    beta, reach = params["beta"], _reach(geom) + math.hypot(*anchor)
    starts = [(beta + 120.0 * k) % 360.0 for k in range(3)]
    north = next(s for s in starts if (-s) % 360.0 < 120.0)  # the sector holding bearing 0 comes first
    starts = sorted(starts, key=lambda s: (s - north) % 360.0)
    cells, rest = [], geom
    for k, s in enumerate(starts):
        if k == len(starts) - 1:
            cells.append(_polygonal(rest))
            break
        wedge = _wedge(anchor[0], anchor[1], s, s + 120.0, reach)
        cell = _polygonal(shapely.intersection(rest, wedge))
        cells.append(cell)
        rest = _polygonal(shapely.difference(rest, cell))
    return cells, [{"bearings": (s, (s + 120.0) % 360.0)} for s in starts]


def _fit_rings(anchor, mx, my, mw, real, keep):
    d = np.hypot(mx - anchor[0], my - anchor[1])
    r1 = _quantile(d, mw, 1 / 3)
    if r1 is None or not r1 > 0:
        return None
    if len(real[0]):
        r1 = _keep_off(r1, np.hypot(real[0] - anchor[0], real[1] - anchor[1]), keep)
    outer = d > r1
    if not outer.any():
        return None
    ox, oy, ow = mx[outer] - anchor[0], my[outer] - anchor[1], mw[outer]
    centre = _bearing(float((ox * ow).sum()), float((oy * ow).sum()))
    best = None
    for b in np.arange(0.0, 180.0, 3.0):
        side = np.sin(math.radians(b)) * oy - np.cos(math.radians(b)) * ox > 0
        imbalance = abs(ow[side].sum() - ow[~side].sum())
        nice = min(abs((b - centre) % 180.0), 180.0 - abs((b - centre) % 180.0)) / 90.0
        score = imbalance + 0.002 * nice
        if best is None or score < best[0]:
            best = (score, float(b))
    return {"r1": float(r1), "line": best[1]}


def _build_rings(geom, anchor, params):
    inner = _polygonal(shapely.intersection(geom, _metric_disc(anchor[0], anchor[1], params["r1"])))
    outer = _polygonal(shapely.difference(geom, inner))
    b = math.radians(params["line"])
    reach = _reach(geom) + math.hypot(*anchor)
    # the side to the left of the line through the anchor at bearing b (normal pointing left)
    nx, ny = -math.cos(b), math.sin(b)
    left = shapely.Polygon([(anchor[0] + math.sin(b) * reach, anchor[1] + math.cos(b) * reach),
                            (anchor[0] - math.sin(b) * reach, anchor[1] - math.cos(b) * reach),
                            (anchor[0] - math.sin(b) * reach + nx * reach, anchor[1] - math.cos(b) * reach + ny * reach),
                            (anchor[0] + math.sin(b) * reach + nx * reach, anchor[1] + math.cos(b) * reach + ny * reach)])
    one = _polygonal(shapely.intersection(outer, left))
    two = _polygonal(shapely.difference(outer, one))
    return [inner, one, two], [{"ring": "inner"}, {"ring": "outer"}, {"ring": "outer"}]


def _fit_cut(mx, my, mw, phi, fraction, real, keep):
    proj = mx * math.sin(math.radians(phi)) + my * math.cos(math.radians(phi))
    t = _quantile(proj, mw, fraction)
    if t is None:
        return None
    if len(real[0]):
        t = _keep_off(t, real[0] * math.sin(math.radians(phi)) + real[1] * math.cos(math.radians(phi)), keep)
    return t


def _fit_one_two(design, mx, my, mw, phi, low, real, keep):
    t1 = _fit_cut(mx, my, mw, phi, 1 / 3 if low else 2 / 3, real, keep)
    if t1 is None:
        return None
    lower = _polygonal(shapely.intersection(design, _halfplane(phi, t1, _reach(design))))
    double = _polygonal(shapely.difference(design, lower)) if low else lower
    if shapely.is_empty(double):
        return None
    proj = mx * math.sin(math.radians(phi)) + my * math.cos(math.radians(phi))
    side = proj > t1 if low else proj <= t1
    phi2 = max(DIRECTIONS, key=lambda d: (_extent_along(double, d), -DIRECTIONS.index(d)))
    t2 = _fit_cut(mx[side], my[side], mw[side], phi2, 1 / 2, real, keep) if side.sum() >= 2 else None
    if t2 is None:
        return None
    return {"phi": phi, "t1": t1, "low": low, "phi2": phi2, "t2": t2}


def _build_one_two(geom, params):
    reach = _reach(geom)
    lower = _polygonal(shapely.intersection(geom, _halfplane(params["phi"], params["t1"], reach)))
    upper = _polygonal(shapely.difference(geom, lower))
    single, double = (lower, upper) if params["low"] else (upper, lower)
    a = _polygonal(shapely.intersection(double, _halfplane(params["phi2"], params["t2"], reach)))
    b = _polygonal(shapely.difference(double, a))
    return [single, a, b], [{"side1": "low" if params["low"] else "high"},
                            {"side1": "high" if params["low"] else "low", "side2": "low"},
                            {"side1": "high" if params["low"] else "low", "side2": "high"}]


def _fit_strips(mx, my, mw, phi, real, keep):
    t1 = _fit_cut(mx, my, mw, phi, 1 / 3, real, keep)
    t2 = _fit_cut(mx, my, mw, phi, 2 / 3, real, keep)
    if t1 is None or t2 is None or not t2 > t1:
        return None
    return {"phi": phi, "t1": t1, "t2": t2}


def _build_strips(geom, params):
    reach = _reach(geom)
    low = _polygonal(shapely.intersection(geom, _halfplane(params["phi"], params["t1"], reach)))
    rest = _polygonal(shapely.difference(geom, low))
    mid = _polygonal(shapely.intersection(rest, _halfplane(params["phi"], params["t2"], reach)))
    high = _polygonal(shapely.difference(rest, mid))
    return [low, mid, high], [{"strip": "low"}, {"strip": "middle"}, {"strip": "high"}]


def _fit_two_two(design, mx, my, mw, phi, real, keep):
    t = _fit_cut(mx, my, mw, phi, 1 / 2, real, keep)
    if t is None:
        return None
    proj = mx * math.sin(math.radians(phi)) + my * math.cos(math.radians(phi))
    lower = _polygonal(shapely.intersection(design, _halfplane(phi, t, _reach(design))))
    upper = _polygonal(shapely.difference(design, lower))
    halves = []
    for part, side in ((lower, proj <= t), (upper, proj > t)):
        if shapely.is_empty(part) or side.sum() < 2:
            return None
        phi2 = max(DIRECTIONS, key=lambda d: (_extent_along(part, d), -DIRECTIONS.index(d)))
        t2 = _fit_cut(mx[side], my[side], mw[side], phi2, 1 / 2, real, keep)
        if t2 is None:
            return None
        halves.append((phi2, t2))
    return {"phi": phi, "t": t, "halves": halves}


def _build_two_two(geom, params):
    reach = _reach(geom)
    lower = _polygonal(shapely.intersection(geom, _halfplane(params["phi"], params["t"], reach)))
    upper = _polygonal(shapely.difference(geom, lower))
    cells = []
    for part, (phi2, t2) in zip((lower, upper), params["halves"]):
        a = _polygonal(shapely.intersection(part, _halfplane(phi2, t2, reach)))
        cells += [a, _polygonal(shapely.difference(part, a))]
    return cells, [{} for _ in cells]


def _score(cells, mx, my, mw, scope_area):
    """The expected size left after the answer: the cells' minimax radii (the bound each would get)
    weighted by the balanced mass they hold, in metres (lower is better); None for a degenerate cut."""
    if any(shapely.is_empty(c) or shapely.area(c) <= 1e-6 * scope_area for c in cells):
        return None
    owner = _assign(cells, mx, my)
    mass = np.array([mw[owner == i].sum() for i in range(len(cells))])
    if mass.sum() <= 0:
        mass = np.array([shapely.area(c) for c in cells])
    radii = np.array([_radius_estimate(c) for c in cells])
    return float((mass * radii).sum() / mass.sum())


def _radius_estimate(geom_m):
    """A quick upper estimate of a cell's minimax radius, for comparing cuts: the farthest hull vertex from
    its smallest enclosing circle's centre, or from the nearest point of the cell when that centre is
    outside it (the representative point itself comes from _minimax)."""
    hull = shapely.get_coordinates(shapely.convex_hull(geom_m))
    centre = shapely.centroid(shapely.minimum_bounding_circle(geom_m))
    if shapely.contains_xy(geom_m, centre.x, centre.y):
        x, y = centre.x, centre.y
    else:
        x, y = shapely.get_coordinates(shapely.shortest_line(geom_m, centre))[0]
    return float(np.hypot(hull[:, 0] - x, hull[:, 1] - y).max())


def _partition(scope, px, py, pw, real, n):
    """The chosen family, its cells (metric, exact), per-cell metadata and the fit, for a scope."""
    geom = scope.geom_m
    design = _design(geom)
    mx, my, mw, mode = _mass_points(scope, design, px, py, pw)
    for attempt in ("as given", "area only"):
        if attempt == "area only":  # no family worked on the weight: balance the area alone
            mx, my, mw, mode = _mass_points(scope, design, px[:0], py[:0], pw[:0])
        found = _fit_families(scope, design, geom, mx, my, mw, real, n)
        if found is not None:
            break
    else:
        raise ValueError(f"scope {scope.scope_id} cannot be split into {n} cells")
    family, params, cells, meta, anchor, scored = found
    if design is not geom:
        cells, meta = _build(family, geom, anchor, params)
    cells = [_clean(shapely.set_precision(_polygonal(c), GRID_M)) for c in cells]
    return {"family": family, "params": params, "cells": cells, "meta": meta, "mode": mode, "anchor_m": anchor,
            "families_scored": scored}


def _fit_families(scope, design, geom, mx, my, mw, real, n):
    """The best family for these mass points: (family, params, cells, meta, anchor, n scored), or None."""
    size = math.sqrt(shapely.area(geom))
    keep = min(KEEP_OFF_M, 0.02 * size)
    scope_area = float(shapely.area(design))
    fits = []
    anchor = None
    if scope.anchor is not None:
        ax, ay = scope.frame.xy(scope.anchor[0], scope.anchor[1])
        anchor = (float(ax), float(ay))
    if n == 4:
        for phi in DIRECTIONS:
            p = _fit_two_two(design, mx, my, mw, phi, real, keep)
            if p:
                fits.append(("two_two", p))
    else:
        if anchor is not None:
            here = shapely.Point(anchor)
            inside = shapely.contains_xy(design, *anchor)
            depth = shapely.distance(shapely.boundary(design), here)
            if inside and depth >= max(1.0, 0.05 * size):
                fits.append(("sectors", _fit_sectors(anchor, mx, my, mw)))
            if depth < max(1.0, 0.05 * size) and (inside or shapely.distance(design, here) <= max(1.0, 0.01 * size)):
                p = _fit_rings(anchor, mx, my, mw, real, keep)
                if p:
                    fits.append(("rings", p))
        for phi in DIRECTIONS:
            for low in (True, False):
                p = _fit_one_two(design, mx, my, mw, phi, low, real, keep)
                if p:
                    fits.append(("parallel", p))
            p = _fit_strips(mx, my, mw, phi, real, keep)
            if p:
                fits.append(("strips", p))
    scored = []
    for order, (family, params) in enumerate(fits):
        cells, meta = _build(family, design, anchor, params)
        s = _score(cells, mx, my, mw, scope_area)
        if s is not None:
            scored.append((s, order, family, params, cells, meta))
    if not scored:
        return None
    best = min(scored, key=lambda x: (x[0], x[1]))
    anchored = [x for x in scored if x[2] in ("sectors", "rings")]
    if anchored:
        top = min(anchored, key=lambda x: (x[0], x[1]))
        if top[0] <= best[0] * (1 + FAMILY_SLACK):
            best = top
    _, _, family, params, cells, meta = best
    return family, params, cells, meta, anchor, len(scored)


def _build(family, geom, anchor, params):
    if family == "sectors":
        return _build_sectors(geom, anchor, params)
    if family == "rings":
        return _build_rings(geom, anchor, params)
    if family == "parallel":
        return _build_one_two(geom, params)
    if family == "strips":
        return _build_strips(geom, params)
    return _build_two_two(geom, params)


# -- representative points ---------------------------------------------------------------------------

def _representative(scope, cell_m, cell_deg, hyps, samples, category=None, urban_probability=0.5):
    """((lat, lng), method): the cell's representative point (module docstring), strictly inside it.

    hyps / samples: (x, y, lat, lng, w) arrays of the real hypotheses and the weight samples in the cell.
    For a checked scope (earlier answers, or land), the best point that scope.allows(): the candidates
    are ranked as usual and lattice points of the cell are added as fallbacks; (None, "none_allowed")
    when no point of the cell fits.
    """
    area = float(shapely.area(cell_m))
    margin = max(MARGIN_M, 0.002 * math.sqrt(area))
    mx, my, _ = _minimax(cell_m, margin)
    held = sum(float(g[4].sum()) for g in (hyps, samples) if g is not None and len(g[4]))
    checked = scope.checked
    cx, cy = [mx], [my]
    if held > 0:
        edge = shapely.boundary(cell_m)
        for group in (hyps, samples):
            if group is None or not len(group[4]):
                continue
            inside = shapely.contains_xy(cell_m, group[0], group[1])
            gx, gy = group[0][inside], group[1][inside]
            if not len(gx):
                continue
            far = shapely.distance(edge, shapely.points(np.column_stack([gx, gy]))) >= margin
            cx += list(gx[far])
            cy += list(gy[far])
    n_main = len(cx)
    if checked:  # fallbacks: a lattice over the cell shrunk by the margin
        inset = _polygonal(shapely.buffer(cell_m, -margin))
        lx, ly = _lattice(inset if not shapely.is_empty(inset) else cell_m, 64)
        cx += list(lx)
        cy += list(ly)
    lat_c, lng_c = scope.frame.latlng(np.array(cx), np.array(cy))
    if held > 0:
        groups = [g for g in (hyps, samples) if g is not None and len(g[4])]
        lats = np.concatenate([g[2] for g in groups])
        lngs = np.concatenate([g[3] for g in groups])
        w = np.concatenate([g[4] for g in groups])
        values = np.round(_theta(_haversine_matrix(lat_c, lng_c, lats, lngs), category, urban_probability) @ w
                          / w.sum(), 12)
    else:  # no weight: the smaller the farthest distance, the better (the minimax point first)
        hull = shapely.get_coordinates(shapely.convex_hull(cell_m))
        values = -np.sqrt((hull[:, 0][None, :] - np.array(cx)[:, None]) ** 2
                          + (hull[:, 1][None, :] - np.array(cy)[:, None]) ** 2).max(axis=1)
        values[0] = np.inf if not checked else values[0]
    order = np.argsort(-values, kind="stable")
    if not checked:
        order = order[:1]  # as before: the best candidate, then the minimax point, then any inside point
        if order[0] != 0:
            order = np.array([order[0], 0])
    for k in order:
        point = coordinate((float(lat_c[k]), float(lng_c[k])))
        if not shapely.contains_xy(cell_deg, point["lng"], point["lat"]):
            continue
        if checked and not scope.allows((point["lat"], point["lng"])):
            continue
        method = "minimax" if k == 0 else "best_expected" if held > 0 and k < n_main else "best_allowed"
        return (point["lat"], point["lng"]), method
    if checked:
        return None, "none_allowed"
    p = shapely.point_on_surface(cell_deg)
    point = coordinate((p.y, p.x))
    return (point["lat"], point["lng"]), "point_on_surface"


# -- labels ------------------------------------------------------------------------------------------

def _cell_extent(cell_m):
    xmin, ymin, xmax, ymax = shapely.bounds(cell_m)
    return xmax - xmin, ymax - ymin


def _anchor_range(cell_m, anchor):
    """(min, max) distance in metres from the anchor to the cell, and its bearing range or None."""
    here = shapely.Point(anchor)
    near = float(shapely.distance(cell_m, here))
    hull = shapely.get_coordinates(shapely.convex_hull(cell_m))
    far = float(np.hypot(hull[:, 0] - anchor[0], hull[:, 1] - anchor[1]).max())
    return near, far


def _labels(scope, part, options_n):
    """[(label, boundary description)] per cell, unique labels."""
    family, cells, meta, params, anchor = part["family"], part["cells"], part["meta"], part["params"], part["anchor_m"]
    name = scope.anchor_label or "the landmark"
    sx, sy = shapely.centroid(scope.geom_m).x, shapely.centroid(scope.geom_m).y
    out = []
    for i, (cell, info) in enumerate(zip(cells, meta)):
        c = shapely.centroid(cell)
        if family == "sectors":
            start, end = info["bearings"]
            mid = (start + 60.0) % 360.0
            near, far = _anchor_range(cell, anchor)
            label = f"{_compass(mid).capitalize()} of {name}"
            text = (f"Bearings {start:.0f}° to {end:.0f}° as seen from {name} (clockwise from north), up to "
                    f"{_fmt_m(far)} from it")
        elif family == "rings" and info["ring"] == "inner":
            label = f"Within {_fmt_m(params['r1'])} of {name}"
            text = f"Less than {_fmt_m(params['r1'])} from {name}, on every side of it"
        elif family == "rings":
            side = _compass(_bearing(c.x - anchor[0], c.y - anchor[1]))
            label = f"{_fmt_m(params['r1'])} or more from {name}, {side} side"
            line = params["line"]
            text = (f"At least {_fmt_m(params['r1'])} from {name}, on its {side} side of the line through it at "
                    f"bearings {line:.0f}° and {(line + 180) % 360:.0f}°")
        else:
            where = _compass(_bearing(c.x - sx, c.y - sy))
            label = f"{where.capitalize()} part"
            text = f"The {where} part of the search area ({scope.label})"
            if anchor is not None:
                near, far = _anchor_range(cell, anchor)
                if shapely.contains_xy(cell, *anchor):
                    text += f", around {name} and up to {_fmt_m(far)} from it"
                else:
                    text += (f", {_fmt_m(near)} to {_fmt_m(far)} from {name}, towards the "
                             f"{_compass(_bearing(c.x - anchor[0], c.y - anchor[1]))}")
        out.append([label, text, c])
    labels = [o[0] for o in out]
    for i, o in enumerate(out):  # unique labels: a finer compass, then a number
        if labels.count(o[0]) > 1 and family not in ("sectors", "rings"):
            where = _compass(_bearing(o[2].x - sx, o[2].y - sy), COMPASS16)
            o[0] = f"{where.capitalize()} part"
    labels = [o[0] for o in out]
    for i, o in enumerate(out):
        if labels.count(o[0]) > 1:
            o[0] = f"{o[0]} ({i + 1})"
    return [(o[0], o[1]) for o in out]


def _display(cell_m, frame, max_points=80):
    """The cell simplified for a map link (at most max_points vertices), WGS84 GeoJSON with 6 decimals,
    and how far the drawing may stray from the cell (the summed simplification tolerances, metres)."""
    simple, strayed = cell_m, 0.0
    tolerance = max(0.25, math.sqrt(float(shapely.area(cell_m))) / 1000.0)
    for _ in range(16):
        if shapely.get_num_coordinates(simple) <= max_points:
            break
        simple = _polygonal(shapely.simplify(simple, tolerance, preserve_topology=True))
        strayed += tolerance
        tolerance *= 1.6
    return geojson(frame.to_deg(simple), decimals=6), strayed


def _design(geom, max_points=DESIGN_MAX_VERTICES):
    """A simplified copy of a large scope for choosing the cuts (the cells are then cut from geom itself)."""
    if shapely.get_num_coordinates(geom) <= max_points:
        return geom
    simple, tolerance = geom, math.sqrt(float(shapely.area(geom))) / 2000.0
    for _ in range(12):
        simple = _polygonal(shapely.simplify(simple, tolerance, preserve_topology=True))
        if shapely.get_num_coordinates(simple) <= max_points:
            break
        tolerance *= 1.6
    return simple if not shapely.is_empty(simple) else geom


def _log_geojson(geom_deg, frame, max_points=LOG_MAX_VERTICES):
    """(GeoJSON, tolerance_m) for logs and the console: exact (7 decimals) up to max_points vertices, else
    simplified in metres until it fits (a whole country has about 100,000). Containment and bounds always
    use the exact geometry."""
    if shapely.get_num_coordinates(geom_deg) <= max_points:
        return geojson(geom_deg), 0.0
    geom_m = frame.to_m(geom_deg)
    simple, tolerance = geom_m, max(1.0, math.sqrt(float(shapely.area(geom_m))) / 2000.0)
    for _ in range(16):
        simple = _polygonal(shapely.simplify(geom_m, tolerance, preserve_topology=True))
        if shapely.get_num_coordinates(simple) <= max_points:
            break
        tolerance *= 1.6
    return geojson(frame.to_deg(simple), decimals=6), round(tolerance, 1)


def map_link(features):
    """A geojson.io link drawing these GeoJSON features (the data travels in the link itself)."""
    collection = {"type": "FeatureCollection", "features": features}
    return "https://geojson.io/#data=data:application/json," + quote(json.dumps(collection, separators=(",", ":")),
                                                                      safe="")


def _feature(geometry, **properties):
    return {"type": "Feature", "properties": properties, "geometry": geometry}


# -- the question ------------------------------------------------------------------------------------

def _is_sample(c):
    return bool((c.details or {}).get("cell_sample"))


def _is_diffuse(c, scope_radius_m):
    d = c.details or {}
    if d.get("residual") or d.get("country_level"):
        return True
    return c.role == "area" and (c.extent_m or 0.0) > DIFFUSE_FACTOR * scope_radius_m


def _arrays(scope, items):
    """(x, y, lat, lng, w) arrays for candidates."""
    lats = np.array([c.lat for c in items], dtype=float)
    lngs = np.array([c.lng for c in items], dtype=float)
    w = np.array([c.weight for c in items], dtype=float)
    x, y = scope.frame.xy(lats, lngs)
    return x, y, lats, lngs, w


def _subset(group, mask):
    return tuple(a[mask] for a in group)


def cell_question(candidates, scope, *, category=None, urban_probability=None, phrase_fn=None, constraints=None,
                  zones=None):
    """A questions.CellQuestion splitting `scope` (a Scope) into cells, plus "Outside this area" (module
    docstring). Candidates (hypotheses, Candidates) set the cuts' balance, the representative points and
    each option's support; every one maps to exactly one option. category or urban_probability (default
    0.5, an assumption) is the score scenario for the representative points. constraints / zones: the
    scope is first cut to the earlier answers and land (constrain()); a scope that already carries them
    (a route's) needs neither. A cell with no allowed point is merged into its neighbour."""
    if category is not None and category not in SCALE_M:
        raise ValueError(f"category must be one of {tuple(SCALE_M)}, got {category!r}")
    if category is None and urban_probability is None:
        urban_probability = 0.5
    if constraints:
        clipped = constrain(scope, constraints, zones)
        if clipped is None:
            raise ValueError(f"the earlier answers leave nothing of scope {scope.scope_id}")
        scope = clipped
    candidates = list(candidates)
    n = N_CELLS_WHOLE if scope.whole else N_CELLS
    radius = math.sqrt(scope.area_m2 / math.pi)
    inside = (scope.contains_many([c.lat for c in candidates], [c.lng for c in candidates])
              if candidates else np.zeros(0, dtype=bool))
    real_items = [c for c, ins in zip(candidates, inside) if ins and c.weight > 0 and not _is_sample(c)
                  and not _is_diffuse(c, radius)]
    sample_items = [c for c, ins in zip(candidates, inside) if ins and c.weight > 0 and _is_sample(c)]
    real = _arrays(scope, real_items)
    samples = _arrays(scope, sample_items)
    px, py, pw = (np.concatenate([real[0], samples[0]]), np.concatenate([real[1], samples[1]]),
                  np.concatenate([real[4], samples[4]]))
    part = _partition(scope, px, py, pw, (real[0], real[1]), n)
    labels = _labels(scope, part, n)

    def represent(cell_m):
        cell_deg = _to_deg(scope.frame, cell_m)
        shapely.prepare(cell_deg)
        in_real = shapely.contains_xy(cell_m, real[0], real[1]) if len(real[0]) else np.zeros(0, dtype=bool)
        in_samp = shapely.contains_xy(cell_m, samples[0], samples[1]) if len(samples[0]) else np.zeros(0, dtype=bool)
        point, method = _representative(scope, cell_m, cell_deg, _subset(real, in_real), _subset(samples, in_samp),
                                        category, urban_probability if category is None else 0.5)
        return cell_deg, point, method

    built = [[cell_m, label, boundary, *represent(cell_m)] for cell_m, (label, boundary) in zip(part["cells"], labels)]
    merged = 0
    while len(built) > 1 and any(b[4] is None for b in built):  # no allowed point: join the nearest neighbour
        j = next(i for i, b in enumerate(built) if b[4] is None)
        edge = shapely.boundary(built[j][0])
        shared = [(float(shapely.length(shapely.intersection(edge, shapely.boundary(b[0])))),
                   -float(shapely.distance(built[j][0], b[0])), i) for i, b in enumerate(built) if i != j]
        i = max(shared)[2]
        cell_m = _clean(shapely.set_precision(shapely.union(built[i][0], built[j][0]), GRID_M))
        label, boundary = f"{built[i][1]} + {built[j][1]}", f"{built[i][2]}; or {built[j][2]}"
        built[i] = [cell_m, label, boundary, *represent(cell_m)]
        del built[j]
        merged += 1
    if any(b[4] is None for b in built):
        raise ValueError(f"no point of scope {scope.scope_id} fits the earlier answers")
    if len(built) < 2 and scope.whole:
        raise ValueError(f"scope {scope.scope_id} keeps a single allowed cell: nothing to ask")
    options, features = [], []
    for k, (cell_m, label, boundary, cell_deg, point, method) in enumerate(built):
        option_id = Q.OPTION_IDS[k]
        deviation = scope.deviation_for(cell_m)
        bound = bound_m(point, cell_deg, deviation)
        west, south, east, north = shapely.bounds(cell_deg)
        display, tolerance = _display(cell_m, scope.frame)
        colour = COLOURS[k % len(COLOURS)]
        cell_features = [_feature(display, option=option_id, title=f"{option_id}) {label}", stroke=colour, fill=colour,
                                  **{"fill-opacity": 0.25, "stroke-width": 2}),
                         _feature({"type": "Point", "coordinates": [point[1], point[0]]}, option=option_id,
                                  title=f"{option_id}) representative point (not a camera position)",
                                  **{"marker-color": colour, "marker-symbol": option_id})]
        features += cell_features
        logged, log_tolerance = _log_geojson(cell_deg, scope.frame)
        option = Q.CellOption(option_id, label, point=coordinate(point), point_role="area", bound_m=bound,
                              cell_id=f"{scope.scope_id}/{option_id}", cell=logged,
                              extent=Q.Box(south, west, north, east), area_m2=float(shapely.area(cell_m)),
                              deviation_m=deviation, map_link=map_link(cell_features), geometry=cell_deg,
                              geometry_m=cell_m)
        option._boundary, option._method, option._map_tolerance_m = boundary, method, tolerance
        option._cell_tolerance_m = log_tolerance
        options.append(option)
    if not scope.whole:
        options.append(Q.Option(Q.OPTION_IDS[len(options)], "Outside this area",
                                f"Anywhere in {Q.ALLOWED_AREA_TEXT} outside the {len(options)} areas above, which "
                                f"together make up the search area ({scope.label}).", complement=True))
    if scope.anchor is not None:
        features.append(_feature({"type": "Point", "coordinates": [scope.anchor[1], scope.anchor[0]]},
                                 title=f"{scope.anchor_label} (the reference the cells are cut around)",
                                 **{"marker-color": "#444444", "marker-symbol": "star"}))
    details = {"scope_kind": "cell", "zone_kind": "cells", "family": part["family"], "balance": part["mode"],
               "cut": _json_params(part["params"]), "families_scored": part["families_scored"],
               "scope_id": scope.scope_id, "depth": scope.depth, "real_hypotheses_inside": len(real_items),
               "weight_samples_inside": len(sample_items), "cells_map": map_link(features),
               "category": category, "urban_probability": None if category is not None else urban_probability,
               "target_bound_m": target_bound_m(category), "merged_cells": merged,
               "constrained_by": len(scope.constraints), "land_rule_m": LAND_TOLERANCE_M if scope.land else None}
    question = Q.CellQuestion("zone", Q.TEMPLATES["cell_whole" if scope.whole else "cell_part"], options,
                              scope=scope, details=details)
    _fill_cells(question, candidates)
    return Q._phrase(question, phrase_fn)


def _json_params(params):
    return {k: (round(v, 3) if isinstance(v, float) else [list(map(lambda x: round(x, 3), h)) for h in v]
                if k == "halves" else v) for k, v in params.items()}


def _fill_cells(question, candidates):
    """Each option's coverage (real hypotheses only in covers; samples count in support) and its detail."""
    held = {o.id: [] for o in question.options}
    for c in sorted(candidates, key=lambda c: c.weight, reverse=True):
        held[question.option_for(c).id].append(c)
    total = sum(c.weight for c in candidates)
    for o in question.options:
        real = [c for c in held[o.id] if not _is_sample(c)]
        o.covers = [c.source for c in real]
        o.support = sum(c.weight for c in held[o.id]) / total if total > 0 else 0.0
        if o.complement:
            continue
        names = [c.label or c.source for c in real if c.weight > 0]
        holds = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        width, height = _cell_extent(o.geometry_m)
        deviation = (f", {_fmt_m(o.deviation_m)} of it for the mapped boundary of {question.scope.root.label}"
                     if o.deviation_m else "")
        o.detail = (f"{o._boundary}. About {_fmt_m(width)} east-west by {_fmt_m(height)} north-south "
                    f"({_fmt_area(o.area_m2)}). The marked point is the cell's representative point, not a camera "
                    f"position; no part of the cell is more than {_fmt_m(o.bound_m)} from it{deviation}. "
                    f"Current candidates in it: {holds or 'none'}.")


def chain(question, option_id):
    """The next scope once the team picked option_id of a CellQuestion (questions.cell_chain).

    A cell becomes the scope, with the question's scope as its parent. "Outside this area" gives the
    parent minus this scope (whose own Outside option covers everything else), going up while that is
    empty; None when the scope was a root: the camera is outside the whole search area, so the route
    ends (for a zone root, region questions take over with that zone excluded). A skip has no answer and
    never reaches this.
    """
    option = question.option(option_id)
    scope = question.scope
    if not option.complement:
        return scope.child(option)
    s = scope
    while s.parent is not None:
        rest = s.remainder()
        if rest is not None:
            return rest
        s = s.parent
    return None


def cell_output(scope, candidates=(), *, category=None, urban_probability=None, note=""):
    """The geographic_cell Output for a picked scope: its representative point (as for an option, with the
    candidates inside it) repeated in all 10 slots, uncertainty_m = the bound recomputed for that point.
    None when the scope carries earlier answers (or land) and no point of it fits them."""
    if category is None and urban_probability is None:
        urban_probability = 0.5
    candidates = list(candidates)
    radius = math.sqrt(scope.area_m2 / math.pi)
    inside = (scope.contains_many([c.lat for c in candidates], [c.lng for c in candidates])
              if candidates else np.zeros(0, dtype=bool))
    real = _arrays(scope, [c for c, ins in zip(candidates, inside) if ins and c.weight > 0 and not _is_sample(c)
                           and not _is_diffuse(c, radius)])
    samples = _arrays(scope, [c for c, ins in zip(candidates, inside) if ins and c.weight > 0 and _is_sample(c)])
    point, method = _representative(scope, scope.geom_m, scope.geom, real, samples, category,
                                    urban_probability if category is None else 0.5)
    if point is None:
        return None
    bound = bound_m(point, scope.geom, scope.deviation_for(scope.geom_m))
    target = target_bound_m(category)
    assumption = category or f"unknown, urban probability {urban_probability} (assumed)"
    text = (f"cell {scope.scope_id} ({scope.label}): its representative point ({method}), not a camera fix; every "
            f"part of the cell is within {bound:.1f} m of it if the cell holds the camera; category {assumption}; "
            f"target bound {target:.0f} m {'reached' if bound <= target else 'not reached'}")
    sources = list(dict.fromkeys([*scope.sources, f"cell:{scope.scope_id}"]))
    return Output(point[0], point[1], "geographic_cell", "area", sources, bound, "geometric_bound",
                  "; ".join(x for x in (note, text) if x))


# -- the route ---------------------------------------------------------------------------------------

@dataclass
class _Piece:
    geom_m: object
    weight: float
    origin: str  # the source of the hypothesis whose weight this is


def _sample_candidate(lat, lng, weight, key, origins, scope_id):
    return Candidate(float(lat), float(lng), "area", f"cellmass:{key}", label="search area weight", weight=float(weight),
                     details={"cell_sample": True, "spread_of": origins, "scope_id": scope_id,
                              "point": "a sample of the weight spread over the search area, not a camera position"})


@dataclass
class CellRoute:
    """The cell route's state (module docstring). Treat it as immutable: answer() returns a new route."""

    root: Scope
    scope: Scope | None
    others: list  # Candidates kept as points: camera hypotheses in the root, everything outside it
    pieces: list  # _Piece: weight spread uniformly over parts of the root
    spread: list  # the Candidates whose weight was spread
    history: list = field(default_factory=list)  # [{"question_id", "option_id", "label", "scope_id"}]
    category: str | None = None
    urban_probability: float | None = 0.5
    answer_accuracy: float = Q.DEFAULT_ANSWER_ACCURACY
    _cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def start(cls, hypotheses, scope, *, category=None, urban_probability=None,
              answer_accuracy=Q.DEFAULT_ANSWER_ACCURACY, inside_weight=None, constraints=None, zones=None):
        """Spread every non-camera hypothesis inside the root scope over its search disc there.

        Unless one of those discs covers the whole root (the landmark a search disc is drawn around, or
        a zone's own point), the root also gets a uniform piece: the camera may be anywhere in it, away
        from every hypothesis. Its weight is inside_weight, by default the weight spread inside (half of
        the root's), or with nothing inside as much as all the other hypotheses together (an
        assumption: the team just picked this area).

        constraints: [(question, option_id), ...], every earlier answered place or zone question in answer
        order (skips excluded; the answer that picked this scope included). The scope, and every cell and
        point the route offers or outputs, keeps to them, and stays on land when a zone index is at hand
        (zones, or one an answered RegionQuestion carries). None or []: exactly the behaviour without them.
        ValueError when the answers leave nothing of the scope (route_scope(..., constraints) returns
        None then, so a caller going through it never sees this).
        """
        clipped = constrain(scope, constraints, zones)
        if clipped is None:
            raise ValueError(f"the earlier answers leave nothing of scope {scope.scope_id}")
        scope = clipped
        if category is not None and category not in SCALE_M:
            raise ValueError(f"category must be one of {tuple(SCALE_M)}, got {category!r}")
        if category is None and urban_probability is None:
            urban_probability = 0.5
        hyps = [h for h in hypotheses if not _is_sample(h)]
        start, scope = scope, scope.root  # the weight is spread over the whole chain: "Outside" can recover into it
        radius = math.sqrt(scope.area_m2 / math.pi)
        inside = scope.contains_many([h.lat for h in hyps], [h.lng for h in hyps]) if hyps else []
        spread, others, pieces = [], [], []
        for h, ins in zip(hyps, inside):
            if ins and h.role != "camera" and h.weight > 0 and not _is_diffuse(h, radius):
                spread.append(h)
            else:
                others.append(h)
        for h in spread:
            r, _ = search_radius(h)
            disc = scope.frame.to_m(geodesic_disc(h.lat, h.lng, r))
            here = _polygonal(shapely.intersection(disc, scope.geom_m))
            if h.source in scope.sources or h.source in start.sources or shapely.area(here) >= 0.999 * scope.area_m2:
                here = scope.geom_m
            if shapely.is_empty(here):
                others.append(h)
                continue
            pieces.append(_Piece(here, float(h.weight), h.source))
        covered = any(shapely.area(p.geom_m) >= 0.999 * scope.area_m2 for p in pieces)
        if not covered:
            if inside_weight is not None:
                weight = inside_weight
            elif pieces:
                weight = sum(p.weight for p in pieces)
            else:
                weight = max(sum(h.weight for h in others), 1.0)
            pieces.append(_Piece(scope.geom_m, float(weight), scope.scope_id))
        return cls(scope, start, others, pieces, spread, [], category, urban_probability, answer_accuracy)

    # -- hypotheses -----------------------------------------------------------------------------------

    def _samples(self):
        scope = self.scope or self.root
        inside_parts, mass_in = [], 0.0
        for k, p in enumerate(self.pieces):
            if p.weight <= 0:
                continue
            area = float(shapely.area(p.geom_m))
            if scope is self.root:
                part = p.geom_m
            elif shapely.intersects(p.geom_m, scope.geom_m):
                part = _polygonal(shapely.intersection(p.geom_m, scope.geom_m))
            else:
                part = shapely.Polygon()
            a_in = float(shapely.area(part)) if not shapely.is_empty(part) else 0.0
            inside_parts.append((k, p, part, a_in, area))
            mass_in += p.weight * a_in / area
        out = []
        for k, p, part, a_in, area in inside_parts:
            if a_in > 0 and mass_in > 0:
                share = p.weight * a_in / area
                n = max(MIN_PIECE_SAMPLES, int(round(SAMPLES * share / mass_in)))
                x, y = _lattice(part, n)
                lats, lngs = scope.frame.latlng(x, y)
                for i, (lat, lng) in enumerate(zip(lats, lngs)):
                    out.append(_sample_candidate(lat, lng, share / len(x), f"{k}:{i}", [p.origin], scope.scope_id))
            a_out = area - a_in
            if a_out > 1e-9 * area:
                rest = p.geom_m if a_in <= 0 else _polygonal(shapely.difference(p.geom_m, scope.geom_m))
                if shapely.is_empty(rest):
                    continue
                x, y = _lattice(rest, OUTSIDE_SAMPLES)
                x, y = x[:OUTSIDE_SAMPLES], y[:OUTSIDE_SAMPLES]
                lats, lngs = scope.frame.latlng(x, y)
                for i, (lat, lng) in enumerate(zip(lats, lngs)):
                    out.append(_sample_candidate(lat, lng, p.weight * a_out / area / len(x), f"{k}:o{i}", [p.origin],
                                                 scope.scope_id))
        return out

    def hypotheses(self):
        """The hypotheses for questions, gains and answers: the point hypotheses and the weight samples."""
        if "hypotheses" not in self._cache:
            self._cache["hypotheses"] = sorted(self.others + self._samples(), key=lambda c: c.weight, reverse=True)
        return self._cache["hypotheses"]

    def question(self, phrase_fn=None):
        """The cell question on the current scope (cached: the same object until the next answer)."""
        if self.scope is None:
            raise ValueError("the route has left its search area: no cell question")
        if "question" not in self._cache:
            self._cache["question"] = cell_question(self.hypotheses(), self.scope, category=self.category,
                                                    urban_probability=self.urban_probability, phrase_fn=phrase_fn)
        return self._cache["question"]

    def gain(self, question=None):
        """questions.expected_gain of the question over the route's hypotheses, leaving out the diffuse
        ones (country residuals, country-wide alternatives, areas far wider than the scope): expected_gain
        treats hypotheses as points, and a residual's point (its country's largest city) would otherwise
        stand for "anywhere in the country" as an exact spot and hide the gain of any cell question."""
        question = question or self.question()
        scope = self.scope or self.root
        radius = math.sqrt(scope.area_m2 / math.pi)
        hyps = [h for h in self.hypotheses() if not _is_diffuse(h, radius)] or self.hypotheses()
        return Q.expected_gain(hyps, question, category=self.category,
                               urban_probability=None if self.category else self.urban_probability,
                               answer_accuracy=self.answer_accuracy)

    # -- answers --------------------------------------------------------------------------------------

    def answer(self, question, option_id):
        """The team picked option_id of this route's question: a new route (soft update, next scope)."""
        if question.scope is not self.scope:
            raise ValueError("the question was not asked on this route's current scope")
        chosen = question.option(option_id)
        n = len(question.options)
        a = self.answer_accuracy
        if not 1 / n <= a < 1:
            raise ValueError("answer_accuracy must be from 1/n to below 1, so a wrong answer stays recoverable")
        factor = (1 - a) / ((n - 1) * a)
        others = Q.apply_answer(self.others, question, option_id, a)
        cells = [o for o in question.options if not o.complement]
        outside = 1.0 if chosen.complement else factor
        pieces = []
        for p in self.pieces:
            area = float(shapely.area(p.geom_m))
            if area <= 0 or p.weight <= 0:
                pieces.append(p)
                continue
            if not shapely.intersects(p.geom_m, self.scope.geom_m):  # wholly in "Outside this area"
                pieces.append(_Piece(p.geom_m, float(p.weight * outside), p.origin))
                continue
            rest = p.geom_m
            for o in cells:
                sub = _polygonal(shapely.intersection(p.geom_m, o.geometry_m))
                if shapely.is_empty(sub) or shapely.area(sub) <= 1e-12 * area:
                    continue
                pieces.append(_Piece(sub, float(p.weight * shapely.area(sub) / area * (1.0 if o is chosen else factor)),
                                     p.origin))
                rest = _polygonal(shapely.difference(rest, sub))
            if not shapely.is_empty(rest) and shapely.area(rest) > 1e-9 * area:
                pieces.append(_Piece(rest, float(p.weight * shapely.area(rest) / area * outside), p.origin))
        step = {"question_id": question.question_id, "option_id": option_id, "label": chosen.label,
                "scope_id": self.scope.scope_id}
        return CellRoute(self.root, chain(question, option_id), others, pieces, self.spread, [*self.history, step],
                         self.category, self.urban_probability, self.answer_accuracy)

    @property
    def answered(self):
        return len(self.history)

    def bound(self):
        """(lat, lng, bound_m) of the current scope's representative point, with the route's weight."""
        if self.scope is None:
            return None
        if "bound" not in self._cache:
            o = cell_output(self.scope, self.hypotheses(), category=self.category,
                            urban_probability=self.urban_probability)
            self._cache["bound"] = None if o is None else (o.lat, o.lng, o.uncertainty_m)
        return self._cache["bound"]

    def done(self):
        """True when the current scope's bound meets the category's target (or the route has left)."""
        if self.scope is None or self.bound() is None:  # left, or no point fits the earlier answers
            return True
        return self.bound()[2] <= target_bound_m(self.category)

    def output(self, note=""):
        """The geographic_cell Output for the current scope, or None while no cell has been picked."""
        if self.scope is None or not self.scope.picked:
            return None
        steps = f"{self.answered} cell answer{'s' if self.answered != 1 else ''}"
        return cell_output(self.scope, self.hypotheses(), category=self.category,
                           urban_probability=self.urban_probability, note="; ".join(x for x in (note, steps) if x))

    def exit_hypotheses(self):
        """The hypotheses for the rest of the pipeline: the point hypotheses, the current cell as an area
        Candidate holding the weight inside it, and each spread hypothesis with the rest of its weight."""
        rest = {}
        inside_weight = 0.0
        scope = self.scope if self.scope is not None and self.bound() is not None else None
        for p in self.pieces:
            area = float(shapely.area(p.geom_m))
            if scope is not None and area > 0:
                part = _polygonal(shapely.intersection(p.geom_m, scope.geom_m))
                share = float(shapely.area(part)) / area if not shapely.is_empty(part) else 0.0
            else:
                share = 0.0
            inside_weight += float(p.weight * share)
            rest[p.origin] = rest.get(p.origin, 0.0) + float(p.weight * (1 - share))
        out = list(self.others)
        for h in self.spread:
            out.append(Candidate(**{**h.to_dict(), "weight": rest.pop(h.source, 0.0)}))
        if scope is not None and inside_weight > 0:
            lat, lng, bound = self.bound()
            out.append(Candidate(lat, lng, "area", f"cell:{scope.scope_id}", label=scope.label, weight=inside_weight,
                                 extent_m=bound, details={"cell_id": scope.scope_id, "bound_m": bound,
                                                          "extent_source": "geometric_bound",
                                                          "cell": _log_geojson(scope.geom, scope.frame)[0],
                                                          "point": "the cell's representative point, not a camera "
                                                                   "position"}))
        for origin, weight in rest.items():  # a root without hypotheses: its leftover weight on its point
            if weight > 0:
                lat, lng, bound = self.root.rep
                out.append(Candidate(lat, lng, "area", f"cell:{self.root.scope_id}", label=self.root.label,
                                     weight=weight, extent_m=bound, details={"cell_id": self.root.scope_id,
                                                                             "extent_source": "geometric_bound"}))
        return sorted(out, key=lambda c: c.weight, reverse=True)

    def summary(self):
        lat, lng, bound = self.bound() or (None, None, None)
        return {"root": self.root.scope_id, "scope": self.scope.scope_id if self.scope else None,
                "answered": self.answered, "history": self.history, "bound_m": bound,
                "target_bound_m": target_bound_m(self.category), "category": self.category,
                "urban_probability": None if self.category else self.urban_probability,
                "pieces": len(self.pieces), "spread": [h.source for h in self.spread]}


def log_cell_output(run, output, route_or_scope, *, stage="ask"):
    """Log the cell output's bound and category assumption (evidence "cell_output"), then the output."""
    route = route_or_scope if isinstance(route_or_scope, CellRoute) else None
    scope = route.scope if route is not None else route_or_scope
    category = route.category if route is not None else None
    urban_probability = route.urban_probability if route is not None and category is None else None
    payload = {"observation": f"cell {scope.scope_id}: output within {output.uncertainty_m:.1f} m of any point of the "
                              f"cell (geometric bound, assuming the picked cell holds the camera)",
               "bound_m": output.uncertainty_m, "target_bound_m": target_bound_m(category),
               "category": category, "category_assumption": category or "unknown",
               "urban_probability": urban_probability, "point": coordinate((output.lat, output.lng)),
               "scope": scope.to_dict()}
    if route is not None:
        payload["route"] = route.summary()
    run.evidence("cell_output", payload, stage=stage, actor="agent")
    return output.log(run)


# -- glue --------------------------------------------------------------------------------------------

def _unique_match(c):
    d = c.details or {}
    return (d.get("tier", 9) <= 1 and d.get("ambiguity", 9) <= 1 and not d.get("chain")
            and not d.get("generic_query"))


def route_scope(hypotheses, *, zones=None, zone_scope=None, place_question=None, place_option_id=None,
                dominant_share=DOMINANT_SHARE, strong_share=STRONG_SHARE, constraints=None):
    """(Scope or None, why): where the cell route starts; cut to the earlier answers when given."""
    scope, why = _route_scope(hypotheses, zones=zones, zone_scope=zone_scope, place_question=place_question,
                              place_option_id=place_option_id, dominant_share=dominant_share,
                              strong_share=strong_share)
    if scope is None or not constraints:
        return scope, why
    clipped = constrain(scope, constraints, zones)
    if clipped is None:
        return None, f"{why}; but the earlier answers leave nothing of {scope.label or scope.scope_id}"
    return clipped, why


def _route_scope(hypotheses, *, zones=None, zone_scope=None, place_question=None, place_option_id=None,
                 dominant_share=DOMINANT_SHARE, strong_share=STRONG_SHARE):
    """(Scope or None, why): where the cell route starts for these hypotheses.

      zone       zone_scope is a leaf zone the team picked (region questions down to a parish,
                 province or department): the cells cut the zone itself
      place      the team picked a place option (place_question, place_option_id): the search disc
                 around the heaviest landmark or area it held, at most the option's radius
      dominant   the heaviest landmark or area hypothesis (no residual, no country-wide alternative)
                 holds strong_share of the weight within its search disc, or dominant_share with a
                 unique exact name match (tier 0-1, ambiguity 1, no chain)
    """
    hyps = [h for h in hypotheses if h.weight > 0 and not _is_sample(h)]
    total = sum(h.weight for h in hyps)
    if zones is not None and zone_scope is not None:
        z = zones.get(zone_scope)
        if z.is_leaf:
            return Scope.from_zone(zones, z), f"the team picked {z.label}, a leaf zone: cells inside it"
        kids = zones.children(z)
        while len(kids) == 1 and zones.children(kids[0]):
            kids = zones.children(kids[0])
        real = [h for h in hyps if not str(h.source).startswith("zone:") and not _is_diffuse(h, 1e12)
                and zones.contains(z.id, h.point)]
        if len(kids) > Q.MAX_OPTIONS - 1 and not real:
            return Scope.from_zone(zones, z), (f"the team picked {z.label}: no hypothesis is in it and it has "
                                               f"{len(kids)} subzones, so cells split it faster than naming 3 at a time")
        return None, f"{z.label}: named subzones split it (region questions)"
    if place_question is not None and place_option_id is not None:
        option = place_question.option(place_option_id)
        if not option.complement:
            held = [h for h in hyps if place_question.option_for(h).id == option.id and not _is_diffuse(h, 1e12)]
            if not held:
                return None, f"the team picked {option.label}, a country-wide residual: no cell route"
            lat, lng = option.latlng
            confirmed = Scope.disc(lat, lng, option.radius_m, scope_id=f"place:{option.id}@{option.radius_m:.0f}m",
                                   kind="camera" if option.point_role == "camera" else "area", anchor_label=option.label,
                                   sources=tuple(option.covers[:1]), picked=True,
                                   details={"place_option": option.id, "rule": "the place option the team picked"})
            places = [h for h in held if h.role in ("landmark", "area")]
            if places:
                anchor = max(places, key=lambda h: h.weight)
                radius, _ = search_radius(anchor)
                if radius < 0.9 * option.radius_m:  # the evidence's disc first, inside the area the team confirmed
                    return (Scope.around(anchor, parent=confirmed),
                            f"the team picked {option.label}: search around {anchor.label or anchor.source} first")
            return confirmed, f"the team picked {option.label}: its disc"
    if not total > 0:
        return None, "no supported hypothesis"
    ranked = sorted((h for h in hyps if h.role in ("landmark", "area") and not _is_diffuse(h, 1000.0)),
                    key=lambda h: h.weight, reverse=True)
    if not ranked:
        return None, "no landmark or area hypothesis"
    top = ranked[0]
    radius, _ = search_radius(top)
    near = _haversine(top.lat, top.lng, [h.lat for h in hyps], [h.lng for h in hyps]) <= radius
    share = float(sum(h.weight for h, ok in zip(hyps, near) if ok) / total)
    if share >= strong_share or (share >= dominant_share and _unique_match(top)):
        return Scope.around(top), (f"{top.label or top.source} holds {share:.0%} of the weight within "
                                   f"{_fmt_m(radius)} of it")
    return None, f"no dominant landmark: the heaviest, {top.label or top.source}, holds {share:.0%}"


def spread_candidates(scope, weight=1.0, n=12):
    """`weight` spread evenly over the scope as n area Candidates on a lattice (the cell counterpart of
    panoloc.zones.Zones.spread): points that let a question split an area that holds no hypothesis."""
    x, y = _lattice(scope.geom_m, n)
    lats, lngs = scope.frame.latlng(x, y)
    spacing = math.sqrt(scope.area_m2 / max(len(x), 1))
    return [Candidate(float(lat), float(lng), "area", f"cellspread:{scope.scope_id}:{i}", label=scope.label,
                      weight=weight / len(x), extent_m=spacing,
                      details={"spread_of": scope.scope_id, "extent_source": "assumed",
                               "point": "a point of the area, not a camera position"})
            for i, (lat, lng) in enumerate(zip(lats, lngs))]
