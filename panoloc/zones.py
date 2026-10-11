"""Named administrative zones for the zone questions: country > region > ... > parish (PLAN.md 3.4, 4.4; T32).

tools/build_zones.py builds Data/index/zones.gpkg (layer "zones", WGS84) and Data/index/zones.json (the
sources, their versions and declared CRSs, the tolerances, counts and the gap and overlap measurements)
from CAOP 2025 for Portugal and geoBoundaries for Spain and France. This module only reads them, as
panoloc.names reads names.sqlite. It needs shapely and pyogrio, so it runs in .venv.

Zones. A zone ID is "<country>:<level>:<source code>"; a country is just "PT", "ES" or "FR". The primary
tree, coarsest first:
  PT  country > district (18) > municipality > parish
      country > autonomous_region (Açores, Madeira) > island > municipality > parish
  ES  country > community (17 autonomous communities, Ceuta, Melilla) > province (52)
  FR  country > region (13) > department (96): metropolitan France and Corsica, no overseas France
Codes are CAOP's DT, DTMN and DTMNFR (DICOFRE), its NUTS 1 code for the autonomous regions, the
geoBoundaries shapeISO where it is a real ISO 3166-2 code (French regions) and its shapeID elsewhere.
Portugal also has the alternate tree "nuts": nuts2 (9 NUTS 2024 regions) > nuts3 (26); a municipality
lists its NUTS 3 subregion in also_in, and children(zone, tree="nuts") walks PT > nuts2 > nuts3 >
municipality > parish. Location.also holds a point's NUTS zones. The Canaries, the Balearics,
Ceuta and Melilla are Spain. A name is the source's own spelling (geoBoundaries provinces have no
accents: "Malaga", "Palmas, Las"); Zone.label adds the level: "Distrito de Setúbal", "Lisboa (município)",
"Santa Maria Maior (freguesia, Lisboa)", "Madrid (provincia)", "Paris (département)".

Leaves (parishes, provinces, departments) tile each country with no gap or overlap, and every coarser
zone is the union of its leaves, so the levels nest exactly. Containment is always decided on the
leaves: a coarser zone's stored geometry can be simplified further for display (zones.json says how
much), but its area, bounding box, representative point and hull come from the union of its leaves.

locate(lat, lng) finds the leaf holding the point (an STRtree over the leaves, each prepared on first
use) and returns its Location: the chain of zones from the country down to the leaf, plus the zones of
other trees holding it (Location.also: NUTS). A point outside every leaf (a pier, a beach, an estuary,
a gap between two countries' borders) goes to the nearest leaf within snap_m, 1 km by default, and
Location.distance_m says how far it was; beyond that, locate returns None. The three countries come from
different sources and their borders do not match: the build gave each overlap to one country (Portugal,
the official CAOP border, then Spain, then France), and the snap covers the gaps.

bound_m(point, zone): a conservative maximum distance from the point to anywhere in the zone. The
farthest point of a region from any point is a vertex of its convex hull, so take the largest Haversine
distance (R = 6371 km, as panoloc.scoring and the scorer) to the hull vertices of the union of the
zone's leaves. Add deviation_m, the largest measured distance from the source boundary to the stored,
simplified one (over the zone's leaves), then 0.6% and 1 m as panoloc.questions.cell_bound_m, rounded
up to 0.1 m. The representative point (Zone.rep) is the centre of the largest circle inscribed in the
zone's largest part, so it is inside the zone; it marks the zone, never a camera position.

  from panoloc.zones import Zones
  with Zones.open() as zones:                          # FileNotFoundError (ZonesNotBuilt) if not built
      loc = zones.locate(38.7076, -9.1365)             # Praça do Comércio
      [z.label for z in loc.chain]                     # Portugal, Distrito de Lisboa, Lisboa (município), ...
      zones.children("PT"); zones.get("PT:district:15").label     # 'Distrito de Setúbal'
      zones.bound_m((38.52, -8.89), "PT:district:15")  # metres from that point to anywhere in the district
      zones.candidate("PT:district:15")                # an area Candidate: rep point, extent_m = bound
      zones.spread("PT:district:15", weight=0.5)       # area Candidates over its municipalities, by area
Questions treat hypotheses as points, so for a zone the team picked that holds no hypothesis use
spread(), not one candidate(): its points let the next question split the zone (until T42's cells).
Zones.from_leaves(leaves, coarse) builds the same index in memory from shapely polygons (tests).
panoloc.questions.region_question asks about these zones; region_chain carries the scope along.
"""
import functools
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyogrio
import shapely

from panoloc.candidates import Candidate
from panoloc.names import normalise
from panoloc.questions import BOUND_ABSOLUTE_MARGIN_M, BOUND_RELATIVE_MARGIN
from panoloc.scoring import EARTH_RADIUS_M

SCHEMA = "panoloc.zones/1"
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "Data" / "index" / "zones.gpkg"
LAYER = "zones"
PRIMARY = "primary"
SNAP_M = 1000.0  # a point this close to a zone, outside every zone, belongs to it (piers, beaches, estuaries)
M_PER_DEG = EARTH_RADIUS_M * math.pi / 180  # metres per degree of latitude on the scorer's sphere
LOCATE_CACHE = 1 << 16
COUNTRIES = ("PT", "ES", "FR")
COUNTRY_NAMES = {"PT": "Portugal", "ES": "Spain", "FR": "France"}
ALLOWED_AREA_TEXT = "Portugal, Spain and France"

# level: (singular, plural) in English, for option details
LEVELS = {
    "country": ("country", "countries"),
    "district": ("district", "districts"),
    "autonomous_region": ("autonomous region", "autonomous regions"),
    "island": ("island", "islands"),
    "municipality": ("municipality", "municipalities"),
    "parish": ("parish", "parishes"),
    "nuts2": ("NUTS 2 region", "NUTS 2 regions"),
    "nuts3": ("NUTS 3 subregion", "NUTS 3 subregions"),
    "community": ("autonomous community", "autonomous communities"),
    "province": ("province", "provinces"),
    "region": ("region", "regions"),
    "department": ("department", "departments"),
}
# The article Portuguese uses with a district's name ("Distrito do Porto"); the others take "de".
DISTRICT_ARTICLE = {"Porto": "do", "Guarda": "da"}
_TYPED_COMMUNITY = re.compile(r"^(Comunidad|Comunitat|Región|Principado|Ciudad Autónoma)\b")
_INVERTED = re.compile(r"^(?P<base>.+), (?P<article>La|Las|El|Los|Les|Illes|A|O|As|Os)$")
COLUMNS = ("zone_id", "name", "short_name", "level", "country", "parent_id", "tree", "depth", "is_leaf", "also_in", "area_km2",
           "rep_lat", "rep_lng", "rep_radius_m", "rep_method", "south", "west", "north", "east", "deviation_m",
           "outline_deviation_m", "hull", "source", "source_code", "n_children", "n_leaves", "n_parts", "n_vertices")


class ZonesNotBuilt(FileNotFoundError):
    """The zone index file is missing: callers fall back to box cells (panoloc.questions.zone_question)."""


def display_name(name, level):
    """The source name as people write it: geoBoundaries lists some provinces article last ("Palmas, Las")."""
    if level == "province":
        m = _INVERTED.match(name)
        if m:
            return f"{m['article']} {m['base']}"
    return name


def zone_label(name, level, parent_name=None):
    """The name with its level, in the country's own terms: "Distrito do Porto", "Lisboa (município)"."""
    shown = display_name(name, level)
    if level == "district":
        return f"Distrito {DISTRICT_ARTICLE.get(name, 'de')} {name}"
    if level == "municipality":
        return f"{shown} (município)"
    if level == "parish":
        return f"{shown} (freguesia, {parent_name})" if parent_name else f"{shown} (freguesia)"
    if level == "community":
        return shown if _TYPED_COMMUNITY.match(shown) else f"{shown} (comunidad autónoma)"
    if level == "province":
        return f"{shown} (provincia)"
    if level == "region":
        return f"{shown} (région)"
    if level == "department":
        return f"{shown} (département)"
    if level in ("nuts2", "nuts3"):
        return f"{shown} (NUTS {level[-1]})"
    return shown  # countries, autonomous regions and islands carry their kind in the name


def describe(name, level, country, parent=None):
    """What the zone is, in English: "a municipality of Portugal, in Distrito de Lisboa". `parent` is
    (name, level) of the zone above it, or None."""
    country_name = COUNTRY_NAMES.get(country, country)
    singular = LEVELS.get(level, (level, level))[0]
    if level == "country":
        return "a country"
    if level == "community" and name.startswith("Ciudad Autónoma"):
        return "an autonomous city of Spain"
    article = "an" if singular[0] in "aeiou" else "a"
    if parent is None or parent[1] == "country":
        return f"{article} {singular} of {country_name}"
    return f"{article} {singular} of {country_name}, in {zone_label(*parent)}"


def search_text(name, level, country, parent=None):
    """What to type into a map search to see the zone's outline; `parent` as in describe()."""
    country_name = COUNTRY_NAMES.get(country, country)
    shown = display_name(name, level)
    if level == "country":
        return shown
    if level == "district":
        return f"{zone_label(name, level)}, {country_name}"
    if level in ("parish", "municipality") and parent is not None and parent[1] != "country":
        return f"{shown}, {display_name(*parent)}, {country_name}"
    if level == "province":
        return f"Provincia de {shown}, {country_name}"
    if level == "department":
        return f"{shown} (département), {country_name}"
    return f"{shown}, {country_name}"


@dataclass(frozen=True)
class Zone:
    """One zone. rep = (lat, lng), a point inside the zone; bbox = (south, west, north, east)."""

    id: str
    name: str  # as the source spells it
    level: str
    country: str
    parent_id: str | None
    tree: str = PRIMARY
    depth: int = 0
    is_leaf: bool = False
    also_in: tuple = ()
    area_km2: float = 0.0
    rep: tuple = (0.0, 0.0)
    rep_radius_m: float = 0.0  # radius of the inscribed circle at rep: how deep inside the zone it is
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)
    deviation_m: float = 0.0  # largest distance from the source boundary to the stored one, over its leaves
    source: str = ""
    source_code: str = ""
    n_children: int = 0
    n_leaves: int = 0
    short_name: str = ""  # the source's short form where it has one (CAOP "designacao_simplificada")
    label: str = ""
    description: str = ""
    search_text: str = ""

    @property
    def singular(self):
        return LEVELS.get(self.level, (self.level, self.level))[0]

    @property
    def plural(self):
        return LEVELS.get(self.level, (self.level, self.level))[1]

    def to_dict(self):
        """JSON-ready summary for logs."""
        south, west, north, east = self.bbox
        return {"zone_id": self.id, "name": self.name, "label": self.label, "level": self.level,
                "country": self.country, "parent_id": self.parent_id, "area_km2": self.area_km2,
                "rep": {"lat": self.rep[0], "lng": self.rep[1]},
                "bbox": {"south": south, "west": west, "north": north, "east": east}}


@dataclass(frozen=True)
class Location:
    """Where a point is: chain from the country down to the leaf, and the zones of other trees holding it."""

    chain: tuple
    distance_m: float = 0.0  # 0 inside the leaf; otherwise how far outside it the point was (at most snap_m)
    also: tuple = ()

    @property
    def snapped(self):
        return self.distance_m > 0

    @property
    def leaf(self):
        return self.chain[-1]

    @property
    def country(self):
        return self.chain[0].country

    @functools.cached_property
    def ids(self):
        return frozenset(z.id for z in (*self.chain, *self.also))

    def level(self, level):
        """The zone of that level holding the point, or None."""
        return next((z for z in (*self.chain, *self.also) if z.level == level), None)

    def __contains__(self, zone_id):
        return zone_id in self.ids

    def to_dict(self):
        return {"chain": [z.id for z in self.chain], "labels": [z.label for z in self.chain],
                "also": [z.id for z in self.also], "distance_m": round(self.distance_m, 1)}


# -- geometry helpers shared with tools/build_zones.py ------------------------------------------------

def haversine_many(lat, lng, lats, lngs):
    """Haversine distances in metres from (lat, lng) to arrays of points (panoloc.scoring.haversine_m, vectorised)."""
    lat1, lng1 = math.radians(lat), math.radians(lng)
    lat2, lng2 = np.radians(lats), np.radians(lngs)
    h = np.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def _scale(geom, k):
    """An affine copy with longitudes multiplied by k: a local equal-scale frame (containment is unchanged)."""
    return shapely.transform(geom, lambda xy: xy * np.array([k, 1.0]))


def representative_point(geom):
    """(lat, lng, radius_m, method): the centre of the largest inscribed circle of the largest part.

    Computed in a frame where a degree of longitude is scaled by cos(latitude), so the circle is round
    on the ground; the transform is affine, so the point stays inside. Falls back to point_on_surface
    in the rare case that rounding puts the centre on the boundary.
    """
    parts = shapely.get_parts(geom)
    south, north = shapely.bounds(geom)[1::2]
    k = math.cos(math.radians((south + north) / 2))
    scaled = _scale(parts, k)
    largest = scaled[int(np.argmax(shapely.area(scaled)))]
    xmin, ymin, xmax, ymax = largest.bounds
    tolerance = max(math.hypot(xmax - xmin, ymax - ymin) * 1e-4, 1e-7)
    circle = shapely.maximum_inscribed_circle(largest, tolerance)
    (x, y), (bx, by) = shapely.get_coordinates(circle)
    lat, lng = float(y), float(x / k)
    if shapely.contains_xy(geom, lng, lat):
        return lat, lng, float(math.hypot(bx - x, by - y) * M_PER_DEG), "inscribed_circle"
    p = shapely.point_on_surface(parts[int(np.argmax(shapely.area(scaled)))])
    return float(p.y), float(p.x), 0.0, "point_on_surface"


def area_km2(geom):
    """Geodesic area on the WGS84 ellipsoid, in km2. pyproj signs each ring's area by its orientation,
    so the polygons are oriented first (exteriors counter-clockwise, holes clockwise)."""
    from pyproj import Geod
    return abs(Geod(ellps="WGS84").geometry_area_perimeter(shapely.orient_polygons(geom))[0]) / 1e6


def hull_lnglat(geom):
    """The convex hull's vertices as an (n, 2) array of [lng, lat], ring closed."""
    return shapely.get_coordinates(shapely.convex_hull(geom))


def union(geoms):
    """Union of zone geometries: the fast exact coverage union when they form a valid coverage."""
    geoms = np.asarray(list(geoms), dtype=object)
    if len(geoms) == 1:
        return geoms[0]
    if shapely.coverage_is_valid(geoms):
        return shapely.coverage_union_all(geoms)
    return shapely.union_all(geoms)


def derive(leaves, coarse=()):
    """Zone rows (dicts with COLUMNS but the outline) and exact geometries, from leaves and the zones above.

    leaves: dicts with zone_id, name, level, country, parent_id, geometry (WGS84, x = longitude), and
    optionally deviation_m, source, source_code. coarse: the same without geometry, plus tree ("primary"
    by default) and also_in for zones listed in another tree. A coarse zone is the union of its children
    (and, for another tree's zone, of the zones listing it in also_in). Returns (rows, geometries).
    """
    records = {}
    for rec in leaves:
        records[rec["zone_id"]] = {**rec, "is_leaf": True}
    for rec in coarse:
        if rec["zone_id"] in records:
            raise ValueError(f"zone {rec['zone_id']} is listed twice")
        records[rec["zone_id"]] = {**rec, "is_leaf": False}
    for rec in records.values():
        rec.setdefault("tree", PRIMARY)
        rec["also_in"] = list(rec.get("also_in") or ())
    members = defaultdict(list)  # zone -> the zones it is the union of
    for zid, rec in records.items():
        parent = rec.get("parent_id")
        if parent is not None:
            if parent not in records:
                raise ValueError(f"zone {zid} has an unknown parent {parent}")
            if records[parent]["tree"] != rec["tree"]:
                raise ValueError(f"zone {zid} and its parent {parent} are in different trees")
            members[parent].append(zid)
        for other in rec["also_in"]:
            if other not in records or records[other]["tree"] == PRIMARY:
                raise ValueError(f"zone {zid}: also_in {other} is not a zone of another tree")
            members[other].append(zid)
    geometry, leaf_sets, depth = {}, {}, {}

    def build(zid, stack=()):
        if zid in geometry:
            return
        if zid in stack:
            raise ValueError(f"zone {zid} contains itself")
        rec = records[zid]
        if rec["is_leaf"]:
            if members[zid]:
                raise ValueError(f"leaf {zid} has zones under it")
            geom = rec["geometry"]
            if geom is None or shapely.is_empty(geom) or not shapely.is_valid(geom):
                raise ValueError(f"leaf {zid} has no valid geometry")
            geometry[zid], leaf_sets[zid] = geom, {zid}
            return
        if not members[zid]:
            raise ValueError(f"zone {zid} has no leaves under it")
        for m in members[zid]:
            build(m, (*stack, zid))
        geometry[zid] = union(geometry[m] for m in members[zid])
        leaf_sets[zid] = set().union(*(leaf_sets[m] for m in members[zid]))

    def depth_of(zid):
        if zid not in depth:
            parent = records[zid].get("parent_id")
            depth[zid] = 0 if parent is None else depth_of(parent) + 1
        return depth[zid]

    rows, geoms = [], []
    for zid, rec in records.items():
        build(zid)
        geom = geometry[zid]
        lat, lng, radius, method = representative_point(geom)
        west, south, east, north = (float(v) for v in shapely.bounds(geom))
        leaf_deviation = max(float(records[lf].get("deviation_m") or 0.0) for lf in leaf_sets[zid])
        rows.append({
            "zone_id": zid, "name": rec["name"], "short_name": rec.get("short_name") or rec["name"],
            "level": rec["level"], "country": rec["country"],
            "parent_id": rec.get("parent_id"), "tree": rec["tree"], "depth": depth_of(zid),
            "is_leaf": rec["is_leaf"], "also_in": rec["also_in"], "area_km2": area_km2(geom),
            "rep_lat": lat, "rep_lng": lng, "rep_radius_m": radius, "rep_method": method,
            "south": south, "west": west, "north": north, "east": east, "deviation_m": leaf_deviation,
            "hull": hull_lnglat(geom), "source": rec.get("source", ""), "source_code": rec.get("source_code", ""),
            "n_children": len(members[zid]), "n_leaves": len(leaf_sets[zid]),
            "n_parts": int(shapely.get_num_geometries(geom)),
            "n_vertices": int(shapely.get_num_coordinates(geom)),
        })
        geoms.append(geom)
    return rows, geoms


class Zones:
    """Read-only zone index (module docstring). Build one with Zones.open() or Zones.from_leaves()."""

    def __init__(self, rows, geometries, *, path=None, meta=None, snap_m=SNAP_M):
        self.path = None if path is None else Path(path)
        self.meta = meta or {}
        self.snap_m = float(snap_m)
        self._geoms = np.asarray(geometries, dtype=object)
        self._hull_raw = [r["hull"] for r in rows]
        self._hulls = {}
        raw = {r["zone_id"]: r for r in rows}
        self._index = {r["zone_id"]: i for i, r in enumerate(rows)}
        self._zones = {}
        for r in rows:
            above = raw.get(r["parent_id"]) if r["parent_id"] else None
            parent = None if above is None else (above.get("short_name") or above["name"], above["level"])
            self._zones[r["zone_id"]] = self._zone_of(r, parent)
        self._children = defaultdict(list)  # (tree, parent ID or None) -> zones
        self._members = defaultdict(list)  # zone of another tree -> zones listing it in also_in
        for z in self._zones.values():
            self._children[(z.tree, z.parent_id)].append(z)
            for other in z.also_in:
                self._members[other].append(z)
        for kids in (*self._children.values(), *self._members.values()):
            kids.sort(key=lambda z: (normalise(z.short_name), z.id))  # "Évora" before "Porto"
        leaves = [i for i, r in enumerate(rows) if r["is_leaf"]]
        self._leaf_ids = [rows[i]["zone_id"] for i in leaves]
        self._leaf_geoms = self._geoms[leaves] if leaves else np.array([], dtype=object)
        self._prepared = np.zeros(len(leaves), dtype=bool)
        self._tree = shapely.STRtree(self._leaf_geoms)
        self._chains = {}
        self._exact = {}
        self._locate = functools.lru_cache(maxsize=LOCATE_CACHE)(self._locate_uncached)

    @staticmethod
    def _zone_of(r, parent):
        """A Zone from a row; parent is (short name, level) of the zone above it, or None."""
        also = r["also_in"]
        if isinstance(also, str):
            also = json.loads(also) if also else []
        name, level, country = r["name"], r["level"], r["country"]
        short = r.get("short_name") or name
        return Zone(
            id=r["zone_id"], name=name, level=level, country=country, parent_id=r["parent_id"] or None,
            tree=r["tree"] or PRIMARY, depth=int(r["depth"]), is_leaf=bool(r["is_leaf"]), also_in=tuple(also),
            area_km2=float(r["area_km2"]), rep=(float(r["rep_lat"]), float(r["rep_lng"])),
            rep_radius_m=float(r["rep_radius_m"]),
            bbox=(float(r["south"]), float(r["west"]), float(r["north"]), float(r["east"])),
            deviation_m=float(r["deviation_m"]), source=r["source"] or "", source_code=r["source_code"] or "",
            n_children=int(r["n_children"]), n_leaves=int(r["n_leaves"]), short_name=short,
            label=zone_label(short, level, parent[0] if parent else None),
            description=describe(short, level, country, parent), search_text=search_text(short, level, country, parent))

    # -- loading ---------------------------------------------------------------------------------------

    @classmethod
    def open(cls, path=DEFAULT_PATH, snap_m=SNAP_M):
        """The index built by tools/build_zones.py; ZonesNotBuilt (a FileNotFoundError) when it is missing."""
        path = Path(path)
        if not path.is_file():
            raise ZonesNotBuilt(f"no zone index at {path}: build it with .venv/bin/python -I tools/build_zones.py")
        info = pyogrio.read_info(path, layer=LAYER)
        schema = (info.get("layer_metadata") or {}).get("schema")
        if schema != SCHEMA:
            raise RuntimeError(f"{path} has schema {schema!r}, expected {SCHEMA!r}: rebuild it with "
                               ".venv/bin/python -I tools/build_zones.py")
        meta_, _, wkb, fields = pyogrio.raw.read(path, layer=LAYER)
        columns = dict(zip(meta_["fields"], fields))
        missing = [c for c in COLUMNS if c not in columns]
        if missing:
            raise RuntimeError(f"{path} lacks columns {missing}: rebuild it")
        rows = [dict(zip(COLUMNS, values)) for values in zip(*(columns[c] for c in COLUMNS))]
        for r in rows:
            r["also_in"] = json.loads(r["also_in"]) if r["also_in"] else []
        sidecar = path.with_suffix(".json")
        meta = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else {}
        return cls(rows, shapely.from_wkb(wkb), path=path, meta=meta, snap_m=snap_m)

    @classmethod
    def from_leaves(cls, leaves, coarse=(), snap_m=SNAP_M):
        """An in-memory index from leaf polygons and the zones above them (see derive())."""
        rows, geoms = derive(leaves, coarse)
        return cls(rows, geoms, snap_m=snap_m)

    def close(self):
        """Nothing to release; kept so Zones works like NameIndex in a with block."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __len__(self):
        return len(self._zones)

    def __iter__(self):
        return iter(self._zones.values())

    @property
    def version(self):
        """A short build identity for run logs."""
        built = self.meta.get("built_utc")
        return f"{SCHEMA} built {built}" if built else SCHEMA

    # -- lookups ---------------------------------------------------------------------------------------

    def get(self, zone):
        """The Zone for an ID (a Zone is returned as is); KeyError when unknown."""
        if isinstance(zone, Zone):
            return zone
        try:
            return self._zones[zone]
        except KeyError:
            raise KeyError(f"no zone {zone!r}") from None

    def __contains__(self, zone_id):
        return zone_id in self._zones

    def roots(self):
        """The countries: the zones that tile the whole allowed area."""
        return list(self._children[(PRIMARY, None)])

    def children(self, zone=None, tree=PRIMARY):
        """The zones directly under `zone` (None: the countries). Another tree (tree="nuts") starts under
        a country with its own top zones; there a zone's children are its subzones in that tree, or else
        the primary zones listing it in also_in (NUTS 3 > municipalities > parishes)."""
        if zone is None:
            return list(self._children[(tree, None)])
        z = self.get(zone)
        if z.level == "country" and tree != PRIMARY:
            return [k for k in self._children[(tree, None)] if k.country == z.country]
        kids = self._children[(z.tree, z.id)]
        if not kids and z.tree != PRIMARY:
            kids = self._members[z.id]
        return list(kids)

    def parent(self, zone):
        z = self.get(zone)
        return self._zones[z.parent_id] if z.parent_id else None

    def ancestors(self, zone, include_self=True):
        """The zones above `zone` in its tree, coarsest first (the zone itself last when include_self)."""
        z = self.get(zone)
        chain = [z] if include_self else []
        while z.parent_id:
            z = self._zones[z.parent_id]
            chain.append(z)
        return chain[::-1]

    def is_within(self, zone, other):
        """True when `zone` is `other` or lies inside it, in any tree."""
        z, other = self.get(zone), self.get(other)
        if other.level == "country" and other.tree == PRIMARY:
            return z.country == other.country
        for a in self.ancestors(z):
            if a.id == other.id or any(b.id == other.id for x in a.also_in for b in self.ancestors(x)):
                return True
        return False

    def leaves(self, zone):
        """The leaf zones the zone is the union of."""
        z = self.get(zone)
        if z.is_leaf:
            return [z]
        out = []
        for kid in self.children(z, tree=z.tree):
            out.extend(self.leaves(kid))
        return sorted({k.id: k for k in out}.values(), key=lambda k: k.id)

    def search(self, text, level=None, country=None):
        """Zones whose name matches `text` (accents, case and punctuation ignored), exact names first."""
        key = normalise(text)
        exact, partial = [], []
        for z in self._zones.values():
            if (level and z.level != level) or (country and z.country != country):
                continue
            names = {normalise(z.name), normalise(z.short_name), normalise(display_name(z.name, z.level))}
            if key in names:
                exact.append(z)
            elif key and any(key in n for n in names):
                partial.append(z)
        return sorted(exact, key=lambda z: z.depth) + sorted(partial, key=lambda z: (z.depth, z.name))

    # -- geometry --------------------------------------------------------------------------------------

    def geometry(self, zone):
        """The zone's stored geometry (WGS84, x = longitude). For a leaf, the exact zone."""
        return self._geoms[self._index[self.get(zone).id]]

    def exact_geometry(self, zone):
        """The union of the zone's leaves: the region containment and bounds refer to (cached)."""
        z = self.get(zone)
        if z.is_leaf:
            return self.geometry(z)
        if z.id not in self._exact:
            self._exact[z.id] = union(self.geometry(k) for k in self.leaves(z))
        return self._exact[z.id]

    def hull(self, zone):
        """The convex hull vertices of the zone's leaves, (n, 2) [lng, lat]."""
        z = self.get(zone)
        if z.id not in self._hulls:
            raw = self._hull_raw[self._index[z.id]]
            self._hulls[z.id] = np.asarray(json.loads(raw) if isinstance(raw, str) else raw, dtype=float)
        return self._hulls[z.id]

    def bound_m(self, point, zone):
        """Conservative maximum distance in metres from `point` (lat, lng) to anywhere in the zone."""
        z = self.get(zone)
        lat, lng = (float(v) for v in point)
        hull = self.hull(z)
        farthest = float(haversine_many(lat, lng, hull[:, 1], hull[:, 0]).max())
        value = (farthest + z.deviation_m) * (1 + BOUND_RELATIVE_MARGIN) + BOUND_ABSOLUTE_MARGIN_M
        return math.ceil(value * 10) / 10

    def outline(self, zone, max_points=150):
        """A GeoJSON Polygon for drawing the zone ([lng, lat]): the outer ring of its largest part,
        simplified to at most max_points points; None when that part covers under 80% of the zone."""
        z = self.get(zone)
        geom = self.geometry(z)
        parts = shapely.get_parts(geom)
        k = math.cos(math.radians((z.bbox[0] + z.bbox[2]) / 2))
        areas = shapely.area(_scale(parts, k))
        if areas.sum() <= 0 or areas.max() < 0.8 * areas.sum():
            return None
        ring = shapely.Polygon(parts[int(np.argmax(areas))].exterior)
        size = math.hypot(z.bbox[3] - z.bbox[1], z.bbox[2] - z.bbox[0])
        tolerance = size / 400
        simple = ring
        for _ in range(12):
            simple = shapely.simplify(ring, tolerance, preserve_topology=True)
            if shapely.get_num_coordinates(simple) <= max_points:
                break
            tolerance *= 1.6
        coords = [[round(float(x), 5), round(float(y), 5)] for x, y in shapely.get_coordinates(simple.exterior)]
        return {"type": "Polygon", "coordinates": [coords]}

    # -- containment -----------------------------------------------------------------------------------

    def locate(self, lat, lng, snap_m=None):
        """The Location of (lat, lng): its chain from the country down to the leaf, or None when the
        point is farther than snap_m (default self.snap_m, 1 km) from every zone."""
        return self._locate(float(lat), float(lng), self.snap_m if snap_m is None else float(snap_m))

    def contains(self, zone, point):
        """True when `point` (lat, lng) lies in the zone, counting a snap to it (locate)."""
        loc = self.locate(*point)
        return loc is not None and self.get(zone).id in loc.ids

    @functools.cached_property
    def _leaf_deviations(self):
        return np.array([self._zones[z].deviation_m for z in self._leaf_ids], dtype=float)

    def on_land(self, point, tolerance_m=25.0):
        """True when `point` (lat, lng) lies in a leaf zone, or within tolerance_m plus that leaf's
        deviation_m of one: the stored outline is simplified by up to deviation_m, so a beach or a pier
        on true land can lie that far outside it. Never the 1 km snap of locate (T42: no point at sea)."""
        lat, lng = float(point[0]), float(point[1])
        if self.locate(lat, lng, snap_m=0) is not None:
            return True
        if not len(self._leaf_ids):
            return False
        reach = tolerance_m + float(self._leaf_deviations.max())
        return any(d <= tolerance_m + self._leaf_deviations[i] for d, i in self._nearest_leaves(lat, lng, reach))

    def land_parts(self, geom):
        """[(part, deviation_m)]: the leaves meeting `geom`'s bounding box (WGS84), clipped to that box,
        each with its leaf's deviation_m (T42: land around an area, true coast within the deviation)."""
        west, south, east, north = (float(v) for v in shapely.bounds(geom))
        found = self._tree.query(shapely.box(west, south, east, north))
        out = []
        for i in sorted(int(k) for k in found):
            part = shapely.clip_by_rect(self._leaf_geoms[i], west, south, east, north)
            if not shapely.is_valid(part):
                part = shapely.make_valid(part)
            out += [(p, float(self._leaf_deviations[i])) for p in shapely.get_parts(part)
                    if p.geom_type in ("Polygon", "MultiPolygon") and not shapely.is_empty(p)]
        return out

    def land(self, geom):
        """The leaves meeting `geom`'s bounding box (WGS84), clipped to that box and merged: the land
        (with the inland waters the sources include) around an area. Empty at sea (T42)."""
        parts = [p for p, _ in self.land_parts(geom)]
        return shapely.union_all(parts) if parts else shapely.Polygon()

    def _leaf(self, i):
        if not self._prepared[i]:
            shapely.prepare(self._leaf_geoms[i])
            self._prepared[i] = True
        return self._leaf_geoms[i]

    def _location(self, i, distance_m):
        if i not in self._chains:
            chain = tuple(self.ancestors(self._leaf_ids[i]))
            also = {}
            for z in chain:
                for other in z.also_in:
                    for a in self.ancestors(other):
                        also[a.id] = a
            self._chains[i] = (chain, tuple(also.values()))
        chain, also = self._chains[i]
        return Location(chain, distance_m, also)

    def _locate_uncached(self, lat, lng, snap_m):
        if not (math.isfinite(lat) and math.isfinite(lng)):
            raise ValueError(f"not a coordinate: {lat}, {lng}")
        for i in sorted(self._tree.query(shapely.Point(lng, lat))):
            if shapely.intersects_xy(self._leaf(i), lng, lat):
                return self._location(i, 0.0)
        if snap_m <= 0:
            return None
        nearest = self._nearest_leaves(lat, lng, snap_m)
        if nearest and nearest[0][0] <= snap_m:
            distance, i = nearest[0]
            return self._location(i, max(distance, 1e-3))
        return None

    def _nearest_leaves(self, lat, lng, reach_m):
        """[(distance_m, leaf index)] of the leaves within reach_m of the point, nearest first."""
        dlat = reach_m / M_PER_DEG
        dlng = reach_m / (M_PER_DEG * max(math.cos(math.radians(lat)), 1e-6))
        window = (lng - dlng, lat - dlat, lng + dlng, lat + dlat)
        found = []
        for i in self._tree.query(shapely.box(*window)):
            d = self._distance_m(self._leaf_geoms[i], lat, lng, window)
            if d <= reach_m:
                found.append((d, int(i)))
        return sorted(found)

    @staticmethod
    def _distance_m(geom, lat, lng, window=None):
        """Metres from (lat, lng) to the geometry, in a local equirectangular frame centred on the point
        (accurate to well under 0.1% within a few km). `window` clips the geometry first."""
        if window is not None:
            geom = shapely.clip_by_rect(geom, *window)
            if shapely.is_empty(geom):
                return math.inf
        k = math.cos(math.radians(lat)) * M_PER_DEG
        local = shapely.transform(geom, lambda xy: (xy - np.array([lng, lat])) * np.array([k, M_PER_DEG]))
        return float(shapely.distance(shapely.Point(0.0, 0.0), local))

    def distance_m(self, point, zone):
        """Approximate metres from `point` (lat, lng) to the zone's stored geometry; 0 inside the zone.
        For choosing the nearest zone of a far point (a local projection, less exact far away, and a
        coarser zone's outline is simplified), never for bounds."""
        z = self.get(zone)
        if self.contains(z, point):
            return 0.0
        lat, lng = (float(v) for v in point)
        return self._distance_m(self.geometry(z), lat, lng)

    def nearest(self, point, zones=None):
        """(zone, distance_m) of the zone nearest to `point` among `zones` (IDs or Zones; default the
        countries), whatever the distance."""
        candidates = [self.get(z) for z in (zones if zones is not None else self.roots())]
        if not candidates:
            raise ValueError("no zones to choose from")
        scored = [(self.distance_m(point, z), z.depth, z.id, z) for z in candidates]
        d, _, _, z = min(scored, key=lambda s: s[:3])
        return z, d

    # -- candidates ------------------------------------------------------------------------------------

    def candidate(self, zone, weight=1.0, source=None, label=None):
        """The zone as an `area` Candidate: its representative point, with extent_m = bound_m from it.

        For a zone the team picked that holds no hypothesis (T42): the point marks the zone, not the
        camera, and the extent covers the whole zone.
        """
        z = self.get(zone)
        bound = self.bound_m(z.rep, z)
        return Candidate(z.rep[0], z.rep[1], "area", source or f"zone:{z.id}", label=label or z.label,
                         weight=weight, extent_m=bound, country=z.country,
                         details={"zone_id": z.id, "level": z.level, "area_km2": round(z.area_km2, 3),
                                  "bound_m": bound, "extent_source": "geometric_bound",
                                  "point": "the zone's representative point (its largest inscribed circle's "
                                           "centre), not a camera position"})

    def spread(self, zone, weight=1.0, tree=PRIMARY):
        """`weight` spread over the zone: one area Candidate per subzone (a zone with one subzone is
        looked through), in proportion to their areas; the zone itself when it has none.

        Questions and expected gains treat hypotheses as points, so a single point for a zone the team
        picked would put all its weight in one subzone. Spread points let the next question split the
        zone (until T42's cells take over).
        """
        z = self.get(zone)
        kids = self.children(z, tree=tree)
        while len(kids) == 1 and self.children(kids[0], tree=tree):
            kids = self.children(kids[0], tree=tree)
        if not kids:
            return [self.candidate(z, weight)]
        total = sum(k.area_km2 for k in kids)
        out = []
        for k in kids:
            c = self.candidate(k, weight * k.area_km2 / total)
            c.details["spread_of"] = z.id
            out.append(c)
        return out
