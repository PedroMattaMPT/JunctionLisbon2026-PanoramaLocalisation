"""P(urban) for a panorama whose category is unknown, from where its hypotheses lie (PLAN.md 1.3; T80).

The scorer's distance scale is 100 m for Urban and 10 km for non-Urban, and the organisers reveal the
label only after submission. A fixed 0.5 under-rewards precision in towns: the question gate stopped
urban cell refinement at 40-80 m (T42). So the probability comes from the hypotheses themselves: the
GHSL settlement model (SMOD E2025, 1 km, Data/geo/ghsl/smod) at each of the heaviest hypothesis
centres, urban iff class >= 21 (DEGURBA cities and towns, the rule Data/splits uses), weighted by
fusion weight, then squeezed into [LOW, HIGH] because the organisers' definition may differ from
DEGURBA's. It is geographic data about candidate places, never anything from another panorama. Log
the value as an assumption (Run evidence "urban_probability").

  from panoloc.urban import urban_probability
  p, detail = urban_probability(fused.hypotheses)       # None, detail when the raster is missing
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOD_TIF = REPO_ROOT / "Data/geo/ghsl/smod/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.tif"
URBAN_MIN_SMOD = 21
LOW, HIGH = 0.15, 0.85
TOP = 50
MAX_SPREAD_M = 20_000.0  # a hypothesis wider than this (a region, a country residual) says nothing about urbanity

_SOURCE = None


def _open():
    global _SOURCE
    if _SOURCE is None:
        import pyproj
        import rasterio
        src = rasterio.open(SMOD_TIF)
        _SOURCE = (src, pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True))
    return _SOURCE


def smod_classes(points):
    """GHSL SMOD class at each (lat, lng); values outside the raster's classes mean no data."""
    src, to_moll = _open()
    xy = [to_moll.transform(lng, lat) for lat, lng in points]
    return [int(v[0]) for v in src.sample(xy)]


def urban_probability(hypotheses, low=LOW, high=HIGH, top=TOP):
    """(p, detail): the weight share of the heaviest point-like hypotheses in GHSL urban cells, squeezed
    into [low, high]; (None, detail) when the raster is missing or no hypothesis is point-like."""
    from panoloc.fusion import spread_m
    pts = [h for h in sorted(hypotheses, key=lambda h: h.weight, reverse=True)[:top]
           if h.weight > 0 and spread_m(h) <= MAX_SPREAD_M]
    if not pts:
        return None, {"reason": "no point-like hypothesis"}
    try:
        classes = smod_classes([(h.lat, h.lng) for h in pts])
    except Exception as exc:  # raster missing or unreadable: the caller keeps its default
        return None, {"reason": f"GHSL SMOD unavailable: {type(exc).__name__}: {exc}"}
    total = sum(h.weight for h in pts)
    urban = sum(h.weight for h, c in zip(pts, classes) if c >= URBAN_MIN_SMOD and c <= 30)
    share = urban / total if total > 0 else 0.5
    p = low + (high - low) * share
    return p, {"urban_share": round(share, 4), "points": len(pts), "rule": f"SMOD class >= {URBAN_MIN_SMOD}",
               "range": [low, high], "top": [{"source": h.source, "smod": c} for h, c in zip(pts[:5], classes[:5])]}
