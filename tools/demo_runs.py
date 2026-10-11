#!/usr/bin/env python3
"""Write one demo run per warm-up panorama, to check replays and maps against known locations.

Each run is a real panoloc.runlog event log (events.jsonl only; log.json is removed) next to its
panorama, so the Aqui console can open the folder with "Replay a log". Nothing is inferred from the
image. A run holds:
  - the team's estimate from Data/warmup_locations.json as team evidence, and as candidates with its
    alternatives and two invented decoy cities over 100 km away, one of them in another country
    (source demo:decoy-*), so the questions have something to rule out
  - an initial output, then the human loop with the real panoloc.questions builders: a sign-language
    feature question skipped (free, changes nothing), a zone question answered with the zone holding
    the estimate (x0.95), two invented look-alike spots 2 km away inside that zone (demo:lookalike-*,
    precise estimates only), a text cue (x0.8) and a place question answered with the estimate
    (x0.95). Each answer is applied with apply_answer; expected gains are computed, not invented
  - a final output with the estimate in all 10 slots, at multiplier 0.95 x 0.95 x 0.8 = 0.722

Questions also carry the console's proposed fields (app/CONTRACT.md): gain, break_even, a string
scope, and per option a GeoJSON zone and a none flag. Cues name no place (RULES.md rule 6).

These coordinates are EVALUATION DATA, not agent output (RULES.md, PLAN.md 4.6). The runs go to
demo_runs/ (gitignored), away from runs/, and every log says so in versions and notes: never feed
them to the agent, the photo bank, training, calibration or the galleries.

The panorama itself is not copied: each folder and every event name it by filename (to replay it with
the photo in the console, select the JPEG from Data/Panorama Warm-Up/ along with the log). Stage and
answer times are simulated, as in tools/sample_log.py.

Usage (from the repo root):  python3 tools/demo_runs.py [--out demo_runs] [--overwrite]
Prints one line per panorama with the final coordinate, its uncertainty and the multiplier.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from panoloc.candidates import Candidate, normalise  # noqa: E402
from panoloc.questions import (BREAK_EVEN, apply_answer, expected_gain, feature_question,  # noqa: E402
                               place_question, zone_question)
from panoloc.runlog import Run  # noqa: E402
from panoloc.scoring import best_point, haversine_m  # noqa: E402

REFERENCES = ROOT / "Data" / "warmup_locations.json"
SOURCE = "demo:warmup_reference"
NOTE = ("demo: the team's estimated camera position from Data/warmup_locations.json. "
        "Evaluation data, not agent output.")
URBAN_PROBABILITY = 0.5  # the Urban label stays unknown during a run (PLAN.md 1.3)
DECOYS = [("Porto", "PT", 41.1496, -8.6110), ("Faro", "PT", 37.0194, -7.9304),  # invented look-alikes
          ("Seville", "ES", 37.3891, -5.9845), ("Madrid", "ES", 40.4168, -3.7038),
          ("Bordeaux", "FR", 44.8378, -0.5792), ("Lyon", "FR", 45.7640, 4.8357)]
DECOY_MIN_DISTANCE_M = 100_000
LOOKALIKE_DISTANCE_M = 2000
BEARINGS = [("N", 0), ("E", 90), ("S", 180), ("W", 270), ("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)]
LANGUAGES = ["Portuguese", "Spanish", "French", "No readable writing"]
LANGUAGE_OF = {"PT": 0, "ES": 1, "FR": 2}
CUES = [  # pointers to what to look at: no place named or hinted at (RULES.md rule 6)
    "Read every sign at full resolution before choosing.",
    "Look at the paving, the street furniture and the window shapes, not only the large buildings.",
    "Check the ground under the camera as well as the horizon.",
    "Compare the building materials and roof tiles with your reference photos.",
]


class SimulatedClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


def short(text, limit=60):
    """The first clause of a place description, for option and candidate labels."""
    cut = min((i for i in (text.find(sep) for sep in (" (", ", ", " - ", ": ")) if i > 0), default=len(text))
    text = text[:cut]
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def initial_candidates(ref, notes, index):
    """The estimate, its alternatives and two decoy cities over 100 km away (the first in another
    country, so the language question can tell them apart), as weighted hypotheses."""
    precise = ref["confidence"] == "high"
    role = "camera" if precise else "area"
    alternatives = ref.get("alternatives", [])
    alt_weight = 0.15 if precise else 0.3  # a coarse estimate's alternatives are real contenders
    rotated = DECOYS[index % len(DECOYS):] + DECOYS[:index % len(DECOYS)]
    far = [d for d in rotated if haversine_m((ref["lat"], ref["lon"]), d[2:]) > DECOY_MIN_DISTANCE_M]
    foreign = next(d for d in far if d[1] != ref["country"])
    decoys = [foreign, next(d for d in far if d is not foreign)]
    candidates = [Candidate(ref["lat"], ref["lon"], role, SOURCE, label=short(ref["place"]),
                            weight=0.6 - alt_weight if alternatives else 0.6,
                            accuracy_m=ref["error_radius_m"] if precise else None,
                            extent_m=None if precise else ref["error_radius_m"], country=ref["country"],
                            evidence=notes, details={"place": ref["place"], "confidence": ref["confidence"]})]
    for i, alt in enumerate(alternatives, start=1):
        candidates.append(Candidate(alt["lat"], alt["lon"], role, f"demo:warmup_alternative-{i}",
                                    label=short(alt["place"]), weight=alt_weight / len(alternatives),
                                    country=ref["country"], details={"place": alt["place"], "why": alt.get("why")}))
    for name, country, lat, lng in decoys:
        candidates.append(Candidate(lat, lng, "area", f"demo:decoy-{name.lower()}", label=f"{name} centre (decoy)",
                                    weight=0.2, extent_m=3000, country=country, details={"invented": True}))
    return candidates


def offset(lat, lng, bearing_deg, distance_m):
    """A point distance_m from (lat, lng) along bearing_deg; flat-Earth, fine at a few km."""
    north = distance_m * math.cos(math.radians(bearing_deg)) / 111_195
    east = distance_m * math.sin(math.radians(bearing_deg)) / (111_195 * math.cos(math.radians(lat)))
    return lat + north, lng + east


def lookalikes(reference, zone, weight):
    """Two invented spots LOOKALIKE_DISTANCE_M from the estimate, inside the chosen zone cell."""
    spots = []
    for name, bearing in BEARINGS:
        lat, lng = offset(reference.lat, reference.lng, bearing, LOOKALIKE_DISTANCE_M)
        if zone.contains((lat, lng)):
            spots.append(Candidate(lat, lng, "camera", f"demo:lookalike-{name.lower()}",
                                   label=f"Look-alike spot {LOOKALIKE_DISTANCE_M // 1000} km {name} (decoy)",
                                   weight=weight, accuracy_m=10, country=reference.country,
                                   details={"invented": True}))
        if len(spots) == 2:
            return spots
    return spots


def log_candidates(run, candidates):
    run.candidates([{"candidate_id": f"c{i}", **c.to_dict(), "supports": c.evidence, "contradicts": []}
                    for i, c in enumerate(normalise(candidates), start=1)])


def zone_geometry(box):
    """A zone cell as the GeoJSON Polygon the console draws ([lng, lat] order)."""
    ring = [[box.west, box.south], [box.east, box.south], [box.east, box.north], [box.west, box.north],
            [box.west, box.south]]
    return {"type": "Polygon", "coordinates": [ring]}


def log_question(run, question, candidates):
    """Run.ask with the question's options and expected gain, plus the console's proposed fields."""
    gain = expected_gain(candidates, question, urban_probability=URBAN_PROBABILITY)
    options = []
    for o in question.options:
        d = o.to_dict()
        if o.bbox is not None:
            d["zone"] = zone_geometry(o.bbox)
        if o.complement:
            d["none"] = True
        options.append(d)
    details = {**question.details, "gain": round(gain["gain"], 6), "break_even": BREAK_EVEN,
               "expected_gain": gain, "worded_by": "template"}
    if question.scope is not None:
        details.update(scope=["Portugal · Spain · France"], scope_box=question.scope.to_dict())
    question.question_id = run.ask(question.text, options, kind=question.kind, **details)


def answer(run, question, candidates, holds):
    """The team picks the option holding `holds`; the soft update follows (panoloc.questions)."""
    option = question.option_for(holds)
    run.answer(question.question_id, option.id)
    candidates = apply_answer(candidates, question, option.id)
    log_candidates(run, candidates)
    return candidates, option


def write_run(ref, out, index):
    clock = SimulatedClock()
    precise = ref["confidence"] == "high"
    run = Run(ref["file"], out, run_id=f"demo-{Path(ref['file']).stem}", clock=clock,
              versions={"demo": "tools/demo_runs.py", "reference": "Data/warmup_locations.json (evaluation only)"})

    with run.stage("reference"):
        clock.wait(0.4)
        notes = [run.evidence("reference_note", {"observation": text}, stage="reference", actor="team")
                 for text in ref["evidence"]]
        notes.insert(0, run.evidence("reference_location", {
            "observation": ref["place"], "inference": ref["method"], "country": ref["country"],
            "urban_estimate": ref["urban"], "error_radius_m": ref["error_radius_m"],
            "confidence_label": ref["confidence"], "heading_yaw0_deg": ref.get("heading_yaw0_deg"),
        }, stage="reference", actor="team"))
        clock.wait(0.3)

    candidates = initial_candidates(ref, notes, index)
    reference = candidates[0]
    log_candidates(run, candidates)
    clock.wait(0.2)
    point, _ = best_point([c.point for c in candidates], [(c.point, c.weight) for c in candidates],
                          urban_probability=URBAN_PROBABILITY)
    best = next(c for c in candidates if c.point == point)
    run.output([point] * 10, method="coarse_candidate", sources=[best.source], source_role=best.role,
               uncertainty_m=best.accuracy_m or best.extent_m, uncertainty_source="source_estimate",
               note="demo: initial answer, before any question")

    clock.wait(1.5)
    question = feature_question(candidates, "Which language is the writing on signs and shopfronts in?",
                                LANGUAGES, lambda c: LANGUAGE_OF[c.country])
    log_question(run, question, candidates)
    clock.wait(9 + 2 * (index % 4))
    run.skip(question.question_id)  # free, and nothing is inferred from it

    clock.wait(1.0)
    question = zone_question(candidates)
    log_question(run, question, candidates)
    clock.wait(22 + 3 * (index % 5))
    candidates, zone = answer(run, question, candidates, reference)

    if precise:  # a closer look inside the chosen zone turns up look-alike spots
        clock.wait(4.0)
        candidates += lookalikes(reference, zone, weight=0.25 * sum(c.weight for c in candidates))
        log_candidates(run, candidates)

    clock.wait(18 + index % 7)
    run.cue(CUES[index % len(CUES)])

    clock.wait(2.0)
    question = place_question(candidates)
    log_question(run, question, candidates)
    clock.wait(28 + 4 * (index % 3))
    candidates, _ = answer(run, question, candidates, reference)

    clock.wait(0.5)
    run.output([(ref["lat"], ref["lon"])] * 10, method="reference_camera" if precise else "coarse_candidate",
               sources=[SOURCE], source_role="camera" if precise else "area",
               uncertainty_m=ref["error_radius_m"], uncertainty_source="source_estimate", note=NOTE)
    clock.wait(0.1)
    run.finish().unlink()  # keep events.jsonl only
    return run


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="demo_runs", help="folder for the runs (default: demo_runs)")
    ap.add_argument("--overwrite", action="store_true", help="replace demo runs already in --out")
    args = ap.parse_args()

    out = Path(args.out)
    refs = json.loads(REFERENCES.read_text(encoding="utf-8"))
    for ref in refs:
        folder = out / f"demo-{Path(ref['file']).stem}"
        if folder.exists():
            if not args.overwrite:
                sys.exit(f"{folder} exists; pass --overwrite to replace the demo runs")
            shutil.rmtree(folder)

    for index, ref in enumerate(refs):
        run = write_run(ref, out, index)
        final = run.outputs[-1]
        first = final["coordinates"][0]
        print(f"{ref['file']}  {first['lat']:.6f}, {first['lng']:.6f}  ±{final['position_uncertainty_m']} m  "
              f"x{len(final['coordinates'])}  multiplier {final['penalty']['multiplier']:.4f}  {run.dir}")


if __name__ == "__main__":
    main()
