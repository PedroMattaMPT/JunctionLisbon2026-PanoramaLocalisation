"""Conservative fusion of clues into weighted hypotheses, and the score-aware output (PLAN.md 1.1, 1.3, 3.2; T18).

Fusion turns what perception found into one weighted list of typed candidates (the hypotheses), then
picks the coordinate to repeat in all 10 slots. The probability arithmetic stays here, in code: no
model ever produces or sees any of these numbers.

Inputs:
  Clue  one observation that proposes alternative places: an OCR name or postcode looked up in the name
        index, the regions an OCR item names, one VLM landmark hypothesis, the kNN neighbours from the
        photo bank, the region head's top regions. Its candidates are alternatives for that one
        observation (at most one of them is the place), never independent support.
  Hint  soft country evidence (a plate layout, a post box colour, a sign's language). It scales
        candidates by country and never excludes one.

Every clue and hint has a correlation group, and clues in one group never confirm each other: one OCR
sign ("ocr:<sign_id>", whatever items it holds), the VLM ("vlm": one model's answers share its biases),
the PE-Core bank ("pe-core": kNN and the region head share an encoder), GeoCLIP ("geoclip").

Weights (PLAN 3.2: group and cap, never a product of every output):
  own(h)      reliability x w(h) / max(scale, sum of w over the clue). Name-index weights are comparable
              across lookups (panoloc.names), so a lookup clue has scale LOOKUP_SCALE: one strong
              unambiguous match carries most of the clue's reliability, fifteen "Igreja Matriz" share
              it, and a weak partial match stays weak. Generator clues (kNN, region head, GeoCLIP) are
              distributions: scale None, so their weights are normalised within the clue. A place that
              several clues propose (same source ID) keeps its best own(h).
  agreement   for each other group g: 1 + AGREE_GAIN x the best (reliability x match likelihood) among
              g's candidates compatible with h (closer than both spreads plus AGREE_SLACK_M). The
              product over groups is capped at MAX_AGREEMENT. Two signs that name places in one town
              lift that town; a sign never lifts itself. Country-wide alternatives and residuals lift
              nothing. An item pointing to a country whose region it can't name ("925 450 732": a PT mobile
              or a Toledo landline) gets a country-wide alternative, so the clue splits instead of betting
              everything on the one region it can name.
  country     P(country) x 3: hint ratios (HINT_RATIO by strength) multiply within a group, capped at
              MAX_GROUP_RATIO; groups multiply; every country keeps at least COUNTRY_FLOOR.
  weight(h) = own x agreement x country, then normalised over all hypotheses. One residual hypothesis
              per country is added (COUNTRY_FALLBACKS: its largest metropolitan area, spread
              FALLBACK_SPREAD_M, RESIDUAL_WEIGHT x P(country) before normalising), so a wrong clue can
              never remove the right country (PLAN 3.2) and a panorama with no clue still gets an answer.
Name clues are cleaned before fusion (T31 hand-off, measured on Panoramax val): overseas entries and
fuzzy matches of queries of FUZZY_MIN_LETTERS letters or fewer are dropped; office and organisation
entries are damped (OFFICE_FACTOR: an EU funding panel's "SDEF" named an energy office 62 km away);
when one country holds CONFIDENT_COUNTRY of the prior, name lookups search that country only (the
residuals keep the others); and a candidate shared by many places (ambiguity, OSM occurrences) lends
only 1/sqrt(n) of its agreement strength, so three generic names cannot outvote one unique match.
Constants: OCR name/postcode reliabilities, the region-head weight and REGION_CLUES were calibrated on
130 cached val panoramas (T39, tools/calibrate_fusion.py, kept only where both collection folds agreed);
the others are still hand-set. Weights are support, not calibrated probabilities.

Selection (PLAN 1.1, 1.3): each hypothesis is spread uniformly over a disc of radius spread_m(c): its
extent plus its stated accuracy, at least ROLE_SPREAD_M for its role, plus LANDMARK_VIEW_M for a
landmark (the camera stands some way from what it photographs). The disc is sampled on 3 rings of 8
bearings. A point's expected theta is the weighted mean of theta over those samples; the chosen point is
the centre of the hypothesis with the best value, among the MAX_POINTS heaviest. While the category is
unknown, the expected score is urban_probability x urban + (1 - urban_probability) x non-urban. The best
point under each category alone is recorded too, with whether the two differ (PLAN 1.3).

Output: coarse_candidate, its coordinate repeated 10 times. reference_camera needs a verified match
(details["verified_match"], T41); geographic_cell needs an answered cell (T42). The uncertainty is the
chosen hypothesis's spread when its extent or accuracy is known ("source_estimate"), else unknown.

  from panoloc.fusion import clues_from_ocr, clues_from_vlm, fuse, hints_from_ocr, hints_from_vlm, log_fusion
  with NameIndex.open() as names:
      clues = clues_from_ocr(ocr.items, names, {s.sign_id: s.confidence for s in ocr.signs})
      clues += clues_from_vlm(vlm.landmarks, vlm.hints, names)
  fused = fuse(clues, hints_from_ocr(ocr.items) + hints_from_vlm(vlm.hints), urban_probability=0.5)
  fused.hypotheses[:5], fused.country, fused.selection["point"]
  log_fusion(run, fused)
  fused.output.log(run)
"""
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field

import numpy as np

from panoloc.candidates import ROLE_PREFERENCE, Candidate, Output
from panoloc.names import STOPWORDS, normalise
from panoloc.scoring import BASE_POINTS, EARTH_RADIUS_M, MAX_ENTRIES, RANK_FACTOR, SCALE_M, ZERO_DISTANCE_M

COUNTRIES = ("PT", "ES", "FR")
STRENGTHS = ("strong", "medium-strong", "medium", "weak")  # COUNTRY_CLUES 0; OCR uses the same words

# Hand-set, except where a comment below gives the T39 calibration
HINT_RATIO = {"strong": 4.0, "medium-strong": 3.0, "medium": 2.0, "weak": 1.3}
MAX_GROUP_RATIO = 8.0
COUNTRY_FLOOR = 0.02
LOOKUP_SCALE = 1.0
AGREE_GAIN = 3.0
AGREE_SLACK_M = 500.0
MAX_AGREEMENT = 30.0
RESIDUAL_WEIGHT = 0.1
DEFAULT_URBAN_PROBABILITY = 0.5  # PLAN 1.3: an assumption, logged with every selection

# T39, Sun 01:30, tools/calibrate_fusion.py on 130 cached val panoramas (100 ES/FR + 30 PT): names x2 and
# region clues off were the changes both collection folds agreed on; with the region head x1.5 (pipeline)
# they raise both folds (2,342 -> 2,410; 1,459 -> 1,638) and every country (PT 4,147 -> 4,366, ES 1,570 ->
# 1,647, FR 530 -> 660). Region items still give country hints. Report: runs/eval/calibration-val130.json
OCR_NAME_RELIABILITY = 1.0  # x the sign's confidence
OCR_POSTCODE_RELIABILITY = {"strong": 1.0, "medium-strong": 1.0, "medium": 1.0, "weak": 0.6}
REGION_RELIABILITY = {"strong": 0.6, "medium-strong": 0.5, "medium": 0.4, "weak": 0.2}
REGION_CLUES = False  # areas from the regions an OCR item or VLM hint names: off since T39 (see above)
VLM_LANDMARK_RELIABILITY = {"high": 0.5, "medium": 0.3, "low": 0.15}
VLM_REGION_FACTOR = 0.5  # VLM region hints count half an OCR one
ALTERNATIVE_READING_FACTOR = 0.6  # an item only an alternative OCR reading shows
LOOKUP_LIMIT = 20
FUZZY_MIN_LETTERS = 6  # a fuzzy match of a shorter fragment ("EALA", "RAMPA") is noise
OFFICE_FACTOR = 0.2
CONFIDENT_COUNTRY = 0.85
# One-word sign texts that are also place names: a fire-safety "FOGO" sent an app run to Fogo (Cape Verde /
# Azores entries). An OCR name whose every word is here is not looked up; "Praia da Rocha" still is.
SIGN_WORDS = frozenset("""
fogo saida extintor incendio emergencia perigo entrada praia centro estacao parque farmacia correio policia
fuego salida extintor incendio emergencia peligro entrada playa centro estacion parque farmacia correos policia
feu sortie extincteur incendie urgence danger entree plage centre gare parc pharmacie poste police
""".split())
REGION_MIN_EXTENT_M = 5_000.0  # a region named by an item is an admin unit, not a same-named shop

ROLE_SPREAD_M = {"camera": 15.0, "landmark": 30.0, "area": 300.0}
LANDMARK_VIEW_M = 60.0
FALLBACK_SPREAD_M = 150_000.0
MAX_POINTS = 150
RING_FRACTIONS = tuple(math.sqrt((k + 0.5) / 3) for k in range(3))  # equal-area rings of a uniform disc
BEARINGS = 8
EXPECTED_SCORE_FACTOR = BASE_POINTS * sum(RANK_FACTOR ** r for r in range(MAX_ENTRIES))  # 8,025.26 x theta

# The residual "somewhere in this country" hypotheses: largest metropolitan areas (population data,
# never the warm-up set), as candidates.GLOBAL_FALLBACK does for the whole area
COUNTRY_FALLBACKS = {
    "PT": Candidate(38.7223, -9.1393, "area", "fallback:PT", label="Portugal (residual: Lisbon area)", weight=0.0,
                    extent_m=FALLBACK_SPREAD_M, country="PT", details={"extent_source": "assumed", "residual": True}),
    "ES": Candidate(40.4168, -3.7038, "area", "fallback:ES", label="Spain (residual: Madrid area)", weight=0.0,
                    extent_m=FALLBACK_SPREAD_M, country="ES", details={"extent_source": "assumed", "residual": True}),
    "FR": Candidate(48.8566, 2.3522, "area", "fallback:FR", label="France (residual: Paris area)", weight=0.0,
                    extent_m=FALLBACK_SPREAD_M, country="FR", details={"extent_source": "assumed", "residual": True}),
}


@dataclass
class Clue:
    clue_id: str
    kind: str  # ocr_name, ocr_postcode, ocr_region, vlm_landmark, vlm_region, knn, region_head, geoclip ...
    group: str  # correlation group: clues in one group never confirm each other
    reliability: float  # 0-1: how far the clue is trusted to be about this place (placeholder until T39)
    candidates: list  # Candidate alternatives
    scale: float | None = LOOKUP_SCALE  # None: a distribution, normalised within the clue
    text: str = ""
    evidence: list = field(default_factory=list)

    def __post_init__(self):
        if not 0 <= self.reliability <= 1:
            raise ValueError(f"reliability must be in [0, 1], got {self.reliability}")


@dataclass
class Hint:
    source: str  # "ocr:i4", "vlm:post_box=red"
    group: str
    countries: tuple
    strength: str
    detail: str = ""

    def __post_init__(self):
        if self.strength not in HINT_RATIO:
            raise ValueError(f"strength must be one of {tuple(HINT_RATIO)}, got {self.strength!r}")
        self.countries = tuple(c for c in self.countries if c in COUNTRIES)


@dataclass
class Fusion:
    hypotheses: list  # Candidates, weights normalised, heaviest first
    country: dict  # P(country)
    selection: dict
    output: Output
    clues: list
    hints: list

    def summary(self, top=5):
        return {"country": {c: round(p, 4) for c, p in self.country.items()},
                "clues": len(self.clues), "hints": len(self.hints), "hypotheses": len(self.hypotheses),
                "top": [{"label": h.label, "source": h.source, "role": h.role, "weight": round(h.weight, 4),
                         "lat": round(h.lat, 6), "lng": round(h.lng, 6)} for h in self.hypotheses[:top]],
                "selection": self.selection}


def weaker(strength, steps=1):
    return STRENGTHS[min(STRENGTHS.index(strength) + steps, len(STRENGTHS) - 1)]


# -- geometry -----------------------------------------------------------------------------------------

def spread_m(c):
    """Radius of the disc the camera is assumed to lie in for this hypothesis."""
    known = (c.extent_m or 0.0) + (c.accuracy_m or 0.0)
    return max(ROLE_SPREAD_M[c.role], known) + (LANDMARK_VIEW_M if c.role == "landmark" else 0.0)


def haversine_matrix(lat1, lng1, lat2, lng2):
    """Metres between every point of the first set (rows) and every point of the second (columns)."""
    lat1, lng1, lat2, lng2 = (np.radians(np.asarray(a, dtype=float)) for a in (lat1, lng1, lat2, lng2))
    dlat = lat2[None, :] - lat1[:, None]
    dlng = lng2[None, :] - lng1[:, None]
    h = np.sin(dlat / 2) ** 2 + np.cos(lat1)[:, None] * np.cos(lat2)[None, :] * np.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def disc_samples(lat, lng, radius_m):
    """3 equal-area rings x 8 bearings over a uniform disc, staggered per ring; local flat offsets."""
    lats, lngs = [], []
    for k, fraction in enumerate(RING_FRACTIONS):
        r = radius_m * fraction
        for b in range(BEARINGS):
            bearing = math.radians(b * 360 / BEARINGS + k * 15)
            lats.append(lat + r * math.cos(bearing) / 111_320.0)
            lngs.append(lng + r * math.sin(bearing) / (111_320.0 * max(0.05, math.cos(math.radians(lat)))))
    return lats, lngs


def theta_array(distance_m, category):
    d = np.where(distance_m < ZERO_DISTANCE_M, 0.0, distance_m)
    return 2.0 / (1.0 + d / SCALE_M[category])


# -- country prior ----------------------------------------------------------------------------------

def country_prior(hints, base=None):
    """P(country) from soft hints: products within a group capped at MAX_GROUP_RATIO, groups multiplied,
    every country kept at COUNTRY_FLOOR or more."""
    p = dict(base or {c: 1 / len(COUNTRIES) for c in COUNTRIES})
    by_group = defaultdict(list)
    for h in hints:
        if h.countries and set(h.countries) != set(COUNTRIES):
            by_group[h.group].append(h)
    for group_hints in by_group.values():
        ratio = {c: 1.0 for c in COUNTRIES}
        for h in group_hints:
            for c in h.countries:
                ratio[c] *= HINT_RATIO[h.strength]
        low = min(ratio.values())
        for c in COUNTRIES:
            p[c] *= min(ratio[c] / low, MAX_GROUP_RATIO)
    total = sum(p.values())
    p = {c: v / total for c, v in p.items()}
    low = set()
    while True:  # pin the countries under the floor, rescale the others; repeat if that pushes one under
        low |= {c for c, v in p.items() if v < COUNTRY_FLOOR}
        high = sum(v for c, v in p.items() if c not in low)
        p = {c: COUNTRY_FLOOR if c in low else v * (1 - COUNTRY_FLOOR * len(low)) / high for c, v in p.items()}
        if all(v >= COUNTRY_FLOOR - 1e-12 for v in p.values()):
            return p


# -- match likelihood ---------------------------------------------------------------------------------

def match_likelihood(c, clue_max_weight):
    """How well the candidate matches its clue, 0-1, whatever its prominence.

    Name-index candidates: weight / (prior x name factor), undoing panoloc.names' prominence prior.
    Others: weight relative to the clue's heaviest candidate.
    """
    d = c.details or {}
    if "prior" in d and d.get("prior"):
        name_factor = 1.0 if d.get("name_kind") in ("label", "name", None) else 0.6
        return max(0.0, min(1.0, c.weight / (d["prior"] * name_factor)))
    return c.weight / clue_max_weight if clue_max_weight > 0 else 0.0


# -- fusion -----------------------------------------------------------------------------------------

def _sharing(c):
    """How many places share the candidate's name: its lookup ambiguity or OSM occurrences, at least 1."""
    d = c.details or {}
    return max(1, d.get("ambiguity") or 1, d.get("occurrences") or 1)


def _country_level(c):
    """A country-wide alternative or residual: it confirms nothing nearby (no agreement strength)."""
    d = c.details or {}
    return bool(d.get("country_level") or d.get("residual"))


def _entries(clues, country):
    """One row per (clue, candidate): own weight, agreement strength, group."""
    rows = []
    for clue in clues:
        cands = [c for c in clue.candidates if c.weight > 0]
        if not cands or clue.reliability <= 0:
            continue
        total = sum(c.weight for c in cands)
        denom = max(clue.scale, total) if clue.scale else total
        top = max(c.weight for c in cands)
        for c in cands:
            rows.append({"clue": clue, "cand": c, "own": clue.reliability * c.weight / denom,
                         "strength": 0.0 if _country_level(c) else
                         clue.reliability * match_likelihood(c, top) / math.sqrt(_sharing(c)),
                         "group": clue.group,
                         "spread": spread_m(c), "country": c.country})
    return rows


def fuse(clues, hints=(), *, category=None, urban_probability=DEFAULT_URBAN_PROBABILITY, country_base=None,
         note=""):
    """Clues and hints -> Fusion: normalised hypotheses (heaviest first), P(country), the selection and the Output.

    category ("urban" / "non-urban") when it is known; otherwise urban_probability weighs both scenarios.
    """
    clues, hints = list(clues), list(hints)
    country = country_prior(hints, country_base)
    rows = _entries(clues, country)

    # Merge rows proposing the same place (same source ID) into one hypothesis: its best own weight
    merged = {}
    for row in rows:
        key = row["cand"].source
        if key not in merged or row["own"] > merged[key]["own"]:
            merged[key] = {**row, "clues": merged.get(key, {}).get("clues", [])}
        merged[key]["clues"].append(row["clue"].clue_id)
    hyps = list(merged.values())

    if hyps and rows:
        d = haversine_matrix([h["cand"].lat for h in hyps], [h["cand"].lng for h in hyps],
                             [r["cand"].lat for r in rows], [r["cand"].lng for r in rows])
        compatible = d <= (np.array([h["spread"] for h in hyps])[:, None]
                           + np.array([r["spread"] for r in rows])[None, :] + AGREE_SLACK_M)
        strength = np.array([r["strength"] for r in rows])
        row_groups = np.array([r["group"] for r in rows])
        bonus = np.ones(len(hyps))
        agreeing = [[] for _ in hyps]
        for g in sorted(set(row_groups)):
            in_g = row_groups == g
            best = np.where(compatible[:, in_g], strength[in_g][None, :], 0.0).max(axis=1)
            for i, h in enumerate(hyps):
                if h["group"] != g and best[i] > 0:
                    bonus[i] *= 1 + AGREE_GAIN * best[i]
                    agreeing[i].append(str(g))
        bonus = np.minimum(bonus, MAX_AGREEMENT)
    else:
        bonus, agreeing = np.ones(len(hyps)), [[] for _ in hyps]

    hypotheses = []
    for i, h in enumerate(hyps):
        c = h["cand"]
        factor = country[c.country] * len(COUNTRIES) if c.country in country else 1.0
        weight = h["own"] * float(bonus[i]) * factor
        details = {**c.details, "fusion": {"own": round(h["own"], 6), "agreement": round(float(bonus[i]), 4),
                                           "agreeing_groups": agreeing[i], "country_factor": round(factor, 4),
                                           "group": h["group"], "clues": h["clues"], "spread_m": round(h["spread"], 1)}}
        evidence = list(dict.fromkeys([*c.evidence, *h["clue"].evidence]))
        hypotheses.append(Candidate(**{**asdict(c), "weight": weight, "details": details, "evidence": evidence}))
    for code, fallback in COUNTRY_FALLBACKS.items():
        hypotheses.append(Candidate(**{**asdict(fallback), "weight": RESIDUAL_WEIGHT * country[code]}))

    total = sum(h.weight for h in hypotheses)
    for h in hypotheses:
        h.weight = h.weight / total
    hypotheses.sort(key=lambda h: (h.weight, ROLE_PREFERENCE[h.role]), reverse=True)

    selection = select(hypotheses, category=category, urban_probability=urban_probability)
    output = make_output(hypotheses[selection["index"]], selection, note)
    return Fusion(hypotheses, country, selection, output, clues, hints)


def select(hypotheses, *, category=None, urban_probability=DEFAULT_URBAN_PROBABILITY, max_points=MAX_POINTS,
           allowed=None):
    """PLAN 1.1: the hypothesis centre with the best expected theta, each hypothesis spread over its disc.

    allowed: one bool per hypothesis; only allowed centres are offered as points (every hypothesis still counts
    in the expectation), e.g. those consistent with the team's answers. Returns a JSON-ready dict; "index" is
    the chosen hypothesis's position in `hypotheses`.
    """
    if category is not None and category not in SCALE_M:
        raise ValueError(f"category must be one of {tuple(SCALE_M)}, got {category!r}")
    if category is None and not 0 <= urban_probability <= 1:
        raise ValueError("urban_probability must be in [0, 1]")
    weights = np.array([h.weight for h in hypotheses], dtype=float)
    if not weights.sum() > 0:
        raise ValueError("hypothesis weights must sum to more than 0")
    weights = weights / weights.sum()
    s_lat, s_lng, s_w = [], [], []
    for h, w in zip(hypotheses, weights):
        lats, lngs = disc_samples(h.lat, h.lng, spread_m(h))
        s_lat += lats
        s_lng += lngs
        s_w += [w / len(lats)] * len(lats)
    pool = [i for i in range(len(hypotheses)) if allowed is None or allowed[i]]
    if not pool:
        raise ValueError("no allowed hypothesis to choose from")
    order = sorted(pool, key=lambda i: (hypotheses[i].weight, ROLE_PREFERENCE[hypotheses[i].role]), reverse=True)[:max_points]
    d = haversine_matrix([hypotheses[i].lat for i in order], [hypotheses[i].lng for i in order], s_lat, s_lng)
    s_w = np.array(s_w)
    value = {cat: theta_array(d, cat) @ s_w for cat in SCALE_M}
    if category is not None:
        mixed = value[category]
    else:
        mixed = urban_probability * value["urban"] + (1 - urban_probability) * value["non-urban"]

    def pick(v):
        best = max(range(len(order)), key=lambda j: (round(float(v[j]), 12), ROLE_PREFERENCE[hypotheses[order[j]].role]))
        return order[best], float(v[best])

    index, expected = pick(mixed)
    per_category = {}
    for cat in SCALE_M:
        i, v = pick(value[cat])
        per_category[cat] = {"index": i, "point": [hypotheses[i].lat, hypotheses[i].lng], "source": hypotheses[i].source,
                             "expected_theta": round(v, 6)}
    chosen = hypotheses[index]
    return {"index": index, "point": [chosen.lat, chosen.lng], "source": chosen.source, "label": chosen.label,
            "role": chosen.role, "expected_theta": round(expected, 6),
            "expected_score_unpenalised": round(expected * EXPECTED_SCORE_FACTOR, 1),
            "category": category, "urban_probability": None if category is not None else urban_probability,
            "per_category": per_category,
            "categories_differ": per_category["urban"]["source"] != per_category["non-urban"]["source"],
            "points_considered": len(order)}


def make_output(chosen, selection, note=""):
    """The Output for the selected hypothesis (PLAN 3.3 contract)."""
    verified = chosen.role == "camera" and (chosen.details or {}).get("verified_match")
    method = "reference_camera" if verified else "coarse_candidate"
    if chosen.extent_m is not None or chosen.accuracy_m is not None:
        uncertainty_m, uncertainty_source = spread_m(chosen), "source_estimate"
    else:
        uncertainty_m, uncertainty_source = None, "unknown"
    category = selection["category"] or f"urban probability {selection['urban_probability']} (assumed)"
    text = (f"best expected theta {selection['expected_theta']:.4f} ({category}) at {chosen.label or chosen.source}; "
            f"urban and non-urban optima {'differ' if selection['categories_differ'] else 'agree'}")
    sources = [chosen.source] + [c for c in (chosen.details or {}).get("fusion", {}).get("clues", [])]
    return Output(chosen.lat, chosen.lng, method, chosen.role, sources, uncertainty_m, uncertainty_source,
                  "; ".join(x for x in (note, text) if x))


# -- clues and hints from perception ----------------------------------------------------------------

def _is_office(c):
    d = c.details or {}
    tags = d.get("tags") or {}
    osm_type = str(d.get("osm_type") or "")
    return osm_type.startswith("office") or "office" in tags or "government" in tags


def clean_name_candidates(candidates, query=""):
    """Drop overseas entries and fuzzy matches of short fragments; damp office and organisation entries."""
    letters = sum(ch.isalpha() for ch in (query or ""))
    out = []
    for c in candidates:
        d = c.details or {}
        if d.get("overseas") or (d.get("match_type") == "fuzzy" and letters <= FUZZY_MIN_LETTERS - 1):
            continue
        if _is_office(c):
            c = Candidate(**{**asdict(c), "weight": c.weight * OFFICE_FACTOR, "details": {**d, "damped": "office"}})
        out.append(c)
    return out


def confident_countries(country):
    """[country] when one country holds CONFIDENT_COUNTRY of the prior, else None (search them all)."""
    best = max(country, key=country.get)
    return [best] if country[best] >= CONFIDENT_COUNTRY else None


def _lookup_clue(clue_id, kind, group, reliability, text, candidates, evidence=()):
    return Clue(clue_id, kind, group, reliability, list(candidates), LOOKUP_SCALE, text, list(evidence))


def _region_candidates(names, regions, limit=5):
    """Admin-sized area candidates for the regions an item or hint names: [{country, name, ...}] or names."""
    out, seen = [], set()
    for region in regions:
        name, countries = (region.get("name"), [region["country"]] if region.get("country") else None) \
            if isinstance(region, dict) else (region, None)
        if not name:
            continue
        for c in names.lookup(name, countries=countries, limit=limit, fuzzy=False, partial=False):
            if c.role == "area" and (c.extent_m or 0) >= REGION_MIN_EXTENT_M and c.source not in seen:
                seen.add(c.source)
                out.append(c)
    return out


def _uncovered_countries(found, countries, why):
    """Country-wide alternatives for the countries an item points to but names no region in.

    "925 450 732" is a Portuguese mobile or a landline in Toledo: the clue must split between "Toledo"
    and "anywhere in Portugal", not put everything on Toledo. Each gets the weight of one covered country.
    """
    covered = {c.country for c in found}
    missing = [c for c in countries if c in COUNTRY_FALLBACKS and c not in covered]
    if not missing or not covered:
        return []
    share = sum(c.weight for c in found) / len(covered)
    out = []
    for code in missing:
        base = COUNTRY_FALLBACKS[code]
        out.append(Candidate(**{**asdict(base), "source": f"country:{code}", "weight": share,
                                "label": f"{code}, anywhere ({why})",
                                "details": {"extent_source": "assumed", "country_level": True}}))
    return out


def clues_from_ocr(items, names, sign_confidence=None, countries=None):
    """Clues from panoloc.ocr items: name lookups, postcodes, and the regions an item names.

    items: OcrResult.items (dicts with kind, value, countries, regions, strength, sign_id, source,
    details). sign_confidence: {sign_id: confidence}; a missing sign counts 0.8. countries limits name
    lookups (confident_countries); postcodes and regions carry their own countries.
    """
    sign_confidence = sign_confidence or {}
    clues = []
    for item in items:
        sign = item.get("sign_id") or "?"
        group = f"ocr:{sign}"
        item_id = item.get("item_id") or f"{sign}:{len(clues)}"
        conf = sign_confidence.get(sign, 0.8)
        factor = ALTERNATIVE_READING_FACTOR if item.get("source") == "alternative" else 1.0
        evidence = [e for e in (item.get("evidence_id"),) if e]
        kind = item.get("kind")
        if kind == "name":
            query = (item.get("details") or {}).get("query") or item.get("value")
            words = [w for w in normalise(query or "").split() if w not in STOPWORDS]
            if query and words and all(w in SIGN_WORDS for w in words):
                continue  # a safety or direction sign word, not a place
            if query:
                found = clean_name_candidates(names.lookup(query, countries=countries, limit=LOOKUP_LIMIT), query)
                if found:
                    clues.append(_lookup_clue(f"ocr:{item_id}", "ocr_name", group,
                                              OCR_NAME_RELIABILITY * conf * factor, query, found, evidence))
        elif kind == "postcode":
            countries = item.get("countries") or []
            found = names.postcode(item["value"], country=countries[0] if len(countries) == 1 else None)
            if found:
                reliability = OCR_POSTCODE_RELIABILITY.get(item.get("strength"), 0.3) * conf * factor
                clues.append(_lookup_clue(f"ocr:{item_id}", "ocr_postcode", group, reliability, item["value"],
                                          found, evidence))
        if REGION_CLUES and kind != "postcode" and item.get("regions"):
            found = _region_candidates(names, item["regions"])
            if found:
                found += _uncovered_countries(found, item.get("countries") or [], f"{kind} {item.get('value')}")
                reliability = REGION_RELIABILITY.get(item.get("strength"), 0.2) * factor
                clues.append(_lookup_clue(f"ocr:{item_id}:regions", "ocr_region", group, reliability,
                                          f"{kind} {item.get('value')}", found, evidence))
    return clues


def clues_from_vlm(landmarks, vlm_hints, names, countries=None):
    """Clues from panoloc.vlm: one per landmark hypothesis, plus one per region a hint names. Group "vlm"."""
    clues = []
    for i, lm in enumerate(landmarks or [], 1):
        reliability = VLM_LANDMARK_RELIABILITY.get(lm.get("confidence"), 0.15)
        reliability *= min(1.5, 1 + 0.1 * (lm.get("support", 1) - 1))
        if lm.get("digits_unverified"):
            reliability *= 0.5
        found = clean_name_candidates(names.lookup(lm["name"], countries=countries, limit=LOOKUP_LIMIT), lm["name"])
        if found:
            clues.append(_lookup_clue(f"vlm:landmark:{i}", "vlm_landmark", "vlm", min(1.0, reliability), lm["name"],
                                      found))
    for h in vlm_hints or []:
        if not REGION_CLUES or not h.get("regions"):
            continue
        strength = h.get("strength") or "weak"
        if not h.get("majority", True) or h.get("conflict"):
            strength = weaker(strength)
        found = _region_candidates(names, h["regions"])
        if found:
            clues.append(_lookup_clue(f"vlm:{h['key']}={h['value']}", "vlm_region", "vlm",
                                      REGION_RELIABILITY.get(strength, 0.2) * VLM_REGION_FACTOR,
                                      f"{h['key']}={h['value']}", found))
    return clues


def hints_from_ocr(items):
    """Country hints from OCR items that point to countries (plates, phones, languages, domains, codes)."""
    out = []
    for item in items:
        countries, strength = item.get("countries") or [], item.get("strength")
        if not countries or strength not in HINT_RATIO:
            continue
        if item.get("source") == "alternative":
            strength = weaker(strength)
        out.append(Hint(f"ocr:{item.get('item_id', '?')}", f"ocr:{item.get('sign_id') or '?'}", tuple(countries),
                        strength, f"{item.get('kind')} {item.get('value')}"))
    return out


def hints_from_vlm(vlm_hints):
    """Country hints from panoloc.vlm hints; one weaker step for a minority, conflicting or hard-to-see answer."""
    out = []
    for h in vlm_hints or []:
        strength = h.get("strength")
        if not h.get("countries") or strength not in HINT_RATIO:
            continue
        if not h.get("majority", True) or h.get("conflict") or h.get("hard"):
            strength = weaker(strength)
        out.append(Hint(f"vlm:{h['key']}={h['value']}", "vlm", tuple(h["countries"]), strength,
                        f"{h['key']}={h['value']} in {len(h.get('views', []))} view(s)"))
    return out


# -- run log ----------------------------------------------------------------------------------------

def log_fusion(run, fused, *, stage="fuse", top=50):
    """Log the heaviest hypotheses (candidates.updated, with candidate IDs) and one fusion evidence event."""
    ranked = []
    for i, h in enumerate(fused.hypotheses[:top], 1):
        ranked.append({"candidate_id": f"h{i}", **h.to_dict()})
    run.candidates(ranked, stage=stage)
    s = fused.selection
    observation = (f"{len(fused.hypotheses)} hypotheses from {len(fused.clues)} clues and {len(fused.hints)} hints; "
                   f"P(country) " + ", ".join(f"{c} {p:.0%}" for c, p in fused.country.items())
                   + f"; best point {s['label'] or s['source']} (expected theta {s['expected_theta']:.4f})")
    return run.evidence("fusion", {**fused.summary(), "observation": observation}, stage=stage, actor="agent")
