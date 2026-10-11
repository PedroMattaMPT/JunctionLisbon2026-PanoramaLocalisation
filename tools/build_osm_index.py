#!/usr/bin/env python3
"""Build the OSM name indexes Data/index/osm_<CC>.sqlite read by panoloc.names (TASKS.md T31, PLAN.md 4.4).

One database per country, from the Geofabrik extract in Data/geo/osm/ (pyosmium). NameIndex.open()
attaches every osm_<CC>.sqlite next to names.sqlite; names.sqlite itself is never touched, only read
to link OSM objects to its Wikidata and GeoNames entries. The extracts are downloaded files, so every
value is checked (identifiers, finite WGS84 points, postcode formats) and SQL is parameterised.

What is extracted (KEY_ORDER and RULES; the first key of an object with a rule decides):
  named objects  shop, amenity, tourism, leisure, historic, office, craft, healthcare, railway stations
                 and halts, public_transport stations, aerodromes, man_made landmarks, natural features,
                 named landuse, named buildings, waterfalls and dams, motorway service areas, place=*.
                 Nodes and ways; relations are not read. Names: name, the name:<lang> tags of
                 panoloc.names (labels), official_name, short_name, alt_name, loc_name, old_name and brand
                 (aliases; ";" splits several). An object with a brand but no name is labelled by it.
  streets        named highway ways (STREET_CLASSES, no *_link). One street is many ways: ways with the
                 same normalised name merge when they share an end node or come within about
                 STREET_MERGE_M of each other (a STREET_CELL_M grid, 3 x 3 neighbourhood). The point of a
                 merged street is its median node (the node nearest the coordinate-wise median of its
                 nodes, so it lies ON the street) and its extent the farthest node from it, + STREET_HALF_WIDTH_M.
                 Ways are sampled to at most STREET_SAMPLE nodes besides their ends.
  postcodes      addr:postcode of every object (nodes, and ways at a few sampled nodes), aggregated per
                 (country, code): the median point (the address nearest the coordinate-wise median),
                 the count, and the spread (p50, p90 and max distance from the median point, after
                 dropping outliers: farther than POSTCODE_OUTLIER x p50 and the kind's minimum).
                 extent_m = max(p90, the kind's floor). PT 4-3 codes are street-level; ES and FR
                 5-digit codes commune-level; PT 4-digit prefixes aggregate all their codes' addresses.
Objects of the same name and role within POI_MERGE_M merge too (a shop node inside its building way).
An object is kept when its point lies in its country's outline (geoBoundaries ADM0; ADM1 regions for
France, whose ADM0 is simplified) or within BORDER_TOLERANCE_M of it and inside no other country's
outline: Geofabrik extracts reach a few km over the border.

Roles and extents. Shops, buildings, stations and other POIs are `landmark`; streets, squares,
places, natural extents, named landuse and postcodes are `area`. Nothing is `camera`. A way's extent
is its footprint (farthest node from its point, details["extent_source"] "source"); a node takes the
type's assumed radius (RULES, "assumed").

Prior (place.prominence, read by panoloc.names as prior = 0.2 + 0.8 x prominence): the type's
prominence from RULES (a railway station 0.35, a castle 0.35, a shop 0.04, a residential street
0.1), raised to the linked Wikidata/GeoNames entry's prominence when there is one. Chains and generic
names are handled at lookup through name.occ, the number of entries carrying that normalised name in
the country ("Pingo Doce", "Rua da Igreja", "Farmácia").

Linking. An object with wikidata=Q... is that Wikidata item when names.sqlite has it ("wikidata
tag"). Objects of LINK_FAMILIES (places, natural features, heritage, stations, streets, squares ...)
also link to a names.sqlite entry sharing a squashed name within LINK_LANDMARK_M (landmarks) or, for
areas, half the smaller extent between LINK_RADIUS_M and LINK_MAX_M ("name within ..."). A linked
object takes the entry's group, or "same-place:<entry source>" when the entry has none; that override
is stored in main_group, so the entry reports the same group when the OSM index is attached.

Tables (as in names.sqlite, so panoloc.names searches both the same way):
  place      one row per entry; id = OSM_ID_OFFSET[country] + n; source "osm:n123" / "osm:w456"
  name       (place, normalised name) rows sorted by prior / occ, with the squashed and core keys, and occ
  ftok, tokdf, fkey, fgram   word and trigram indexes (tools/build_name_index.py)
  link       place -> names.sqlite source, distance and how; main_group: names.sqlite source -> group
  postcode   OSM aggregates, same columns as names.sqlite's postcode table
  meta       schema, country, id offset, extract (replication timestamp and sequence, size, md5), stats

Work files go to Data/index/tmp/osm_<CC>/ (never /tmp, a RAM disk on the dev laptop): the staging
database and the node locations. The build is resumable: pass 1 (tagged nodes and ways) and pass 2
(the locations of the nodes those ways need, through an IdFilter per node-id range so memory stays
bounded) are checkpointed, and a rerun continues after the last finished pass when the input and
the script version are unchanged. The database is written to <out>.tmp-<pid> and renamed when complete.

Usage (from the repo root, with the venv: pyosmium, numpy and shapely; -I because it reads downloaded files):
  .venv/bin/python -I tools/build_osm_index.py PT        # Data/index/osm_PT.sqlite
  .venv/bin/python -I tools/build_osm_index.py ES FR --out-suffix .pending   # osm_ES.pending.sqlite ...: not attached
  nohup nice -n 19 ionice -c3 .venv/bin/python -I tools/build_osm_index.py FR > Data/index/osm_FR.log 2>&1 &
  .venv/bin/python -I tools/build_osm_index.py PT --pbf FILE --out FILE --names FILE --outline none
Measured on the dev laptop, niced, with other jobs running (2026-10-08 Geofabrik extracts):
  PT  425 MB extract: 136 s (pass 1 39 s, pass 2 15 s), peak RSS 1.2 GB, 365 MB; 491,110 entries (221,145
      streets from 417,164 ways, 274,277 POIs and places from 283,207 objects, 4,312 dropped over the border),
      525,216 names, 41,990 links (13,441 by wikidata tag), 44,596 postcodes and 808 prefixes from 560,439 addresses
  ES  1.5 GB extract: 537 s (pass 1 169 s, pass 2 66 s), peak RSS 1.6 GB, 1.5 GB; 2,361,983 entries (750,597
      streets from 1,763,330 ways, 1,613,714 POIs and places), 2,525,023 names, 220,449 links (109,868 by
      wikidata tag), 7,624 postcodes from 1,664,686 addresses
  FR  5.0 GB extract: 1,212 s (pass 1 331 s, pass 2 166 s for 40.3M nodes), peak RSS 2.6 GB, 2.9 GB;
      4,656,862 entries (1,930,755 streets from 3,786,872 ways, 2,729,396 POIs and places), 4,808,791 names,
      459,251 links (139,293 by wikidata tag), 7,201 postcodes from 1,618,158 addresses
  The work folder peaks at about 3x the output (FR: 4.2 GB staging + 0.6 GB node arrays) and is removed after a build.
"""
import argparse
import array
import json
import math
import os
import re
import resource
import shutil
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from panoloc import names as N  # noqa: E402
from panoloc.scoring import haversine_m  # noqa: E402
import build_name_index as B  # noqa: E402

SCRIPT_VERSION = 1  # bump when pass 1 or pass 2 change: a resumed build then starts over
PBF = {"PT": "portugal-latest.osm.pbf", "ES": "spain-latest.osm.pbf", "FR": "france-latest.osm.pbf"}
OSM_DIR = ROOT / "Data" / "geo" / "osm"
OUTLINES = {"PT": ["PRT-ADM0.geojson"], "ES": ["ESP-ADM0.geojson"], "FR": ["FRA-ADM1.geojson"]}
OUTLINE_DIR = ROOT / "Data" / "geo" / "boundaries" / "geoboundaries"
WORK_DIR = ROOT / "Data" / "index" / "tmp"

PASS1_KEYS = ("name", "brand", "addr:postcode")
STREET_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                  "living_street", "pedestrian", "service", "track", "road", "busway", "footway", "path",
                  "cycleway", "steps", "bridleway"}
STREET_PROMINENCE = {"motorway": 0.12, "trunk": 0.12, "primary": 0.15, "secondary": 0.15, "tertiary": 0.12,
                     "residential": 0.1, "living_street": 0.1, "pedestrian": 0.12, "unclassified": 0.06,
                     "road": 0.06, "service": 0.05, "busway": 0.05, "track": 0.04, "footway": 0.05, "path": 0.04,
                     "cycleway": 0.04, "steps": 0.05, "bridleway": 0.04}
STREET_SAMPLE = 16       # interior nodes kept per street way, besides both ends
STREET_MERGE_M = 400.0   # same-name ways about this close are one street
STREET_CELL_M = STREET_MERGE_M / 2
STREET_HALF_WIDTH_M = 10.0
STREET_MIN_EXTENT_M = 25.0
WAY_SAMPLE = 200         # nodes kept per POI way
POSTCODE_WAY_SAMPLE = 4  # nodes averaged for an address way (a building)
POI_MERGE_M = 40.0
MIN_FOOTPRINT_M = 8.0
BORDER_TOLERANCE_M = 2000.0
LINK_LANDMARK_M = 300.0
LINK_RADIUS_M, LINK_MAX_M = B.LINK_RADIUS_M, B.LINK_MAX_M
NODE_CHUNK_IDS = 1000 << 22  # node ids per pass-2 IdFilter: its bitset takes at most 512 MB
MAX_LIST = 10
BATCH = 50_000
OSM_LANGS = ("pt", "es", "fr", "en", "ca", "gl", "eu")
QID = re.compile(r"^Q[1-9]\d{0,11}$")
KEEP_TAGS = ("name", "alt_name", "old_name", "official_name", "short_name", "loc_name", "brand", "brand:wikidata",
             "operator", "wikidata", "addr:street", "addr:housenumber", "addr:postcode", "addr:city", "addr:place",
             *(f"name:{lang}" for lang in OSM_LANGS))
MAX_TAG_CHARS = 200

# -- postcodes ---------------------------------------------------------------------------------------
POSTCODE_RE = {"PT": re.compile(r"^\s*(?:PT?\s*-?\s*)?(\d{4})(?:\s*[-‐‑–—]?\s*(\d{3}))?(?!\d)"),
               "ES": re.compile(r"^\s*(?:E\s*-?\s*)?(\d{5})(?!\d)"),
               "FR": re.compile(r"^\s*(?:F\s*-?\s*)?(\d{5})(?!\d)")}
POSTCODE_FLOOR_M = {("PT", "code"): 50.0, ("PT", "prefix"): 500.0, ("ES", "code"): 300.0, ("FR", "code"): 300.0}
POSTCODE_FEW = 5             # fewer addresses than this: at least POSTCODE_FEW_FLOOR_M
POSTCODE_FEW_FLOOR_M = {"code": 100.0, "prefix": 1000.0}
POSTCODE_OUTLIER = 5.0       # an address farther than 5 x p50 ...
POSTCODE_OUTLIER_MIN_M = {("PT", "code"): 1000.0, ("PT", "prefix"): 5000.0, ("ES", "code"): 15000.0,
                          ("FR", "code"): 15000.0}  # ... and than this is an outlier (a typo, a mis-tag)


def valid_postcode(country, value):
    """(code, prefix) for an addr:postcode value: PT ("1100-148", "1100") or 5-digit ES / FR codes; None if not one."""
    m = POSTCODE_RE[country].match(value or "")
    if not m:
        return None
    if country == "PT":
        head, tail = m.group(1), m.group(2)
        if head[0] == "0":
            return None
        return (f"{head}-{tail}" if tail else None), head
    code = m.group(1)
    if country == "ES" and not 1 <= int(code[:2]) <= 52:
        return None
    if country == "FR" and not (1 <= int(code[:2]) <= 95):
        return None
    return code, None


# -- what to extract: key -> {value: (role, extent_m, prominence)}; "*" for any other value ---------------
# Keys are tried in KEY_ORDER; the first with a matching rule decides. a = area, l = landmark.
_RULES = """
place       city:a:8000:.6 town:a:1500:.45 village:a:600:.3 hamlet:a:300:.15 isolated_dwelling:a:100:.05
            farm:a:200:.05 suburb:a:1500:.3 borough:a:3000:.35 quarter:a:700:.25 neighbourhood:a:400:.2
            city_block:a:100:.05 locality:a:300:.1 square:a:60:.2 island:a:2000:.3 islet:a:100:.1
railway     station:l:100:.35 halt:l:30:.2 tram_stop:l:15:.08
public_transport  station:l:100:.3
aeroway     aerodrome:a:1500:.3 terminal:l:100:.1 heliport:l:50:.05
historic    castle:l:80:.35 fort:l:100:.25 monastery:l:80:.3 palace:l:80:.3 church:l:25:.2 chapel:l:12:.12
            ruins:l:50:.15 archaeological_site:l:100:.2 monument:l:10:.2 memorial:l:8:.12 city_gate:l:10:.2
            tower:l:15:.2 manor:l:40:.15 pillory:l:5:.15 aqueduct:l:300:.25 bridge:l:100:.2
            wayside_cross:l:5:.05 wayside_shrine:l:5:.05 boundary_stone:l:5:.03 milestone:l:5:.03 *:l:20:.12
tourism     museum:l:50:.3 attraction:l:50:.25 viewpoint:l:30:.2 artwork:l:8:.1 gallery:l:30:.12
            hotel:l:30:.12 motel:l:30:.08 hostel:l:15:.08 guest_house:l:15:.08 apartment:l:20:.05
            chalet:l:20:.05 alpine_hut:l:20:.1 wilderness_hut:l:15:.08 camp_site:a:150:.1 caravan_site:a:150:.08
            picnic_site:l:50:.05 zoo:a:300:.3 theme_park:a:300:.3 aquarium:l:60:.3 information:l:10:.05
            *:l:30:.08
amenity     place_of_worship:l:25:.15 monastery:l:80:.3 townhall:l:30:.25 courthouse:l:30:.15
            university:l:200:.3 college:l:80:.15 school:l:50:.1 kindergarten:l:25:.05 library:l:25:.12
            hospital:l:100:.25 clinic:l:25:.08 doctors:l:15:.04 dentist:l:15:.03 pharmacy:l:12:.05
            bank:l:15:.04 post_office:l:15:.08 police:l:20:.08 fire_station:l:25:.08 theatre:l:40:.2
            cinema:l:40:.12 arts_centre:l:40:.15 community_centre:l:30:.08 marketplace:l:50:.15
            bus_station:l:50:.25 ferry_terminal:l:60:.25 fuel:l:25:.05 parking:l:40:.03 fountain:l:8:.1
            restaurant:l:12:.05 cafe:l:12:.05 bar:l:12:.04 pub:l:12:.04 fast_food:l:12:.03 ice_cream:l:10:.03
            *:l:20:.04
shop        mall:l:150:.15 department_store:l:50:.1 supermarket:l:40:.05 *:l:15:.04
leisure     park:a:300:.15 garden:a:150:.12 nature_reserve:a:3000:.15 golf_course:a:600:.15 marina:a:300:.2
            stadium:l:120:.3 sports_centre:l:50:.08 water_park:l:200:.15 common:a:300:.1 beach_resort:a:300:.1
            pitch:l:40:.04 swimming_pool:l:30:.05 playground:l:30:.03 fitness_centre:l:20:.03 *:l:30:.05
man_made    lighthouse:l:15:.3 tower:l:15:.12 bridge:l:100:.2 water_tower:l:15:.1 windmill:l:15:.12
            pier:l:100:.15 breakwater:l:200:.1 obelisk:l:8:.12 cross:l:5:.05 chimney:l:10:.05 works:l:150:.05
            *:l:20:.04
natural     peak:a:300:.15 volcano:a:1500:.25 saddle:a:200:.08 ridge:a:2000:.1 hill:a:600:.1 valley:a:3000:.1
            cliff:a:300:.1 beach:a:400:.2 bay:a:3000:.2 cape:a:300:.2 peninsula:a:3000:.15 isthmus:a:1000:.1
            strait:a:3000:.15 reef:a:500:.08 shoal:a:500:.05 water:a:800:.15 wetland:a:1500:.08 wood:a:3000:.1
            heath:a:1000:.06 scrub:a:500:.04 grassland:a:500:.04 sand:a:300:.06 dune:a:500:.08 glacier:a:1500:.1
            spring:l:15:.08 cave_entrance:l:30:.12 rock:l:30:.05 stone:l:10:.05 tree:l:10:.05 arch:l:20:.12
waterway    waterfall:l:40:.15 dam:l:150:.15 weir:l:30:.05
highway     services:l:100:.08 rest_area:l:80:.05
landuse     residential:a:400:.1 industrial:a:500:.08 commercial:a:300:.08 retail:a:300:.08 military:a:1000:.08
            cemetery:a:100:.08 *:a:300:.04
office      *:l:15:.03
craft       *:l:15:.03
healthcare  *:l:25:.04
building    church:l:25:.15 cathedral:l:60:.3 chapel:l:12:.12 train_station:l:100:.3 *:l:25:.06
"""
RULES = {}
for _line in re.findall(r"^(\w+)\s+(.+(?:\n {12}.+)*)", _RULES, re.M):
    RULES[_line[0]] = {v: ({"a": "area", "l": "landmark"}[r], float(e), float(p))
                       for v, r, e, p in (item.split(":") for item in _line[1].split())}
KEY_ORDER = ("place", "railway", "public_transport", "aeroway", "historic", "tourism", "amenity", "shop", "leisure",
             "man_made", "natural", "waterway", "highway", "landuse", "office", "craft", "healthcare", "building")
EXCLUDE = {  # street furniture and services whose names say nothing about the place
    "amenity": {"atm", "bench", "bicycle_parking", "bicycle_rental", "post_box", "vending_machine", "waste_basket",
                "waste_disposal", "recycling", "parking_space", "parking_entrance", "toilets", "drinking_water",
                "shelter", "charging_station", "telephone", "clock", "bbq", "grit_bin", "hunting_stand", "water_point",
                "watering_place", "motorcycle_parking", "taxi", "car_sharing", "compressed_air", "loading_dock",
                "table", "lounger", "shower", "photo_booth", "ticket_validator", "feeding_place", "give_box",
                "letter_box", "public_bookcase", "bicycle_repair_station", "device_charging_station", "smoking_area",
                "trolley_bay", "parcel_locker", "dog_toilet"},
    "man_made": {"street_cabinet", "manhole", "pipeline", "utility_pole", "surveillance", "flagpole", "pole",
                 "cable_distribution_cabinet", "monitoring_station", "petroleum_well", "embankment", "cutline", "dyke",
                 "goods_conveyor", "clearcut"},
    "leisure": {"picnic_table", "firepit", "bleachers", "outdoor_seating", "slipway", "bandstand"},
    "historic": {"tomb", "grave"},
}
# Families whose objects may also be in names.sqlite under the same name (name-and-distance links)
LINK_FAMILIES = {"place", "railway", "public_transport", "aeroway", "historic", "tourism", "natural", "waterway",
                 "man_made", "street", "landuse", "building", "leisure", "amenity"}
LINK_AMENITY = {"place_of_worship", "monastery", "townhall", "courthouse", "university", "college", "school", "library",
                "hospital", "theatre", "cinema", "arts_centre", "marketplace", "bus_station", "ferry_terminal",
                "fountain"}


def classify(tags):
    """(rule, family, role, extent_m, prominence) for a tag dict, or None."""
    for key in KEY_ORDER:
        value = tags.get(key)
        if value is None:
            continue
        table = RULES[key]
        if value in EXCLUDE.get(key, ()):
            continue
        if key == "tourism" and value == "information" and tags.get("information") not in ("office", "visitor_centre"):
            continue
        hit = table.get(value)
        rule = f"{key}={value}"
        if hit is None:
            hit = table.get("*")
            if hit is None:
                continue
        return (rule[:80], key, *hit)
    return None


def name_entries(tags):
    """(original, kind, language) names of an object, label first."""
    out = []
    name = (tags.get("name") or "").strip()
    if name:
        out.append((name, "label", None))
    for lang in OSM_LANGS:
        value = (tags.get(f"name:{lang}") or "").strip()
        if value:
            out.append((value, "label", lang))
    for key in ("official_name", "short_name", "alt_name", "loc_name", "old_name", "brand"):
        for part in (tags.get(key) or "").split(";"):
            if part.strip():
                out.append((part.strip(), "alias", None))
    return out


def kept_tags(tags, primary=None):
    out = {k: tags[k][:MAX_TAG_CHARS] for k in KEEP_TAGS if tags.get(k)}
    if primary:
        key, _, value = primary.partition("=")
        out[key] = value
    return out


def log_line(message):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{datetime.now():%H:%M:%S} {message} (peak RSS {rss:,.0f} MB)", flush=True)


def peak_rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)


def local_xy(lat, lng, lat0, lng0):
    """Metres east and north of (lat0, lng0), equirectangular (numpy arrays or floats)."""
    import numpy as np
    k = math.cos(math.radians(lat0))
    return (np.asarray(lng) - lng0) * (111_320.0 * k), (np.asarray(lat) - lat0) * 110_574.0


def median_point(lat, lng):
    """Index of the point nearest the coordinate-wise median (a member point, so it lies on the object)."""
    import numpy as np
    mlat, mlng = float(np.median(lat)), float(np.median(lng))
    x, y = local_xy(lat, lng, mlat, mlng)
    return int(np.argmin(x * x + y * y))


def distances_m(lat, lng, lat0, lng0):
    import numpy as np
    x, y = local_xy(lat, lng, lat0, lng0)
    return np.sqrt(x * x + y * y)


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def root(self, x):
        parent = self.parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.root(a), self.root(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self):
        out = defaultdict(list)
        for i in range(len(self.parent)):
            out[self.root(i)].append(i)
        return list(out.values())


def grid_union(uf, points_lat, points_lng, owner, cell_m):
    """Union the owners of points that fall in the same or neighbouring cells of a cell_m grid."""
    import numpy as np
    if len(owner) < 2:
        return
    lat0, lng0 = float(np.mean(points_lat)), float(np.mean(points_lng))
    x, y = local_xy(points_lat, points_lng, lat0, lng0)
    cx, cy = np.floor(x / cell_m).astype(np.int64), np.floor(y / cell_m).astype(np.int64)
    first = {}
    for gx, gy, o in set(zip(cx.tolist(), cy.tolist(), owner)):
        cell = (gx, gy)
        if cell in first:
            uf.union(first[cell], o)
        else:
            first[cell] = o
    for (gx, gy), o in first.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                other = first.get((gx + dx, gy + dy))
                if other is not None and other != o:
                    uf.union(o, other)


class Outline:
    """Country outlines for the border check: own country, and the other two."""

    def __init__(self, country, outline_dir=OUTLINE_DIR):
        import shapely
        from shapely.geometry import shape
        self.shapely = shapely
        self.own, self.others = [], []
        self.files = []
        for c, files in OUTLINES.items():
            for name in files:
                path = Path(outline_dir) / name
                if not path.is_file():
                    if c == country:
                        raise FileNotFoundError(f"no outline {path}: pass --outline none to skip the border check")
                    continue
                with open(path, encoding="utf-8") as f:
                    doc = json.load(f)
                geoms = [shape(feat["geometry"]) for feat in doc.get("features", []) if feat.get("geometry")]
                for g in geoms:
                    shapely.prepare(g)
                (self.own if c == country else self.others).extend(geoms)
                self.files.append(B.file_record(path))

    def keep(self, lat, lng):
        """Boolean mask: inside the own outline, or near it (BORDER_TOLERANCE_M) and inside no other."""
        import numpy as np
        shapely = self.shapely
        lat, lng = np.asarray(lat, dtype=float), np.asarray(lng, dtype=float)
        inside = np.zeros(len(lat), dtype=bool)
        for g in self.own:
            todo = ~inside
            if todo.any():
                inside[todo] |= shapely.contains_xy(g, lng[todo], lat[todo])
        out = np.flatnonzero(~inside)
        keep = inside.copy()
        if len(out):
            other = np.zeros(len(out), dtype=bool)
            for g in self.others:
                other |= shapely.contains_xy(g, lng[out], lat[out])
            cand = out[~other]
            if len(cand):
                pts = shapely.points(lng[cand], lat[cand])
                near = np.zeros(len(cand), dtype=bool)
                tol = BORDER_TOLERANCE_M / 111_000.0 / np.maximum(np.cos(np.radians(lat[cand])), 0.3)
                for g in self.own:
                    near |= shapely.dwithin(g, pts, tol)
                keep[cand[near]] = True
        return keep


STAGE_SQL = """
CREATE TABLE IF NOT EXISTS stage_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS poi (osm TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, rule TEXT NOT NULL,
    family TEXT NOT NULL, role TEXT NOT NULL, extent REAL NOT NULL, extent_rule TEXT NOT NULL,
    extent_source TEXT NOT NULL, prom REAL NOT NULL, norm TEXT NOT NULL, label TEXT NOT NULL, names TEXT NOT NULL,
    tags TEXT NOT NULL, wikidata TEXT);
CREATE TABLE IF NOT EXISTS way_poi (way INTEGER NOT NULL, rule TEXT NOT NULL, family TEXT NOT NULL, role TEXT NOT NULL,
    extent REAL NOT NULL, prom REAL NOT NULL, norm TEXT NOT NULL, label TEXT NOT NULL, names TEXT NOT NULL,
    tags TEXT NOT NULL, wikidata TEXT, closed INTEGER NOT NULL, refs BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS street (way INTEGER NOT NULL, norm TEXT NOT NULL, label TEXT NOT NULL, class TEXT NOT NULL,
    names TEXT NOT NULL, wikidata TEXT, refs BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS pc_node (code TEXT, prefix TEXT, lat REAL NOT NULL, lng REAL NOT NULL, osm TEXT NOT NULL,
    street TEXT, city TEXT);
CREATE TABLE IF NOT EXISTS pc_way (code TEXT, prefix TEXT, way INTEGER NOT NULL, street TEXT, city TEXT,
    refs BLOB NOT NULL);
"""

ENTRY_SQL = """
DROP TABLE IF EXISTS entry; DROP TABLE IF EXISTS ename; DROP TABLE IF EXISTS occ; DROP TABLE IF EXISTS pc_point;
CREATE TABLE entry (eid INTEGER PRIMARY KEY, source TEXT NOT NULL, label TEXT NOT NULL, lat REAL NOT NULL,
    lng REAL NOT NULL, role TEXT NOT NULL, extent REAL NOT NULL, prom REAL NOT NULL, family TEXT NOT NULL,
    linkable INTEGER NOT NULL, wikidata TEXT, info TEXT NOT NULL);
CREATE TABLE ename (eid INTEGER NOT NULL, norm TEXT NOT NULL, squash TEXT NOT NULL, core TEXT NOT NULL,
    langs TEXT NOT NULL, kind TEXT NOT NULL, original TEXT NOT NULL);
CREATE TABLE pc_point (code TEXT, prefix TEXT, lat REAL NOT NULL, lng REAL NOT NULL, osm TEXT NOT NULL, street TEXT,
    city TEXT);
"""

OUT_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE place (id INTEGER PRIMARY KEY, source TEXT NOT NULL, label TEXT NOT NULL, lat REAL NOT NULL,
                    lng REAL NOT NULL, countries TEXT NOT NULL, role TEXT NOT NULL, extent_m REAL NOT NULL,
                    prominence REAL NOT NULL, grp TEXT, info TEXT NOT NULL);
CREATE TABLE link (place_id INTEGER NOT NULL, other TEXT NOT NULL, distance_m REAL NOT NULL, how TEXT NOT NULL);
CREATE TABLE main_group (source TEXT PRIMARY KEY, grp TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE postcode (country TEXT NOT NULL, code TEXT NOT NULL, kind TEXT NOT NULL, lat REAL NOT NULL,
                       lng REAL NOT NULL, extent_m REAL NOT NULL, label TEXT NOT NULL, info TEXT NOT NULL,
                       PRIMARY KEY (country, code)) WITHOUT ROWID;
"""


def sample_refs(refs, interior):
    """Both ends plus at most `interior` evenly spaced interior refs."""
    n = len(refs)
    if n <= interior + 2:
        return refs
    step = (n - 1) / (interior + 1)
    return [refs[round(i * step)] for i in range(interior + 2)]


def pack(refs):
    return array.array("q", refs).tobytes()


class OsmBuilder:
    def __init__(self, country, pbf, out, names_path, outline, work, log):
        self.country, self.pbf, self.out = country, Path(pbf), Path(out)
        self.names_path = Path(names_path) if names_path else None
        self.outline, self.work, self.log = outline, Path(work), log
        self.stats = Counter()
        self.timing = {}
        self.offset = N.OSM_ID_OFFSET[country]

    # -- staging ------------------------------------------------------------------------------------------

    def open_stage(self, fingerprint):
        self.work.mkdir(parents=True, exist_ok=True)
        os.environ["SQLITE_TMPDIR"] = str(self.work.resolve())
        path = self.work / "stage.sqlite"
        con = sqlite3.connect(path, uri=True)  # uri: names.sqlite is attached read-only by URI
        con.execute("PRAGMA temp_store_directory = '{}'".format(str(self.work.resolve()).replace("'", "''")))
        for pragma in ("journal_mode = OFF", "synchronous = OFF", "cache_size = -262144", "temp_store = FILE"):
            con.execute(f"PRAGMA {pragma}")
        con.executescript(STAGE_SQL)
        meta = dict(con.execute("SELECT key, value FROM stage_meta"))
        if meta.get("fingerprint") != fingerprint:
            con.close()
            shutil.rmtree(self.work)
            self.work.mkdir(parents=True)
            con = sqlite3.connect(path, uri=True)
            for pragma in ("journal_mode = OFF", "synchronous = OFF", "cache_size = -262144", "temp_store = FILE"):
                con.execute(f"PRAGMA {pragma}")
            con.executescript(STAGE_SQL)
            con.execute("INSERT INTO stage_meta VALUES ('fingerprint', ?)", (fingerprint,))
            con.commit()
            meta = {"fingerprint": fingerprint}
        self.con, self.stage_meta = con, meta

    def mark(self, key, value="done"):
        self.con.execute("INSERT OR REPLACE INTO stage_meta VALUES (?, ?)", (key, value))
        self.con.commit()
        self.stage_meta[key] = value

    # -- pass 1: tagged nodes and ways ---------------------------------------------------------------------

    def pass1(self):
        import osmium
        rows = {"poi": [], "way_poi": [], "street": [], "pc_node": [], "pc_way": []}
        width = {"poi": 15, "way_poi": 13, "street": 7, "pc_node": 7, "pc_way": 6}

        def flush(table=None):
            for t in [table] if table else list(rows):
                if rows[t]:
                    self.con.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * width[t])})", rows[t])
                    self.stats[f"stage_{t}"] += len(rows[t])
                    rows[t] = []

        def add(table, row):
            rows[table].append(row)
            if len(rows[table]) >= BATCH:
                flush(table)

        country = self.country
        fp = osmium.FileProcessor(str(self.pbf), osmium.osm.NODE | osmium.osm.WAY) \
            .with_filter(osmium.filter.KeyFilter(*PASS1_KEYS))
        seen = 0
        for o in fp:
            seen += 1
            if seen % 2_000_000 == 0:
                self.log(f"pass 1: {seen:,} tagged objects")
            tags = dict(o.tags)
            postcode = tags.get("addr:postcode")
            parsed = valid_postcode(country, postcode) if postcode else None
            if postcode and not parsed:
                self.stats["postcode_values_rejected"] += 1
            if o.is_node():
                loc = o.location
                if not loc.valid():
                    self.stats["bad_nodes"] += 1
                    continue
                lat, lng = loc.lat, loc.lon
                if parsed:
                    add("pc_node", (parsed[0], parsed[1], lat, lng, f"n{o.id}", tags.get("addr:street"),
                                    tags.get("addr:city") or tags.get("addr:place")))
                rule = classify(tags)
                if rule:
                    names = name_entries(tags)
                    if names:
                        r, family, role, extent, prom = rule
                        wikidata = tags.get("wikidata") if QID.match(tags.get("wikidata") or "") else None
                        add("poi", (f"n{o.id}", lat, lng, r, family, role, extent, f"osm type: {r}", "assumed",
                                    prom, N.normalise(names[0][0]), names[0][0][:B.MAX_NAME_CHARS],
                                    json.dumps(names, ensure_ascii=False),
                                    json.dumps(kept_tags(tags, r), ensure_ascii=False), wikidata))
                continue
            refs = [n.ref for n in o.nodes]
            if not refs:
                continue
            rule = classify(tags)
            highway = tags.get("highway")
            name = (tags.get("name") or "").strip()
            wikidata = tags.get("wikidata") if QID.match(tags.get("wikidata") or "") else None
            if name and highway in STREET_CLASSES and not (rule and rule[1] == "place"):
                names = name_entries(tags)
                add("street", (o.id, N.normalise(name), name[:B.MAX_NAME_CHARS], highway,
                               json.dumps(names, ensure_ascii=False), wikidata, pack(sample_refs(refs, STREET_SAMPLE))))
            elif rule:
                names = name_entries(tags)
                if names:
                    r, family, role, extent, prom = rule
                    closed = int(len(refs) >= 4 and refs[0] == refs[-1])
                    add("way_poi", (o.id, r, family, role, extent, prom, N.normalise(names[0][0]),
                                    names[0][0][:B.MAX_NAME_CHARS], json.dumps(names, ensure_ascii=False),
                                    json.dumps(kept_tags(tags, r), ensure_ascii=False), wikidata, closed,
                                    pack(sample_refs(refs, WAY_SAMPLE))))
            if parsed:
                add("pc_way", (parsed[0], parsed[1], o.id, tags.get("addr:street"),
                               tags.get("addr:city") or tags.get("addr:place"),
                               pack(sample_refs(refs[:-1] if len(refs) > 1 and refs[0] == refs[-1] else refs,
                                                POSTCODE_WAY_SAMPLE - 2))))
        flush()
        self.stats["pass1_objects"] = seen
        self.con.commit()

    # -- pass 2: locations of the nodes the staged ways need ----------------------------------------------

    def pass2(self):
        import numpy as np
        import osmium
        refs = array.array("q")
        for table in ("street", "way_poi", "pc_way"):
            for (blob,) in self.con.execute(f"SELECT refs FROM {table}"):
                refs.frombytes(blob)
        needed = np.unique(np.frombuffer(refs, dtype=np.int64)) if refs else np.zeros(0, dtype=np.int64)
        del refs
        self.stats["pass2_needed_nodes"] = int(len(needed))
        ids = np.empty(len(needed), dtype=np.int64)
        lat = np.empty(len(needed), dtype=np.int32)
        lon = np.empty(len(needed), dtype=np.int32)
        k = 0
        start = 0
        while start < len(needed):
            stop = int(np.searchsorted(needed, needed[start] + NODE_CHUNK_IDS))
            part = needed[start:stop]
            id_filter = osmium.filter.IdFilter(part)
            for node in osmium.FileProcessor(str(self.pbf), osmium.osm.NODE).with_filter(id_filter):
                loc = node.location
                if loc.valid():
                    ids[k], lat[k], lon[k] = node.id, loc.y, loc.x
                    k += 1
            del id_filter
            self.log(f"pass 2: node ids {int(part[0]):,}-{int(part[-1]):,}: {k:,} of {len(needed):,} located")
            start = stop
        ids, lat, lon = ids[:k], lat[:k], lon[:k]
        order = np.argsort(ids, kind="stable")
        ids, lat, lon = ids[order], lat[order], lon[order]
        self.stats["pass2_located_nodes"] = int(k)
        np.save(self.work / "node_ids.npy", ids)
        np.save(self.work / "node_lat.npy", lat)
        np.save(self.work / "node_lon.npy", lon)

    def load_nodes(self):
        import numpy as np
        self.node_ids = np.load(self.work / "node_ids.npy")
        self.node_lat = np.load(self.work / "node_lat.npy")
        self.node_lon = np.load(self.work / "node_lon.npy")

    def coords(self, blob):
        """(lat, lng, refs) arrays for a packed ref list; refs without a location are left out."""
        import numpy as np
        refs = np.frombuffer(blob, dtype=np.int64)
        if not len(self.node_ids):
            return np.zeros(0), np.zeros(0), refs[:0]
        idx = np.searchsorted(self.node_ids, refs)
        idx[idx >= len(self.node_ids)] = 0
        ok = self.node_ids[idx] == refs
        idx = idx[ok]
        return self.node_lat[idx] * 1e-7, self.node_lon[idx] * 1e-7, refs[ok]

    # -- entries ---------------------------------------------------------------------------------------------

    def finish_ways(self):
        """POI ways -> poi rows (point and footprint); address ways -> postcode points."""
        import numpy as np
        import shapely
        self.con.execute("DELETE FROM poi WHERE osm LIKE 'w%'")  # a resumed run recomputes them
        rows = []
        for (way, rule, family, role, extent, prom, norm, label, names, tags, wikidata, closed,
             blob) in self.con.execute("SELECT * FROM way_poi"):
            lat, lng, _ = self.coords(blob)
            if len(lat) == 0:
                self.stats["ways_without_nodes"] += 1
                continue
            if closed and len(lat) >= 4:
                lat0, lng0 = float(lat.mean()), float(lng.mean())
                poly = shapely.Polygon(np.column_stack([lng, lat]))
                point = poly.point_on_surface() if poly.is_valid and poly.area > 0 else None
                if point is not None and not point.is_empty:
                    plat, plng = point.y, point.x
                else:
                    i = int(np.argmin(distances_m(lat, lng, lat0, lng0)))
                    plat, plng = float(lat[i]), float(lng[i])
            else:
                i = len(lat) // 2
                plat, plng = float(lat[i]), float(lng[i])
            footprint = float(distances_m(lat, lng, plat, plng).max()) if len(lat) > 1 else 0.0
            rows.append((f"w{way}", plat, plng, rule, family, role, round(max(footprint, MIN_FOOTPRINT_M), 1),
                         "footprint: farthest node from the point", "source", prom, norm, label, names, tags, wikidata))
            if len(rows) >= BATCH:
                self.con.executemany(f"INSERT INTO poi VALUES ({','.join('?' * 15)})", rows)
                rows = []
        if rows:
            self.con.executemany(f"INSERT INTO poi VALUES ({','.join('?' * 15)})", rows)
        self.con.commit()

    def new_entry(self, rows, names_rows, source, label, lat, lng, role, extent, prom, family, wikidata, info, names):
        eid = len(rows) + self.entry_count
        linkable = int(family in LINK_FAMILIES and (family != "amenity" or info.get("osm_type", "").split("=")[-1]
                                                    in LINK_AMENITY))
        rows.append((eid, source, label, lat, lng, role, extent, prom, family, linkable, wikidata,
                     B.compact_json(info)))
        for norm, squashed, core, languages, kind, original in B.names_of(names):
            names_rows.append((eid, norm, squashed, core, ",".join(languages), kind, original))

    def flush_entries(self, rows, names_rows, force=False):
        if rows and (force or len(rows) >= BATCH):
            self.con.executemany("INSERT INTO entry VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            self.con.executemany("INSERT INTO ename VALUES (?,?,?,?,?,?,?)", names_rows)
            self.entry_count += len(rows)
            rows.clear()
            names_rows.clear()

    def build_entries(self):
        """Merged streets and deduplicated POIs -> entry and ename."""
        import numpy as np
        self.con.executescript(ENTRY_SQL)
        self.entry_count = 1
        rows, names_rows = [], []
        # streets, one name at a time
        self.con.execute("CREATE INDEX IF NOT EXISTS street_norm ON street(norm)")
        group, current = [], None
        cursor = self.con.execute("SELECT norm, way, label, class, names, wikidata, refs FROM street ORDER BY norm, way")
        for row in cursor:
            if row[0] != current and group:
                self.merge_streets(group, rows, names_rows)
                self.flush_entries(rows, names_rows)
                group = []
            current = row[0]
            group.append(row)
        if group:
            self.merge_streets(group, rows, names_rows)
        self.flush_entries(rows, names_rows, force=True)
        self.log(f"streets: {self.stats['street_ways']:,} ways -> {self.stats['streets']:,} streets")
        # POIs, one name at a time
        self.con.execute("CREATE INDEX IF NOT EXISTS poi_norm ON poi(norm)")
        group, current = [], None
        for row in self.con.execute("SELECT * FROM poi ORDER BY norm, role, osm"):
            if row[10] != current and group:
                self.merge_pois(group, rows, names_rows)
                self.flush_entries(rows, names_rows)
                group = []
            current = row[10]
            group.append(row)
        if group:
            self.merge_pois(group, rows, names_rows)
        self.flush_entries(rows, names_rows, force=True)
        self.log(f"POIs: {self.stats['poi_objects']:,} objects -> {self.stats['pois']:,} entries")
        # postcode points: nodes, and ways at the mean of their sampled nodes
        self.con.execute("INSERT INTO pc_point SELECT * FROM pc_node")
        points = []
        for code, prefix, way, street, city, blob in self.con.execute("SELECT * FROM pc_way"):
            lat, lng, _ = self.coords(blob)
            if len(lat):
                points.append((code, prefix, float(lat.mean()), float(lng.mean()), f"w{way}", street, city))
        self.con.executemany("INSERT INTO pc_point VALUES (?,?,?,?,?,?,?)", points)
        self.con.commit()

    def merge_streets(self, group, rows, names_rows):
        import numpy as np
        segs = []
        for norm, way, label, cls, names, wikidata, blob in group:
            lat, lng, refs = self.coords(blob)
            if len(lat) == 0:
                self.stats["street_ways_without_nodes"] += 1
                continue
            segs.append((way, label, cls, names, wikidata, lat, lng, refs))
        if not segs:
            return
        self.stats["street_ways"] += len(segs)
        uf = UnionFind(len(segs))
        ends = {}
        for i, s in enumerate(segs):
            for ref in (int(s[7][0]), int(s[7][-1])):
                if ref in ends:
                    uf.union(i, ends[ref])
                else:
                    ends[ref] = i
        if len(segs) > 1:
            owner = [i for i, s in enumerate(segs) for _ in range(len(s[5]))]
            grid_union(uf, np.concatenate([s[5] for s in segs]), np.concatenate([s[6] for s in segs]), owner,
                       STREET_CELL_M)
        for members in uf.groups():
            parts = [segs[i] for i in members]
            lat = np.concatenate([p[5] for p in parts])
            lng = np.concatenate([p[6] for p in parts])
            owner = np.concatenate([np.full(len(p[5]), j) for j, p in enumerate(parts)])
            i = median_point(lat, lng)
            plat, plng = float(lat[i]), float(lng[i])
            extent = float(distances_m(lat, lng, plat, plng).max()) + STREET_HALF_WIDTH_M
            length = 0.0
            for p in parts:
                if len(p[5]) > 1:
                    x, y = local_xy(p[5], p[6], float(p[5][0]), float(p[6][0]))
                    length += float(np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2).sum())
            home = parts[int(owner[i])]
            classes = Counter(p[2] for p in parts)
            best_class = max(classes, key=lambda c: (STREET_PROMINENCE.get(c, 0.04), classes[c]))
            labels = Counter(p[1] for p in parts)
            label = max(labels, key=lambda name: (labels[name], name))
            names, seen = [], set()
            for p in sorted(parts, key=lambda p: p[1] != label):
                for entry in json.loads(p[3]):
                    key = (entry[0], entry[1], entry[2])
                    if key not in seen:
                        seen.add(key)
                        names.append(entry)
            names.sort(key=lambda e: (e[0] != label, e[1] != "label"))
            wikidata = Counter(p[4] for p in parts if p[4])
            qid = wikidata.most_common(1)[0][0] if wikidata else None
            ways = sorted(p[0] for p in parts)
            info = {"source": "osm", "osm_id": f"w{home[0]}", "osm_ids": [f"w{w}" for w in ways[:MAX_LIST]],
                    "n_objects": len(parts), "osm_type": f"highway={best_class}",
                    "highway": dict(classes.most_common(5)), "length_m": round(length),
                    "tags": {"name": label, **({"wikidata": qid} if qid else {})},
                    "role_rule": "osm street", "extent_rule": "merged street: farthest node from the median node + 10 m",
                    "extent_source": "source"}
            self.new_entry(rows, names_rows, f"osm:w{home[0]}", label, round(plat, 7), round(plng, 7), "area",
                           round(max(extent, STREET_MIN_EXTENT_M), 1), STREET_PROMINENCE.get(best_class, 0.04),
                           "street", qid, info, names)
            self.stats["streets"] += 1

    def merge_pois(self, group, rows, names_rows):
        import numpy as np
        self.stats["poi_objects"] += len(group)
        by_role = defaultdict(list)
        for row in group:
            by_role[row[5]].append(row)
        for role, items in by_role.items():
            uf = UnionFind(len(items))
            if len(items) > 1:
                lat = np.array([r[1] for r in items])
                lng = np.array([r[2] for r in items])
                grid_union(uf, lat, lng, list(range(len(items))), POI_MERGE_M)
            for members in uf.groups():
                parts = [items[i] for i in members]
                if len(parts) > 1:  # the grid is coarse: keep only those truly within POI_MERGE_M of the first
                    first = max(parts, key=lambda r: (r[0].startswith("w"), r[6], r[0]))
                    d = distances_m(np.array([r[1] for r in parts]), np.array([r[2] for r in parts]), first[1], first[2])
                    close = [p for p, dist in zip(parts, d) if dist <= POI_MERGE_M + first[6]]
                    for p in parts:
                        if p not in close:
                            self.emit_poi([p], rows, names_rows)
                    parts = close
                self.emit_poi(parts, rows, names_rows)

    def emit_poi(self, parts, rows, names_rows):
        # the representative: a way (it has a footprint) with the widest extent, then the lowest id
        best = max(parts, key=lambda r: (r[0].startswith("w"), r[6], -int(r[0][1:])))
        osm, lat, lng, rule, family, role, extent, extent_rule, extent_source, prom, norm, label, names, tags, \
            wikidata = best
        all_names, seen = [], set()
        for p in sorted(parts, key=lambda p: p is not best):
            for entry in json.loads(p[12]):
                key = tuple(entry)
                if key not in seen:
                    seen.add(key)
                    all_names.append(entry)
        qids = Counter(p[14] for p in parts if p[14])
        qid = wikidata or (qids.most_common(1)[0][0] if qids else None)
        ids = sorted((p[0] for p in parts), key=lambda s: (s[0], int(s[1:])))
        info = {"source": "osm", "osm_id": osm, "osm_type": rule, "tags": json.loads(tags),
                "role_rule": f"osm {rule}", "extent_rule": extent_rule, "extent_source": extent_source}
        if len(parts) > 1:
            info["osm_ids"], info["n_objects"] = ids[:MAX_LIST], len(parts)
        self.new_entry(rows, names_rows, f"osm:{osm}", label, round(lat, 7), round(lng, 7), role, extent,
                       max(p[9] for p in parts), family, qid, info, all_names)
        self.stats["pois"] += 1

    # -- border check ---------------------------------------------------------------------------------------

    def border(self):
        import numpy as np
        if self.outline is None:
            self.stats["border_check"] = 0
            return
        for table, key in (("entry", "eid"), ("pc_point", "rowid")):
            ids, lat, lng = [], [], []
            for i, a, b in self.con.execute(f"SELECT {key}, lat, lng FROM {table}"):
                ids.append(i)
                lat.append(a)
                lng.append(b)
            if not ids:
                continue
            keep = self.outline.keep(np.array(lat), np.array(lng))
            drop = [(ids[i],) for i in np.flatnonzero(~keep).tolist()]
            self.con.execute("DROP TABLE IF EXISTS temp.dropped")
            self.con.execute("CREATE TEMP TABLE dropped (id INTEGER PRIMARY KEY)")
            self.con.executemany("INSERT INTO temp.dropped VALUES (?)", drop)
            self.con.execute(f"DELETE FROM {table} WHERE {key} IN (SELECT id FROM temp.dropped)")
            if table == "entry":
                self.con.execute("DELETE FROM ename WHERE eid IN (SELECT id FROM temp.dropped)")
            self.stats[f"outside_country_{table}"] = len(drop)
        self.con.commit()
        self.stats["border_check"] = 1

    # -- links to names.sqlite ---------------------------------------------------------------------------

    def links(self):
        """[(eid, main source, distance_m, how, main prominence, main group)] and the prominence per eid."""
        if self.names_path is None or not self.names_path.is_file():
            self.stats["links_skipped_no_names_index"] = 1
            return {}
        self.con.execute("ATTACH DATABASE ? AS m", (self.names_path.resolve().as_uri() + "?mode=ro&immutable=1",))
        best = {}  # (eid, main source) -> (distance, how, prominence, group)
        # wikidata tags: the item itself, wherever names.sqlite puts it
        wanted = defaultdict(list)
        for eid, qid, lat, lng in self.con.execute("SELECT eid, wikidata, lat, lng FROM entry WHERE wikidata IS NOT NULL"):
            wanted[f"wikidata:{qid}"].append((eid, lat, lng))
        self.stats["wikidata_tagged"] = sum(map(len, wanted.values()))
        if wanted:
            for source, lat, lng, prom, grp in self.con.execute(
                    "SELECT source, lat, lng, prominence, grp FROM m.place WHERE source >= 'wikidata:' "
                    "AND source < 'wikidata;'"):
                for eid, elat, elng in wanted.get(source, ()):
                    best[(eid, source)] = (haversine_m((lat, lng), (elat, elng)), "wikidata tag", prom, grp)
        self.stats["links_wikidata_tag"] = len(best)
        # same squashed name nearby, for families names.sqlite also holds; a box of LINK_MAX_M (cos(lat) >= 0.6
        # up to 53 degrees north), then the exact distance
        reach, reach_lng = LINK_MAX_M / 111_000, LINK_MAX_M / 111_000 / 0.6
        query = """
            SELECT e.eid, e.lat, e.lng, e.role, e.extent, p.source, p.lat, p.lng, p.role, p.extent_m, p.prominence, p.grp
            FROM ename n JOIN entry e ON e.eid = n.eid
            JOIN m.name mn ON mn.squash = n.squash JOIN m.place p ON p.id = mn.place_id
            WHERE e.linkable = 1 AND p.lat BETWEEN e.lat - ? AND e.lat + ? AND p.lng BETWEEN e.lng - ? AND e.lng + ?
        """
        n_name = 0
        for eid, lat, lng, role, extent, source, plat, plng, prole, pextent, prom, grp in self.con.execute(
                query, (reach, reach, reach_lng, reach_lng)):
            d = haversine_m((lat, lng), (plat, plng))
            if role == "area" and prole == "area":
                radius = min(LINK_MAX_M, max(LINK_RADIUS_M, min(extent, pextent) / 2))
            else:
                radius = LINK_LANDMARK_M
            key = (eid, source)
            if d <= radius and (key not in best or (best[key][1] != "wikidata tag" and d < best[key][0])):
                if key not in best:
                    n_name += 1
                best[key] = (d, f"name within {radius:.0f} m", prom, grp)
        self.stats["links_name"] = n_name
        self.con.commit()
        self.con.execute("DETACH DATABASE m")
        return best

    # -- the output database --------------------------------------------------------------------------------

    def write(self, out_con, links):
        country, bit = self.country, N.COUNTRY_BITS[self.country]
        # occurrences of each normalised name: how many entries carry it
        self.con.executescript("""
            CREATE TABLE occ (norm TEXT PRIMARY KEY, n INTEGER NOT NULL) WITHOUT ROWID;
            INSERT INTO occ SELECT norm, COUNT(DISTINCT eid) FROM ename GROUP BY norm;
        """)
        # links -> per entry: links list, prominence, group; main_group overrides
        per_entry = defaultdict(list)
        for (eid, source), (d, how, prom, grp) in links.items():
            per_entry[eid].append((d if how != "wikidata tag" else -1.0, source, d, how, prom, grp))
        overrides = {}
        entry_group, entry_prom = {}, {}
        for eid, items in per_entry.items():
            items.sort()
            _, source, d, how, prom, grp = items[0]
            group = grp or f"same-place:{source}"
            entry_group[eid] = group
            if grp is None:
                overrides.setdefault(source, group)
            entry_prom[eid] = max(prom for *_, prom, _ in items)
        self.stats["linked_entries"] = len(per_entry)
        out_con.executemany("INSERT INTO main_group VALUES (?, ?)", sorted(overrides.items()))
        import numpy as np
        link_rows = []
        place_rows = []
        stats_role, stats_family = Counter(), Counter()
        last = self.con.execute("SELECT MAX(eid) FROM entry").fetchone()[0] or 0
        rank_prior = np.zeros(last + 1, dtype=np.float64)  # prior of each entry, for the name order
        cur = self.con.execute("SELECT eid, source, label, lat, lng, role, extent, prom, family, info FROM entry ORDER BY eid")
        for eid, source, label, lat, lng, role, extent, prom, family, info in cur:
            pid = self.offset + eid
            items = per_entry.get(eid, ())
            if items:
                info = json.loads(info)
                info["linked"] = [{"source": s, "distance_m": round(d, 1), "how": how} for _, s, d, how, *_ in items[:5]]
                info = B.compact_json(info)
            prominence = round(max(prom, entry_prom.get(eid, 0.0)), 6)
            rank_prior[eid] = N.prior(prominence)
            place_rows.append((pid, source, label, lat, lng, country, role, extent, prominence,
                               entry_group.get(eid), info))
            for _, s, d, how, *_ in items:
                link_rows.append((pid, s, round(d, 1), how))
            stats_role[role] += 1
            stats_family[family] += 1
            if len(place_rows) >= BATCH:
                out_con.executemany("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?,?)", place_rows)
                place_rows = []
        if place_rows:
            out_con.executemany("INSERT INTO place VALUES (?,?,?,?,?,?,?,?,?,?,?)", place_rows)
        out_con.executemany("INSERT INTO link VALUES (?,?,?,?)", link_rows)
        out_con.execute("CREATE INDEX link_place ON link(place_id)")
        out_con.execute("CREATE INDEX link_other ON link(other)")
        self.stats["entries"] = sum(stats_role.values())
        self.stats["entries_by_role"] = dict(stats_role)
        self.stats["entries_by_family"] = dict(stats_family.most_common())
        self.stats["links"] = len(link_rows)
        # names, sorted by prior / occurrences (most specific first), as names.sqlite sorts by prominence
        out_con.execute("""CREATE TABLE stage.name_stage (place_id INTEGER NOT NULL, norm TEXT NOT NULL,
            squash TEXT NOT NULL, core TEXT NOT NULL, langs TEXT NOT NULL, kind TEXT NOT NULL, original TEXT NOT NULL,
            cmask INTEGER NOT NULL, occ INTEGER NOT NULL, rank REAL NOT NULL)""")
        rows = []
        occ_cur = self.con.execute("SELECT n.eid, n.norm, n.squash, n.core, n.langs, n.kind, n.original, o.n "
                                   "FROM ename n JOIN occ o ON o.norm = n.norm")
        for eid, norm, squash, core, langs, kind, original, occ in occ_cur:
            if not rank_prior[eid]:
                continue
            rows.append((self.offset + eid, norm, squash, core, langs, kind, original, bit, occ,
                         float(rank_prior[eid]) / occ))
            if len(rows) >= BATCH:
                out_con.executemany("INSERT INTO stage.name_stage VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
                rows = []
        if rows:
            out_con.executemany("INSERT INTO stage.name_stage VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        del rank_prior
        out_con.executescript("""
            CREATE TABLE name (place_id INTEGER NOT NULL, norm TEXT NOT NULL, squash TEXT NOT NULL, core TEXT NOT NULL,
                               langs TEXT NOT NULL, kind TEXT NOT NULL, original TEXT NOT NULL, cmask INTEGER NOT NULL,
                               occ INTEGER NOT NULL);
            INSERT INTO name SELECT place_id, norm, squash, core, langs, kind, original, cmask, occ
                FROM stage.name_stage ORDER BY rank DESC, place_id, norm;
            DROP TABLE stage.name_stage;
            CREATE INDEX name_squash ON name(squash);
            CREATE INDEX name_core ON name(core);
        """)
        self.stats["names"] = out_con.execute("SELECT COUNT(*) FROM name").fetchone()[0]
        top = self.con.execute("SELECT norm, n FROM occ ORDER BY n DESC LIMIT 25").fetchall()
        self.stats["most_common_names"] = {norm: n for norm, n in top}
        self.stats["names_with_occ_ge_8"] = self.con.execute("SELECT COUNT(*) FROM occ WHERE n >= 8").fetchone()[0]

    def postcodes(self, out_con):
        import numpy as np
        records = []
        for kind, column in (("code", "code"), ("prefix", "prefix")):
            if kind == "prefix" and self.country != "PT":
                continue
            group, current = [], None
            cur = self.con.execute(f"SELECT {column}, lat, lng, osm, street, city FROM pc_point "
                                   f"WHERE {column} IS NOT NULL ORDER BY {column}, osm")
            for row in cur:
                if row[0] != current and group:
                    records.append(self.postcode_record(kind, current, group, np))
                    group = []
                current = row[0]
                group.append(row)
            if group:
                records.append(self.postcode_record(kind, current, group, np))
        out_con.executemany("INSERT INTO postcode VALUES (?,?,?,?,?,?,?,?)", records)
        self.stats["postcode_codes"] = sum(1 for r in records if r[2] == "code")
        self.stats["postcode_prefixes"] = sum(1 for r in records if r[2] == "prefix")
        self.stats["postcode_addresses"] = self.con.execute("SELECT COUNT(*) FROM pc_point").fetchone()[0]

    def postcode_record(self, kind, code, group, np):
        lat = np.array([r[1] for r in group])
        lng = np.array([r[2] for r in group])
        i = median_point(lat, lng)
        plat, plng = float(lat[i]), float(lng[i])
        d = distances_m(lat, lng, plat, plng)
        p50 = float(np.median(d))
        limit = max(POSTCODE_OUTLIER * p50, POSTCODE_OUTLIER_MIN_M[(self.country, kind)])
        inliers = d <= limit
        di = d[inliers]
        p90 = float(np.percentile(di, 90)) if len(di) else 0.0
        n = len(group)
        floor = POSTCODE_FLOOR_M[(self.country, kind)]
        if int(inliers.sum()) < POSTCODE_FEW:
            floor = max(floor, POSTCODE_FEW_FLOOR_M[kind])
        extent = max(p90, floor)
        streets = Counter(r[4] for r, ok in zip(group, inliers) if ok and r[4])
        places = Counter(r[5] for r, ok in zip(group, inliers) if ok and r[5])
        info = {"source": "osm", "n_addresses": n, "n_inliers": int(inliers.sum()), "n_outliers": int((~inliers).sum()),
                "spread_p50_m": round(p50, 1), "spread_p90_m": round(p90, 1),
                "spread_max_m": round(float(di.max()) if len(di) else 0.0, 1),
                "median_address": group[i][3], "osm_ids": [r[3] for r in group[:5]],
                "streets": [{"street": s, "n": k} for s, k in streets.most_common(3)] or None,
                "places": [{"place": s, "n": k} for s, k in places.most_common(3)] or None,
                "extent_source": "source",
                "extent_rule": f"p90 distance of the addresses from the median address, at least {floor:.0f} m"}
        where = ", ".join(x for x in (streets.most_common(1)[0][0] if streets else None,
                                      places.most_common(1)[0][0] if places else None) if x)
        label = f"{code} {where}".strip()[:B.MAX_NAME_CHARS]
        return (self.country, code, kind, round(plat, 7), round(plng, 7), round(extent, 1), label, B.compact_json(info))


def extract_record(pbf):
    """Size, mtime, the Geofabrik .md5 when it names the file, and the replication header."""
    import osmium
    pbf = Path(pbf)
    st = pbf.stat()
    try:
        shown = str(pbf.resolve().relative_to(ROOT))
    except ValueError:
        shown = str(pbf)
    record = {"path": shown, "bytes": st.st_size,
              "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}
    md5 = pbf.with_name(pbf.name + ".md5")
    if md5.is_file():
        parts = md5.read_text(encoding="utf-8", errors="replace").split()
        if len(parts) >= 2 and parts[1].lstrip("*") == pbf.name and re.fullmatch(r"[0-9a-f]{32}", parts[0]):
            record["md5"] = parts[0]
    header = osmium.io.Reader(str(pbf), osmium.osm.NOTHING).header()
    for key in ("osmosis_replication_timestamp", "osmosis_replication_sequence_number", "osmosis_replication_base_url",
                "generator", "timestamp"):
        value = header.get(key)
        if value:
            record[key] = value[:200]
    return record


def build(country, pbf=None, out=None, names=N.DEFAULT_PATH, outline="auto", work=None, keep_work=False,
          log=log_line):
    """Build osm_<country>.sqlite (replacing `out` only on success) and return the build report."""
    country = country.upper()
    if country not in N.COUNTRY_BITS:
        raise ValueError(f"country must be one of {N.COUNTRIES}, got {country!r}")
    pbf = Path(pbf) if pbf else OSM_DIR / PBF[country]
    out = Path(out) if out else N.DEFAULT_PATH.parent / f"osm_{country}.sqlite"
    work = Path(work) if work else WORK_DIR / f"osm_{country}"
    if not pbf.is_file():
        raise FileNotFoundError(f"no extract at {pbf}")
    started, t0 = datetime.now(timezone.utc), time.monotonic()
    extract = extract_record(pbf)
    border = Outline(country) if outline == "auto" else None if outline in (None, "none") else Outline(country, outline)
    fingerprint = json.dumps({"v": SCRIPT_VERSION, "country": country, "pbf": extract["path"],
                              "bytes": extract["bytes"], "mtime": extract["mtime_utc"]}, sort_keys=True)
    b = OsmBuilder(country, pbf, out, names, border, work, log)
    b.open_stage(fingerprint)
    resumed = []
    t = time.monotonic()
    if b.stage_meta.get("pass1") != "done":
        for table in ("poi", "way_poi", "street", "pc_node", "pc_way"):
            b.con.execute(f"DELETE FROM {table}")
        b.pass1()
        b.mark("pass1")
        b.mark("pass1_stats", json.dumps(dict(b.stats)))
        log(f"{country} pass 1 done in {time.monotonic() - t:,.0f} s: " + ", ".join(
            f"{k} {v:,}" for k, v in b.stats.items() if k.startswith("stage_")))
    else:
        b.stats.update(json.loads(b.stage_meta.get("pass1_stats", "{}")))
        resumed.append("pass1")
    b.timing["pass1_s"] = round(time.monotonic() - t, 1)
    t = time.monotonic()
    if b.stage_meta.get("pass2") != "done":
        b.pass2()
        b.mark("pass2")
        b.mark("pass2_stats", json.dumps({k: v for k, v in b.stats.items() if k.startswith("pass2")}))
        log(f"{country} pass 2 done in {time.monotonic() - t:,.0f} s")
    else:
        b.stats.update(json.loads(b.stage_meta.get("pass2_stats", "{}")))
        resumed.append("pass2")
    b.timing["pass2_s"] = round(time.monotonic() - t, 1)
    t = time.monotonic()
    b.load_nodes()
    b.finish_ways()
    b.build_entries()
    del b.node_ids, b.node_lat, b.node_lon
    b.border()
    b.timing["entries_s"] = round(time.monotonic() - t, 1)
    log(f"{country} entries built in {time.monotonic() - t:,.0f} s")
    t = time.monotonic()
    links = b.links()
    b.timing["links_s"] = round(time.monotonic() - t, 1)
    log(f"{country} links: {len(links):,} ({b.stats.get('links_wikidata_tag', 0):,} by wikidata tag)")

    out.parent.mkdir(parents=True, exist_ok=True)
    for stale in out.parent.glob(f"{out.name}.tmp-*"):
        stale.unlink()
    tmp = out.with_name(f"{out.name}.tmp-{os.getpid()}")
    stage = work / f"out-stage-{os.getpid()}.sqlite"
    con = sqlite3.connect(tmp)
    try:
        con.execute("PRAGMA temp_store_directory = '{}'".format(str(work.resolve()).replace("'", "''")))
        for pragma in ("journal_mode = OFF", "synchronous = OFF", "cache_size = -262144", "temp_store = FILE",
                       "threads = 4"):
            con.execute(f"PRAGMA {pragma}")
        con.execute("ATTACH DATABASE ? AS stage", (str(stage),))
        con.execute("PRAGMA stage.journal_mode = OFF")
        con.executescript(OUT_SQL)
        t = time.monotonic()
        b.write(con, links)
        b.postcodes(con)
        con.execute("DETACH DATABASE stage")
        stage.unlink(missing_ok=True)
        log(f"{country} places and names written: {b.stats['entries']:,} entries, {b.stats['names']:,} names, "
            f"{b.stats['postcode_codes']:,} postcodes")
        word = B.Builder(con, log)
        word.word_index()
        word.trigram_index()
        b.stats["fuzzy_keys"], b.stats["fuzzy_postings"] = word.stats["fuzzy_keys"], word.stats["fuzzy_postings"]
        b.timing["write_s"] = round(time.monotonic() - t, 1)
        names_meta = {}
        if b.names_path and b.names_path.is_file():
            mcon = sqlite3.connect(b.names_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
            names_meta = {k: json.loads(v) for k, v in mcon.execute(
                "SELECT key, value FROM meta WHERE key IN ('schema', 'built_utc')")}
            mcon.close()
        report = {
            "schema": N.OSM_SCHEMA, "country": country, "id_offset": b.offset,
            "built_utc": started.isoformat(timespec="seconds"), "script": "tools/build_osm_index.py",
            "script_version": SCRIPT_VERSION, "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "unicodedata": unicodedata.unidata_version, "byteorder": sys.byteorder, "extract": extract,
            "names_index": {"path": str(b.names_path) if b.names_path else None, **names_meta},
            "outlines": border.files if border else None, "resumed": resumed, "stats": dict(b.stats),
            "timing": b.timing,
            "constants": {"street_merge_m": STREET_MERGE_M, "street_sample": STREET_SAMPLE, "poi_merge_m": POI_MERGE_M,
                          "border_tolerance_m": BORDER_TOLERANCE_M, "link_landmark_m": LINK_LANDMARK_M,
                          "link_radius_m": LINK_RADIUS_M, "link_max_m": LINK_MAX_M,
                          "postcode_floor_m": {f"{c} {k}": v for (c, k), v in POSTCODE_FLOOR_M.items()},
                          "postcode_few": POSTCODE_FEW, "postcode_outlier": POSTCODE_OUTLIER,
                          "street_prominence": STREET_PROMINENCE},
            "rules": {k: {v: list(r) for v, r in table.items()} for k, table in RULES.items()},
            "key_order": KEY_ORDER, "exclude": {k: sorted(v) for k, v in EXCLUDE.items()},
        }
        report["build_seconds"] = round(time.monotonic() - t0, 1)
        report["peak_rss_mb"] = peak_rss_mb()
        con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in report.items()])
        con.execute("ANALYZE")
        con.commit()
        con.execute("PRAGMA journal_mode = DELETE")
        con.close()
        os.replace(tmp, out)
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        stage.unlink(missing_ok=True)
        raise
    b.con.close()
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    report["build_seconds"] = round(time.monotonic() - t0, 1)
    report["bytes"] = out.stat().st_size
    report["peak_rss_mb"] = peak_rss_mb()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("countries", nargs="+", help="PT, ES and/or FR, built one after the other")
    ap.add_argument("--pbf", type=Path, help="extract (default: Data/geo/osm/<country>-latest.osm.pbf)")
    ap.add_argument("--out", type=Path, help="output file (default: Data/index/osm_<CC>.sqlite); one country only")
    ap.add_argument("--out-suffix", default="", help="write Data/index/osm_<CC><suffix>.sqlite, e.g. .pending")
    ap.add_argument("--names", type=Path, default=N.DEFAULT_PATH, help="names.sqlite to link to (read only)")
    ap.add_argument("--outline", default="auto", help="'auto' (geoBoundaries), 'none', or a folder of outlines")
    ap.add_argument("--work", type=Path, help="work folder (default: Data/index/tmp/osm_<CC>)")
    ap.add_argument("--keep-work", action="store_true", help="keep the staging files after a successful build")
    args = ap.parse_args()
    countries = [c.upper() for c in args.countries]
    if (args.out or args.pbf or args.work) and len(countries) > 1:
        ap.error("--out, --pbf and --work need a single country")
    for country in countries:
        out = args.out or N.DEFAULT_PATH.parent / f"osm_{country}{args.out_suffix}.sqlite"
        report = build(country, args.pbf, out, args.names, args.outline, args.work, args.keep_work)
        s = report["stats"]
        log_line(f"wrote {out}: {report['bytes'] / 1e6:,.0f} MB in {report['build_seconds']:,.0f} s, peak RSS "
                 f"{report['peak_rss_mb']:,} MB; {s['entries']:,} entries ({s['streets']:,} streets), "
                 f"{s['names']:,} names, {s['links']:,} links, {s['postcode_codes']:,} postcodes "
                 f"from {s['postcode_addresses']:,} addresses")


if __name__ == "__main__":
    main()
