"""Tests for the scoring in tools/compare_vlm.py (T47): no model, no GPU, no image.

Run from the repo root: .venv/bin/python -m unittest tests.test_compare_vlm
"""
import importlib.util
import unittest
from pathlib import Path

from panoloc import vlm

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("tool_compare_vlm", REPO / "tools" / "compare_vlm.py")
cv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cv)

NV = vlm.NOT_VISIBLE


def answers(**seen):
    """A full answer dict: every key not_visible except the ones given."""
    return {key: seen.get(key, NV) for key in vlm.KEYS}


def chat(prompt_tokens=4000, prompt_s=2.0, output_tokens=180, output_s=4.0, load_s=0.0):
    """One captured /api/chat response, durations in nanoseconds as Ollama sends them."""
    return {"load_duration": int(load_s * 1e9), "prompt_eval_count": prompt_tokens,
            "prompt_eval_duration": int(prompt_s * 1e9), "eval_count": output_tokens,
            "eval_duration": int(output_s * 1e9), "done_reason": "stop"}


class CompareAnswerTest(unittest.TestCase):
    def test_outcomes(self):
        self.assertEqual(cv.compare_answer("portuguese", "portuguese"), "match")
        self.assertEqual(cv.compare_answer(NV, NV), "match")
        self.assertEqual(cv.compare_answer("red", NV), "false_visible")
        self.assertEqual(cv.compare_answer("other", NV), "false_visible")
        self.assertEqual(cv.compare_answer(NV, "red"), "false_invisible")
        self.assertEqual(cv.compare_answer("blue_correio_azul", "red"), "wrong_value")
        self.assertEqual(cv.compare_answer(vlm.INVALID, NV), "invalid")
        self.assertEqual(cv.compare_answer(None, "red"), "invalid")

    def test_unsure_or_missing_label_is_not_scored(self):
        self.assertIsNone(cv.compare_answer("red", cv.UNSURE))
        self.assertIsNone(cv.compare_answer("red", None))

    def test_a_list_label_accepts_any_of_its_values(self):
        label = ["maritime_pine", "flat_pine_monoculture"]
        self.assertEqual(cv.compare_answer("flat_pine_monoculture", label), "match")
        self.assertEqual(cv.compare_answer("eucalyptus", label), "wrong_value")
        self.assertEqual(cv.compare_answer(NV, label), "false_invisible")

    def test_check_labels_rejects_typos_and_bad_lists(self):
        cv.check_labels({"crops": {"a": {"post_box": "red", "roof": cv.UNSURE, "_note": "anything"}}})
        for bad in ({"post_box": "reed"}, {"postbox": "red"}, {"vegetation": ["eucalyptus", NV]},
                    {"vegetation": []}):
            with self.assertRaises(ValueError, msg=bad):
                cv.check_labels({"crops": {"a": bad}})


class AgreementTest(unittest.TestCase):
    def setUp(self):
        self.labels = {"a": answers(sign_language="portuguese", pavement="grey_setts", utility_pole=cv.UNSURE),
                       "b": answers(vegetation=["maritime_pine", "flat_pine_monoculture"])}

    def test_groups_visible_agreement_and_error_kinds(self):
        found = cv.outcomes({"a": answers(sign_language="portuguese", pavement="asphalt", bollard="flat_post_wide_reflector"),
                             "b": answers()}, self.labels)
        self.assertNotIn(("a", "utility_pole"), found)  # unsure
        s = cv.summarise(found, self.labels, vlm.KEYS)
        self.assertEqual(s["n"], 2 * len(vlm.KEYS) - 1)
        self.assertEqual((s["visible_n"], s["visible_match"]), (3, 1))
        self.assertEqual((s["false_visible"], s["false_invisible"], s["wrong_value"]), (1, 1, 1))
        self.assertEqual(s["match"], s["n"] - 3)
        small = cv.summarise(found, self.labels, cv.SMALL_KEYS)
        self.assertEqual((small["false_visible"], small["not_visible_n"]), (1, 2 * len(cv.SMALL_KEYS) - 1))
        large = cv.summarise(found, self.labels, cv.LARGE_KEYS)
        self.assertEqual((large["visible_n"], large["visible_agreement"]), (2, 0.5))

    def test_a_failed_crop_is_invalid_on_every_scored_key(self):
        found = cv.outcomes({"a": answers()}, self.labels)
        self.assertTrue(all(o == "invalid" for (crop, _), o in found.items() if crop == "b"))

    def test_not_visible_rate_and_sign_test(self):
        self.assertEqual(cv.not_visible_rate({"a": answers(post_box="red")}), round(23 / 24, 3))
        self.assertEqual(cv.sign_test(0, 0), 1.0)
        self.assertEqual(cv.sign_test(3, 3), 1.0)
        self.assertEqual(cv.sign_test(5, 0), 0.0625)
        self.assertEqual(cv.sign_test(0, 5), 0.0625)
        p = cv.paired({("a", "roof"): "match", ("a", "flag"): "match", ("b", "roof"): "invalid"},
                      {("a", "roof"): "false_visible", ("a", "flag"): "match", ("b", "roof"): "match"})
        self.assertEqual((p["n"], p["a_only_right"], p["b_only_right"]), (3, 1, 1))


class CountryTest(unittest.TestCase):
    def test_strength_weighted_call(self):
        hints, scores = cv.country_scores(answers(sign_language="portuguese", post_box="yellow_logo_unclear"))
        self.assertEqual(cv.country_call(scores), "PT")  # strong PT (4) over medium ES/FR (1 each)
        self.assertEqual(len(hints), 2)

    def test_no_hint_tie_and_invalid_values_make_no_call(self):
        self.assertIsNone(cv.country_call(cv.country_scores(answers())[1]))
        self.assertIsNone(cv.country_call(cv.country_scores(answers(sign_language="portuguese",
                                                                    post_box="yellow_crown_horn_logo"))[1]))
        self.assertIsNone(cv.country_call(cv.country_scores(answers(sign_language="klingon", roof=vlm.INVALID))[1]))

    def test_scored_against_gps_with_hint_precision(self):
        result = cv.score_countries({"a": answers(sign_language="spanish"), "b": answers(flag="france"),
                                     "c": answers()}, {"a": "ES", "b": "ES", "c": "PT"})
        self.assertEqual((result["calls"], result["correct"], result["accuracy_of_calls"]), (2, 1, 0.5))
        self.assertEqual((result["hints"], result["hints_right"], result["strong_hints"]), (2, 1, 1))
        self.assertEqual(result["per_crop"]["b"]["call"], "FR")


class TranscriptionTest(unittest.TestCase):
    def test_line_found_keeps_case_accents_and_word_edges(self):
        text = "IDIOMES SUPERNOVA / Anglès Francès\nensenyament  de qualitat / SORTIE D’ENGINS"
        self.assertTrue(cv.line_found("ensenyament de qualitat", text))
        self.assertTrue(cv.line_found("SORTIE D'ENGINS", text))  # curly apostrophe
        self.assertFalse(cv.line_found("Angles", text))
        self.assertFalse(cv.line_found("anglès", text))
        self.assertTrue(cv.line_found("anglès", text, fold=True))
        self.assertFalse(cv.line_found("IDIOME", text))  # inside a longer word
        self.assertFalse(cv.line_found("SUPERNOVA Anglès", "SUPERNOVA, Anglès"))

    def test_substring_distance(self):
        self.assertEqual(cv.substring_distance("VILANOVA", "CAPRICCIO DI VILANOVA"), 0)
        self.assertEqual(cv.substring_distance("CAPRICCIO DI VILANOVA", "x CAPRICCIO DE VILANOVA y"), 1)
        self.assertEqual(cv.substring_distance("ABC", ""), 3)
        self.assertEqual(cv.edit_distance("kitten", "sitting"), 3)

    def test_score_transcriptions(self):
        labels = {"s1": ["VENDE", "VANDA CARDOSO", "916 924 921"], "s2": "SINGER", "s3": cv.UNSURE,
                  "_note": "ignored"}
        outputs = {"s1": {"text": "VENDE / Vanda Cardoso / 916 924 921", "legible": "yes"},
                   "s2": {"error": {"type": "VLMTimeout"}}}
        r = cv.score_transcriptions(outputs, labels)
        self.assertEqual((r["signs"], r["lines"], r["lines_exact"], r["lines_exact_ci"]), (2, 4, 2, 3))
        self.assertEqual((r["digit_lines"], r["digit_lines_exact"], r["signs_all_lines_exact"]), (1, 1, 0))
        self.assertEqual(r["per_sign"]["s2"]["lines"][0]["cer"], 1.0)


class LandmarkTest(unittest.TestCase):
    def test_named_right_and_named_without_a_place(self):
        labels = {"a": {"_landmarks": {"Ponte Luis I": ["luis"], "Mosteiro da Serra do Pilar": ["pilar"]}},
                  "b": {"_landmarks": {"Palacio da Pena": ["pena"]}}, "c": {}, "d": {}}
        outputs = {"a": {"landmarks": [{"name": "Ponte Dom Luís I"}]}, "b": {"landmarks": [{"name": "Penafiel"}]},
                   "c": {"landmarks": [{"name": "Torre de Belém"}]}, "d": {"error": {"type": "VLMTimeout"}}}
        r = cv.score_landmarks(outputs, labels)
        self.assertEqual((r["crops_with_place"], r["named_right"]), (2, 1))  # "penafiel" is not "pena"
        self.assertEqual((r["crops_without_place"], r["named_without_place"]), (2, 1))
        self.assertEqual(r["per_crop"]["a"]["hits"], ["Ponte Luis I"])


class TimingAndCheckTest(unittest.TestCase):
    def test_timing_summary_excludes_loads_and_failed_crops(self):
        doc = {"load_s": 30.0, "crops": {
            "a": {"latency_s": 6.5, "ollama": [chat()]},
            "b": {"latency_s": 26.5, "ollama": [chat(load_s=20.0)]},  # a mid-pass reload
            "c": {"error": {"type": "VLMTimeout"}, "ollama": []}},
            "signs": {"s": {"ollama": [chat(prompt_tokens=800, prompt_s=0.5, output_tokens=20, output_s=0.5)]}}}
        t = cv.timing_summary(doc)
        self.assertEqual((t["crops"], t["compute_s_mean"], t["ten_crops_compute_s"]), (2, 6.0, 60.0))
        self.assertEqual((t["wall_s_mean"], t["ten_crops_wall_s"], t["mid_pass_load_s_max"]), (6.5, 65.0, 20.0))
        self.assertEqual((t["output_tok_s"], t["prompt_tok_s"], t["sign_compute_s_mean"]), (45.0, 2000.0, 1.0))

    def test_gpu_summary_takes_the_peaks_of_the_model_runner(self):
        samples = [{"smi": {"used_mib": 9000, "util_pct": 90.0, "procs": [{"pid": 7, "name": "llama-server", "mib": 6000},
                                                                           {"pid": 9, "name": "python", "mib": 2400}]},
                    "ps": [{"name": "m", "size_vram": 5_800_000_000}], "runner_pids": [7]},
                   {"smi": {"used_mib": 9500, "util_pct": 100.0, "procs": [{"pid": 7, "name": "llama-server", "mib": 6500}]},
                    "ps": [{"name": "m", "size_vram": 5_900_000_000}, {"name": "other", "size_vram": 9e9}],
                    "runner_pids": [7]}]
        g = cv.gpu_summary(samples, "m")
        self.assertEqual((g["size_vram_gb"], g["runner_mib"], g["gpu_used_mib_peak"]), (5.9, 6500, 9500))
        self.assertEqual((g["other_mib_peak"], g["other_share"]), (2400, 0.5))
        self.assertEqual(g["other_processes"], [{"pid": 9, "name": "python", "cmd": None, "mib_peak": 2400, "share": 0.5}])
        # what Ollama can evict (its runners) counts as free; the python process stays
        self.assertEqual(cv.free_after_evict({"smi": {**samples[0]["smi"], "total_mib": 16303}}), 16303 - 9000 + 6000)
        self.assertIsNone(cv.free_after_evict({"smi": {"error": "nvidia-smi missing"}}))

    def test_check2(self):
        def summary(model, agreement, exact, gb, ten):
            return {"model": model, "groups": {"all": {"agreement": agreement}}, "transcription": {"exact_rate": exact},
                    "vram": {"size_vram_gb": gb, "runner_gb": gb + 1}, "timing": {"ten_crops_compute_s": ten,
                                                                                 "ten_crops_wall_s": ten + 5}}
        keep = cv.check2(summary("q", 0.9, 0.8, 5.8, 55.0), summary("g", 0.85, 0.8, 8.0, 70.0))
        self.assertEqual((keep["rule_literal"], keep["resident_gb"]), ("keep", 6.8))
        self.assertEqual(cv.check2(summary("q", 0.9, 0.8, 5.8, 61.0), summary("g", 0.8, 0.7, 8.0, 70.0))["rule_literal"],
                         "switch")
        self.assertEqual(cv.check2(summary("q", 0.9, 0.6, 5.8, 50.0), summary("g", 0.8, 0.7, 8.0, 70.0))["rule_literal"],
                         "mixed accuracy: team call")


if __name__ == "__main__":
    unittest.main()
