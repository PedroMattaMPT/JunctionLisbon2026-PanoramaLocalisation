#!/usr/bin/env python3
"""Build the zone index Data/index/zones.gpkg (+ zones.json) read by panoloc.zones (TASKS.md T32, PLAN.md 3.4, 4.4).

Named administrative zones for the agent's zone questions, so options follow borders the team knows
instead of box cuts. Everything is read from local files (nothing is downloaded); they are downloaded
files, so run this with -I. Every input's path, size, mtime, sha256, download record and declared CRS
goes into zones.json.
  Data/geo/boundaries/caop/   CAOP 2025 (DGT): Continente (cont_*, declares PT-TM06/ETRS89, EPSG:3763),
                              RAA central and eastern groups (raa_cen_ori_*, PTRA08 UTM 26N, EPSG:5015),
                              RAA western group (raa_oci_*, UTM 25N, EPSG:5014), RAM (ram_*, UTM 28N, EPSG:5016).
                              The CRS of each file is read from it, never assumed.
  Data/geo/boundaries/geoboundaries/  geoBoundaries gbOpen GeoJSON (CRS84): ESP-ADM1 (communities and the
                              two autonomous cities), ESP-ADM2 (provinces), FRA-ADM1 (regions), FRA-ADM2
                              (departments), and the PRT, ESP and FRA ADM0 outlines (compared, not used).
  Data/geo/downloads.log      when and from which URL each archive came (geoBoundaries pinned to a commit)
Scope: Portugal with the Azores and Madeira; Spain with the Canaries, the Balearics, Ceuta and Melilla;
metropolitan France with Corsica. This geoBoundaries build has no overseas French unit at all (the
build checks it), so overseas France is out of scope by construction.

Zones (panoloc.zones has the tree, the ID format and the labels). Leaves are parishes (CAOP freguesias),
provinces and departments; every coarser zone is the union of its leaves:
  PT  municipalities by DTMN, districts and islands by DT (CAOP's island "districts" in the Azores and
      Madeira), autonomous regions by NUTS 1 code, NUTS 2 and 3 by code (the alternate tree "nuts")
  ES  communities (ADM1) and provinces (ADM2) by shapeID: ESP-ADM1 gives "ESP" as every shapeISO and
      ADM2 none. A province belongs to the community it overlaps most (each at least 98.8% here).
  FR  regions by shapeISO (real ISO 3166-2 codes), departments by shapeID, parent by largest overlap.
A community or region is the union of its provinces or departments, not geoBoundaries' own ADM1 polygon,
so levels nest exactly; the ADM1 and ADM0 polygons are only compared (zones.json "qa").

Geometry, step by step:
  1. Leaves are simplified with shapely.coverage_simplify (GEOS coverage simplification, Visvalingam-
     Whyatt with shared edges kept identical, so neighbours never gain gaps or overlaps) in a metric CRS:
     CAOP in each file's own CRS, Spain in ETRS89 / UTM 30N (EPSG:25830, Canaries included), France in
     RGF93 / Lambert-93 (EPSG:2154). LEAF_TOLERANCE is a VW tolerance (about the square root of the area
     of the triangles removed), not a distance, so step 4 measures each leaf's real deviation.
  2. Each source's coverage is checked (coverage_is_valid, overlaps between neighbours, holes of its
     union with their location) and cleaned with coverage_clean only if invalid.
  3. Leaves go to WGS84 (EPSG:4326; the GeoPackage stores x = longitude). The three countries' borders
     come from different sources: each overlap goes to the first of PRIORITY (Portugal, the official
     CAOP border, then Spain, then France) and is cut from the other. Overlaps and the gaps left along
     the PT-ES and ES-FR borders are measured (sampled every BORDER_STEP_M, up to BORDER_REACH_M wide)
     and reported; panoloc.zones.locate snaps a point in a gap to the nearest zone within 1 km.
  4. deviation_m of a leaf: the largest distance from its source boundary to its stored boundary, both in
     the metric CRS. The source rings are sampled at their vertices and every SAMPLE_M; a distance can
     exceed the larger of two neighbouring samples' by at most half their spacing, which is added. A
     coarser zone takes the largest deviation of its leaves.
  5. Coarser zones: the union of their leaves gives area_km2 (geodesic, WGS84 ellipsoid), the bbox, the
     convex hull (stored as JSON, for panoloc.zones.bound_m) and the representative point (centre of the
     largest inscribed circle of the largest part). Their stored geometry is that union, simplified for
     display with coverage_simplify per level (OUTLINE_TOLERANCE, a scaled-degree frame); its own
     deviation from the union is stored as outline_deviation_m. Containment and bounds never use it.
  6. Self-check: the file is reopened with panoloc.zones and every leaf's representative point must
     locate to that leaf; locate() timings are recorded.

Writes zones.tmp-<pid>.gpkg and renames it over <out> only when complete, then <out with .json>. Working
files never go to /tmp (a RAM disk on the dev laptop).

Usage (from the repo root, in the venv; -I because it reads downloaded files):
  .venv/bin/python -I tools/build_zones.py              # ~185 s, 42 MB file, 1.2 GB peak RSS (2026-10-10 data)
  .venv/bin/python -I tools/build_zones.py --out Data/index/zones.gpkg --tolerance PT=10 --tolerance ES=25
"""
import argparse
import hashlib
import json
import math
import os
import re
import resource
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pyogrio  # noqa: E402
import pyproj  # noqa: E402
import shapely  # noqa: E402
from pyproj import Transformer  # noqa: E402

from panoloc import zones as Z  # noqa: E402

CAOP_DIR = ROOT / "Data" / "geo" / "boundaries" / "caop"
GB_DIR = ROOT / "Data" / "geo" / "boundaries" / "geoboundaries"
DOWNLOADS_LOG = ROOT / "Data" / "geo" / "downloads.log"
WGS84 = "EPSG:4326"

# (source key, file under CAOP_DIR, layer prefix, downloaded archive)
CAOP_FILES = (
    ("caop2025-continente", "Continente/Continente_CAOP2025.gpkg", "cont", "CAOP_Continente_2025-gpkg.zip"),
    ("caop2025-acores-central-oriental", "RAA/ArqAcores_GCentral_GOriental_CAOP2025.gpkg", "raa_cen_ori",
     "CAOP_RAA_2025-gpkg.zip"),
    ("caop2025-acores-ocidental", "RAA/ArqAcores_GOcidental_CAOP2025.gpkg", "raa_oci", "CAOP_RAA_2025-gpkg.zip"),
    ("caop2025-madeira", "RAM/ArqMadeira_CAOP2025.gpkg", "ram", "CAOP_RAM_2025-gpkg.zip"),
)
GB_COUNTRIES = {"ES": ("ESP", "EPSG:25830", "community", "province"),
                "FR": ("FRA", "EPSG:2154", "region", "department")}
BORDERS = (("PT", "ES", "EPSG:25829"), ("ES", "FR", "EPSG:2154"))  # border pair and the metric CRS to measure in
LEAF_TOLERANCE = {"PT": 10.0, "ES": 25.0, "FR": 25.0}  # coverage_simplify tolerance of the leaves, metres (VW)
OUTLINE_TOLERANCE = {"municipality": 40.0, "island": 40.0, "district": 80.0, "autonomous_region": 80.0,
                     "nuts3": 80.0, "nuts2": 120.0, "community": 120.0, "region": 120.0, "country": 200.0}
SAMPLE_M = 10.0  # source boundaries are sampled at least this densely to measure deviations
STORED_SEGMENT_DEG = 0.01  # stored edges are straight in degrees: traced this finely in the metric CRS
PRIORITY = ("PT", "ES", "FR")
BORDER_STEP_M = 20.0
BORDER_REACH_M = 1000.0
MIN_PART_M2 = 1.0  # polygon dust left by cutting a cross-border overlap
OVERLAP_PART_M2 = 100.0  # overlaps below this are reported in totals only
MAX_NAME = 200
CODE = {"dtmnfr": re.compile(r"^\d{4}[0-9A-Z]{2}$"), "dtmn": re.compile(r"^\d{4}$"), "dt": re.compile(r"^\d{2}$"),
        "nuts1": re.compile(r"^[1-3]$"), "nuts2": re.compile(r"^[1-3][0-9A-D]$"),
        "nuts3": re.compile(r"^[1-3][0-9A-D][0-9A-E]$"), "shapeID": re.compile(r"^[0-9A-Za-z]{6,40}$"),
        "iso": re.compile(r"^[A-Z]{2}-[0-9A-Z]{1,3}$")}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def log_line(message):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{datetime.now():%H:%M:%S} {message} (peak RSS {rss:,.0f} MB)", flush=True)


def peak_rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)


def shown_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def file_record(path):
    path = Path(path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    st = path.stat()
    return {"path": shown_path(path), "bytes": st.st_size,
            "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "sha256": digest.hexdigest()}


def downloads(path=DOWNLOADS_LOG):
    """{file name: {"downloaded", "bytes", "url"}} from tools/fetch_geo.sh's log (last entry wins)."""
    out = {}
    if not Path(path).is_file():
        return out
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1].isdigit() and parts[2].startswith("https://"):
            name = parts[2].rsplit("/", 1)[-1]
            m = re.fullmatch(r"geoBoundaries-([A-Z]{3}-ADM\d)\.geojson", name)
            out[f"{m[1]}.geojson" if m else name] = {"downloaded": parts[0], "bytes": int(parts[1]), "url": parts[2]}
    return out


def clean_name(value, what):
    name = " ".join(str(value or "").split())  # also drops geoBoundaries' stray no-break spaces
    if not name or len(name) > MAX_NAME or _CONTROL.search(name):
        raise ValueError(f"bad {what} name {value!r}")
    return name


def check_code(value, kind, what):
    code = str(value or "").strip()
    if not CODE[kind].match(code):
        raise ValueError(f"bad {what} code {value!r}")
    return code


def read_layer(path, layer, columns, geometry=True):
    """(declared CRS, shapely geometries or None, {column: array}) of one layer."""
    info = pyogrio.read_info(path, layer=layer)
    meta, _, wkb, fields = pyogrio.raw.read(path, layer=layer, columns=list(columns), read_geometry=geometry)
    data = dict(zip(meta["fields"], fields))
    missing = [c for c in columns if c not in data]
    if missing:
        raise ValueError(f"{path} layer {layer}: missing columns {missing}")
    geoms = shapely.from_wkb(wkb) if geometry else None
    if geometry:
        bad = ~shapely.is_valid(geoms)
        if bad.any():
            geoms[bad] = shapely.make_valid(geoms[bad])
    return info["crs"], geoms, data


def gpkg_contents(path):
    """{table: last_change} from a GeoPackage's gpkg_contents (read-only)."""
    try:
        con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            return {t: c for t, c in con.execute("SELECT table_name, last_change FROM gpkg_contents")}
        finally:
            con.close()
    except sqlite3.Error:
        return {}


def geojson_crs(path):
    """The "crs" member a GeoJSON file declares (looked for in its first 4 KB), or None."""
    with open(path, "rb") as f:
        head = f.read(4096).decode("utf-8", errors="replace")
    m = re.search(r'"crs"\s*:\s*\{.*?"name"\s*:\s*"([^"]+)"', head, re.S)
    return m[1] if m else None


def transformer(src, dst):
    return Transformer.from_crs(src, dst, always_xy=True)


def transform_record(t):
    return {"from": t.source_crs.to_string(), "to": t.target_crs.to_string(), "operation": t.description,
            "accuracy_m": None if t.accuracy is None or t.accuracy < 0 else t.accuracy, "pipeline": t.definition}


def apply(t, geoms):
    return shapely.transform(geoms, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))


def geodesic_m2(geom):
    """Geodesic area of the polygonal parts, oriented first (pyproj signs a ring's area by its orientation)."""
    polys = [p for p in shapely.get_parts(geom) if p.geom_type == "Polygon"]
    return Z.area_km2(shapely.MultiPolygon(polys)) * 1e6 if polys else 0.0


def polygonal(geom):
    """Valid polygonal parts only, dust (< MIN_PART_M2) dropped, as a MultiPolygon (or None if empty)."""
    geom = shapely.make_valid(geom) if not shapely.is_valid(geom) else geom
    parts = [p for p in shapely.get_parts(geom) if p.geom_type == "Polygon" and not p.is_empty]
    parts = [p for p in parts if geodesic_m2(p) >= MIN_PART_M2]
    return shapely.MultiPolygon(parts) if parts else None


def segments(geom):
    """Every boundary edge of a polygonal geometry as a 2-point LineString."""
    rings = shapely.get_rings(shapely.get_parts(geom))
    coords, idx = shapely.get_coordinates(rings, return_index=True)
    same = idx[1:] == idx[:-1]
    return shapely.linestrings(np.stack([coords[:-1][same], coords[1:][same]], axis=1))


def deviation_m(source_metric, stored_metric, step=SAMPLE_M):
    """Largest distance from the source boundary to the stored boundary (module docstring, step 4)."""
    rings = shapely.segmentize(shapely.get_rings(shapely.get_parts(source_metric)), step)
    coords, ring = shapely.get_coordinates(rings, return_index=True)
    tree = shapely.STRtree(segments(stored_metric))
    (which, _), dist = tree.query_nearest(shapely.points(coords), return_distance=True, all_matches=False)
    d = np.empty(len(coords))
    d[which] = dist
    same = ring[1:] == ring[:-1]
    spacing = np.hypot(*np.diff(coords, axis=0).T)
    between = (d[1:] + d[:-1] + spacing)[same] / 2
    return float(max(d.max(), between.max() if len(between) else 0.0))


def scaled_frame(lat0):
    k = math.cos(math.radians(lat0))
    return (lambda g: shapely.transform(g, lambda xy: xy * np.array([k, 1.0])),
            lambda g: shapely.transform(g, lambda xy: xy / np.array([k, 1.0])))


# -- Portugal: CAOP 2025 ---------------------------------------------------------------------------------

class Caop:
    """One CAOP file: parishes (leaves) and the attribute tables of the levels above them."""

    def __init__(self, key, rel, prefix, archive, log):
        self.key, self.prefix, self.archive = key, prefix, archive
        self.path = CAOP_DIR / rel
        self.crs, geoms, f = read_layer(self.path, f"{prefix}_freguesias", ("dtmnfr", "freguesia", "municipio",
                                                                            "designacao_simplificada", "area_ha"))
        _, _, m = read_layer(self.path, f"{prefix}_municipios", ("dtmn", "municipio", "distrito_ilha", "nuts3_cod"),
                             geometry=False)
        _, _, d = read_layer(self.path, f"{prefix}_distritos", ("dt", "distrito", "nuts1_cod"), geometry=False)
        _, _, n1 = read_layer(self.path, f"{prefix}_nuts1", ("codigo", "nuts1"), geometry=False)
        _, _, n2 = read_layer(self.path, f"{prefix}_nuts2", ("codigo", "nuts2"), geometry=False)
        _, _, n3 = read_layer(self.path, f"{prefix}_nuts3", ("codigo", "nuts3", "nuts2"), geometry=False)
        self.nuts1 = {check_code(c, "nuts1", "NUTS 1"): clean_name(n, "NUTS 1") for c, n in zip(n1["codigo"], n1["nuts1"])}
        self.nuts2 = {check_code(c, "nuts2", "NUTS 2"): clean_name(n, "NUTS 2") for c, n in zip(n2["codigo"], n2["nuts2"])}
        self.nuts3 = {}
        for c, n, parent in zip(n3["codigo"], n3["nuts3"], n3["nuts2"]):
            code = check_code(c, "nuts3", "NUTS 3")
            if self.nuts2.get(code[:2]) != clean_name(parent, "NUTS 2"):
                raise ValueError(f"{self.path}: NUTS 3 {code} names NUTS 2 {parent!r}, not {self.nuts2.get(code[:2])!r}")
            self.nuts3[code] = clean_name(n, "NUTS 3")
        self.districts = {}
        for c, n, nuts1 in zip(d["dt"], d["distrito"], d["nuts1_cod"]):
            code, nuts1 = check_code(c, "dt", "district"), check_code(nuts1, "nuts1", "NUTS 1")
            if nuts1 not in self.nuts1:
                raise ValueError(f"{self.path}: district {code} in unknown NUTS 1 {nuts1}")
            self.districts[code] = (clean_name(n, "district"), nuts1)
        self.municipalities = {}
        for c, n, dname, nuts3 in zip(m["dtmn"], m["municipio"], m["distrito_ilha"], m["nuts3_cod"]):
            code, nuts3 = check_code(c, "dtmn", "municipality"), check_code(nuts3, "nuts3", "NUTS 3")
            if code[:2] not in self.districts or self.districts[code[:2]][0] != clean_name(dname, "district"):
                raise ValueError(f"{self.path}: municipality {code} is not in district {code[:2]}")
            if nuts3 not in self.nuts3:
                raise ValueError(f"{self.path}: municipality {code} in unknown NUTS 3 {nuts3}")
            self.municipalities[code] = (clean_name(n, "municipality"), nuts3)
        self.parishes = []  # (code, name, short name, source geometry, area_ha)
        self.name_mismatches = 0
        for code, name, mname, short, geom, area in zip(f["dtmnfr"], f["freguesia"], f["municipio"],
                                                       f["designacao_simplificada"], geoms, f["area_ha"]):
            code = check_code(code, "dtmnfr", "parish")
            if code[:4] not in self.municipalities:
                raise ValueError(f"{self.path}: parish {code} is not in a municipality")
            self.name_mismatches += clean_name(mname, "municipality") != self.municipalities[code[:4]][0]
            name = clean_name(name, "parish")
            self.parishes.append((code, name, clean_name(short, "parish") if short else name, geom, float(area)))
        codes = [p[0] for p in self.parishes]
        if len(set(codes)) != len(codes):
            raise ValueError(f"{self.path}: repeated parish codes")
        log(f"CAOP {key}: {len(self.parishes)} parishes, {len(self.municipalities)} municipalities, "
            f"{len(self.districts)} districts or islands, CRS {self.crs}")

    def simplify(self, tolerance):
        source = np.array([p[3] for p in self.parishes], dtype=object)
        self.qa = {"coverage_valid": bool(shapely.coverage_is_valid(source)),
                   "invalid_edge_m": float(shapely.length(shapely.coverage_invalid_edges(source)).sum()),
                   "source_vertices": int(shapely.get_num_coordinates(source).sum())}
        if not self.qa["coverage_valid"]:
            raise ValueError(f"{self.path}: the parishes are not a valid coverage")
        u = shapely.coverage_union_all(source)
        self.qa["union_holes"] = sum(len(p.interiors) for p in shapely.get_parts(u))
        simple = shapely.coverage_simplify(source, tolerance)
        if not shapely.coverage_is_valid(simple) or not shapely.is_valid(simple).all() or shapely.is_empty(simple).any():
            raise ValueError(f"{self.path}: coverage_simplify({tolerance}) broke the coverage")
        self.qa.update(simplified_vertices=int(shapely.get_num_coordinates(simple).sum()), tolerance_m=tolerance)
        self.source, self.simple = source, simple

    def checks(self):
        """CAOP's own municipality and district polygons against the union of their parishes."""
        out = {}
        for layer, key, size in (("municipios", "dtmn", 4), ("distritos", "dt", 2)):
            _, geoms, data = read_layer(self.path, f"{self.prefix}_{layer}", (key,))
            groups = defaultdict(list)
            for p, geom in zip(self.parishes, self.source):
                groups[p[0][:size]].append(geom)
            worst = 0.0
            for code, geom in zip(data[key], geoms):
                u = shapely.coverage_union_all(np.array(groups[str(code)], dtype=object))
                worst = max(worst, shapely.area(shapely.symmetric_difference(geom, u)))
            out[f"{layer}_vs_parish_union_max_m2"] = round(float(worst), 3)
        return out


# -- Spain and France: geoBoundaries ---------------------------------------------------------------------

def read_gb(stem, shape_type, iso3):
    path = GB_DIR / f"{stem}.geojson"
    crs, geoms, f = read_layer(path, None, ("shapeName", "shapeISO", "shapeID", "shapeGroup", "shapeType"))
    for group, kind in zip(f["shapeGroup"], f["shapeType"]):
        if group != iso3 or kind != shape_type:
            raise ValueError(f"{path}: a {kind} of {group}, expected {shape_type} of {iso3}")
    names = [clean_name(n, stem) for n in f["shapeName"]]
    ids = [check_code(i, "shapeID", f"{stem} shapeID") for i in f["shapeID"]]
    isos = [str(i or "").strip() for i in f["shapeISO"]]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: repeated shapeID")
    return {"path": path, "crs": crs, "declared_crs": geojson_crs(path), "names": names, "ids": ids,
            "isos": isos, "geoms": geoms}


def gb_codes(layer):
    """shapeISO where every unit has a distinct real ISO 3166-2 code, else shapeID (ids are unique)."""
    isos = layer["isos"]
    if all(CODE["iso"].match(i) for i in isos) and len(set(isos)) == len(isos):
        return list(isos), "shapeISO"
    return list(layer["ids"]), "shapeID"


def overlaps(geoms, names):
    tree = shapely.STRtree(geoms)
    left, right = tree.query(geoms, predicate="intersects")
    total, worst = 0.0, []
    for i, j in zip(left, right):
        if i < j:
            a = float(shapely.area(shapely.intersection(geoms[i], geoms[j])))
            if a > 0:
                total += a
                worst.append({"a": names[i], "b": names[j], "km2": round(a / 1e6, 6)})
    return total, sorted(worst, key=lambda w: -w["km2"])[:5]


def holes(union_geom, back):
    out = []
    for poly in shapely.get_parts(union_geom):
        for ring in poly.interiors:
            hole = shapely.Polygon(ring)
            p = shapely.point_on_surface(hole)
            lng, lat = back.transform(p.x, p.y)
            out.append({"km2": round(hole.area / 1e6, 4), "lat": round(lat, 5), "lng": round(lng, 5)})
    return sorted(out, key=lambda h: -h["km2"])


class GeoBoundaries:
    """One country's provinces or departments (leaves) and the regions above them."""

    def __init__(self, country, log):
        iso3, self.crs_metric, self.upper_level, self.leaf_level = GB_COUNTRIES[country]
        self.country, self.iso3 = country, iso3
        self.adm2, self.adm1, self.adm0 = (read_gb(f"{iso3}-ADM{n}", f"ADM{n}", iso3) for n in (2, 1, 0))
        to_m = transformer(self.adm2["crs"], self.crs_metric)
        self.back = transformer(self.crs_metric, WGS84)
        self.to_metric = to_m
        self.leaf_m = apply(to_m, self.adm2["geoms"])
        self.upper_m = apply(to_m, self.adm1["geoms"])
        self.outline_m = apply(to_m, self.adm0["geoms"])
        self.upper_codes, self.upper_code_kind = gb_codes(self.adm1)
        self.leaf_codes, self.leaf_code_kind = gb_codes(self.adm2)
        tree = shapely.STRtree(self.upper_m)
        self.parent, shares = [], []
        for geom in self.leaf_m:
            best = max(((float(shapely.area(shapely.intersection(geom, self.upper_m[j]))) / geom.area, int(j))
                        for j in tree.query(geom, predicate="intersects")), default=(0.0, -1))
            if best[0] < 0.95:
                raise ValueError(f"{iso3}: a unit lies in no single ADM1 (best share {best[0]:.3f})")
            self.parent.append(best[1])
            shares.append(best[0])
        self.min_share = min(shares)
        log(f"geoBoundaries {iso3}: {len(self.leaf_m)} ADM2 in {len(self.upper_m)} ADM1, CRS {self.adm2['crs']} "
            f"(declared {self.adm2['declared_crs']}); smallest share in its ADM1 {self.min_share:.4f}")

    def simplify(self, tolerance, log):
        names = self.adm2["names"]
        qa = {"coverage_valid": bool(shapely.coverage_is_valid(self.leaf_m)),
              "invalid_edge_m": float(shapely.length(shapely.coverage_invalid_edges(self.leaf_m)).sum()),
              "source_vertices": int(shapely.get_num_coordinates(self.leaf_m).sum())}
        total, worst = overlaps(self.leaf_m, names)
        qa.update(overlap_km2=round(total / 1e6, 6), worst_overlaps=worst)
        u = shapely.union_all(self.leaf_m)
        qa["union_holes"] = holes(u, self.back)
        leaves = self.leaf_m
        if not qa["coverage_valid"]:
            leaves = shapely.coverage_clean(self.leaf_m, gap_width=50.0)
            qa["cleaned"] = {"gap_width_m": 50.0, "valid_after": bool(shapely.coverage_is_valid(leaves))}
            log(f"{self.iso3}: ADM2 cleaned with coverage_clean")
        simple = shapely.coverage_simplify(leaves, tolerance)
        if not shapely.coverage_is_valid(simple) or not shapely.is_valid(simple).all() or shapely.is_empty(simple).any():
            raise ValueError(f"{self.iso3}: coverage_simplify({tolerance}) broke the coverage")
        qa.update(tolerance_m=tolerance, simplified_vertices=int(shapely.get_num_coordinates(simple).sum()))
        # how the ADM1 and ADM0 polygons differ from the unions of the provinces or departments
        upper = []
        for j, geom in enumerate(self.upper_m):
            kids = [i for i, p in enumerate(self.parent) if p == j]
            sym = float(shapely.area(shapely.symmetric_difference(geom, shapely.union_all(self.leaf_m[kids]))))
            upper.append({"name": self.adm1["names"][j], "units": len(kids), "sym_diff_km2": round(sym / 1e6, 3),
                          "share": round(sym / geom.area, 6)})
        sym0 = float(shapely.area(shapely.symmetric_difference(shapely.union_all(self.outline_m), u)))
        qa.update(adm1_vs_adm2_union=sorted(upper, key=lambda r: -r["sym_diff_km2"]),
                  adm0_vs_adm2_union={"sym_diff_km2": round(sym0 / 1e6, 1), "share": round(sym0 / u.area, 5),
                                      "adm0_vertices": int(shapely.get_num_coordinates(self.outline_m).sum())},
                  adm0_bounds_wgs84=[round(v, 3) for v in shapely.bounds(self.adm0["geoms"][0])])
        self.qa, self.simple = qa, simple
        self.upper_m = self.outline_m = None  # compared; no longer needed
        self.adm1["geoms"] = self.adm0["geoms"] = None
        log(f"{self.iso3}: coverage valid {qa['coverage_valid']}, overlaps {qa['overlap_km2']} km2, "
            f"{len(qa['union_holes'])} holes; simplified {qa['source_vertices']:,} -> {qa['simplified_vertices']:,} vertices")


# -- cross-border overlaps and gaps ---------------------------------------------------------------------

def resolve_overlaps(leaves, log):
    """Cut each lower-priority leaf where it overlaps a higher-priority country's leaves (WGS84, in place)."""
    report = defaultdict(lambda: {"overlap_km2": 0.0, "leaves_cut": 0, "parts_over_100_m2": 0, "largest": []})
    done = []
    for country in PRIORITY:
        mine = [r for r in leaves if r["country"] == country]
        if done:
            higher = np.array([r["geometry"] for r in done], dtype=object)
            tree = shapely.STRtree(higher)
            for r in mine:
                hits = tree.query(r["geometry"], predicate="intersects")
                if not len(hits):
                    continue
                other = shapely.union_all(higher[hits])
                inter = shapely.intersection(r["geometry"], other)
                area = geodesic_m2(inter)
                if area <= 0:
                    continue
                cut = polygonal(shapely.difference(r["geometry"], other))
                if cut is None:
                    raise ValueError(f"{r['zone_id']} lies entirely inside another country")
                entry = report[f"{done[hits[0]]['country']}-{country}"]
                entry["overlap_km2"] += area / 1e6
                entry["leaves_cut"] += 1
                for p in shapely.get_parts(inter):
                    if p.geom_type == "Polygon" and geodesic_m2(p) >= OVERLAP_PART_M2:
                        entry["parts_over_100_m2"] += 1
                        to, _ = scaled_frame(p.centroid.y)
                        width = 2 * shapely.length(shapely.maximum_inscribed_circle(to(p), 1e-7)) * Z.M_PER_DEG
                        entry["largest"].append({"cut_from": r["name"], "km2": round(geodesic_m2(p) / 1e6, 4),
                                                 "max_width_m": round(float(width), 1),
                                                 "lat": round(float(p.centroid.y), 4),
                                                 "lng": round(float(p.centroid.x), 4)})
                r["geometry"] = cut
        done.extend(mine)
    out = {}
    for key, entry in report.items():
        largest = sorted(entry["largest"], key=lambda w: -w["km2"])
        out[key] = {"overlap_km2": round(entry["overlap_km2"], 4), "given_to": key.split("-")[0],
                    "leaves_cut": entry["leaves_cut"], "parts_over_100_m2": entry["parts_over_100_m2"],
                    "widest_part_m": max((w["max_width_m"] for w in largest), default=0.0), "largest": largest[:5]}
        log(f"cross-border {key}: {entry['overlap_km2']:.3f} km2 of overlap given to {key.split('-')[0]} "
            f"({entry['parts_over_100_m2']} parts over 100 m2, widest {out[key]['widest_part_m']} m)")
    return out


def border_gaps(leaves, a, b, crs):
    """Along the a-b border, sample a's boundary every BORDER_STEP_M where b is within BORDER_REACH_M:
    how much of it touches b, how much faces a gap and how wide, and how much still overlaps."""
    ga = np.array([r["geometry"] for r in leaves if r["country"] == a], dtype=object)
    gb = np.array([r["geometry"] for r in leaves if r["country"] == b], dtype=object)
    reach_deg = 2 * BORDER_REACH_M / Z.M_PER_DEG
    near_a = np.unique(shapely.STRtree(gb).query(ga, predicate="dwithin", distance=reach_deg)[0])
    near_b = np.unique(shapely.STRtree(ga).query(gb, predicate="dwithin", distance=reach_deg)[0])
    if not len(near_a) or not len(near_b):
        return {"border_km": 0.0}
    t = transformer(WGS84, crs)
    ua = shapely.union_all(apply(t, ga[near_a]))
    ub = shapely.union_all(apply(t, gb[near_b]))
    coords = shapely.get_coordinates(shapely.segmentize(shapely.boundary(ua), BORDER_STEP_M))
    tree = shapely.STRtree(segments(ub))
    (which, _), dist = tree.query_nearest(shapely.points(coords), return_distance=True, all_matches=False)
    d = np.empty(len(coords))
    d[which] = dist
    inside = shapely.contains_xy(ub, coords[:, 0], coords[:, 1])
    facing = d <= BORDER_REACH_M
    touching = facing & (d <= 1.0)
    gap = facing & ~touching & ~inside
    overlap = facing & ~touching & inside
    km = BORDER_STEP_M / 1000
    widths = d[gap]
    return {"measured_in": crs, "border_km": round(facing.sum() * km, 1), "touching_km": round(touching.sum() * km, 1),
            "gap_km": round(gap.sum() * km, 1), "overlap_km": round(overlap.sum() * km, 1),
            "gap_width_m": {"median": round(float(np.median(widths)), 1) if len(widths) else 0.0,
                            "p95": round(float(np.percentile(widths, 95)), 1) if len(widths) else 0.0,
                            "max": round(float(widths.max()), 1) if len(widths) else 0.0},
            "gap_area_km2_approx": round(float(widths.sum() * BORDER_STEP_M / 1e6), 3),
            "sampled_every_m": BORDER_STEP_M, "reach_m": BORDER_REACH_M}


# -- display outlines of the coarser zones --------------------------------------------------------------

def outlines(rows, geoms, log):
    """Simplified display geometry for coarser zones: coverage_simplify per (country, tree, level) in a
    scaled-degree frame, so neighbours stay gapless. Returns (geometries, outline deviations in metres)."""
    out = list(geoms)
    dev = [0.0] * len(rows)
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        if not r["is_leaf"] and OUTLINE_TOLERANCE.get(r["level"]):
            groups[(r["country"], r["tree"], r["level"])].append(i)
    for (country, tree, level), idx in sorted(groups.items()):
        lat0 = float(np.mean([(rows[i]["south"] + rows[i]["north"]) / 2 for i in idx]))
        to, back = scaled_frame(lat0)
        exact = np.array([geoms[i] for i in idx], dtype=object)
        scaled = to(exact)
        tolerance = OUTLINE_TOLERANCE[level] / Z.M_PER_DEG
        try:
            simple = shapely.coverage_simplify(scaled, tolerance) if shapely.coverage_is_valid(scaled) \
                else shapely.simplify(scaled, tolerance, preserve_topology=True)
        except shapely.errors.GEOSException:
            continue
        simple = back(simple)
        for k, i in enumerate(idx):
            g = simple[k]
            if g is None or shapely.is_empty(g) or not shapely.is_valid(g):
                continue
            # metres, measured in the scaled frame (a few % off far from lat0: display only)
            dev[i] = deviation_m(to(geoms[i]), to(g), step=SAMPLE_M / Z.M_PER_DEG * 10) * Z.M_PER_DEG
            out[i] = g
        log(f"outlines {country} {tree} {level}: {len(idx)} zones, "
            f"{int(shapely.get_num_coordinates(exact).sum()):,} -> "
            f"{int(sum(shapely.get_num_coordinates(out[i]) for i in idx)):,} vertices")
    return out, dev


# -- assembly -------------------------------------------------------------------------------------------

# Where each country's leaves may lie (west, south, east, north): mainland and islands. A unit outside,
# such as an overseas French department in a later geoBoundaries build, stops the build.
SCOPE_BOXES = {"PT": ((-10.0, 36.8, -6.1, 42.2), (-31.5, 36.5, -24.5, 39.9), (-17.5, 29.8, -15.5, 33.2)),
               "ES": ((-9.6, 35.0, 4.6, 43.9), (-18.4, 27.4, -13.0, 29.6)),
               "FR": ((-5.6, 41.2, 9.8, 51.2),)}


def check_scope(leaves):
    for r in leaves:
        west, south, east, north = shapely.bounds(r["geometry"])
        if not any(w <= west and s <= south and east <= e and north <= n for w, s, e, n in SCOPE_BOXES[r["country"]]):
            raise ValueError(f"{r['zone_id']} ({r['name']}) lies outside {r['country']}'s scope: "
                             f"{west:.2f}, {south:.2f}, {east:.2f}, {north:.2f}")


def caop_zones(files):
    """Leaf records (geometry still to come) and coarse records for Portugal."""
    leaves, coarse, seen = [], {}, set()

    def add(rec):
        if rec["zone_id"] not in coarse:
            coarse[rec["zone_id"]] = rec

    add({"zone_id": "PT", "name": "Portugal", "level": "country", "country": "PT", "parent_id": None,
         "source": "caop2025", "source_code": "PT"})
    for f in files:
        source = f"caop2025:{f.prefix}"
        for code, name in f.nuts2.items():
            add({"zone_id": f"PT:nuts2:{code}", "name": name, "level": "nuts2", "country": "PT", "parent_id": None,
                 "tree": "nuts", "source": source, "source_code": code})
        for code, name in f.nuts3.items():
            add({"zone_id": f"PT:nuts3:{code}", "name": name, "level": "nuts3", "country": "PT",
                 "parent_id": f"PT:nuts2:{code[:2]}", "tree": "nuts", "source": source, "source_code": code})
        for code, (name, nuts1) in f.districts.items():
            if nuts1 == "1":
                add({"zone_id": f"PT:district:{code}", "name": name, "level": "district", "country": "PT",
                     "parent_id": "PT", "source": source, "source_code": code})
            else:
                region = f"PT:autonomous_region:{nuts1}"
                add({"zone_id": region, "name": f.nuts1[nuts1], "level": "autonomous_region", "country": "PT",
                     "parent_id": "PT", "source": source, "source_code": nuts1})
                add({"zone_id": f"PT:island:{code}", "name": name, "level": "island", "country": "PT",
                     "parent_id": region, "source": source, "source_code": code})
        for code, (name, nuts3) in f.municipalities.items():
            district, nuts1 = code[:2], f.districts[code[:2]][1]
            parent = f"PT:district:{district}" if nuts1 == "1" else f"PT:island:{district}"
            add({"zone_id": f"PT:municipality:{code}", "name": name, "level": "municipality", "country": "PT",
                 "parent_id": parent, "also_in": [f"PT:nuts3:{nuts3}"], "source": source, "source_code": code})
        for k, (code, name, short, _, area_ha) in enumerate(f.parishes):
            zid = f"PT:parish:{code}"
            if zid in seen:
                raise ValueError(f"parish {code} appears in two CAOP files")
            seen.add(zid)
            leaves.append({"zone_id": zid, "name": name, "short_name": short, "level": "parish", "country": "PT",
                           "parent_id": f"PT:municipality:{code[:4]}", "source": source, "source_code": code,
                           "file": f, "k": k, "source_area_km2": area_ha / 100})
    return leaves, list(coarse.values())


def gb_zones(g):
    names = {"ES": "Spain", "FR": "France"}
    upper_ids = [f"{g.country}:{g.upper_level}:{c}" for c in g.upper_codes]
    coarse = [{"zone_id": g.country, "name": names[g.country], "level": "country", "country": g.country,
               "parent_id": None, "source": f"geoboundaries:{g.iso3}-ADM0", "source_code": g.adm0["ids"][0]}]
    used = sorted(set(g.parent))
    for j in used:
        coarse.append({"zone_id": upper_ids[j], "name": g.adm1["names"][j], "level": g.upper_level,
                       "country": g.country, "parent_id": g.country, "source": f"geoboundaries:{g.iso3}-ADM1",
                       "source_code": g.upper_codes[j]})
    leaves = []
    for i, code in enumerate(g.leaf_codes):
        leaves.append({"zone_id": f"{g.country}:{g.leaf_level}:{code}", "name": g.adm2["names"][i],
                       "level": g.leaf_level, "country": g.country, "parent_id": upper_ids[g.parent[i]],
                       "source": f"geoboundaries:{g.iso3}-ADM2", "source_code": code, "gb": g, "k": i})
    return leaves, coarse


def write_gpkg(path, rows, geoms, layer_metadata):
    fields = list(Z.COLUMNS)
    data = []
    for c in fields:
        values = [r[c] for r in rows]
        if c in ("also_in",):
            values = [json.dumps(v, ensure_ascii=False) for v in values]
        elif c == "hull":
            values = [json.dumps([[round(float(x), 7), round(float(y), 7)] for x, y in v]) for v in values]
        if c in ("depth", "n_children", "n_leaves", "n_parts", "n_vertices"):
            data.append(np.array(values, dtype=np.int64))
        elif c == "is_leaf":
            data.append(np.array([int(bool(v)) for v in values], dtype=np.int32))
        elif c in ("area_km2", "rep_lat", "rep_lng", "rep_radius_m", "south", "west", "north", "east", "deviation_m",
                   "outline_deviation_m"):
            data.append(np.array(values, dtype=np.float64))
        else:
            data.append(np.array(values, dtype=object))
    wkb = shapely.to_wkb(np.array([_multi(g) for g in geoms], dtype=object))
    pyogrio.raw.write(str(path), wkb, data, fields, layer=Z.LAYER, driver="GPKG", geometry_type="MultiPolygon",
                      crs=WGS84, layer_metadata=layer_metadata)


def _multi(geom):
    return geom if geom.geom_type == "MultiPolygon" else shapely.MultiPolygon([geom])


def self_check(path, log):
    with Z.Zones.open(path) as zones:
        leaves = [z for z in zones if z.is_leaf]
        wrong = [z.id for z in leaves if (loc := zones.locate(*z.rep)) is None or loc.leaf.id != z.id
                 or loc.distance_m != 0]
        rng = np.random.default_rng(32)
        lat = rng.uniform(36.0, 43.5, 4000)
        lng = rng.uniform(-9.5, 3.3, 4000)
        t = time.perf_counter()
        found = sum(zones.locate(a, b) is not None for a, b in zip(lat, lng))
        per_ms = (time.perf_counter() - t) / len(lat) * 1000
        log(f"self-check: {len(leaves) - len(wrong)}/{len(leaves)} leaf points locate to their leaf; "
            f"locate {per_ms:.3f} ms per uncached call over random Iberian points ({found} in a zone)")
        return {"leaf_rep_points_ok": len(leaves) - len(wrong), "leaf_rep_points_wrong": wrong[:20],
                "locate_ms_per_call_uncached": round(per_ms, 4), "random_points": len(lat), "random_found": int(found)}


def build(out=Z.DEFAULT_PATH, tolerance=None, log=log_line):
    out = Path(out)
    tolerance = {**LEAF_TOLERANCE, **(tolerance or {})}
    started, t0 = datetime.now(timezone.utc), time.monotonic()
    out.parent.mkdir(parents=True, exist_ok=True)
    for stale in out.parent.glob(f"{out.stem}.tmp-*{out.suffix}"):
        stale.unlink()
    tmp = out.with_name(f"{out.stem}.tmp-{os.getpid()}{out.suffix}")  # GDAL wants the .gpkg extension
    dl = downloads()
    sources, qa = [], {"caop": {}, "geoboundaries": {}}

    # Portugal
    files = [Caop(key, rel, prefix, archive, log) for key, rel, prefix, archive in CAOP_FILES]
    for f in files:
        f.simplify(tolerance["PT"])
        qa["caop"][f.key] = {**f.qa, "parish_municipality_name_mismatches": f.name_mismatches, **f.checks()}
        to_wgs = transformer(f.crs, WGS84)
        f.to_wgs, f.from_wgs = to_wgs, transformer(WGS84, f.crs)
        f.stored = apply(to_wgs, f.simple)
        contents = gpkg_contents(f.path)
        sources.append({"key": f.key, "country": "PT", "version": "CAOP 2025", **file_record(f.path),
                        "download": dl.get(f.archive), "archive": f.archive, "declared_crs": f.crs,
                        "crs_name": pyproj.CRS(f.crs).name, "transform": transform_record(to_wgs),
                        "layers": {name: contents.get(name) for name in
                                   (f"{f.prefix}_{x}" for x in ("freguesias", "municipios", "distritos", "nuts1",
                                                                "nuts2", "nuts3"))},
                        "layers_note": "gpkg_contents.last_change of each layer read"})
        log(f"CAOP {f.key}: simplified {f.qa['source_vertices']:,} -> {f.qa['simplified_vertices']:,} vertices")
    pt_leaves, pt_coarse = caop_zones(files)
    for r in pt_leaves:
        r["geometry"] = polygonal(r["file"].stored[r["k"]])

    # Spain and France
    gb_leaves, gb_coarse, gbs = [], [], []
    for country in ("ES", "FR"):
        g = GeoBoundaries(country, log)
        g.simplify(tolerance[country], log)
        g.stored = apply(g.back, g.simple)
        qa["geoboundaries"][g.iso3] = {**g.qa, "parent_by_largest_overlap_min_share": round(g.min_share, 5),
                                       "upper_code": g.upper_code_kind, "leaf_code": g.leaf_code_kind}
        for n, layer in ((2, g.adm2), (1, g.adm1), (0, g.adm0)):
            name = f"{g.iso3}-ADM{n}.geojson"
            sources.append({"key": f"geoboundaries-{g.iso3}-ADM{n}", "country": country,
                            "version": _gb_version(dl.get(name)), **file_record(layer["path"]),
                            "download": dl.get(name), "declared_crs": layer["declared_crs"], "read_crs": layer["crs"],
                            "metric_crs": g.crs_metric, "transform": transform_record(g.to_metric),
                            "units": len(layer["names"]), "used_for": {2: "leaves", 1: "names, codes, parents",
                                                                       0: "comparison only"}[n]})
        leaves, coarse = gb_zones(g)
        for r in leaves:
            r["geometry"] = polygonal(g.stored[r["k"]])
        gb_leaves += leaves
        gb_coarse += coarse
        gbs.append(g)
    prt = read_gb("PRT-ADM0", "ADM0", "PRT")
    sources.append({"key": "geoboundaries-PRT-ADM0", "country": "PT", "version": _gb_version(dl.get("PRT-ADM0.geojson")),
                    **file_record(prt["path"]), "download": dl.get("PRT-ADM0.geojson"),
                    "declared_crs": prt["declared_crs"], "read_crs": prt["crs"], "used_for": "comparison only"})

    leaves = pt_leaves + gb_leaves
    if any(r["geometry"] is None for r in leaves):
        raise ValueError("a leaf lost its geometry")
    qa["cross_border_overlaps"] = resolve_overlaps(leaves, log)
    qa["cross_border_gaps"] = {f"{a}-{b}": border_gaps(leaves, a, b, crs) for a, b, crs in BORDERS}
    for key, gap in qa["cross_border_gaps"].items():
        log(f"border {key}: {gap.get('border_km')} km facing, {gap.get('touching_km')} touching, "
            f"{gap.get('gap_km')} km of gap (median {gap.get('gap_width_m', {}).get('median')} m)")

    # deviations of the stored leaves from their sources, in the metric CRS
    caop_area = {}
    for r in leaves:
        if r["country"] == "PT":
            f = r["file"]
            src, back = f.source[r["k"]], f.from_wgs
            caop_area[r["zone_id"]] = r["source_area_km2"]
        else:
            g = r["gb"]
            src, back = g.leaf_m[r["k"]], g.to_metric
        stored_m = apply(back, shapely.segmentize(r["geometry"], STORED_SEGMENT_DEG))
        r["deviation_m"] = deviation_m(src, stored_m)
    dev = defaultdict(list)
    for r in leaves:
        dev[r["country"]].append(r["deviation_m"])
    qa["leaf_deviation_m"] = {c: {"median": round(float(np.median(v)), 1), "p95": round(float(np.percentile(v, 95)), 1),
                                  "p99": round(float(np.percentile(v, 99)), 1), "max": round(float(np.max(v)), 1)}
                              for c, v in dev.items()}
    log("leaf deviation (m): " + "; ".join(f"{c} median {s['median']} p99 {s['p99']} max {s['max']}"
                                           for c, s in qa["leaf_deviation_m"].items()))

    # all zones
    check_scope(leaves)
    clean = [{k: v for k, v in r.items() if k not in ("file", "k", "gb", "source_area_km2", "overlap_cut_km2")}
             for r in leaves]
    rows, geoms = Z.derive(clean, pt_coarse + gb_coarse)
    log(f"derived {len(rows)} zones")
    laea = transformer(WGS84, "EPSG:3035")  # equal-area: symmetric differences in km2
    portugal = apply(laea, geoms[next(i for i, row in enumerate(rows) if row["zone_id"] == "PT")])
    outline = apply(laea, shapely.union_all(prt["geoms"]))
    sym = float(shapely.area(shapely.symmetric_difference(portugal, outline)))
    qa["caop_vs_prt_adm0"] = {"sym_diff_km2": round(sym / 1e6, 1), "share": round(sym / shapely.area(portugal), 5),
                              "measured_in": "EPSG:3035", "adm0_vertices": int(shapely.get_num_coordinates(prt["geoms"]).sum())}
    log(f"CAOP Portugal vs geoBoundaries PRT-ADM0: {sym / 1e6:.1f} km2 symmetric difference")
    del prt["geoms"]
    ratios = [row["area_km2"] / caop_area[row["zone_id"]] for row in rows
              if caop_area.get(row["zone_id"], 0) > 0]
    qa["caop_area_vs_area_ha"] = {"parishes": len(ratios), "median_ratio": round(float(np.median(ratios)), 6),
                                  "min_ratio": round(float(np.min(ratios)), 4), "max_ratio": round(float(np.max(ratios)), 4)}
    stored, outline_dev = outlines(rows, geoms, log)
    for row, d in zip(rows, outline_dev):
        row["outline_deviation_m"] = round(d, 1)
    for row, g in zip(rows, stored):
        row["n_vertices"] = int(shapely.get_num_coordinates(g))
    counts = defaultdict(Counter)
    for row in rows:
        counts[row["country"]][row["level"]] += 1

    built = started.isoformat(timespec="seconds")
    layer_metadata = {"schema": Z.SCHEMA, "built_utc": built, "script": "tools/build_zones.py"}
    try:
        write_gpkg(tmp, rows, stored, layer_metadata)
        os.replace(tmp, out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    report = {
        "schema": Z.SCHEMA, "built_utc": built, "script": "tools/build_zones.py",
        "python": sys.version.split()[0],
        "libraries": {"shapely": shapely.__version__, "geos": shapely.geos_version_string,
                      "pyogrio": pyogrio.__version__, "gdal": pyogrio.__gdal_version_string__,
                      "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str, "numpy": np.__version__},
        "output": {"path": shown_path(out), "layer": Z.LAYER, "crs": WGS84,
                   "axis_order": "GeoPackage x = longitude, y = latitude", "features": len(rows),
                   "columns": list(Z.COLUMNS), "bytes": out.stat().st_size},
        "scope": {"portugal": "mainland, Azores, Madeira (CAOP 2025)",
                  "spain": "mainland, Balearics, Canaries, Ceuta, Melilla (geoBoundaries ESP)",
                  "france": "metropolitan France and Corsica (geoBoundaries FRA)",
                  "overseas_france": "out of the default scope; this geoBoundaries build has no overseas unit "
                                     "(FRA-ADM0 bounds " + str(qa["geoboundaries"]["FRA"]["adm0_bounds_wgs84"]) + ")",
                  "others": "Andorra, Gibraltar, Monaco and other neighbours are in no zone"},
        "sources": sources,
        "parameters": {"leaf_tolerance_m": tolerance, "tolerance_kind": "shapely.coverage_simplify (Visvalingam-"
                       "Whyatt; about the square root of the removed triangles' area), not a distance: see deviation_m",
                       "leaf_metric_crs": {"PT": "each CAOP file's own CRS", "ES": GB_COUNTRIES["ES"][1],
                                           "FR": GB_COUNTRIES["FR"][1]},
                       "outline_tolerance_m": OUTLINE_TOLERANCE,
                       "outline_note": "display geometry of coarser zones only; containment and bounds use the leaves",
                       "deviation_sample_m": SAMPLE_M, "stored_segment_deg": STORED_SEGMENT_DEG,
                       "cross_border_priority": list(PRIORITY), "border_step_m": BORDER_STEP_M,
                       "border_reach_m": BORDER_REACH_M, "min_part_m2": MIN_PART_M2, "snap_m_default": Z.SNAP_M},
        "counts": {c: dict(sorted(v.items())) for c, v in counts.items()},
        "qa": qa,
    }
    report["self_check"] = self_check(out, log)
    report["build_seconds"] = round(time.monotonic() - t0, 1)
    report["peak_rss_mb"] = peak_rss_mb()
    side = out.with_suffix(".json")
    tmp_json = side.with_name(f"{side.name}.tmp-{os.getpid()}")
    tmp_json.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=_json_default) + "\n",
                        encoding="utf-8")
    os.replace(tmp_json, side)
    return report


def _gb_version(download):
    if not download:
        return "geoBoundaries gbOpen (download record missing)"
    m = re.search(r"/geoBoundaries/raw/([0-9a-f]{7,40})/", download["url"])
    return f"geoBoundaries gbOpen, repository commit {m[1]}" if m else "geoBoundaries gbOpen"


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serialisable: {type(value)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Z.DEFAULT_PATH, help="zone file (default: Data/index/zones.gpkg)")
    ap.add_argument("--tolerance", action="append", default=[], metavar="CC=M",
                    help="leaf simplification tolerance per country, e.g. PT=10 (default: %s)" % LEAF_TOLERANCE)
    args = ap.parse_args()
    tolerance = {}
    for item in args.tolerance:
        country, _, value = item.partition("=")
        if country not in LEAF_TOLERANCE or not value:
            ap.error(f"--tolerance takes CC=metres with CC in {sorted(LEAF_TOLERANCE)}, got {item!r}")
        tolerance[country] = float(value)
    report = build(args.out, tolerance)
    counts = report["counts"]
    log_line(f"wrote {report['output']['path']}: {report['output']['bytes'] / 1e6:.1f} MB, "
             f"{report['output']['features']:,} zones in {report['build_seconds']:.0f} s; "
             + "; ".join(f"{c} " + ", ".join(f"{n} {lvl}" for lvl, n in v.items()) for c, v in counts.items()))


if __name__ == "__main__":
    main()
