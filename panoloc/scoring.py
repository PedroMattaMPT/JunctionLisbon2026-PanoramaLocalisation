"""Challenge score (RULES.md rules 1-12) and the expected-score objective (PLAN.md 1.1).

  entry_score = 1000 × 0.95^(rank - 1) × theta(distance) × penalty multiplier × special factor
  distance < 10 m counts as 0
  urban:     theta = 2 / (1 + d / 100)
  non-urban: theta = 2 / (1 + d / 10000)
  special factor = 3 for the Special One, otherwise 1

A panorama scores the sum over its entries (at most 10). The penalty multiplier is the one in force
when the entry was produced: panoloc.runlog snapshots it on every output. Distances are Haversine on
a sphere of radius 6,371,000 m (rule 2: gis.tools, Haversine). Points are (lat, lng) in degrees,
latitude first. Categories are "urban" and "non-urban", as in panoloc.runlog.

PLAN.md 1.1: choose the coordinate that maximises expected theta under the current hypotheses and
repeat it in all 10 slots. The most likely hypothesis is not always that coordinate.
"""
import math

EARTH_RADIUS_M = 6_371_000.0
BASE_POINTS = 1000.0
RANK_FACTOR = 0.95
SPECIAL_FACTOR = 3.0
ZERO_DISTANCE_M = 10.0
SCALE_M = {"urban": 100.0, "non-urban": 10_000.0}
MAX_ENTRIES = 10


def haversine_m(a, b):
    """Great-circle distance in metres between two (lat, lng) points."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def theta(distance_m, category):
    """Distance factor: 2 at the spot (under 10 m), 1 at 100 m urban or 10 km non-urban."""
    d = 0.0 if distance_m < ZERO_DISTANCE_M else distance_m
    return 2.0 / (1.0 + d / SCALE_M[category])


def entry_score(rank, distance_m, category, multiplier=1.0, special=False):
    if not 1 <= rank <= MAX_ENTRIES:
        raise ValueError(f"rank must be 1 to {MAX_ENTRIES}, got {rank}")
    return (BASE_POINTS * RANK_FACTOR ** (rank - 1) * theta(distance_m, category) * multiplier
            * (SPECIAL_FACTOR if special else 1.0))


def list_score(guesses, truth, category, multipliers=1.0, special=False):
    """Score of a ranked list of up to 10 (lat, lng) guesses against the true spot.

    multipliers is one penalty multiplier for the whole list, or one per entry.
    """
    if len(guesses) > MAX_ENTRIES:
        raise ValueError(f"at most {MAX_ENTRIES} guesses, got {len(guesses)}")
    if isinstance(multipliers, (int, float)):
        multipliers = [multipliers] * len(guesses)
    if len(multipliers) != len(guesses):
        raise ValueError("one multiplier per guess")
    return sum(entry_score(rank, haversine_m(g, truth), category, m, special)
               for rank, (g, m) in enumerate(zip(guesses, multipliers), start=1))


def max_score(entries=MAX_ENTRIES, special=False):
    """All entries exact and unpenalised: 16,050.52 for 10 entries, 48,151.57 for the Special One."""
    return sum(entry_score(rank, 0.0, "urban", 1.0, special) for rank in range(1, entries + 1))


def score_output(output, truth, category, special=None):
    """Score an output.produced payload of panoloc.runlog: its coordinates under its penalty snapshot."""
    guesses = [(c["lat"], c["lng"]) for c in output["coordinates"]]
    special = output.get("special_one", False) if special is None else special
    return list_score(guesses, truth, category, output["penalty"]["multiplier"], special)


def expected_theta(point, hypotheses, category=None, urban_probability=None):
    """PLAN.md 1.1 utility of outputting `point`: sum_j p_j × theta(distance(point, y_j)).

    hypotheses: iterable of ((lat, lng), weight); weights are normalised here. Give either a known
    category, or urban_probability while the label is unknown (PLAN.md 1.3): that probability is
    an assumption, so log it with the result.
    """
    hypotheses = list(hypotheses)
    total = sum(w for _, w in hypotheses)
    if total <= 0:
        raise ValueError("hypothesis weights must sum to more than 0")
    if (category is None) == (urban_probability is None):
        raise ValueError("give exactly one of category and urban_probability")
    if category is not None:
        return sum(w * theta(haversine_m(point, y), category) for y, w in hypotheses) / total
    if not 0 <= urban_probability <= 1:
        raise ValueError("urban_probability must be in [0, 1]")
    return sum(w * (urban_probability * theta(d, "urban") + (1 - urban_probability) * theta(d, "non-urban"))
               for y, w in hypotheses for d in [haversine_m(point, y)]) / total


def best_point(points, hypotheses, category=None, urban_probability=None):
    """The point among `points` with the highest expected theta, and that value.

    The coordinate to repeat in all 10 slots (PLAN.md 1.1). Offer hypothesis positions and other
    supported camera positions as `points`; a centroid between distant alternatives may be a place
    no camera could stand.
    """
    hypotheses = list(hypotheses)
    scored = [(expected_theta(p, hypotheses, category, urban_probability), p) for p in points]
    if not scored:
        raise ValueError("no points to choose from")
    value, point = max(scored, key=lambda s: s[0])
    return point, value
