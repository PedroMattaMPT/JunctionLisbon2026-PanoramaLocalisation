"""Name lookup: OCR place names, postcodes and VLM landmark names -> typed candidates (PLAN.md 3.3, 4.4).

tools/build_name_index.py builds Data/index/names.sqlite from the Wikidata extract (items with
labels and aliases in pt/es/fr/en/ca/gl/eu/mul) and the GeoNames dumps (places with alternate names,
and postcodes) for Portugal, Spain and France. tools/build_osm_index.py builds one OSM index per
country next to it (osm_PT.sqlite, osm_ES.sqlite, osm_FR.sqlite: see OSM below). This module only
reads those files.

Coordinates mark what the source describes (a monument, a station, a town centre, a postcode
centroid), never a camera. So every candidate is a `landmark` (building, monument, shop, station,
bridge, other point object) or an `area` (settlement, administrative unit, street, square, park,
beach, lake, mountain, forest, postcode). `extent_m` is the radius around the point, taken from the
per-type tables in tools/build_name_index.py: details["extent_source"] is "assumed", or "source"
when the item's own coordinates spread wider, and details["extent_rule"] names the rule.
`accuracy_m` stays None: no source states a position accuracy.

Matching works on normalise(): NFKD, combining marks dropped, casefold, œ/æ/ø/ł/đ/þ/ı folded,
everything but letters and digits turned into single spaces. Two keys derived from it absorb OCR
habits. The squashed key drops the spaces ("MONTSAINT MICHEL"). The core key also drops articles
and prepositions (STOPWORDS: "Torre Belem" for "Torre de Belém"). Only names that are ASCII after
normalisation are indexed, so GeoNames' non-Latin alternate names are left out.

lookup(text) matches at these tiers (details["tier"], details["match_type"]):
  0 exact         the normalised text equals a label, alias or alternate name
  1 spacing       ... once spaces are ignored
    abbreviation  ... once sign abbreviations are spelt out (ABBREVIATIONS: St, Sta, Av, N. Sra ...)
    stopwords     ... once articles and prepositions are ignored
  2 fuzzy         core keys within 1 edit (4-8 letters), 2 (9-15) or 3 (16 or more); OCR look-alikes
                  (0/o, 1/l, 5/s ...) cost half an edit; candidates come from a trigram index. A short
                  word one letter off an article ("Bailleul-ln-Soc") is also tried as that article,
                  and the match is then checked on the whole name
  3 within        a run of the text's words is a name ("Torre de Belém, Lisboa": both)
    contains      a name contains every content word of the text ("Jerónimos": the monastery)
Every place that matches is kept, so an ambiguous name such as "Santa Maria" returns many places;
details["ambiguity"] counts the places matching at that tier. Results come one per place: exact
matches first, then all the others by weight, at most `limit`. When the exact matches alone fill
`limit`, the other tiers are not searched.

weight = match likelihood x name factor x prior (/ occurrences for OSM, below). It is unnormalised
support for fusion, comparable across tiers and across lookups, and not a probability:
  likelihood   exact 1, spacing and abbreviation 0.8, stopwords 0.6, fuzzy 0.5 x 0.35^edits,
               within and contains 0.2 x coverage^2, coverage being the share of the text (within) or
               of the name (contains) that the match explains; a run inside a longer matching run
               counts half its coverage. One edit (0.175) outweighs a partial match explaining under 93%
  name factor  1 for a label (GeoNames: the main name), 0.6 for an alias or alternate name
  prior        0.2 + 0.8 x prominence. Prominence in [0, 1] comes from Wikidata sitelinks (+0.15 for
               a heritage designation) or GeoNames population (+ a bonus for capitals and seats)
details also holds match_type, match_score (1 exact, lower for weaker matches), matched_name,
language, name_kind, prominence, types, heritage, population and the other source fields.

The same place often appears in both sources. A Wikidata item and a GeoNames entry that share a name
within 1 km (two large areas: within half the smaller extent, up to 5 km) are linked at build time:
details["same_place_as"] lists the linked entries, and `group` ("same-place:<source>") is the same
for the whole linked set, so fusion can count it once. Unlinked candidates have no group.

postcode(code) resolves PT 4-3 codes ("3750-011"), ES and FR 5-digit codes (both countries when the
country is not given) and a bare PT 4-digit prefix ("1100") as one aggregate area. The point is a
centroid carrying GeoNames' accuracy flag (details["geonames_accuracy"]: 1 estimated, 3-4 the point
of a named place, 5-6 a centroid), and the extent covers the code's places. A postcode narrows an
area; it never fixes the camera.

OSM. open() also attaches every osm_<CC>.sqlite next to names.sqlite; osm=False, or the environment
variable PANOLOC_NAMES_OSM=0, leaves them out (exactly the results without them, for A/B runs). They
hold named shops, amenities, stations, heritage, natural features, places, named buildings and
landuse, merged streets (one entry per street, its point on the street: tools/build_osm_index.py) and
addr:postcode aggregates. OSM names go through the same tiers. details["source"] is "osm", with
osm_id ("n123", "w456"; osm_ids when objects were merged), osm_type ("shop=supermarket"), the tags of
interest (name, brand, wikidata, addr:*) and occurrences. Shops, buildings and POIs are landmarks;
streets, squares, places and natural extents areas. A way's extent is its footprint (extent_source
"source"), a node's the type's assumed radius ("assumed").
  prior        OSM has no sitelinks: prominence is the type's (a station or a castle 0.35, a museum 0.3, a
               residential street 0.1, a shop 0.04), raised to the linked Wikidata/GeoNames entry's
  occurrences  how many entries of that country carry the matched name. A name many places share
               ("Pingo Doce", "Rua da Igreja", "Farmácia") is one ambiguous clue: each match's weight is
               divided by its occurrences, and from CHAIN_MIN on (details["chain"]) a lookup keeps only
               CHAIN_KEEP of its places per country, so a chain never floods the results; ambiguity counts all,
               and a place left out stays out (a store does not come back as "Pingo Doce BP", contains)
  generic      when the text itself is a name CHAIN_MIN or more places carry exactly, every other OSM
               match (variant, fuzzy, partial) is one more of those places: its weight is divided by that
               count too (details["generic_query"]), so "Rua e Igreja" stays weak for "Rua da Igreja"
  one word     an OSM entry named by a single content word ("Decor", "Feliz", one of Spain's 566k
               place=locality toponyms) is divided by the number of OSM names holding that word instead,
               when larger (details["word_frequency"]): a one-word reading may come from any of their
               signs. Settlements (SETTLEMENTS: city ... hamlet, suburb, island) are not: their sign is their name
  sign words   OSM entries named by a sign phrase (SIGN_PHRASES: "Se Vende", "Privado", "Sortie" ...) never match
  short fuzzy  texts whose core key is under OSM_FUZZY_MIN (7) letters get no fuzzy OSM match: with millions
               of short OSM names, "LEARL" one edit from a hamlet "Léal" is a coincidence
lookup(text, near=(lat, lng, radius_m)) searches only a box of +- radius_m around a point, without the
chain cap, and gives details["near_distance_m"]: is a "Pingo Doce" or a "Rua da Igreja" near a
hypothesis that other clues support? (Weights keep the country-wide occurrences.)
An OSM object tagged wikidata=Q... is that item; places, natural features, heritage, stations, streets
and squares also link to a names.sqlite entry sharing the name nearby. Linked entries share `group`
and list each other in same_place_as ("how": "wikidata tag" or "name within ... m"), whichever
side the match comes from.
postcode() adds the OSM aggregate when there is one, first: source "osm-postcode:<CC>:<code>", the
median address as the point (an address, so on the ground), extent the p90 distance of the addresses
from it (at least a floor per kind: extent_rule), details n_addresses, n_outliers, spread_p50_m,
spread_p90_m, spread_max_m, streets, places and geonames_distance_m. The GeoNames candidate stays as
the alternative, with details["source"] "geonames", and the two share the weight (OSM_POSTCODE_SHARE):
PT codes and prefixes prefer OSM (0.65, 0.8 from 3 addresses, 0.9 from 10: street-level codes, 448 m
-> 28 m median error in a simulation at the val cameras), ES and FR 5-digit codes split it evenly
(commune-level codes, where GeoNames' town-centre point did as well). Without an OSM aggregate the
GeoNames candidate is exactly as before.

  from panoloc.names import NameIndex
  with NameIndex.open() as names:                       # Data/index/names.sqlite + the osm_<CC>.sqlite beside it
      names.lookup("Torre de Belém")                    # [Candidate(role="landmark", source="wikidata:Q215003", ...)]
      names.lookup("IGREJA MATRIZ", countries=["PT"], limit=20)
      names.postcode("3750-011"); names.postcode("1100"); names.postcode("28013", country="ES")
      names.osm                                         # [{"country": "PT", "extract_timestamp": ...}, ...]
  NameIndex.open(osm=False)                             # names.sqlite only
Use one NameIndex per thread: a sqlite3 connection is not shared across threads.
"""
import array
import heapq
import itertools
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
import warnings
from collections import Counter, defaultdict
from pathlib import Path

from panoloc.candidates import Candidate
from panoloc.scoring import haversine_m

SCHEMA = "panoloc.names/1"
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "Data" / "index" / "names.sqlite"
COUNTRIES = ("PT", "ES", "FR")
COUNTRY_BITS = {"PT": 1, "ES": 2, "FR": 4}
ALL_COUNTRIES = 7
OSM_SCHEMA = "panoloc.names.osm/1"
OSM_ID_OFFSET = {"PT": 1 << 40, "ES": 2 << 40, "FR": 3 << 40}  # place ids of osm_<CC>.sqlite start here
OSM_ENV = "PANOLOC_NAMES_OSM"  # "0", "off", "false" or "no": NameIndex.open() attaches no OSM index

# -- normalisation (shared with tools/build_name_index.py: changing it means rebuilding the index) --

_FOLD = str.maketrans({"œ": "oe", "æ": "ae", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i",
                       "ħ": "h", "ŧ": "t"})
_NOT_ALNUM = re.compile(r"[\W_]+")

STOPWORDS = frozenset(
    "a ao aos as au aux d da das de del dels des do dos du e el els em en et i l la las le les lo los "
    "na nas no nos o os y and at in near of the".split())

# Abbreviations common on PT/ES/FR signs, expanded at query time only (the index holds full names).
# Two-word patterns are tried before one-word ones.
ABBREVIATIONS = {
    ("n", "sra"): ("nossa senhora",), ("n", "s"): ("nossa senhora",), ("nsa", "sra"): ("nossa senhora",),
    ("ntra", "sra"): ("nuestra senora",), ("nra", "sra"): ("nuestra senora",), ("n", "d"): ("notre dame",),
    ("nd",): ("notre dame",), ("st",): ("saint",), ("ste",): ("sainte",), ("sts",): ("saints",),
    ("stes",): ("saintes",), ("sta",): ("santa",), ("sto",): ("santo",), ("sn",): ("san",),
    ("s",): ("sao", "san", "santa", "saint"), ("sr",): ("senhor", "senor"), ("sra",): ("senhora", "senora"),
    ("d",): ("dom", "dona", "don"), ("dr",): ("doutor", "doctor", "docteur"), ("dra",): ("doutora", "doctora"),
    ("eng",): ("engenheiro",), ("prof",): ("professor",), ("pe",): ("padre",), ("fr",): ("frei", "fray"),
    ("gen",): ("general",), ("gal",): ("general",), ("cel",): ("coronel",), ("mal",): ("marechal",),
    ("cde",): ("conde",), ("vde",): ("visconde",), ("pres",): ("presidente", "president"),
    ("av",): ("avenida", "avenue"), ("avda",): ("avenida",), ("avd",): ("avenida",), ("r",): ("rua", "rue"),
    ("c",): ("calle", "carrer"), ("pc",): ("praca",), ("pca",): ("praca",), ("pl",): ("place", "plaza", "placa"),
    ("pza",): ("plaza",), ("lg",): ("largo",), ("lgo",): ("largo",), ("tv",): ("travessa",),
    ("trav",): ("travessa",), ("estr",): ("estrada",), ("ctra",): ("carretera",), ("bd",): ("boulevard",),
    ("bld",): ("boulevard",), ("bvd",): ("boulevard",), ("blvd",): ("boulevard",), ("ch",): ("chemin",),
    ("imp",): ("impasse",), ("mte",): ("monte",), ("mt",): ("mont", "monte", "mount"),
    ("pto",): ("porto", "puerto"), ("fte",): ("fonte", "fuente"), ("qta",): ("quinta",),
    ("urb",): ("urbanizacao", "urbanizacion"), ("esc",): ("escola", "escuela"),
    ("univ",): ("universidade", "universidad", "universite"), ("fac",): ("faculdade", "facultad", "faculte"),
    ("igr",): ("igreja",), ("cap",): ("capela",), ("bo",): ("bairro", "barrio"),
}
MAX_VARIANTS = 12

# Characters OCR confuses; a substitution between them costs half an edit.
_LOOKALIKES = ("o0", "l1", "i1", "il", "s5", "b8", "z2", "g6", "g9", "q9", "uv", "ce", "nh")
CONFUSABLE = frozenset(p for a, b in _LOOKALIKES for p in ((a, b), (b, a)))


def normalise(text):
    """Accent-, case- and punctuation-insensitive form: "Mont-Saint-Michel" -> "mont saint michel"."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text)).casefold()
    if not s.isascii():
        s = "".join(ch for ch in s if not unicodedata.combining(ch)).translate(_FOLD)
    return _NOT_ALNUM.sub(" ", s).strip()


def keys(norm):
    """(squashed key, core key) of a normalised name. The core key also drops STOPWORDS, unless that
    leaves nothing: "torre de belem" -> ("torredebelem", "torrebelem")."""
    tokens = norm.split()
    content = [t for t in tokens if t not in STOPWORDS]
    squashed = "".join(tokens)
    return squashed, "".join(content) if content else squashed


def trigrams(key):
    """Distinct trigrams of a key padded with ^ and $; a key of n letters has n positional trigrams."""
    padded = f"^{key}$"
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def max_edits(length):
    """Edits a fuzzy match may need: none under 4 letters, 1 up to 8, 2 up to 15, then 3."""
    return 0 if length < 4 else 1 if length <= 8 else 2 if length <= 15 else 3


def edit_distance(a, b, limit=None):
    """Optimal-string-alignment distance (substitution, insertion, deletion, adjacent transposition),
    where a substitution between CONFUSABLE characters costs 0.5. Returns more than `limit` (without
    finishing) as soon as the distance must exceed it."""
    cap = None if limit is None else round(2 * limit)  # costs are doubled to stay in integers
    la, lb = len(a), len(b)
    if cap is not None and 2 * abs(la - lb) > cap:
        return (cap + 1) / 2
    prev2, prev = None, list(range(0, 2 * lb + 1, 2))
    for i in range(1, la + 1):
        ca = a[i - 1]
        cur = [2 * i] + [0] * lb
        for j in range(1, lb + 1):
            cb = b[j - 1]
            diagonal = prev[j - 1] + (0 if ca == cb else 1 if (ca, cb) in CONFUSABLE else 2)
            cost = min(diagonal, prev[j] + 2, cur[j - 1] + 2)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb and ca != cb:
                cost = min(cost, prev2[j - 2] + 2)
            cur[j] = cost
        if cap is not None and min(cur) > cap:
            return (cap + 1) / 2
        prev2, prev = prev, cur
    return prev[lb] / 2


def expand_abbreviations(norm):
    """Normalised variants of `norm` with its abbreviations spelt out (at most MAX_VARIANTS)."""
    tokens, options, i, expanded = norm.split(), [], 0, False
    while i < len(tokens):
        for size in (2, 1):
            expansions = ABBREVIATIONS.get(tuple(tokens[i:i + size])) if i + size <= len(tokens) else None
            if expansions:
                options.append(expansions)
                i, expanded = i + size, True
                break
        else:
            options.append((tokens[i],))
            i += 1
    if not expanded:
        return []
    variants = (" ".join(choice) for choice in itertools.product(*options))
    return [v for v in itertools.islice(variants, MAX_VARIANTS) if v != norm]


def misread_stopwords(norm):
    """Words of 2-3 letters one substitution away from a stopword ("ln" for "le"): likely misread articles."""
    return [t for t in norm.split() if 2 <= len(t) <= 3 and t not in STOPWORDS and (t,) not in ABBREVIATIONS
            and any(len(w) == len(t) and sum(a != b for a, b in zip(t, w)) == 1 for w in STOPWORDS)]


def parse_postcode(code, country=None):
    """[(country, code)] pairs to look up for a postcode string; [] when it is not one.

    "3750-011", "3750 011" and "3750011" are PT 4-3 codes; four digits are a PT prefix (or, when the
    country is ES or FR, a code that lost its leading zero); five digits are ES and/or FR. A leading
    "P-", "E-" or "F-" (or "PT", "ES", "FR") gives the country, as does `country`, which wins.
    """
    s = str(code or "").strip().upper()
    hint = None
    m = re.match(r"^(PT|ES|FR|P|E|F)\s*[-‐–—:]?\s*(?=[\dO])", s)
    if m:
        hint = {"P": "PT", "E": "ES", "F": "FR"}.get(m.group(1), m.group(1))
        s = s[m.end():]
    digits = re.sub(r"[\s\-‐‑‒–—.]", "", s.translate(str.maketrans("OIL", "011")))
    if not digits.isdigit():
        return []
    country = str(country).strip().upper() if country else None
    if country is not None and country not in COUNTRY_BITS:
        raise ValueError(f"country must be one of {COUNTRIES} or None, got {country!r}")
    wanted = [country] if country else [hint] if hint else list(COUNTRIES)
    if len(digits) == 7 and "PT" in wanted:
        return [("PT", f"{digits[:4]}-{digits[4:]}")]
    if len(digits) == 4:
        if "PT" in wanted:
            return [("PT", digits)]
        return [(c, "0" + digits) for c in ("ES", "FR") if c in wanted]
    if len(digits) == 5:
        return [(c, digits) for c in ("ES", "FR") if c in wanted]
    return []


def country_mask(countries):
    """Bit mask for a country filter: None (all), "PT", "PT,ES" or an iterable of codes."""
    if countries is None:
        return ALL_COUNTRIES
    if isinstance(countries, str):
        countries = re.split(r"[\s,;|]+", countries.strip())
    mask = 0
    for c in countries:
        c = str(c).strip().upper()
        if c:
            if c not in COUNTRY_BITS:
                raise ValueError(f"countries must be among {COUNTRIES}, got {c!r}")
            mask |= COUNTRY_BITS[c]
    if not mask:
        raise ValueError("countries is empty: pass None to search all countries")
    return mask


# -- match tiers and weights ---------------------------------------------------------------------

TIER = {"exact": 0, "spacing": 1, "abbreviation": 1, "stopwords": 1, "fuzzy": 2, "within": 3, "contains": 3}
LIKELIHOOD = {"exact": 1.0, "spacing": 0.8, "abbreviation": 0.8, "stopwords": 0.6}
NAME_FACTOR = {"label": 1.0, "name": 1.0, "alias": 0.6, "alternate": 0.6}
MATCH_SCORE = {"exact": 1.0, "spacing": 0.98, "abbreviation": 0.97, "stopwords": 0.95}
FUZZY_LIKELIHOOD, FUZZY_PER_EDIT = 0.5, 0.35
PARTIAL_LIKELIHOOD = 0.2
FUZZY_MAX_KEY = 64  # longer core keys are not in the trigram index
FUZZY_POSTINGS = 400_000  # posting entries counted per fuzzy lookup, rarest trigrams first
FUZZY_VERIFY = 300  # keys checked with edit_distance, most shared trigrams first
GENERIC_DF = 2000  # a word in more names than this is generic on its own ("igreja", "rue", "quinta")
MAX_SPAN_WORDS = 6
MAX_QUERY_WORDS = 40
CONTAINS_ROWS = 200
POSTCODE_ACCURACY_NOTE = ("GeoNames accuracy flag: 1 = estimated from neighbouring codes, 4 = point of a GeoNames "
                          "place, 6 = centroid of addresses or shape; 2, 3 and 5 are intermediate levels")
# OSM places a one-word sign usually names (an entry sign): exempt from the one-word rule (word_df)
SETTLEMENTS = frozenset(f"place={v}" for v in ("city", "town", "village", "hamlet", "suburb", "borough", "quarter",
                                               "neighbourhood", "island", "islet"))
# Sign phrases that OSM sometimes holds as names (a for-sale sign mapped as a restaurant): never an OSM match
SIGN_PHRASES = frozenset(normalise(t) for t in (
    "se vende", "vende se", "vende-se", "vendese", "sevende", "se alquila", "alquila", "aluga se", "aluga-se", "alugase",
    "arrenda se", "arrenda-se", "trespassa se", "trespassa-se", "trespasse", "a vendre", "à vendre", "a louer", "à louer",
    "vendu", "vendido", "privado", "privada", "privé", "prive", "propriedade privada", "propiedad privada",
    "propriété privée", "entrada", "salida", "saida", "saída", "sortie", "entrée", "aberto", "abierto", "ouvert",
    "fechado", "cerrado", "fermé", "ferme"))
OSM_FUZZY_MIN = 7  # shorter core keys get no fuzzy OSM matches: millions of short OSM names make them coincidences
CHAIN_MIN = 8  # an OSM name that this many entries of one country carry is a chain or a generic name ...
CHAIN_KEEP = 3  # ... of which one lookup keeps this many places (details["ambiguity"] still counts them all)
# (addresses at least, the OSM aggregate's share of the weight when GeoNames has the code too). Measured on
# simulated reads at the external val cameras (T31): PT 4-3 codes median error 448 m (GeoNames) -> 28 m (OSM),
# PT prefixes 1,293 -> 590 m; ES 5-digit codes 303 -> 321 m, a wash: there both stay equal alternatives
OSM_POSTCODE_SHARE = {"PT": ((10, 0.9), (3, 0.8), (1, 0.65)), "ES": ((1, 0.5),), "FR": ((1, 0.5),)}


def prior(prominence):
    return 0.2 + 0.8 * min(1.0, max(0.0, prominence or 0.0))


def osm_postcode_share(n_addresses, country="PT"):
    """Weight of an OSM postcode aggregate when GeoNames has the code too (its point gets the rest)."""
    table = OSM_POSTCODE_SHARE[country]
    for at_least, share in table:
        if (n_addresses or 0) >= at_least:
            return share
    return table[-1][1]


class _Match:
    __slots__ = ("place_id", "match_type", "score", "likelihood", "prominence", "name", "extra", "occ", "generic",
                 "word_df")

    def __init__(self, row, match_type, score, likelihood, extra=None, generic=1, word_df=1):
        self.place_id, self.prominence = row[0], row[6]
        self.name = row[1:6]  # norm, core, langs, kind, original
        self.occ = row[7] if len(row) > 7 else 1  # entries carrying this name: OSM indexes only, else 1
        self.match_type, self.score, self.likelihood, self.extra = match_type, score, likelihood, extra or {}
        # an OSM match other than exact, when the text itself is a generic name: its number of places
        self.generic = generic if len(row) > 7 and TIER[match_type] > 0 else 1
        self.word_df = word_df  # an OSM landmark named by one word: the names holding that word

    @property
    def tier(self):
        return TIER[self.match_type]

    @property
    def weight(self):
        w = self.likelihood * NAME_FACTOR.get(self.name[3], 1.0) * prior(self.prominence)
        divisor = max(self.occ, self.word_df) * self.generic
        return w / divisor if divisor > 1 else w

    def rank(self):
        return (self.tier > 0, -self.weight, -self.score)


_NAME_COLUMNS = "n.place_id, n.norm, n.core, n.langs, n.kind, n.original, p.prominence"
_OSM_NAME_COLUMNS = _NAME_COLUMNS + ", n.occ, p.role, json_extract(p.info, '$.osm_type')"
_BY_KEY_TEMPLATE = ("SELECT {columns} FROM name n JOIN place p ON p.id = n.place_id "
                    "WHERE n.{{column}} = ?{{extra}} AND (n.cmask & ?) != 0 ORDER BY n.rowid LIMIT ?")
_BY_KEY = _BY_KEY_TEMPLATE.format(columns=_NAME_COLUMNS)
_COUNT_BY_KEY = "SELECT COUNT(DISTINCT n.place_id) FROM name n WHERE n.{column} = ?{extra} AND (n.cmask & ?) != 0"
_COUNT_NEAR = ("SELECT COUNT(DISTINCT n.place_id) FROM name n JOIN place p ON p.id = n.place_id "
               "WHERE n.{column} = ?{extra} AND (n.cmask & ?) != 0")
_CONTAINS_TEMPLATE = ("SELECT {columns} FROM ftok JOIN name n ON n.rowid = ftok.rowid "
                      "JOIN place p ON p.id = n.place_id WHERE ftok MATCH ?{{near}} AND (n.cmask & ?) != 0 LIMIT ?")
_CONTAINS = _CONTAINS_TEMPLATE.format(columns=_NAME_COLUMNS).format(near="")
_NEAR = " AND p.lat BETWEEN ? AND ? AND p.lng BETWEEN ? AND ?"
_PLACE_COLUMNS = "id, source, label, lat, lng, countries, role, extent_m, grp, info"
_POSTCODE = "SELECT kind, lat, lng, extent_m, label, info FROM postcode WHERE country = ? AND code = ?"
_OFF = ("0", "off", "false", "no")


def _connect(path):
    # immutable: the builders replace a file by renaming, so an open index never changes underneath
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    con.execute("PRAGMA cache_size = -65536")
    return con


def osm_paths(path=DEFAULT_PATH, osm=None):
    """The OSM indexes NameIndex.open(path, osm=osm) attaches (see there)."""
    if osm is False or (osm is None and os.environ.get(OSM_ENV, "").strip().lower() in _OFF):
        return []
    if osm is None or osm is True:
        folder = Path(path).parent
        return [folder / f"osm_{c}.sqlite" for c in COUNTRIES if (folder / f"osm_{c}.sqlite").is_file()]
    return [Path(p) for p in ([osm] if isinstance(osm, (str, Path)) else osm)]


class _Source:
    """One database the lookups search: names.sqlite, or one country's OSM index (osm_<CC>.sqlite)."""

    def __init__(self, con, path, meta, osm=False):
        self.con, self.path, self.meta, self.osm = con, Path(path), meta, osm
        self.country = meta.get("country") if osm else None
        self.mask = COUNTRY_BITS[self.country] if osm else ALL_COUNTRIES
        self.offset = int(meta.get("id_offset", 0)) if osm else 0
        self.swap = meta.get("byteorder", "little") != sys.byteorder
        columns = _OSM_NAME_COLUMNS if osm else _NAME_COLUMNS
        self.by_key = _BY_KEY_TEMPLATE.format(columns=columns)
        self.contains = _CONTAINS_TEMPLATE.format(columns=columns)
        self._df = {}

    def doc_frequency(self, token):
        if token not in self._df:
            row = self.con.execute("SELECT df FROM tokdf WHERE token = ?", (token,)).fetchone()
            self._df[token] = row[0] if row else 0
        return self._df[token]

    def word_df(self, row):
        """For an OSM entry whose name is one content word ("Decor", "Feliz", a "Fuente" locality): how many
        names hold that word, since a one-word reading may come from any of them. 1 otherwise, and for
        settlements (SETTLEMENTS), whose one-word names are what their signs show."""
        if not self.osm or row[9] in SETTLEMENTS:
            return 1
        words = [t for t in row[1].split() if t not in STOPWORDS]
        return max(1, self.doc_frequency(words[0])) if len(words) == 1 else 1

    def fuzzy_keys(self, core):
        """(core key, edits) of indexed keys within max_edits(len(core)) of `core`, excluding `core`."""
        n, k = len(core), max_edits(len(core))
        if k == 0 or n > FUZZY_MAX_KEY:
            return []
        grams = trigrams(core)
        lo, hi = max(4, n - k), min(FUZZY_MAX_KEY, n + k)
        marks = ",".join("?" * len(grams))
        sizes = Counter()
        for gram, size in self.con.execute(
                f"SELECT gram, n FROM fgram WHERE gram IN ({marks}) AND len BETWEEN ? AND ?", (*grams, lo, hi)):
            sizes[gram] += size
        # q-gram lemma: each edit destroys at most 3 of the query's trigrams, so a key within k edits
        # shares at least len(chosen) - 3k of any chosen subset. The rarest trigrams are counted first,
        # within a budget; trigrams with no postings at all count as destroyed.
        chosen, total = [], 0
        for gram in sorted(sizes, key=sizes.__getitem__):
            if total + sizes[gram] > FUZZY_POSTINGS and len(chosen) > 3 * k:
                break
            chosen.append(gram)
            total += sizes[gram]
        need = max(1, len(chosen) - 3 * k)
        counts = Counter()
        for gram in chosen:
            for (blob,) in self.con.execute("SELECT ids FROM fgram WHERE gram = ? AND len BETWEEN ? AND ?",
                                            (gram, lo, hi)):
                ids = array.array("I")
                ids.frombytes(blob)
                if self.swap:
                    ids.byteswap()
                counts.update(ids)
        hits = [i for i, c in counts.items() if c >= need]
        if len(hits) > FUZZY_VERIFY:
            hits = heapq.nlargest(FUZZY_VERIFY, hits, key=counts.__getitem__)
        found = []
        for start in range(0, len(hits), 500):
            batch = hits[start:start + 500]
            for (key,) in self.con.execute(f"SELECT key FROM fkey WHERE id IN ({','.join('?' * len(batch))})", batch):
                if key != core:
                    edits = edit_distance(core, key, k)
                    if edits <= k:
                        found.append((key, edits))
        return sorted(found, key=lambda f: (f[1], f[0]))


class _Search:
    """One lookup's state: the best match per place, the places matching at each tier, chain counts."""

    def __init__(self, sources, mask, cap, near=None):
        self.sources, self.mask, self.cap = sources, mask, cap
        self.best, self.places, self.extra_count, self.chains = {}, defaultdict(set), Counter(), Counter()
        self.capped = set()  # chain places left out: they stay out whatever else they match
        self.generic = 1  # places matching the text exactly, once that is CHAIN_MIN or more (lookup())
        self.near, self.near_sql, self.near_params = None, "", ()
        if near is not None:  # a box of +- radius_m around (lat, lng)
            lat, lng, radius = (float(x) for x in near)
            if not (-90 <= lat <= 90 and -180 <= lng <= 180 and radius > 0):
                raise ValueError(f"near must be (lat, lng, radius_m > 0), got {near!r}")
            dlat = radius / 110_574.0
            dlng = radius / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
            self.near, self.near_sql = (lat, lng, radius), _NEAR
            self.near_params = (lat - dlat, lat + dlat, lng - dlng, lng + dlng)

    def by_key(self, source, column, extra=""):
        return source.by_key.format(column=column, extra=extra + self.near_sql)

    def take(self, column, key, match_type, *, norm_is=None, score=None, likelihood=None, info=None, only=None):
        extra, params = "", [key]
        if norm_is is not None:
            extra = " AND n.norm = ?" if norm_is[0] else " AND n.norm != ?"
            params.append(norm_is[1])
        params.extend(self.near_params)
        for source in [only] if only else self.sources:
            rows = source.con.execute(self.by_key(source, column, extra), (*params, self.mask, self.cap)).fetchall()
            self.keep(source, rows, match_type, score, likelihood, info)
            if len(rows) == self.cap:  # truncated: count the rest for details["ambiguity"]
                count = (_COUNT_NEAR if self.near else _COUNT_BY_KEY).format(column=column, extra=extra + self.near_sql)
                total = source.con.execute(count, (*params, self.mask)).fetchone()[0]
                self.extra_count[TIER[match_type]] += max(0, total - len({r[0] for r in rows}))

    def keep(self, source, rows, match_type, score=None, likelihood=None, info=None, coverage=None):
        for row in rows:
            if source.osm and row[1] in SIGN_PHRASES:
                continue
            if coverage is not None:
                c = coverage(row)
                if c is None:
                    continue
                m = _Match(row, match_type, c, PARTIAL_LIKELIHOOD * c * c, {**(info or {}), "coverage": round(c, 4)},
                           self.generic, source.word_df(row))
            else:
                m = _Match(row, match_type, MATCH_SCORE.get(match_type, score), LIKELIHOOD.get(match_type, likelihood),
                           info, self.generic, source.word_df(row))
            self.places[m.tier].add(m.place_id)
            if m.place_id in self.capped:
                continue
            current = self.best.get(m.place_id)
            if current is None:
                if m.occ >= CHAIN_MIN and self.near is None:  # a chain or generic OSM name: a few per country
                    chain = (source.country, m.name[0])  # stand for the rest
                    if self.chains[chain] >= CHAIN_KEEP:
                        self.capped.add(m.place_id)
                        continue
                    self.chains[chain] += 1
                self.best[m.place_id] = m
            elif m.rank() < current.rank():
                self.best[m.place_id] = m

    def misread_articles(self, source, norm, squashed, core):
        """Fuzzy matches that read a suspect short word as a misread article ("ln" for "le"), kept only
        when the whole squashed name is within max_edits of the query's."""
        suspects = misread_stopwords(norm)
        alternative = "".join(t for t in norm.split() if t not in STOPWORDS and t not in suspects)
        if not suspects or not alternative or alternative == core:
            return
        k = max_edits(len(squashed))
        by_edits = defaultdict(list)
        for row in source.con.execute(self.by_key(source, "core"), (alternative, *self.near_params, self.mask, self.cap)):
            edits = edit_distance(squashed, row[1].replace(" ", ""), k)
            if 0 < edits <= k:
                by_edits[edits].append(row)
        for edits, rows in by_edits.items():
            self.keep(source, rows, "fuzzy", 1 - edits / len(squashed), FUZZY_LIKELIHOOD * FUZZY_PER_EDIT ** edits,
                      {"edit_distance": edits, "misread_words": suspects})

    def partial(self, norm, core):
        tokens = norm.split()
        # within: a run of the query's words is a whole name
        spans = []
        for source in self.sources:
            for i in range(len(tokens) if len(tokens) > 1 else 0):
                for j in range(i + 1, min(len(tokens), i + MAX_SPAN_WORDS) + 1):
                    span = tokens[i:j]
                    # a span starting or ending with a stopword repeats the shorter span without it
                    if len(span) == len(tokens) or span[0] in STOPWORDS or span[-1] in STOPWORDS:
                        continue
                    content = [t for t in span if t not in STOPWORDS]
                    span_core = "".join(content)
                    if len(span_core) < 4 or (len(content) == 1 and source.doc_frequency(content[0]) > GENERIC_DF):
                        continue
                    rows = source.con.execute(self.by_key(source, "core"),
                                              (span_core, *self.near_params, self.mask, self.cap)).fetchall()
                    if rows:
                        spans.append((i, j, " ".join(span), len(span_core) / len(core), rows, source))
        for i, j, text, share, rows, source in spans:
            # a name inside a longer matching run is likely part of that longer name ("... Santa Maria Maior")
            if any(a <= i and j <= b and b - a > j - i for a, b, *_ in spans):
                share /= 2
            self.keep(source, rows, "within", info={"span": text}, coverage=lambda row, share=share: min(share, 0.99))
        # contains: a name holds every content word of the query
        content = list(dict.fromkeys(t for t in tokens if t not in STOPWORDS))
        if not content:
            return
        query = " AND ".join(f'"{t}"' for t in content)  # tokens are [a-z0-9]+, safe inside quotes

        def coverage(row):
            name_core = row[2]
            return None if name_core == core else min(len(core) / max(len(name_core), 1), 0.99)

        for source in self.sources:
            if len(content) == 1 and source.doc_frequency(content[0]) > GENERIC_DF:
                continue
            rows = source.con.execute(source.contains.format(near=self.near_sql),
                                      (query, *self.near_params, self.mask, CONTAINS_ROWS)).fetchall()
            self.keep(source, rows, "contains", coverage=coverage)


class NameIndex:
    """Read-only access to the name index built by tools/build_name_index.py, and to the OSM indexes
    built by tools/build_osm_index.py that open() attaches next to it."""

    def __init__(self, connection, path):
        self._con = connection
        self.path = Path(path)
        self.meta = {k: json.loads(v) for k, v in connection.execute("SELECT key, value FROM meta")}
        if self.meta.get("schema") != SCHEMA:
            raise RuntimeError(f"{path} has schema {self.meta.get('schema')!r}, expected {SCHEMA!r}: "
                               "rebuild it with python3 -I tools/build_name_index.py")
        self._main = _Source(connection, path, self.meta)
        self._sources = [self._main]
        self._by_offset = {0: self._main}
        self.osm = []  # the attached OSM indexes: country, path, extract timestamp, entries

    @classmethod
    def open(cls, path=DEFAULT_PATH, *, osm=None):
        """Open names.sqlite and the OSM indexes beside it.

        osm=None attaches every osm_PT/ES/FR.sqlite in the same folder, unless the environment variable
        PANOLOC_NAMES_OSM is 0, off, false or no; osm=False attaches none (as before T31); osm=True
        attaches them whatever the variable says; a path or a list of paths attaches exactly those.
        An auto-found index with the wrong schema is skipped with a warning; a listed one raises.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"no name index at {path}: build it with python3 -I tools/build_name_index.py")
        index = cls(_connect(path), path)
        try:
            for osm_path in osm_paths(path, osm):
                index.attach_osm(osm_path, required=osm not in (None, True))
        except BaseException:
            index.close()
            raise
        return index

    def attach_osm(self, path, *, required=True):
        """Search one more OSM index (tools/build_osm_index.py); returns its description, or None when skipped."""
        path = Path(path)
        problem, con = None, None
        if not path.is_file():
            problem = f"no OSM index at {path}"
        else:
            con = _connect(path)
            try:
                meta = {k: json.loads(v) for k, v in con.execute("SELECT key, value FROM meta")}
            except sqlite3.DatabaseError as exc:
                meta, problem = {}, f"{path} is not an OSM index ({exc})"
            country = meta.get("country")
            if problem:
                pass
            elif meta.get("schema") != OSM_SCHEMA:
                problem = (f"{path} has schema {meta.get('schema')!r}, expected {OSM_SCHEMA!r}: rebuild it with "
                           ".venv/bin/python -I tools/build_osm_index.py")
            elif country not in COUNTRY_BITS or meta.get("id_offset") != OSM_ID_OFFSET[country]:
                problem = f"{path}: unexpected country {country!r} or id offset"
            elif any(s.country == country for s in self._sources):
                problem = f"{path}: an OSM index for {country} is already attached"
        if problem:
            if con is not None:
                con.close()
            if required:
                raise RuntimeError(problem) if path.is_file() else FileNotFoundError(problem)
            warnings.warn(problem + "; searching without it", RuntimeWarning, stacklevel=3)
            return None
        source = _Source(con, path, meta, osm=True)
        self._sources.append(source)
        self._by_offset[source.offset] = source
        extract = meta.get("extract") or {}
        info = {"country": source.country, "path": str(path), "built_utc": meta.get("built_utc"),
                "extract_timestamp": extract.get("osmosis_replication_timestamp"),
                "entries": (meta.get("stats") or {}).get("entries")}
        self.osm.append(info)
        return info

    def close(self):
        for source in self._sources:
            source.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- names ---------------------------------------------------------------------------------------

    def lookup(self, text, countries=None, limit=10, *, fuzzy=True, partial=True, near=None):
        """Candidates for a place name: one per place, exact matches first, then by weight (module docstring).

        near=(lat, lng, radius_m) searches only a box of +- radius_m around that point (no chain cap there;
        details["near_distance_m"] gives each place's distance): is this chain store or street name near
        a hypothesis that other clues support?
        """
        limit = int(limit)
        mask = country_mask(countries)
        norm = normalise(text)
        if not norm.isascii():  # the index holds Latin-script names only
            norm = "".join(ch if ch.isascii() else " " for ch in norm)
        norm = " ".join(norm.split()[:MAX_QUERY_WORDS])
        if limit <= 0 or not any(ch.isalpha() for ch in norm):
            return []  # nothing to match, or digits only (use postcode())
        squashed, core = keys(norm)
        search = _Search([s for s in self._sources if s.mask & mask], mask, max(4 * limit, 40), near)
        take = search.take

        take("squash", squashed, "exact", norm_is=(True, norm))
        exact = len(search.places.get(0, ())) + search.extra_count[0]
        if exact >= CHAIN_MIN and len(search.sources) > 1:  # with OSM: the text is itself a generic name
            search.generic = exact
        if len(search.best) < limit:  # otherwise no other match can make the cut
            take("squash", squashed, "spacing", norm_is=(False, norm))
            for variant in expand_abbreviations(norm):
                v_squashed, v_core = keys(variant)
                take("squash", v_squashed, "abbreviation", info={"expanded": variant})
                if v_core != v_squashed:
                    take("core", v_core, "abbreviation", info={"expanded": variant})
            take("core", core, "stopwords")
            if fuzzy:
                for source in search.sources:
                    if source.osm and len(core) < OSM_FUZZY_MIN:
                        continue
                    for key, edits in source.fuzzy_keys(core):
                        score = 1 - edits / max(len(core), len(key))
                        take("core", key, "fuzzy", score=score, likelihood=FUZZY_LIKELIHOOD * FUZZY_PER_EDIT ** edits,
                             info={"edit_distance": edits, "matched_key": key}, only=source)
                    search.misread_articles(source, norm, squashed, core)
            if partial:
                search.partial(norm, core)

        ranked = sorted(search.best.values(), key=_Match.rank)[:limit]
        ambiguity = {t: len(ids) + search.extra_count[t] for t, ids in search.places.items()}
        out = self._candidates(ranked, text, norm, mask, ambiguity)
        if search.near:
            for c in out:
                c.details["near_distance_m"] = round(haversine_m(search.near[:2], c.point), 1)
        return out

    def _source_of(self, place_id):
        return self._by_offset[(place_id >> 40) << 40]

    def _candidates(self, ranked, text, norm, mask, ambiguity):
        if not ranked:
            return []
        by_source = defaultdict(list)
        for m in ranked:
            by_source[self._source_of(m.place_id)].append(m.place_id)
        rows, links, groups = {}, defaultdict(list), {}
        for source, ids in by_source.items():
            marks = ",".join("?" * len(ids))
            rows.update({r[0]: (source, r) for r in source.con.execute(
                f"SELECT {_PLACE_COLUMNS} FROM place WHERE id IN ({marks})", ids)})
            if source.osm:
                for place_id, other, distance, how in source.con.execute(
                        f"SELECT place_id, other, distance_m, how FROM link WHERE place_id IN ({marks}) "
                        "ORDER BY distance_m", ids):
                    links[place_id].append({"source": other, "distance_m": distance, "how": how})
            else:
                for place_id, other, distance in source.con.execute(
                        f"SELECT l.place_id, p.source, l.distance_m FROM link l JOIN place p ON p.id = l.other_id "
                        f"WHERE l.place_id IN ({marks}) ORDER BY l.distance_m", ids):
                    links[place_id].append({"source": other, "distance_m": distance})
        osm_sources = [s for s in self._sources if s.osm]
        if osm_sources and self._main in by_source:  # OSM objects linked to these names.sqlite entries
            by_name = {rows[i][1][1]: i for i in by_source[self._main]}
            marks = ",".join("?" * len(by_name))
            for source in osm_sources:
                for other, osm_source, distance, how in source.con.execute(
                        f"SELECT l.other, p.source, l.distance_m, l.how FROM link l JOIN place p ON p.id = l.place_id "
                        f"WHERE l.other IN ({marks}) ORDER BY l.distance_m", list(by_name)):
                    links[by_name[other]].append({"source": osm_source, "distance_m": distance, "how": how})
                for name_source, group in source.con.execute(
                        f"SELECT source, grp FROM main_group WHERE source IN ({marks})", list(by_name)):
                    groups.setdefault(by_name[name_source], group)
        out = []
        for m in ranked:
            source, (_, src, label, lat, lng, countries, role, extent_m, group, info) = rows[m.place_id]
            listed = countries.split("|")
            norm_name, _, langs, kind, original = m.name
            details = {
                "match_type": m.match_type, "match_score": round(m.score, 4), "tier": m.tier,
                "query": str(text), "query_normalised": norm, "matched_name": original,
                "matched_normalised": norm_name, "language": langs.split(",") if langs else None,
                "name_kind": kind, "ambiguity": ambiguity.get(m.tier, 1), **m.extra,
                "prominence": round(m.prominence, 4), "prior": round(prior(m.prominence), 4),
                "countries": listed, **json.loads(info),
            }
            if source.osm:
                details["occurrences"] = m.occ
                if m.occ >= CHAIN_MIN:
                    details["chain"] = True
                if m.generic > 1:
                    details["generic_query"] = m.generic
                if m.word_df > 1:
                    details["word_frequency"] = m.word_df
            if links.get(m.place_id):
                details["same_place_as"] = links[m.place_id]
            out.append(Candidate(lat, lng, role, src, label=label, weight=round(m.weight, 9 if source.osm else 6),
                                 extent_m=extent_m, country=next((c for c in listed if COUNTRY_BITS[c] & mask),
                                                                 listed[0]),
                                 group=group or groups.get(m.place_id), details=details))
        return out

    # -- postcodes -----------------------------------------------------------------------------------

    def postcode(self, code, country=None):
        """Area candidates for a postcode (module docstring); [] when unknown or not a postcode."""
        out = []
        for c, key in parse_postcode(code, country):
            geonames = self._con.execute(_POSTCODE, (c, key)).fetchone()
            osm = next((row for s in self._sources if s.osm and s.country == c
                        for row in [s.con.execute(_POSTCODE, (c, key)).fetchone()] if row), None)
            share = 1.0
            if osm is not None:
                kind, lat, lng, extent_m, label, info = osm
                info = json.loads(info)
                share = osm_postcode_share(info.get("n_addresses"), c) if geonames else 1.0
                details = {"query": str(code), "kind": kind, "code": key, **info}
                if geonames:
                    details["geonames_distance_m"] = round(haversine_m((lat, lng), geonames[1:3]), 1)
                out.append(Candidate(lat, lng, "area", f"osm-postcode:{c}:{key}", label=label, weight=share,
                                     extent_m=extent_m, country=c, details=details))
            if geonames is None:
                continue
            kind, lat, lng, extent_m, label, info = geonames
            details = {"query": str(code), "kind": kind, "code": key, **json.loads(info),
                       "accuracy_note": POSTCODE_ACCURACY_NOTE}
            if osm is not None:
                details["source"] = "geonames"
            out.append(Candidate(lat, lng, "area", f"postcode:{c}:{key}", label=label, weight=round(1.0 - share, 6)
                                 if osm is not None else 1.0, extent_m=extent_m, country=c, details=details))
        return out
