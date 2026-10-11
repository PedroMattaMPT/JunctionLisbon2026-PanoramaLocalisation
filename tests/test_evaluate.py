"""Tests for panoloc.evaluate, tools/evaluate.py and the tagging helpers of tools/build_splits.py.

Run from the repo root: .venv/bin/python -m unittest tests.test_evaluate
"""
import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from panoloc import evaluate as ev
from panoloc.runlog import Run
from panoloc.scoring import haversine_m, max_score

REPO = Path(__file__).resolve().parent.parent
PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented, not a warm-up file
TRUTH = (38.7000, -9.1000)
# Code allowed to name the warm-up reference file: the evaluator, and the demo-run writer (evaluation
# and demo data, never agent input). Keep panoloc/ strict: only its evaluator may read it.
WARMUP_READERS = {"panoloc/evaluate.py", "tools/evaluate.py", "tools/demo_runs.py"}


def offset(point, north_m=0.0, east_m=0.0):
    lat, lng = point
    return (lat + north_m / 111_195.0, lng + east_m / (111_195.0 * 0.7804))  # cos(38.7°) ≈ 0.7804


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", REPO / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixed_predict(panorama_path, runs_dir):
    """Dummy predictor for the --predict hook: one fixed coordinate, repeated."""
    return [list(TRUTH)] * 10


def failing_predict(panorama_path, runs_dir):
    raise RuntimeError("model fell over")


def run_predict(panorama_path, runs_dir):
    """Dummy predictor that goes through panoloc.runlog, as the pipeline will; it never finishes the run,
    so the evaluator reads events.jsonl."""
    run = Run(panorama_path, runs_dir, category=None)
    run.output([offset(TRUTH, north_m=50)] * 10, method="coarse_candidate")
    return str(run.dir)


def refset(refs, name="synthetic"):
    return ev.ReferenceSet(name, refs, source="test")


class TempDirTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)


class ScoreFromLogTest(TempDirTest):
    def test_last_output_with_its_penalty_and_the_trajectory(self):
        run = Run(PANORAMA, self.dir / "runs", category=None)
        run.output([offset(TRUTH, north_m=300)] * 10, method="coarse_candidate", uncertainty_m=None)
        q = run.ask("Which side of the river is this?", ["North bank", "South bank", "None of these"])
        run.answer(q, "a")
        run.output([TRUTH] * 10, method="reference_camera", uncertainty_m=12.0, uncertainty_source="geometric_bound")
        run.finish()

        preds = ev.load_predictions([self.dir / "runs"])
        self.assertEqual(list(preds), [PANORAMA])
        pred = preds[PANORAMA]
        self.assertAlmostEqual(pred.multiplier, 0.95)
        self.assertEqual(len(pred.trajectory), 2)

        ref = ev.Reference(PANORAMA, *TRUTH, error_radius_m=5.0, category="urban", category_source="inferred")
        case = ev.evaluate(refset([ref]), preds)["cases"][0]
        self.assertTrue(case["predicted"])
        self.assertLess(case["distance_m"], 1.0)
        top = max_score()
        self.assertAlmostEqual(case["score"]["urban"]["nominal"], 0.95 * top, places=1)
        self.assertAlmostEqual(case["score"]["non-urban"]["nominal"], 0.95 * top, places=1)
        self.assertAlmostEqual(case["fraction_of_max_ref"], 0.95, places=3)
        # d_max = d + 5 m stays under 10 m, so even the conservative score is exact
        self.assertAlmostEqual(case["score_ref_conservative"], 0.95 * top, places=1)
        self.assertEqual(case["method"], "reference_camera")
        self.assertEqual(case["uncertainty_m"], 12.0)
        self.assertEqual(case["penalty"]["answered_questions"], 1)
        first, last = case["trajectory"]
        self.assertEqual(first["multiplier"], 1.0)
        self.assertAlmostEqual(first["distance_m"], 300, delta=1)
        self.assertAlmostEqual(first["score_urban"], top / 4, delta=2)  # theta(300 m) = 0.5 of the maximum's 2
        self.assertAlmostEqual(last["score_urban"], case["score"]["urban"]["nominal"], places=1)

    def test_radius_bounds_and_hit_status(self):
        ref = ev.Reference(PANORAMA, *TRUTH, error_radius_m=12.0, category="urban")
        pred = ev.Prediction(PANORAMA, [offset(TRUTH, east_m=95)] * 10)
        case = ev.score_case(ref, pred)
        self.assertAlmostEqual(case["distance_max_m"] - case["distance_m"], 12.0, places=0)
        self.assertEqual(case["hits"]["100"], "boundary")  # 95 m nominal, 107 m at the far edge
        self.assertEqual(case["hits"]["1000"], "inside")
        self.assertEqual(case["hits"]["25"], "outside")
        s = case["score"]["urban"]
        self.assertLess(s["lower"], s["nominal"])
        self.assertLess(s["nominal"], s["upper"])
        self.assertEqual(ev.hit_status(50, None, 100), "inside")


class WarmupHashTest(TempDirTest):
    def test_frozen_baseline_loads(self):
        refs = ev.load_set("warmup")
        self.assertEqual(len(refs.references), 20)
        primary = [r for r in refs.references if r.primary]
        self.assertEqual(len(primary), 19)
        # 17 organiser-checked references: radius = their stated distance (under 10 m counts 10); the others 5-12 m
        checked = [r for r in primary if r.tags["organiser_checked"]]
        self.assertEqual(len(checked), 17)
        self.assertTrue(all(10 <= r.error_radius_m <= 30 for r in checked))
        self.assertTrue(all(5 <= r.error_radius_m <= 12 for r in primary if r not in checked))
        self.assertEqual(sorted(r.category for r in primary if r.category_source == "official"),
                         ["non-urban", "urban", "urban"])
        self.assertEqual(refs.meta["organiser_checked"], 17)
        self.assertFalse(refs.meta["is_ground_truth"])

    def test_changed_file_is_refused(self):
        data = self.dir / "Data"
        data.mkdir()
        for name in ev.WARMUP_SHA256:
            shutil.copy(REPO / "Data" / name, data / name)
        ev.load_warmup(self.dir)  # an identical copy passes
        with open(data / "warmup_locations.json", "a", encoding="utf-8") as f:
            f.write(" ")
        with self.assertRaises(ev.ReferenceChanged):
            ev.load_warmup(self.dir)


class WarmupGuardTest(unittest.TestCase):
    def test_only_the_evaluator_names_the_warmup_file(self):
        offenders = []
        for folder in ("panoloc", "tools"):
            for path in sorted((REPO / folder).rglob("*")):
                rel = path.relative_to(REPO).as_posix()
                if not path.is_file() or "__pycache__" in path.parts or rel in WARMUP_READERS:
                    continue
                if b"warmup_locations" in path.read_bytes():
                    offenders.append(rel)
        self.assertEqual(offenders, [], "only the evaluator may read Data/warmup_locations.* (RULES.md, PLAN.md 4.6)")


class AggregationTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.refs = refset([
            ev.Reference("a.jpg", *TRUTH, category="urban", tags={"country": "PT", "landmark_nearby": True}),
            ev.Reference("b.jpg", *TRUTH, category="urban", tags={"country": "PT", "landmark_nearby": False}),
            ev.Reference("c.jpg", *TRUTH, category="non-urban", tags={"country": "ES", "landmark_nearby": False}),
            ev.Reference("d.jpg", *TRUTH, category="non-urban", tags={"country": "ES", "landmark_nearby": True},
                         aliases=["IMG_20250101_120000_00_004.jpg"]),
            ev.Reference("z.jpg", *TRUTH, primary=False, error_radius_m=60_000, tags={"country": "PT"}),
        ])
        path = self.dir / "preds.json"
        path.write_text(json.dumps({
            "a.jpg": [list(TRUTH)] * 10,                                     # exact
            "b.jpg": [list(offset(TRUTH, north_m=150))],                    # 150 m, one entry
            "IMG_20250101_120000_00_004.jpg": [list(offset(TRUTH, east_m=20_000))] * 10,  # via the alias
            "elsewhere.jpg": [[40.0, -8.0]],
        }))
        self.report = ev.evaluate(self.refs, ev.load_predictions([path]), sources=[path])

    def test_primary_metrics_count_missing_as_miss(self):
        p = self.report["primary"]
        self.assertEqual((p["n"], p["n_predicted"], p["n_missing"]), (4, 3, 1))
        self.assertEqual(p["within"]["25"], 0.25)
        self.assertEqual(p["within"]["1000"], 0.5)
        self.assertEqual(p["within"]["100000"], 0.75)
        self.assertAlmostEqual(p["distance_m"]["median"], 150, delta=1)
        self.assertEqual(self.report["predictions"]["unmatched"], ["elsewhere.jpg"])
        missing = next(c for c in self.report["cases"] if c["key"] == "c.jpg")
        self.assertEqual(missing["score_ref"], 0.0)
        exact = max_score()
        total = self.report["primary"]["score"]["urban"]["total"]
        b_score = 1000 * 2 / (1 + 150 / 100)
        d_score = sum(1000 * 0.95 ** i for i in range(10)) * 2 / (1 + 20_000 / 100)
        self.assertAlmostEqual(total, exact + b_score + d_score, delta=1)

    def test_per_tag_groups(self):
        tags = self.report["by_tag"]
        self.assertEqual(set(tags), {"country", "landmark_nearby"})
        self.assertEqual(tags["country"]["PT"]["n"], 2)       # the diagnostic z.jpg stays out
        self.assertEqual(tags["country"]["ES"]["n_missing"], 1)
        self.assertEqual(tags["country"]["PT"]["within"]["1000"], 1.0)
        self.assertEqual(tags["landmark_nearby"]["true"]["n"], 2)
        es_own = tags["country"]["ES"]["score"]["ref_category"]["mean"]
        d_case = next(c for c in self.report["cases"] if c["key"] == "d.jpg")
        self.assertAlmostEqual(es_own, d_case["score"]["non-urban"]["nominal"] / 2, places=1)
        self.assertEqual(len(self.report["diagnostic"]), 1)

    def test_targets_and_table(self):
        t = self.report["targets_plan_4_8"]["urban_camera_accuracy"]
        self.assertEqual((t["urban_references"], t["hits"], t["required"]), (2, 1, 1))
        self.assertTrue(t["pass"])
        table = ev.format_table(self.report)
        self.assertIn("primary: n=4 (missing 1)", table)
        self.assertIn("country=ES", table)


class RunnerTest(TempDirTest):
    def setUp(self):
        super().setUp()
        refs = []
        for i, north in enumerate((0, 400)):
            image = self.dir / f"pano{i}.jpg"
            image.write_bytes(b"")  # the dummies never open it
            refs.append(ev.Reference(image.name, *offset(TRUTH, north_m=north), path=str(image), category="urban",
                                     tags={"country": "PT"}))
        self.refs = refset(refs, name=str(self.dir / "set.json"))
        (self.dir / "set.json").write_text(json.dumps({"set": "dummy", "references": [r.__dict__ for r in refs]}))

    def test_fixed_coordinate_predictor(self):
        predict = ev.load_predictor("tests.test_evaluate:fixed_predict")
        preds = ev.run_predictor(self.refs, predict, self.dir / "runs")
        report = ev.evaluate(self.refs, preds)
        d = [c["distance_m"] for c in report["cases"]]
        self.assertLess(d[0], 1)
        self.assertAlmostEqual(d[1], 400, delta=1)
        self.assertAlmostEqual(report["cases"][0]["score_ref"], max_score(), places=1)
        folders = sorted(p.name for p in (self.dir / "runs").iterdir())
        self.assertEqual(folders, ["001-pano0", "002-pano1"])  # one fresh folder per panorama

    def test_run_folder_predictor_and_failures(self):
        preds = ev.run_predictor(self.refs, run_predict, self.dir / "runs", limit=1)
        self.assertEqual(list(preds), ["pano0.jpg"])
        self.assertEqual(preds["pano0.jpg"].method, "coarse_candidate")
        self.assertAlmostEqual(haversine_m(preds["pano0.jpg"].coordinates[0], TRUTH), 50, delta=1)
        failed = ev.run_predictor(self.refs, failing_predict, self.dir / "runs-failing")
        report = ev.evaluate(self.refs, failed)
        self.assertEqual(report["primary"]["n_missing"], 2)
        self.assertIn("model fell over", report["cases"][0]["error"])

    def test_cli_run(self):
        cli = load_tool("evaluate")
        out = self.dir / "report.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["run", "--set", str(self.dir / "set.json"), "--predict", "tests.test_evaluate:fixed_predict",
                      "--runs-dir", str(self.dir / "eval"), "--out", str(out)])
        report = json.loads(out.read_text())
        self.assertEqual(report["primary"]["n_predicted"], 2)
        self.assertIn("primary: n=2 (missing 0)", stdout.getvalue())

    def test_final_set_use_is_logged(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(ev.record_final_use("first", root=self.dir, n=92), 1)
            self.assertEqual(ev.record_final_use("second", root=self.dir, n=92), 2)
        self.assertIn("ONE run", err.getvalue())
        lines = (self.dir / "Data" / "splits" / "final_runs.log").read_text().splitlines()
        self.assertEqual([json.loads(x)["command"] for x in lines], ["first", "second"])


class BuildSplitsHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bs = load_tool("build_splits")

    def test_smod_rule(self):
        self.assertEqual(self.bs.smod_category(30), ("urban", "urban_centre"))
        self.assertEqual(self.bs.smod_category(21), ("urban", "suburban"))
        self.assertEqual(self.bs.smod_category(13), ("non-urban", "rural_cluster"))
        self.assertEqual(self.bs.smod_category(-200), (None, None))

    def test_nearby_items_and_road_distance(self):
        import numpy as np
        lats = np.array([TRUTH[0], offset(TRUTH, north_m=100)[0], offset(TRUTH, north_m=400)[0]])
        lngs = np.full(3, TRUTH[1])
        idx, dist = self.bs.nearest_items(*TRUTH, lats, lngs, 150)
        self.assertEqual(list(idx), [0, 1])
        self.assertAlmostEqual(dist[1], 100, delta=1)
        road = [offset(TRUTH, north_m=40, east_m=-200), offset(TRUTH, north_m=40, east_m=200)]
        self.assertAlmostEqual(self.bs.point_to_polyline_m(*TRUTH, road), 40, delta=0.5)


if __name__ == "__main__":
    unittest.main()
