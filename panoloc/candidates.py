"""Typed candidate coordinates and the output contract (PLAN.md 3.3).

Every candidate says what its coordinate marks (`role`):
  camera    where a camera stood: the GPS of a reference photo (OSV-5M, Panoramax, Mapillary)
  landmark  the point of a named object: a Wikidata item, an OSM shop or building
  area      the representative point of an extent: a postcode, a town, a region, a geographic cell
A landmark or area point locates the place, not the camera. Only a verified match to a camera
reference, or an answered cell question, can pin down the camera itself.

Coordinates are WGS84 (lat, lng), latitude first: transform anything else before making a Candidate.
`accuracy_m` is the source's own stated position accuracy and stays None when the source gives none,
so an unknown accuracy never turns into a zero-metre error. `extent_m` is the radius of the object or
area around the point; say in `details["extent_source"]` whether it came from the source or was
assumed. `weight` is unnormalised support from fusion, not a calibrated probability.

An Output is what the agent returns:
  method              reference_camera | geographic_cell | coarse_candidate
  uncertainty_m       None when unknown
  uncertainty_source  geometric_bound | source_estimate | estimated_offset | unknown
It repeats its one coordinate in all 10 slots (PLAN.md 1.1). `coarse_output()` is the fallback when
there is neither a camera match nor an answered cell: the best-supported candidate or, with no
candidate at all, GLOBAL_FALLBACK.
"""
import math
from dataclasses import asdict, dataclass, field

from panoloc.scoring import MAX_ENTRIES, haversine_m

ROLES = ("camera", "landmark", "area")
OUTPUT_METHODS = ("reference_camera", "geographic_cell", "coarse_candidate")
UNCERTAINTY_SOURCES = ("geometric_bound", "source_estimate", "estimated_offset", "unknown")
ROLE_PREFERENCE = {"camera": 2, "landmark": 1, "area": 0}  # tie-break: the more specific coordinate wins


def _check_point(lat, lng):
    lat, lng = float(lat), float(lng)
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"not a WGS84 coordinate: lat={lat}, lng={lng}")
    return lat, lng


def _check_positive(name, value):
    if value is not None and not value > 0:
        raise ValueError(f"{name} must be > 0, or None when unknown; got {value}")


@dataclass
class Candidate:
    lat: float
    lng: float
    role: str
    source: str  # "<source>:<id>", e.g. "wikidata:Q1234", "geonames:2267057", "osv5m:4519"
    label: str = ""
    weight: float = 1.0
    accuracy_m: float | None = None
    extent_m: float | None = None
    country: str | None = None  # PT, ES or FR
    group: str | None = None  # correlated sources share a group (e.g. "pe-core") so fusion can cap them
    evidence: list = field(default_factory=list)  # evidence IDs from the run log
    details: dict = field(default_factory=dict)  # source-specific extras: types, population, match score

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {self.role!r}")
        self.lat, self.lng = _check_point(self.lat, self.lng)
        if ":" not in (self.source or ""):
            raise ValueError(f"source must look like '<source>:<id>', got {self.source!r}")
        if not self.weight >= 0:
            raise ValueError(f"weight must be >= 0, got {self.weight}")
        _check_positive("accuracy_m", self.accuracy_m)
        _check_positive("extent_m", self.extent_m)

    @property
    def point(self):
        return (self.lat, self.lng)

    def to_dict(self):
        """For Run.candidates(): plain JSON-ready fields."""
        return asdict(self)


@dataclass
class Output:
    lat: float
    lng: float
    method: str
    source_role: str  # what the output coordinate itself marks
    sources: list = field(default_factory=list)
    uncertainty_m: float | None = None
    uncertainty_source: str = "unknown"
    note: str = ""

    def __post_init__(self):
        self.lat, self.lng = _check_point(self.lat, self.lng)
        if self.method not in OUTPUT_METHODS:
            raise ValueError(f"method must be one of {OUTPUT_METHODS}, got {self.method!r}")
        if self.source_role not in ROLES:
            raise ValueError(f"source_role must be one of {ROLES}, got {self.source_role!r}")
        if self.uncertainty_source not in UNCERTAINTY_SOURCES:
            raise ValueError(f"uncertainty_source must be one of {UNCERTAINTY_SOURCES}")
        _check_positive("uncertainty_m", self.uncertainty_m)
        if (self.uncertainty_m is None) != (self.uncertainty_source == "unknown"):
            raise ValueError("uncertainty_source is 'unknown' exactly when uncertainty_m is None")
        if self.method == "reference_camera" and self.source_role != "camera":
            raise ValueError("a reference_camera output needs a camera coordinate")
        if self.method == "geographic_cell" and self.uncertainty_source != "geometric_bound":
            raise ValueError("a geographic_cell output carries the geometric bound of its cell")

    def coordinates(self, entries=MAX_ENTRIES):
        """The same coordinate in every slot (PLAN.md 1.1)."""
        return [(self.lat, self.lng)] * entries

    def log(self, run):
        """Record this output in a panoloc.runlog Run; returns the output ID."""
        return run.output(self.coordinates(), method=self.method, uncertainty_m=self.uncertainty_m,
                          uncertainty_source=self.uncertainty_source, sources=self.sources,
                          source_role=self.source_role, note=self.note or None)


# With nothing to go on, the expected-score optimum sits on the densest part of the prior, not its
# centre, because theta is sharply peaked. Until T39 calibrates a prior on external data, use the
# largest metropolitan area of the allowed region (population data, never the warm-up set).
GLOBAL_FALLBACK = Candidate(38.7223, -9.1393, "area", "fallback:lisbon", label="Lisbon (global fallback)",
                            weight=0.0, country="PT", details={"why": "largest metro area; placeholder prior"})


def normalise(candidates):
    """Copies with weights summing to 1; equal weights if they sum to 0."""
    total = sum(c.weight for c in candidates)
    n = len(candidates)
    return [Candidate(**{**asdict(c), "weight": c.weight / total if total > 0 else 1 / n}) for c in candidates]


def distinct(candidates, min_separation_m):
    """Greedy non-maximum suppression: the heaviest candidates at least min_separation_m apart.

    For distinct question options and internal alternatives, never for the final 10 slots.
    """
    kept = []
    for c in sorted(candidates, key=lambda c: (c.weight, ROLE_PREFERENCE[c.role]), reverse=True):
        if all(haversine_m(c.point, k.point) >= min_separation_m for k in kept):
            kept.append(c)
    return kept


def coarse_output(candidates, note=""):
    """Fallback output: the heaviest candidate (camera before landmark before area on ties), else GLOBAL_FALLBACK.

    Its uncertainty is the candidate's extent plus its stated accuracy when known; a landmark or area
    point with neither stays 'unknown' rather than pretending to be precise.
    """
    supported = [c for c in candidates if c.weight > 0]
    if not supported:
        best, note = GLOBAL_FALLBACK, note or "no supported candidate: global fallback"
    else:
        best = max(supported, key=lambda c: (c.weight, ROLE_PREFERENCE[c.role]))
    if best.extent_m is not None or best.accuracy_m is not None:
        uncertainty_m, uncertainty_source = (best.extent_m or 0) + (best.accuracy_m or 0), "source_estimate"
    else:
        uncertainty_m, uncertainty_source = None, "unknown"
    return Output(best.lat, best.lng, "coarse_candidate", best.role, [best.source], uncertainty_m,
                  uncertainty_source, note)
