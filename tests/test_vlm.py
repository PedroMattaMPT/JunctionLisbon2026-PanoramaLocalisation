"""Tests for panoloc.vlm. Run from the repo root: .venv/bin/python -m unittest discover -s tests

Everything but LiveOllamaTest uses a fake transport. LiveOllamaTest sends three short requests to the
local Ollama and is skipped when it is unreachable, lacks the model, or PANOLOC_SKIP_LIVE=1.
"""
import io
import json
import os
import re
import tempfile
import unittest
import urllib.error
from dataclasses import dataclass

from panoloc import vlm
from panoloc.runlog import Run

PANORAMA = "IMG_20260115_143012_00_204.jpg"  # invented, not a warm-up file
FORBIDDEN_FIELD = re.compile(r"(^|_)(lat|lng|lon|latitude|longitude|coord\w*|gps|postcode|zip|phone|digits?|number|"
                             r"code|address|plate_text)(_|$)", re.I)


@dataclass
class FakeView:
    name: str
    image: bytes = b"\xff\xd8 not really a jpeg"  # encode_image passes bytes through untouched
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    fov_deg: float = 90.0
    masked_fraction: float = 0.0


def reply(**answers):
    """A full checklist reply: not_visible everywhere unless given."""
    landmarks = answers.pop("landmarks", [])
    return {**{k: vlm.NOT_VISIBLE for k in vlm.KEYS}, **answers, "landmarks": landmarks}


class FakeTransport:
    """Plays back canned Ollama responses (dicts) or raises canned exceptions, in order."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, method, url, payload, timeout):
        self.calls.append({"method": method, "url": url, "payload": payload, "timeout": timeout})
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome(payload)
        return outcome


def chat(content, **extra):
    body = content if isinstance(content, str) else json.dumps(content)
    return {"message": {"role": "assistant", "content": body}, "done": True, "done_reason": "stop",
            "load_duration": 1_000_000, "prompt_eval_count": 1200, "prompt_eval_duration": 400_000_000,
            "eval_count": 160, "eval_duration": 3_500_000_000, **extra}


def by_request(answers_for):
    """A transport outcome that answers each request with the keys its schema asks for."""
    def respond(payload):
        if payload is None or "format" not in payload:
            return {"done": True}  # load, unload
        keys = [k for k in payload["format"]["properties"] if k != "landmarks"]
        obj = {k: answers_for.get(k, vlm.NOT_VISIBLE) for k in keys}
        if "landmarks" in payload["format"]["properties"]:
            obj["landmarks"] = answers_for.get("landmarks", [])
        return chat(obj)
    return respond


def client_with(transport, **kwargs):
    return vlm.OllamaClient(transport=transport, retry_delay_s=0, **kwargs)


def http_error(code, body):
    return urllib.error.HTTPError("http://localhost:11434/api/chat", code, "error", {}, io.BytesIO(body.encode()))


def view_result(view, **answers):
    keys = vlm.GROUND_KEYS if view == "ground" else vlm.KEYS
    landmarks = answers.pop("landmarks", [])
    return vlm.ViewResult(view, 0.0, 0.0, 90.0, 0.0, {k: answers.get(k, vlm.NOT_VISIBLE) for k in keys},
                          landmarks=landmarks)


class SchemaTest(unittest.TestCase):
    def test_the_checklist_has_the_24_keys_of_country_clues_7(self):
        self.assertEqual(len(vlm.KEYS), 24)
        self.assertEqual([len(vlm.GROUP_KEYS[g]) for g in vlm.GROUPS], [11, 10, 3])
        self.assertEqual(vlm.KEYS[:3], ("sign_language", "plate_layout", "post_box"))
        self.assertEqual(vlm.KEYS[-3:], ("vegetation", "terrain", "soil"))

    def test_every_key_takes_not_visible_and_other(self):
        schema = vlm.checklist_schema()
        for key in vlm.KEYS:
            enum = schema["properties"][key]["enum"]
            self.assertIn(vlm.NOT_VISIBLE, enum, key)
            self.assertIn(vlm.OTHER, enum, key)
            self.assertEqual(len(enum), len(set(enum)), key)
            self.assertNotIn(vlm.INVALID, enum, key)  # only code ever writes "invalid"
        self.assertEqual(schema["required"], [*vlm.KEYS, "landmarks"])
        self.assertEqual(list(schema["properties"])[-1], "landmarks")  # asked after the checklist

    def test_no_field_asks_for_coordinates_or_digits(self):
        def walk(node, path):
            if isinstance(node, dict):
                if node.get("type") == "string":
                    # every free-text field is the landmark name; everything else is a closed enum
                    self.assertTrue("enum" in node or path[-1] == "name", path)
                for name, child in node.get("properties", {}).items():
                    self.assertIsNone(FORBIDDEN_FIELD.search(name), name)
                    walk(child, path + [name])
                if "items" in node:
                    walk(node["items"], path + ["items"])
                self.assertNotIn(node.get("type"), ("number", "integer"), path)
        for plan in vlm.PLANS.values():
            for requests in plan.values():
                for r in requests:
                    walk(vlm.checklist_schema(r.keys, r.landmarks), [r.name])

    def test_implications_use_only_the_three_countries_and_known_strengths(self):
        for item in vlm.CHECKLIST:
            self.assertEqual(len(item.values), len(set(item.values)), item.key)
            for o in item.options:
                self.assertNotIn(o.value, (*vlm.SPECIAL, vlm.INVALID), item.key)
                self.assertTrue(set(o.countries) <= {"PT", "ES", "FR"}, (item.key, o.value))
                implies = bool(o.countries or o.regions)
                self.assertEqual(o.strength in vlm.STRENGTHS, implies, (item.key, o.value))
                if not implies:
                    self.assertIsNone(o.strength, (item.key, o.value))
        self.assertEqual({i.key for i in vlm.CHECKLIST if i.hard}, {"red_sign_rim", "pedestrian_sign"})

    def test_the_prompt_lists_every_key_but_never_says_where_an_option_points(self):
        prompt = vlm.system_prompt()
        for key in vlm.KEYS:
            self.assertIn(f"- {key}: ", prompt)
        country_words = re.compile(r"portug|spain|spanish|france|french|iberia", re.I)
        for item in vlm.CHECKLIST:
            if item.key == "sign_language":
                continue  # the options are languages by definition
            for o in item.options:
                self.assertIsNone(country_words.search(o.looks), (item.key, o.value, o.looks))
        self.assertIn("not_visible", prompt)
        self.assertIn("photographer", vlm.GROUND_TEXT)

    def test_plans_ask_every_key_in_the_horizontal_views(self):
        for name, plan in vlm.PLANS.items():
            asked = [k for r in plan["horizontal"] for k in r.keys]
            self.assertEqual(sorted(asked), sorted(vlm.KEYS), name)
            self.assertEqual(sum(r.landmarks for r in plan["horizontal"]), 1, name)
            self.assertEqual([k for r in plan["ground"] for k in r.keys], list(vlm.GROUND_KEYS))
        with self.assertRaises(ValueError):
            vlm.checklist_schema(["post_box", "latitude"])


class ValidationTest(unittest.TestCase):
    def test_a_clean_reply_passes_unchanged(self):
        obj = reply(post_box="red", pavement="white_limestone_cubes",
                    landmarks=[{"name": "Torre de Belém", "kind": "monument", "confidence": "high"}])
        r = vlm.validate_reply(obj, vlm.KEYS, True)
        self.assertEqual(r["invalid"], {})
        self.assertEqual(r["answers"]["post_box"], "red")
        self.assertEqual(r["landmarks"], [{"name": "Torre de Belém", "kind": "monument", "confidence": "high"}])

    def test_bad_values_become_invalid_never_a_real_answer(self):
        obj = reply(post_box="red box", flag="portugal", pavement=7, chevron=None)
        del obj["soil"]
        obj["latitude"] = 38.7
        r = vlm.validate_reply(obj, vlm.KEYS, True)
        for key in ("post_box", "pavement", "chevron", "soil"):
            self.assertEqual(r["answers"][key], vlm.INVALID, key)
        self.assertEqual(r["invalid"]["soil"], "<missing>")
        self.assertEqual(r["invalid"]["post_box"], "red box")
        self.assertEqual(r["answers"]["flag"], "portugal")
        self.assertEqual(r["extra_keys"], ["latitude"])

    def test_only_case_and_spacing_are_forgiven(self):
        self.assertEqual(vlm.coerce_answer("post_box", "Not Visible"), vlm.NOT_VISIBLE)
        self.assertEqual(vlm.coerce_answer("post_box", " RED "), "red")
        self.assertEqual(vlm.coerce_answer("direction_sign", "yellow_d_plate"), "yellow_D_plate")
        self.assertEqual(vlm.coerce_answer("pavement", "white-limestone cubes"), "white_limestone_cubes")
        self.assertIsNone(vlm.coerce_answer("post_box", "yellow"))  # ambiguous between options: not guessed
        self.assertIsNone(vlm.coerce_answer("post_box", "invalid"))
        self.assertIsNone(vlm.coerce_answer("post_box", ["red"]))

    def test_landmarks_without_codes_numbers_or_generic_names(self):
        kept, rejected = vlm.validate_landmarks([
            {"name": "Ponte 25 de Abril", "kind": "bridge", "confidence": "medium"},
            {"name": "Rua Augusta 123", "kind": "street", "confidence": "high"},
            {"name": "38.7, -9.14", "kind": "other", "confidence": "high"},
            {"name": "church", "kind": "church", "confidence": "low"},
            {"name": "Sé de Lisboa", "kind": "cathedral", "confidence": "certain"},
            {"name": "se de lisboa", "kind": "church", "confidence": "high"},
            {"kind": "town"},
            "Óbidos",
        ])
        self.assertEqual([k["name"] for k in kept], ["Ponte 25 de Abril", "Sé de Lisboa"])
        self.assertTrue(kept[0]["digits_unverified"])
        self.assertEqual((kept[1]["kind"], kept[1]["confidence"], kept[1]["coerced"]),
                         ("other", "low", ["kind", "confidence"]))
        self.assertEqual(len(rejected), 5)
        self.assertEqual(vlm.validate_landmarks("Óbidos")[1][0]["reason"], "not a list")

    def test_parse_json_tolerates_fences_and_rejects_non_objects(self):
        self.assertEqual(vlm.parse_json('```json\n{"post_box": "red"}\n```'), {"post_box": "red"})
        self.assertIsNone(vlm.parse_json("[1, 2]"))
        self.assertIsNone(vlm.parse_json('{"post_box": "re'))
        self.assertIsNone(vlm.parse_json(""))


class ClientTest(unittest.TestCase):
    def test_every_request_sends_the_decided_settings(self):
        transport = FakeTransport(chat(reply()))
        client = client_with(transport)
        content, timing = client.chat("system", "text", vlm.checklist_schema(), images=["aW1n"])
        p = transport.calls[0]["payload"]
        self.assertEqual(transport.calls[0]["url"], "http://localhost:11434/api/chat")
        self.assertIs(p["think"], False)
        self.assertEqual(p["keep_alive"], -1)
        self.assertIs(p["stream"], False)
        self.assertEqual(p["model"], "qwen3.5:9b")
        self.assertEqual(p["format"], vlm.checklist_schema())
        self.assertEqual(p["messages"][1]["images"], ["aW1n"])
        o = p["options"]
        self.assertEqual((o["temperature"], o["seed"], o["presence_penalty"], o["num_ctx"]),
                         (0, 0, 0, vlm.DEFAULT_NUM_CTX))
        self.assertEqual(timing["output_tokens"], 160)
        self.assertEqual(timing["prompt_s"], 0.4)
        self.assertEqual(json.loads(content)["post_box"], vlm.NOT_VISIBLE)

    def test_one_retry_then_success(self):
        transport = FakeTransport(urllib.error.URLError(ConnectionRefusedError()), chat(reply()))
        _, timing = client_with(transport).chat("s", "t", {})
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(timing["http_attempts"], 2)

    def test_ollama_down_raises_unavailable_after_one_retry(self):
        transport = FakeTransport(urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")))
        with self.assertRaises(vlm.VLMUnavailable) as ctx:
            client_with(transport).chat("s", "t", {})
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(len(ctx.exception.attempts), 2)
        self.assertIn("unreachable", str(ctx.exception))

    def test_timeouts_raise_vlm_timeout(self):
        for exc in (TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))):
            transport = FakeTransport(exc)
            with self.assertRaises(vlm.VLMTimeout):
                client_with(transport, timeout_s=5).chat("s", "t", {})
            self.assertEqual(len(transport.calls), 2)
            self.assertEqual(transport.calls[0]["timeout"], 5)

    def test_a_missing_model_is_not_retried(self):
        transport = FakeTransport(http_error(404, '{"error":"model \\"qwen3.5:9b\\" not found"}'))
        with self.assertRaises(vlm.VLMUnavailable):
            client_with(transport).chat("s", "t", {})
        self.assertEqual(len(transport.calls), 1)

    def test_a_server_error_is_retried(self):
        transport = FakeTransport(http_error(500, "boom"), chat(reply()))
        client_with(transport).chat("s", "t", {})
        self.assertEqual(len(transport.calls), 2)

    def test_a_model_without_thinking_is_asked_again_without_think(self):
        for retries in (1, 0):  # the re-ask is not a retry
            transport = FakeTransport(http_error(400, '{"error":"model does not support thinking"}'), chat(reply()))
            client = client_with(transport, model="gemma4:12b", retries=retries)
            client.chat("s", "t", {})
            self.assertIn("think", transport.calls[0]["payload"])
            self.assertNotIn("think", transport.calls[1]["payload"])
            client.chat("s", "t", {})  # remembered: no third 400
            self.assertNotIn("think", transport.calls[2]["payload"])
            self.assertIsNone(client.think)

    def test_load_and_unload(self):
        transport = FakeTransport({"done": True, "done_reason": "load"})
        client = client_with(transport)
        self.assertGreaterEqual(client.load(), 0)
        client.unload()
        load, unload = (c["payload"] for c in transport.calls)
        self.assertEqual((load["keep_alive"], load["options"]["num_ctx"]), (-1, vlm.DEFAULT_NUM_CTX))
        self.assertEqual(unload["keep_alive"], 0)
        self.assertTrue(all(c["url"].endswith("/api/generate") for c in transport.calls))


class DescribeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def test_invalid_json_is_retried_once_then_raises(self):
        transport = FakeTransport(chat("{not json"))
        with self.assertRaises(vlm.VLMInvalidResponse) as ctx:
            vlm.describe_view(client_with(transport), FakeView("h000"))
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(ctx.exception.view, "h000")

    def test_a_truncated_reply_counts_as_invalid(self):
        transport = FakeTransport(chat(reply(), done_reason="length"), chat(reply(post_box="red")))
        r = vlm.describe_view(client_with(transport), FakeView("h000"))
        self.assertEqual(r.answers["post_box"], "red")
        self.assertEqual(r.requests[0]["attempts"], 2)

    def test_an_invalid_value_is_retried_and_the_better_reply_kept(self):
        transport = FakeTransport(chat(reply(post_box="purple")), chat(reply(post_box="red")))
        r = vlm.describe_view(client_with(transport), FakeView("h045"))
        self.assertEqual((r.answers["post_box"], r.invalid), ("red", {}))
        transport = FakeTransport(chat(reply(post_box="purple")))
        r = vlm.describe_view(client_with(transport), FakeView("h045"))
        self.assertEqual((r.answers["post_box"], r.invalid["post_box"]), (vlm.INVALID, "purple"))

    def test_ground_views_get_the_ground_items_and_the_photographer_note(self):
        transport = FakeTransport(by_request({"pavement": "black_white_mosaic"}))
        r = vlm.describe_view(client_with(transport), FakeView("ground", pitch_deg=-90.0, masked_fraction=0.29))
        payload = transport.calls[0]["payload"]
        self.assertEqual(list(payload["format"]["properties"]), list(vlm.GROUND_KEYS))
        self.assertIn("photographer", payload["messages"][1]["content"])
        self.assertEqual(r.answers, {"pavement": "black_white_mosaic"})
        self.assertEqual(r.masked_fraction, 0.29)

    def test_the_split_plan_merges_its_two_requests(self):
        transport = FakeTransport(by_request({"post_box": "red", "chevron": "black_yellow"}))
        r = vlm.describe_view(client_with(transport), FakeView("h090"), plan="split")
        self.assertEqual([t["request"] for t in r.requests], ["scene", "road"])
        self.assertEqual(sorted(r.answers), sorted(vlm.KEYS))
        self.assertEqual(r.seen, {"post_box": "red", "chevron": "black_yellow"})

    def test_a_panorama_is_logged_into_the_run(self):
        answers = {"post_box": "red", "pavement": "white_limestone_cubes",
                   "landmarks": [{"name": "Torre de Belém", "kind": "monument", "confidence": "medium"}]}
        transport = FakeTransport(by_request(answers))
        views = [FakeView(n, yaw_deg=i * 45.0) for i, n in enumerate(vlm.HORIZONTAL_VIEWS)]
        views += [FakeView("sky", pitch_deg=90.0), FakeView("ground", pitch_deg=-90.0)]
        run = Run(PANORAMA, self.dir)
        with run.stage("describe", optional=True, model="qwen3.5:9b"):
            result = vlm.describe_panorama(views, client_with(transport), run=run)
        self.assertEqual([r.view for r in result.views], list(vlm.DEFAULT_VIEWS))  # sky is left out
        kinds = [e["payload"]["kind"] for e in run.events if e["type"] == "evidence.added"]
        self.assertEqual(kinds, ["vlm_checklist"] * 9 + ["vlm_summary", "landmark_hypothesis"])
        ev = [e for e in run.events if e["type"] == "evidence.added"]
        self.assertTrue(all(e["stage"] == "describe" and e["model"] == "qwen3.5:9b" for e in ev))
        self.assertEqual(ev[0]["payload"]["box"], {"yaw": 0.0, "pitch": 0.0, "w": 90.0, "h": 90.0})
        summary, landmark = ev[-2]["payload"], ev[-1]["payload"]
        self.assertEqual(summary["aggregate"]["post_box"]["support"], 8)
        self.assertEqual(summary["aggregate"]["pavement"]["support"], 9)  # ground too
        self.assertEqual((landmark["name"], landmark["place_kind"]), ("Torre de Belém", "monument"))
        self.assertEqual(len(landmark["source_evidence"]), 8)
        self.assertTrue(landmark["unverified"])
        self.assertNotIn("lat", landmark)
        self.assertEqual(run.events[-1]["type"], "stage.finished")
        json.dumps(run.events)  # everything logged is JSON

    def test_ollama_down_fails_the_stage_after_logging_and_the_run_goes_on(self):
        transport = FakeTransport(urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")))
        run = Run(PANORAMA, self.dir)
        with run.stage("describe", optional=True, model="qwen3.5:9b"):
            vlm.describe_panorama([FakeView("h000")], client_with(transport), run=run)
        types = [e["type"] for e in run.events]
        self.assertEqual(types[-2:], ["evidence.added", "stage.failed"])
        self.assertEqual(run.events[-2]["payload"]["kind"], "vlm_error")
        self.assertEqual(run.events[-1]["payload"]["error"], "VLMUnavailable")
        run.output([(38.7, -9.1)] * 10, method="coarse_candidate")  # the run still finishes
        run.finish()

    def test_a_failure_mid_panorama_keeps_the_finished_views(self):
        good = by_request({"post_box": "red"})
        transport = FakeTransport(good, good, TimeoutError("timed out"))  # load, h000, then h045 times out twice
        run = Run(PANORAMA, self.dir)
        with self.assertRaises(vlm.VLMTimeout) as ctx:
            vlm.describe_panorama([FakeView("h000"), FakeView("h045")], client_with(transport), run=run)
        partial = ctx.exception.partial
        self.assertTrue(partial.partial)
        self.assertEqual([r.view for r in partial.views], ["h000"])
        self.assertEqual(partial.aggregate["post_box"]["value"], "red")
        self.assertEqual(ctx.exception.view, "h045")
        kinds = [e["payload"]["kind"] for e in run.events if e["type"] == "evidence.added"]
        self.assertEqual(kinds, ["vlm_checklist", "vlm_summary", "vlm_error"])
        self.assertTrue(run.events[-2]["payload"]["partial"])


class AggregateTest(unittest.TestCase):
    def test_votes_ignore_not_visible_other_and_invalid(self):
        views = [view_result("h000", post_box="red"), view_result("h045", post_box="red"),
                 view_result("h090", post_box="blue_correio_azul"), view_result("h135", post_box=vlm.OTHER),
                 view_result("h180", post_box=vlm.INVALID), view_result("ground")]
        a = vlm.aggregate(views)["post_box"]
        self.assertEqual((a["asked"], a["answered"], a[vlm.NOT_VISIBLE], a[vlm.OTHER], a[vlm.INVALID]), (5, 3, 0, 1, 1))
        self.assertEqual(a["votes"], {"red": 2, "blue_correio_azul": 1})
        self.assertEqual((a["value"], a["support"], a["share"]), ("red", 2, 0.667))
        self.assertEqual(a["views"]["red"], ["h000", "h045"])
        self.assertTrue(a["conflict"])
        self.assertFalse(a["country_conflict"])  # both point to PT
        self.assertNotIn("plate_layout", {k for k, v in vlm.aggregate([view_result("ground")]).items()})

    def test_a_tie_has_no_majority_and_disjoint_countries_conflict(self):
        views = [view_result("h000", post_box="red"), view_result("h045", post_box="yellow_la_poste_logo")]
        a = vlm.aggregate(views)["post_box"]
        self.assertIsNone(a["value"])
        self.assertEqual(a["tied"], ["red", "yellow_la_poste_logo"])
        self.assertTrue(a["country_conflict"])
        unseen = vlm.aggregate([view_result("h000")])["post_box"]
        self.assertEqual((unseen["value"], unseen["answered"], unseen["conflict"]), (None, 0, False))

    def test_hints_come_only_from_positive_observations(self):
        views = [view_result("h000", post_box="red", pavement="asphalt", red_sign_rim="red_to_edge"),
                 view_result("h045", post_box="red", vegetation="eucalyptus", terrain="flat_plain"),
                 view_result("ground", pavement="black_white_mosaic")]
        hs = vlm.hints(vlm.aggregate(views))
        self.assertEqual([(h["key"], h["value"]) for h in hs],
                         [("post_box", "red"), ("red_sign_rim", "red_to_edge"), ("pavement", "black_white_mosaic"),
                          ("vegetation", "eucalyptus")])  # strong first, then by support; asphalt implies nothing
        red = hs[0]
        self.assertEqual((red["countries"], red["strength"], red["views"], red["support"], red["majority"]),
                         (["PT"], "strong", ["h000", "h045"], 2, True))
        self.assertTrue(hs[1]["hard"])
        self.assertIn("absent in FR", hs[3]["note"])
        self.assertEqual(vlm.hints(vlm.aggregate([view_result("h000"), view_result("ground")])), [])
        self.assertTrue(all(h["value"] not in (*vlm.SPECIAL, vlm.INVALID) for h in hs))

    def test_landmarks_merge_by_normalised_name(self):
        views = [view_result("h000", landmarks=[{"name": "Torre de Belém", "kind": "monument", "confidence": "low"}]),
                 view_result("h045", landmarks=[{"name": "TORRE DE BELEM", "kind": "building", "confidence": "high"},
                                                {"name": "Padrão dos Descobrimentos", "kind": "monument",
                                                 "confidence": "medium"}]),
                 view_result("h090", landmarks=[{"name": "Torre de Belém", "kind": "monument",
                                                 "confidence": "medium"}])]
        merged = vlm.merge_landmarks(views)
        self.assertEqual([m["name"] for m in merged], ["Torre de Belém", "Padrão dos Descobrimentos"])
        tower = merged[0]
        self.assertEqual((tower["confidence"], tower["views"], tower["support"], tower["kind"]),
                         ("high", ["h000", "h045", "h090"], 3, "monument"))
        self.assertEqual(tower["names"], ["Torre de Belém", "TORRE DE BELEM"])


class TranscribeTest(unittest.TestCase):
    def test_a_transcription_is_always_unverified(self):
        transport = FakeTransport(chat({"legible": "yes", "text": "RUA DO SOL 25 / 1100-123"}))
        t = vlm.transcribe(b"\xff\xd8 fake", client_with(transport))
        self.assertIs(t["verified"], False)
        self.assertEqual(t["digit_runs"], ["25", "1100", "123"])
        self.assertIn("never accept", t["policy"])
        payload = transport.calls[0]["payload"]
        self.assertEqual(payload["format"], vlm.TRANSCRIBE_SCHEMA)
        self.assertNotIn("checklist", payload["messages"][0]["content"])

    def test_a_bad_transcription_reply_raises(self):
        transport = FakeTransport(chat({"legible": "maybe", "text": "x"}))
        with self.assertRaises(vlm.VLMInvalidResponse):
            vlm.transcribe(b"x", client_with(transport))
        self.assertEqual(len(transport.calls), 2)


class LiveOllamaTest(unittest.TestCase):
    """Three short requests against the local Ollama on synthetic images."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("PANOLOC_SKIP_LIVE") == "1":
            raise unittest.SkipTest("PANOLOC_SKIP_LIVE=1")
        cls.client = vlm.OllamaClient(timeout_s=120, retry_delay_s=0.5)
        try:
            cls.client.version()
            names = {m["name"] for m in vlm._post_json("GET", cls.client.host + "/api/tags", None, 5)["models"]}
            cls.was_loaded = any(m.get("name") == cls.client.model for m in cls.client.loaded())
        except (vlm.VLMError, OSError, ValueError, KeyError) as exc:
            raise unittest.SkipTest(f"Ollama unreachable: {exc}")
        if cls.client.model not in names:
            raise unittest.SkipTest(f"{cls.client.model} is not installed")
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise unittest.SkipTest("needs PIL for the synthetic images")
        scene = Image.new("RGB", (512, 512), (200, 200, 205))
        draw = ImageDraw.Draw(scene)
        draw.rectangle((0, 380, 511, 511), fill=(60, 60, 60))           # a dark road
        draw.rectangle((200, 150, 300, 380), fill=(200, 20, 20))         # a red box
        sign = Image.new("RGB", (600, 200), "white")
        ImageDraw.Draw(sign).text((40, 60), "RUA DO SOL", fill="black", font_size=72)
        cls.images = []
        for im in (scene, sign):
            buffer = io.BytesIO()
            im.save(buffer, format="JPEG")
            cls.images.append(buffer.getvalue())

    @classmethod
    def tearDownClass(cls):
        if not getattr(cls, "was_loaded", True):
            try:
                cls.client.unload()  # leave the GPU as we found it
            except vlm.VLMError:
                pass

    def test_live_checklist_reply_is_valid(self):
        image = vlm.encode_image(self.images[0])
        reply, timing, raws = vlm.ask(self.client, image, vlm.Request("smoke", ("post_box", "pavement", "flag"), True),
                                      vlm.HORIZONTAL_TEXT)
        self.assertEqual(reply["invalid"], {}, raws)
        for key, value in reply["answers"].items():
            self.assertIn(value, vlm.ITEMS[key].allowed)
        self.assertIsInstance(reply["landmarks"], list)
        self.assertEqual(timing["done_reason"], "stop")

    def test_live_transcription_is_unverified(self):
        t = vlm.transcribe(self.images[1], self.client)
        self.assertIs(t["verified"], False)
        self.assertIn(t["legible"], ("yes", "partly", "no"))
        self.assertIsInstance(t["text"], str)


if __name__ == "__main__":
    unittest.main()
