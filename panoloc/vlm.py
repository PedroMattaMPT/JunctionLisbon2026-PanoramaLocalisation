"""VLM checklist per perspective view, landmark hypotheses and soft country hints (PLAN.md 3.1, T15).

A local vision-language model served by Ollama looks at each perspective view of a panorama (the 8
horizontal views plus ground, from panoloc.views) and fills a closed checklist in JSON, plus a short
list of specific places it recognises. Code, not the model, aggregates the answers across views and
turns them into hints with the implication table of COUNTRY_CLUES.md section 7 (built from external
sources only, so it may live here as data).

What the model is never asked for: coordinates, and digits of any kind (plate characters, phone
numbers, postcodes, road numbers and codes are OCR's job, panoloc.ocr). Its answers carry no
probabilities either: every number in the output is computed here.

Checklist (CHECKLIST, COUNTRY_CLUES 7): 24 keys in three groups, scene (any scene), road (road
furniture) and landscape. Every key takes its own options plus "not_visible" and "other", which imply
nothing; code adds "invalid" for an answer outside the schema, so a bad value never becomes a real
answer. Each key is phrased object first ("Is there a street post box? Its colour: ..."), the system
prompt says that not_visible is the normal answer, and an object whose telling detail can't be made
out (plate ends, a pole's pattern, reflectors) counts as not_visible too: without that rule the model
filled in plate bands it couldn't see. The prompt describes options visually and never says which
country an option points to, so the model can't answer from its own guess of the place. A few options
are not in the table: post_box "yellow_logo_unclear" (ES or FR), so a yellow box with an unreadable logo
isn't forced onto one of the two logo options, and neutral look-alikes that imply nothing (grey setts,
concrete pavers, painted render, modern facades, plain poles, the EU flag), because without them the
model pushed common surfaces onto options that point to a country.

Requests: one per view and per entry of the plan (PLANS). "single", the default, asks all 24 keys plus
landmarks in one request per horizontal view. "split" asks scene + landscape + landmarks, then road
furniture; the second request repeats the first one's prompt, which llama-server serves from its cache,
so it cost only about 0.2 s more per view, with the same answers in our test. Ground views get only
pavement, and a note that the person in the middle is the photographer (the photographer mask marks
pixels and blanks none, panoloc.views). Every request sends think false, temperature 0, seed 0,
presence/frequency penalties 0 (the qwen3.5 Modelfile sets presence_penalty 1.5, which would push greedy
decoding away from repeating "not_visible"), the same num_ctx (another value reloads the model) and
keep_alive -1, and asks for one-line JSON (pretty-printed replies took about 60% more tokens).
Measured on 2026-10-10 with the GPU capped at 80 W: Ollama 0.34.4 runs qwen3.5 in llama-server and,
this being a hybrid model, reuses no prompt prefix across different images, so every view pays the
whole prompt (system ~2.9k tokens + image ~1.05k tokens: 1.4-2.2 s) plus ~165 reply tokens at ~45 tok/s.
That is about 6 s per horizontal view, 2.5 s for ground and 50-52 s per panorama, with 5.4 GiB resident
(6.8 GB on the GPU) at num_ctx 8192.

Aggregation across views (aggregate): per key, votes of the real answers (not not_visible, other or
invalid), the majority value with its support (views) and share (of the real answers), and conflicts:
"conflict" when views give different real values, "country_conflict" when those values point to
countries with nothing in common. Overlapping views see the same object twice, so votes are
correlated: support counts views, not independent observations. Landmark hypotheses are merged by
panoloc.names.normalise (the name index's own key) with their best confidence, kinds and views.

Hints (hints): one per real value that the table links to countries or regions:
  {key, value, countries, regions, strength, views, support, share, majority, conflict, hard, note}
strength is the table's (strong, medium-strong, medium, weak): how much the clue says, not how often
the model reads it right, which fusion must still calibrate. "hard" marks keys that need a close crop
(sign rims, crossing stripes), which a 1024 px view rarely resolves. Hints are positive observations
only: an unseen feature is missing evidence, never evidence of absence, so not_visible never produces
a hint.

Failures: Ollama unreachable, an HTTP error, a timeout or invalid JSON twice in a row raise a VLMError
subclass (VLMUnavailable, VLMTimeout, VLMInvalidResponse) after one retry. describe_panorama(run=...)
logs every finished view as it goes, then a partial summary and a "vlm_error" evidence event, and
re-raises with the partial result on exc.partial, so the caller's optional run.stage() records the
failure and the run goes on.

transcribe(image) asks for an exact transcription of a sign crop, to check OCR (MODEL_DECISIONS 4).
Its result is always marked verified=False: VLMs "correct" non-words, and digits it reads count only
where OCR read the same digits.

  from panoloc.views import load_panorama, cut_views
  from panoloc.vlm import OllamaClient, describe_panorama, log_results
  client = OllamaClient()                                  # qwen3.5:9b at http://localhost:11434
  result = describe_panorama(cut_views(load_panorama(path)), client)
  result.aggregate["post_box"]["value"], result.hints[:3], result.landmarks
  with run.stage("describe", optional=True, model=client.model):
      describe_panorama(views, client, run=run)            # logs vlm_checklist, vlm_summary, landmark_hypothesis
  client.unload()                                          # keep_alive 0 frees the GPU

CLI: python -m panoloc.vlm <panorama.jpg> [--out DIR] [--model qwen3.5:9b] [--plan single|split]
[--views h000,...,ground] [--unload] [--log-run] writes vlm.json (per-view answers, aggregate, hints,
landmarks, timings, Ollama's resident size) to runs/vlm/<panorama stem>/ by default.
"""
import argparse
import base64
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from panoloc.names import normalise

SCHEMA = "panoloc.vlm/1"
DEFAULT_MODEL = "qwen3.5:9b"
FALLBACK_MODEL = "gemma4:12b"  # MODEL_DECISIONS 1: Ollama caps its image budget at 441 tokens
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_NUM_CTX = 8192  # system prompt + one 1024 px image (~1,050 tokens) + reply; keep one value per model
DEFAULT_TIMEOUT_S = 90.0
DEFAULT_LOAD_TIMEOUT_S = 300.0  # a cold load under RAM pressure took minutes (MODEL_DECISIONS 2)
CHECKLIST_MAX_TOKENS = 900
TRANSCRIBE_MAX_TOKENS = 200
JPEG_QUALITY = 90
NOT_VISIBLE, OTHER, INVALID = "not_visible", "other", "invalid"
SPECIAL = (NOT_VISIBLE, OTHER)
STRENGTHS = ("strong", "medium-strong", "medium", "weak")  # COUNTRY_CLUES 0
GROUPS = ("scene", "road", "landscape")
LANDMARK_KINDS = ("building", "monument", "church", "castle", "bridge", "square", "street", "station", "town",
                  "natural_feature", "other")
CONFIDENCES = ("low", "medium", "high")
MAX_LANDMARKS = 3
MAX_LANDMARK_CHARS = 80
HORIZONTAL_VIEWS = tuple(f"h{yaw:03d}" for yaw in range(0, 360, 45))
DEFAULT_VIEWS = HORIZONTAL_VIEWS + ("ground",)
REPO_ROOT = Path(__file__).resolve().parent.parent


# -- the checklist (COUNTRY_CLUES 7) ---------------------------------------------------------------

@dataclass(frozen=True)
class Option:
    value: str
    looks: str = ""             # visual description for the prompt; never names a country
    countries: tuple = ()       # PT / ES / FR this value points to; empty = no country implied
    regions: tuple = ()
    strength: str | None = None  # STRENGTHS; None when the value implies nothing
    note: str = ""


@dataclass(frozen=True)
class Item:
    key: str
    group: str     # scene, road, landscape
    ask: str       # the question: the object first, then its attributes
    options: tuple
    hard: bool = False  # needs a close, full-resolution crop (COUNTRY_CLUES 0)

    @property
    def values(self):
        return tuple(o.value for o in self.options)

    @property
    def allowed(self):
        return (NOT_VISIBLE, *self.values, OTHER)

    def option(self, value):
        return next((o for o in self.options if o.value == value), None)

    def prompt_line(self):
        opts = " | ".join(f"{o.value} ({o.looks})" if o.looks else o.value for o in self.options)
        return f"- {self.key}: {self.ask} {opts}"


def _o(value, looks="", countries="", regions=(), strength=None, note=""):
    return Option(value, looks, tuple(countries.split()), tuple(regions), strength, note)


# Implications follow the table; where it gives no strength, COUNTRY_CLUES 1 does, else the weakest
# fitting level. The visual descriptions are ours. A few neutral look-alikes (_NEUTRAL) are not in the
# table: without them the model forces common surfaces onto an option that implies a country.
_NEUTRAL = "not in the table: a common look-alike that implies nothing"
CHECKLIST = (
    # A. Any scene
    Item("sign_language", "scene", "Is there readable writing on street signs, shop fronts, plaques or notices? "
         "Its language (ignore brand names and English; on a bilingual sign choose the regional language):", (
        _o("portuguese", "ã õ ç, -ção, Rua, Travessa, Largo", "PT", strength="strong"),
        _o("spanish", "ñ, -ción, Calle, Avenida, del", "ES", strength="strong"),
        _o("catalan", "l·l, à è ò, Carrer, Plaça", "ES FR",
           ("Catalonia", "Valencian Community", "Balearic Islands", "Pyrénées-Orientales (66)"), "strong"),
        _o("galician", "Rúa, unha, x, no ç or ã", "ES", ("Galicia",), "strong"),
        _o("basque", "tx, tz, k, Kalea, -ko", "ES FR", ("Basque Country", "Navarra", "French Basque Country"),
           "strong"),
        _o("french", "é è ê à œ, Rue, Place, du, des", "FR", strength="strong"),
        _o("breton", "c'h, zh, Straed, Ker-", "FR", ("Brittany",), "strong"),
        _o("occitan", "Carrièra, a second street name under a French one", "FR ES",
           ("Toulouse", "Avignon", "Val d'Aran"), "medium"),
        _o("corsican", "chj, ghj, words ending in -u", "FR", ("Corsica",), "strong"))),
    Item("plate_layout", "scene", "Is a car number plate close and sharp enough to see the colour of its two ends (do "
         "not read the characters)? The plate:", (
        _o("blue_left_yellow_right", "blue band left, yellow band right", "PT", strength="strong", note="PT 1998-2020"),
        _o("blue_both_ends", "blue bands at both ends", "FR", strength="strong"),
        _o("blue_left_only", "blue band on the left only", "ES PT", strength="weak", note="ES, or PT since 2020"),
        _o("black_plate_white_chars", "black plate, white characters", "PT FR", strength="weak",
           note="PT before 1992 or old FR"),
        _o("yellow_rear_plate", "the whole plate is yellow", "FR", strength="medium", note="old FR"))),
    Item("post_box", "scene", "Is there a street post box for posting letters (a box or pillar with a letter slot, "
         "not a bin or a fire hydrant)? Its colour:", (
        _o("red", "", "PT", strength="strong"),
        _o("blue_correio_azul", "blue", "PT", strength="strong"),
        _o("yellow_crown_horn_logo", "yellow, crown-and-horn logo", "ES", strength="strong"),
        _o("yellow_la_poste_logo", "yellow, La Poste bird logo", "FR", strength="strong"),
        _o("yellow_logo_unclear", "yellow, logo not readable", "ES FR", strength="medium",
           note="not in the table: yellow rules out PT when the logo is unreadable"),
        _o("brown_la_poste", "brown, La Poste logo", "FR", strength="medium", note="heritage areas"))),
    Item("street_plaque", "scene", "Is there a street-name plaque on a wall or post? Its style:", (
        _o("white_stone_black_serif_corner_bolts", "white stone, black serif capitals, a bolt in each corner", "PT",
           ("Lisbon",), "medium"),
        _o("blue_on_white_azulejo", "blue-on-white painted ceramic tiles", "PT", ("Lisbon", "Azores"), "medium"),
        _o("black_plate_white_caps", "black plate, white capitals", "PT", ("Lisbon",), "weak"),
        _o("pale_green_white_serif", "pale green, white serif capitals", "PT", ("Porto",), "medium"),
        _o("white_marble_black_caps", "white marble, black capitals, no bolts", "ES PT", ("Barcelona",), "weak",
           note="Barcelona or generic PT"),
        _o("oval_blue_gilded_frame", "oval, blue, gilded frame", "ES", ("Bilbao",), "medium"),
        _o("dark_blue_coat_of_arms", "dark blue with a coat of arms", "ES", ("Madrid",), "medium"),
        _o("dark_blue_green_frame_arched", "dark blue, green frame, arched top", "FR", ("Paris",), "medium"),
        _o("red_fleur_de_lis", "with a red fleur-de-lis", "FR", ("Lille",), "medium"),
        _o("corner_bolts_notched_border", "corner bolts and a notched border", "FR", ("Lyon",), "weak"),
        _o("light_yellow", "light yellow", "FR", ("Saint-Étienne",), "weak"))),
    Item("pavement", "scene", "What is the pavement for walking (sidewalk, square or path; if there is none, the "
         "road) made of?", (
        _o("white_limestone_cubes", "small white stone cubes, about 5 cm", "PT", strength="medium-strong"),
        _o("black_white_mosaic", "small black and white stone cubes in patterns", "PT", strength="medium-strong"),
        _o("dark_basalt_white_patterns", "small dark stone cubes with white patterns", "PT", ("Azores", "Madeira"),
           "medium"),
        _o("flower_panot_tiles", "grey square tiles with a flower pattern", "ES", ("Barcelona",), "medium-strong"),
        _o("granite_slabs", "large flat granite slabs, half a metre or more", "PT", ("northern Portugal", "Porto"),
           "weak"),
        _o("diagonal_square_setts", "square stone setts, 10-20 cm, laid diagonally to the road", "PT",
           strength="medium"),
        _o("grey_setts", "grey stone setts or cobbles in rows or arcs", note=_NEUTRAL),
        _o("concrete_pavers", "concrete paving blocks or tiles", note=_NEUTRAL),
        _o("asphalt"),
        _o("dirt", "dirt, gravel or sand"))),
    Item("wall_finish", "scene", "What are the walls of the nearest buildings made of or covered with?", (
        _o("whitewash_blue_or_yellow_bands", "whitewashed, blue or yellow painted bands round doors, windows or base",
           "PT", ("southern Portugal",), "medium-strong"),
        _o("whitewash_plain", "whitewashed, no coloured bands", "PT ES",
           ("southern Portugal", "Andalucía", "Extremadura"), "weak"),
        _o("azulejo_facade", "facade covered in glazed ceramic tiles", "PT", strength="medium"),
        _o("concrete_blocks_white_mortar", "bare grey concrete blocks with white mortar lines", "PT",
           ("northern Portugal",), "medium"),
        _o("concrete_blocks_plain", "bare grey concrete blocks", "ES", ("Galicia",), "weak"),
        _o("granite", "granite stone", "PT ES FR", ("northern Portugal", "Galicia", "Brittany"), "weak"),
        _o("dark_schist", "dark schist stone", "PT", ("Centro (Portugal)", "Douro"), "weak"),
        _o("dark_red_brick", "dark red brick", "FR", ("northern France", "Paris"), "strong"),
        _o("orange_brick", "bright orange brick", "FR", ("Toulouse",), "strong"),
        _o("white_painted_timber", "white walls, timber frame painted red or green", "FR", ("French Basque Country",),
           "strong"),
        _o("white_unpainted_timber", "white walls, bare brown timber frame", "ES",
           ("Basque Country", "Navarra", "Cantabria"), "medium"),
        _o("half_timbering", "exposed timber framing filled with plaster or brick", "FR", ("Alsace", "Normandy"),
           "medium"),
        _o("haussmann_limestone", "cream limestone apartment blocks with wrought-iron balconies", "FR", ("Paris",),
           "medium"),
        _o("pastel_grey_trims_green_shutters", "pastel walls, grey stone trims, green shutters", "PT", ("Azores",),
           "medium"),
        _o("painted_render", "smooth plaster painted a colour other than white", note=_NEUTRAL),
        _o("modern_concrete_glass", "modern concrete, glass or metal panels", note=_NEUTRAL))),
    Item("roof", "scene", "Are roofs visible? What are they covered with?", (
        _o("orange_canal_tiles", "orange curved clay tiles", "", ("the south",), "weak"),
        _o("dark_slate", "dark grey slate", "ES FR", ("NW Spain interior", "NW France", "Massif Central", "Pyrenees"),
           "weak"),
        _o("flat_roofs", "flat roof terraces", "ES", ("SE Spain", "Canary Islands"), "weak"),
        _o("fish_scale_tiles", "tiles in a fish-scale pattern", "FR", ("Alsace",), "medium"),
        _o("stone_slabs", "thick stone slabs", "FR", ("Massif Central",), "weak"),
        _o("mansard_dormers", "steep mansard roofs with dormer windows", "FR", ("Paris",), "medium"),
        _o("thatch"))),
    Item("chimney", "scene", "Is there a distinctive chimney?", (
        _o("ornate_lattice_or_round_spire", "ornate white chimney with lattice openings or a round spire top", "PT",
           ("Algarve",), "strong"),
        _o("large_whitewashed_block", "large whitewashed block chimney", "PT", ("Alentejo",), "medium"),
        _o("gable_end_chimneys", "chimneys on top of the gable ends", "FR", ("Brittany",), "weak"))),
    Item("granary", "scene", "Is there a raised granary (a small storage building on legs)?", (
        _o("long_stone_granary_on_pillars", "long and narrow, on stone pillars", "PT ES", ("Minho", "Galicia"),
           "strong"),
        _o("square_wooden_granary_four_pillars", "square, wooden, on four pillars", "ES", ("Asturias", "León"),
           "strong"))),
    Item("flag", "scene", "Is a flag (a cloth on a pole or hanging from a building) clearly visible? Which one?", (
        _o("portugal", "green and red, coat of arms", "PT", strength="medium"),
        _o("spain", "red-yellow-red stripes", "ES", strength="medium"),
        _o("france", "blue-white-red vertical stripes", "FR", strength="medium"),
        _o("european_union", "blue with a ring of yellow stars", note=_NEUTRAL),
        _o("azores", "white and blue halves, a hawk and nine stars", "PT", ("Azores",), "medium"),
        _o("madeira", "blue-yellow-blue vertical, red cross", "PT", ("Madeira",), "medium"),
        _o("galicia", "white with a blue diagonal band", "ES", ("Galicia",), "medium"),
        _o("senyera", "yellow with four red stripes", "ES FR", ("Catalonia", "Pyrénées-Orientales (66)"), "medium"),
        _o("estelada", "red and yellow stripes with a star in a triangle", "ES", ("Catalan areas of Spain",), "medium"),
        _o("ikurrina", "red with a green diagonal cross and a white cross", "ES FR",
           ("Basque Country", "Navarra", "French Basque Country"), "medium"),
        _o("andalucia", "green-white-green horizontal stripes", "ES", ("Andalucía",), "medium"),
        _o("extremadura", "green-white-black horizontal stripes", "ES", ("Extremadura",), "medium"),
        _o("gwenn_ha_du", "black and white stripes, ermine spots", "FR", ("Brittany",), "medium"),
        _o("occitan_cross", "red with a yellow cross with pommels", "FR", ("Occitanie",), "medium"),
        _o("provence_vertical", "yellow with red vertical stripes", "FR", ("Provence",), "medium"),
        _o("moor_head", "white with a black head wearing a white bandana", "FR", ("Corsica",), "medium"))),
    Item("logo_seen", "scene", "Is one of these logos or signs clearly visible?", (
        _o("ctt_horse_rider", "CTT, a horse rider", "PT", strength="strong"),
        _o("multibanco_mb", "Multibanco MB cash machine", "PT", strength="medium-strong"),
        _o("correos_crown", "Correos, crown and horn", "ES", strength="strong"),
        _o("once", "ONCE lottery", "ES", strength="medium-strong"),
        _o("la_poste_bird", "La Poste bird", "FR", strength="strong"),
        _o("tabac_double_cone", "red double-cone TABAC sign", "FR", strength="medium-strong"),
        _o("fdj", "FDJ lottery", "FR", strength="medium-strong"))),
    # B. Road scenes
    Item("bollard", "road", "Is there a roadside delineator post (a short white post with a reflector at the edge "
         "of a road, not a pedestrian bollard)?", (
        _o("thin_wedge_small_white_reflector", "thin white wedge, black band, small white reflector", "PT",
           strength="medium"),
        _o("flat_post_wide_reflector", "flat post, wide reflector", "PT", strength="medium", note="rare in FR"),
        _o("yellow_orange_rect_reflector", "white post, black band, yellow-orange rectangular reflector", "ES",
           strength="strong", note="also the left side of PT motorways"),
        _o("same_green_top", "the same with a green top", "ES", ("Extremadura",), "strong"),
        _o("square_orange_front", "square post, orange reflector on the front", "ES",
           ("Lleida", "Tarragona", "Las Palmas"), "medium"),
        _o("round_pointed_top_band", "round white post, pointed top, grey or red band", "FR", strength="strong"),
        _o("diagonal_black_band", "white post with a diagonal black band", "FR", ("eastern France",), "weak",
           note="German, Luxembourg or Swiss type"),
        _o("stone_block_red_reflector", "stone block with a red reflector", "PT", ("Madeira",), "strong"))),
    Item("guardrail_reflectors", "road", "Is there a steel crash barrier (a W-shaped guardrail along a road, not a "
         "railing)? Its reflectors:", (
        _o("red", "small red reflectors on the rail", "PT", strength="medium-strong"),
        _o("yellow", "small yellow reflectors on the rail", "ES", strength="medium-strong"),
        _o("none", "a clear view of the rail shows no reflectors", "FR", strength="weak"),
        _o("yellow_black_painted_rail", "rail painted yellow and black", "PT", ("Madeira",), "strong"))),
    Item("chevron", "road", "Is there a curve warning board with arrows (chevrons)?", (
        _o("black_yellow", "black board, yellow arrows", "PT", strength="strong"),
        _o("black_white", "black and white", "ES", strength="medium"),
        _o("blue_white", "blue and white", "ES FR", strength="weak"),
        _o("small_square_red_on_white", "small square, red arrow on white", "ES", ("Murcia",), "strong"),
        _o("large_square_single_arrow", "large square, one arrow", "ES", ("Catalonia",), "medium"))),
    Item("km_marker", "road", "Is there a kilometre marker by the road (do not read its numbers)?", (
        _o("plate_diagonal_colour_left", "wide white plate, coloured left part cut diagonally", "PT",
           strength="strong"),
        _o("tombstone_black_base", "rounded tombstone post, black base", "PT", strength="strong"),
        _o("yellow_base", "tombstone post, yellow base", "PT", strength="strong"),
        _o("coloured_header_rectangle", "flat plate, coloured header band, the word km", "ES", strength="strong"),
        _o("square_no_km_word", "square plate without the word km", "ES",
           ("Extremadura", "Castilla-La Mancha", "Aragón"), "medium"),
        _o("square_madrid_flag", "square plate topped by a red flag with white stars", "ES", ("Madrid",), "strong"),
        _o("extra_tall_junta_band", "extra-tall post with a regional band", "ES", ("Andalucía",), "medium"),
        _o("rounded_top_large", "large post with a rounded top", "ES", ("Bizkaia",), "medium"),
        _o("white_yellow_round_top", "white post, yellow rounded top", "FR", strength="strong", note="D road"),
        _o("white_red_round_top", "white post, red rounded top", "FR", strength="strong", note="N road"),
        _o("plate_decimal_km", "motorway plate with a decimal number", "FR", strength="medium", note="motorway"))),
    Item("direction_sign", "road", "Is there a road direction sign?", (
        _o("white_arrow_plate_black_arrowhead", "white arrow-shaped plate, black border, black arrowhead", "PT",
           strength="strong"),
        _o("green_panel", "green panel", "PT FR", strength="weak", note="PT IP roads, also FR main routes"),
        _o("coloured_number_boxes", "white sign, road numbers in coloured boxes", "ES", strength="strong"),
        _o("offset_outline_italics", "white sign, black outline set in from the edge, small names in italics", "FR",
           strength="strong"),
        _o("yellow_D_plate", "small yellow plate with the road number on top", "FR", strength="strong"),
        _o("cyan_M_plate", "small cyan plate with the road number", "FR", ("French métropoles",), "medium"))),
    Item("red_sign_rim", "road", "Is a red-bordered road sign close enough to see the outer edge of its border?", (
        _o("white_rim", "a thin white rim outside the red", "PT FR", strength="strong"),
        _o("red_to_edge", "the red runs to the edge", "ES", strength="strong")), hard=True),
    Item("pedestrian_sign", "road", "Is a pedestrian-crossing sign close enough to count its stripes?", (
        _o("eight_stripes", "8 stripes", "ES", strength="strong"),
        _o("five_belted_figure", "5 stripes, the figure wears a belt", "PT", strength="medium"),
        _o("five_detached_head", "5 stripes, the figure's head is detached", "FR", strength="medium")), hard=True),
    Item("edge_lines", "road", "Are there painted lines along the edge of a road?", (
        _o("solid", "solid white", "PT ES", strength="weak", note="PT and some ES regions"),
        _o("dashed_short", "short white dashes", "ES",
           ("Castilla y León", "Extremadura", "Castilla-La Mancha", "Catalonia"), "medium"),
        _o("long_widely_spaced", "long dashes, wide gaps", "FR", strength="medium"),
        _o("offset_block_centre", "centre line of offset blocks", "FR", strength="strong"),
        _o("yellow", "yellow", "PT ES", strength="weak", note="kerb no-parking (PT) or roadworks (ES)"))),
    Item("utility_pole", "road", "Is there a utility pole carrying overhead wires (not a lamp post)?", (
        _o("ladder_tall_openings_holes", "concrete, ladder pattern with tall openings or holes", "PT",
           strength="medium-strong"),
        _o("ladder_short_steps", "concrete, ladder pattern with short steps", "ES FR", strength="medium"),
        _o("small_blue_plate", "a small blue plate on the pole", "FR", strength="strong"),
        _o("octagonal_metal", "octagonal metal", "FR", strength="medium"),
        _o("steel_lattice_rect_mesh", "steel lattice with rectangular mesh", "ES", ("Murcia", "southern Alicante"),
           "medium"),
        _o("plain_pole", "plain concrete, wooden or metal pole, no pattern or plate", note=_NEUTRAL))),
    Item("hunting_sign", "road", "Is there a hunting-area sign on a fence, post or tree?", (
        _o("red_white_sign", "red and white: a rectangle, a diamond or a small red-white-red plate", "PT",
           strength="strong"),
        _o("white_coto_privado_de_caza", "white, COTO PRIVADO DE CAZA", "ES", strength="strong"),
        _o("black_white_diagonal_square", "small square split diagonally black and white", "ES", strength="strong"),
        _o("area_privada_de_caca", "ÀREA PRIVADA DE CAÇA", "ES", ("Catalonia", "Balearic Islands"), "strong"))),
    # C. Landscape
    Item("vegetation", "landscape", "Which trees or crops are the most prominent?", (
        _o("eucalyptus", "tall, pale peeling bark, long drooping leaves", "PT ES",
           ("northern and central Portugal", "northern Spain", "Huelva"), "medium", note="essentially absent in FR"),
        _o("maritime_pine", "", "PT ES", ("northern half of Portugal", "Galicia"), "weak"),
        _o("stone_pine", "umbrella-shaped crown"),
        _o("cork_holm_oak_scattered", "oaks scattered over open grassland", "PT ES", ("Alentejo", "dehesa"), "medium"),
        _o("olive_rows", "olive trees in rows"),
        _o("douro_schist_terraces", "steep vineyard terraces walled with dark stone", "PT", ("Douro",), "strong"),
        _o("pergola_vines", "vines trained high on pergolas", "PT", ("Minho",), "medium"),
        _o("citrus", "orange or lemon groves", "PT ES", ("Algarve", "Valencian Community"), "weak"),
        _o("rice_paddies", "", "PT ES", ("Tejo", "Sado", "Mondego", "Ebro delta"), "medium"),
        _o("plastic_greenhouses", "fields of plastic greenhouses", "ES", ("Almería",), "medium"),
        _o("lavender", "lavender fields", "FR", ("Provence",), "medium"),
        _o("flat_pine_monoculture", "flat land densely planted with pines", "FR", ("Landes",), "medium"),
        _o("hedged_bocage", "small fields enclosed by hedgerows", "FR", ("Normandy", "Brittany"), "medium"),
        _o("japanese_cedar", "tall dark conical cedars", "PT", ("Azores",), "medium"),
        _o("banana", "banana plants", "PT ES", ("Madeira", "Canary Islands"), "medium",
           note="the table names Madeira; the Canaries grow them too"),
        _o("palms"))),
    Item("terrain", "landscape", "Is open land visible far away (not hidden by buildings)? Its landform:", (
        _o("flat_plain"),
        _o("rolling", "gentle hills"),
        _o("mountains"),
        _o("granite_boulders_snow_poles", "granite boulders, tall snow poles", "PT", ("Serra da Estrela", "Gerês"),
           "medium"),
        _o("white_sand_pines", "white sand with pines", "PT", ("Setúbal–Sines coast",), "medium"),
        _o("volcanic", "black volcanic rock or cones", "PT ES", ("Azores", "Canary Islands"), "medium"),
        _o("sea_cliffs"))),
    Item("soil", "landscape", "Is a patch of bare earth visible (not pavement, rock or grass)? Its colour:", (
        _o("red", "", "PT ES", ("Teruel", "Castilla-La Mancha", "Alentejo olive land"), "weak"),
        _o("white_grey", "", "ES", ("Aragón", "Ebro valley"), "weak"),
        _o("black_volcanic", "", "ES", ("Lanzarote",), "medium"),
        _o("orange_volcanic", "", "ES", ("Fuerteventura",), "medium"))),
)
ITEMS = {item.key: item for item in CHECKLIST}
KEYS = tuple(ITEMS)
GROUP_KEYS = {g: tuple(i.key for i in CHECKLIST if i.group == g) for g in GROUPS}
GROUND_KEYS = ("pavement",)  # soil is judged in the horizontal views: alone here, the model invents it


@dataclass(frozen=True)
class Request:
    """One request per view: which keys it asks, and whether it also asks for landmarks."""
    name: str
    keys: tuple
    landmarks: bool = False


PLANS = {
    "single": {"horizontal": (Request("checklist", KEYS, landmarks=True),),
               "ground": (Request("ground", GROUND_KEYS),)},
    "split": {"horizontal": (Request("scene", GROUP_KEYS["scene"] + GROUP_KEYS["landscape"], landmarks=True),
                             Request("road", GROUP_KEYS["road"])),
              "ground": (Request("ground", GROUND_KEYS),)},
}
DEFAULT_PLAN = "single"

SYSTEM_RULES = """\
You check one photo against a fixed checklist and reply in JSON. The photo is one view cut from a 360° \
panorama taken at ground level (streets, squares, paths, countryside, sometimes indoors) by a person holding \
the camera; that person, their shadow and the camera stick may appear in the photo, often at the bottom: ignore them.

For each item:
1. First look for the object the item asks about. If it is not in the photo, or it is too small, far, \
blurred or hidden to make out, answer "not_visible". Most items are not visible in most photos.
2. If you can see the object but not the detail that tells the options apart (plate ends too small to see, a pole \
too far to see its pattern, reflectors you cannot make out), answer "not_visible" as well: never fill in a detail you \
cannot see. If you can see the detail, pick the option that matches it, or "other" if none does.
3. Answer only from what this photo shows, never from where you think it was taken. Do not guess.
4. When several options apply, pick the one that covers the most of the photo.
5. Never write numbers, codes, plate characters, phone numbers, addresses or coordinates.
Reply on one line without spaces, like {"sign_language":"...","plate_layout":"...",...,"landmarks":[]}.

Checklist:"""

LANDMARK_RULES = """\
- landmarks: specific named places you recognise for certain in this photo: a well-known building, \
monument, church, castle, bridge, station, square, street, town or natural feature. Recognise the place \
itself, not just a style that is common in a region. Give its name, its kind and your confidence. Leave \
the list empty when you recognise nothing specific, which is the usual case."""

HORIZONTAL_TEXT = "Fill in the checklist for this photo."
GROUND_TEXT = ("This photo looks straight down at the ground. The person in the middle is the photographer "
               "holding the camera: ignore them and look at the ground around them. "
               "Fill in the checklist for this photo.")


def system_prompt():
    """The same text for every view and request: a repeated prompt (the split plan's second request) is
    then served from llama-server's cache, and no request depends on another."""
    return "\n".join([SYSTEM_RULES, *(item.prompt_line() for item in CHECKLIST), LANDMARK_RULES])


def landmark_schema():
    return {"type": "array", "maxItems": MAX_LANDMARKS, "items": {
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 2, "maxLength": MAX_LANDMARK_CHARS},
                       "kind": {"type": "string", "enum": list(LANDMARK_KINDS)},
                       "confidence": {"type": "string", "enum": list(CONFIDENCES)}},
        "required": ["name", "kind", "confidence"]}}


def checklist_schema(keys=KEYS, landmarks=True):
    """The JSON schema sent as Ollama's `format`: one enum per key, landmarks last."""
    unknown = [k for k in keys if k not in ITEMS]
    if unknown:
        raise ValueError(f"not checklist keys: {unknown}")
    properties = {key: {"type": "string", "enum": list(ITEMS[key].allowed)} for key in keys}
    if landmarks:
        properties["landmarks"] = landmark_schema()
    return {"type": "object", "properties": properties, "required": list(properties)}


# -- errors -----------------------------------------------------------------------------------------

class VLMError(RuntimeError):
    """A VLM request failed after its retry. partial holds the finished views (describe_panorama)."""

    def __init__(self, message, *, model=None, view=None, attempts=None):
        super().__init__(message)
        self.model, self.view = model, view
        self.attempts = attempts or []
        self.partial = None


class VLMUnavailable(VLMError):
    """Ollama is unreachable, answered with an HTTP error, or doesn't have the model."""


class VLMTimeout(VLMError):
    """A request (or the model load) took longer than its timeout."""


class VLMInvalidResponse(VLMError):
    """The model returned unusable JSON on every attempt."""


# -- Ollama client (standard library only) ------------------------------------------------------------

def _post_json(method, url, payload, timeout):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _seconds(ns):
    return round(ns / 1e9, 3) if isinstance(ns, (int, float)) else None


class OllamaClient:
    """Ollama's /api/chat with a JSON schema, one retry per request, and errors mapped to VLMError.

    transport(method, url, payload, timeout) -> dict is the HTTP call; tests pass a fake one.
    """

    def __init__(self, model=DEFAULT_MODEL, host=DEFAULT_HOST, *, timeout_s=DEFAULT_TIMEOUT_S,
                 load_timeout_s=DEFAULT_LOAD_TIMEOUT_S, retries=1, retry_delay_s=1.0, keep_alive=-1,
                 num_ctx=DEFAULT_NUM_CTX, think=False, transport=None):
        self.model, self.host = model, host.rstrip("/")
        self.timeout_s, self.load_timeout_s = timeout_s, load_timeout_s
        self.retries, self.retry_delay_s = retries, retry_delay_s
        self.keep_alive, self.num_ctx, self.think = keep_alive, num_ctx, think
        self._transport = transport or _post_json

    def options(self, num_predict=None):
        options = {"temperature": 0, "seed": 0, "num_ctx": self.num_ctx,
                   "presence_penalty": 0, "frequency_penalty": 0, "repeat_penalty": 1.0}
        if num_predict:
            options["num_predict"] = num_predict
        return options

    def settings(self):
        return {"model": self.model, "host": self.host, "num_ctx": self.num_ctx, "think": self.think,
                "keep_alive": self.keep_alive, "temperature": 0, "seed": 0, "timeout_s": self.timeout_s,
                "retries": self.retries}

    def _call(self, method, path, payload, timeout, what):
        """One HTTP call with up to `retries` retries; returns (response, attempts)."""
        attempts = []
        for attempt in range(1 + self.retries):
            if attempt:
                time.sleep(self.retry_delay_s)
            t0 = time.perf_counter()
            try:
                response = self._transport(method, self.host + path, payload, timeout)
                attempts.append({"ok": True, "wall_s": round(time.perf_counter() - t0, 3)})
                return response, attempts
            except urllib.error.HTTPError as exc:
                body = _http_body(exc)
                attempts.append({"ok": False, "error": f"HTTP {exc.code}", "message": body[:300],
                                 "wall_s": round(time.perf_counter() - t0, 3)})
                if exc.code == 400 and "think" in body.lower() and "think" in (payload or {}):
                    self.think = None  # a model without a thinking mode: ask again, and from now on, without it
                    response, more = self._call(method, path, {k: v for k, v in payload.items() if k != "think"},
                                                timeout, what)
                    return response, attempts + more
                if 400 <= exc.code < 500:  # a missing model or a bad request: a retry can't help
                    raise VLMUnavailable(f"Ollama refused {what} for {self.model}: HTTP {exc.code} {body[:200]}",
                                         model=self.model, attempts=attempts) from exc
                error = VLMUnavailable(f"Ollama failed {what} for {self.model}: HTTP {exc.code} {body[:200]}",
                                       model=self.model, attempts=attempts)
            except OSError as exc:  # URLError, refused connections, timeouts
                reason = getattr(exc, "reason", exc)
                timed_out = isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError)
                attempts.append({"ok": False, "error": "timeout" if timed_out else type(reason).__name__,
                                 "message": str(reason)[:300], "wall_s": round(time.perf_counter() - t0, 3)})
                if timed_out:
                    error = VLMTimeout(f"{what} for {self.model} timed out after {timeout:g} s", model=self.model,
                                       attempts=attempts)
                else:
                    error = VLMUnavailable(f"Ollama is unreachable at {self.host} ({what}): {reason}",
                                           model=self.model, attempts=attempts)
            except ValueError as exc:  # a body that isn't UTF-8 JSON
                attempts.append({"ok": False, "error": "bad HTTP body", "message": str(exc)[:300],
                                 "wall_s": round(time.perf_counter() - t0, 3)})
                error = VLMUnavailable(f"Ollama sent a body that isn't JSON ({what}): {exc}", model=self.model,
                                       attempts=attempts)
        raise error

    def version(self):
        response, _ = self._call("GET", "/api/version", None, 10, "the version check")
        return response.get("version")

    def loaded(self):
        """Models Ollama holds in memory now (/api/ps): name, size, size_vram, context_length, expires_at."""
        response, _ = self._call("GET", "/api/ps", None, 10, "the model list")
        return response.get("models", [])

    def load(self):
        """Load the model with this client's num_ctx and keep_alive; returns the seconds it took (about 0
        when it was already resident with the same settings)."""
        t0 = time.perf_counter()
        payload = {"model": self.model, "keep_alive": self.keep_alive, "options": {"num_ctx": self.num_ctx}}
        self._call("POST", "/api/generate", payload, self.load_timeout_s, "the model load")
        return round(time.perf_counter() - t0, 3)

    def unload(self):
        """keep_alive 0: Ollama frees the model's memory now."""
        self._call("POST", "/api/generate", {"model": self.model, "keep_alive": 0}, 60, "the unload")

    def chat(self, system, text, schema, *, images=(), num_predict=CHECKLIST_MAX_TOKENS, timeout_s=None):
        """One schema-constrained chat turn; returns (content string, timing dict). Raises VLMError."""
        user = {"role": "user", "content": text}
        if images:
            user["images"] = list(images)
        payload = {"model": self.model, "messages": [{"role": "system", "content": system}, user],
                   "stream": False, "format": schema, "keep_alive": self.keep_alive,
                   "options": self.options(num_predict)}
        if self.think is not None:
            payload["think"] = self.think
        t0 = time.perf_counter()
        response, attempts = self._call("POST", "/api/chat", payload, timeout_s or self.timeout_s, "a chat request")
        timing = {"wall_s": round(time.perf_counter() - t0, 3), "load_s": _seconds(response.get("load_duration")),
                  "prompt_tokens": response.get("prompt_eval_count"),
                  "prompt_s": _seconds(response.get("prompt_eval_duration")),
                  "output_tokens": response.get("eval_count"), "output_s": _seconds(response.get("eval_duration")),
                  "done_reason": response.get("done_reason"), "http_attempts": len(attempts)}
        message = response.get("message") or {}
        return message.get("content") or "", timing


def _http_body(exc):
    try:
        return exc.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - the body is only for the message
        return ""


# -- images ---------------------------------------------------------------------------------------

def encode_image(image, *, max_side=None, min_side=None):
    """Base64 for Ollama: encoded bytes or a file path are sent as they are; a View or an H x W x 3
    uint8 array is encoded as JPEG (PIL, imported only then), resized to fit [min_side, max_side]."""
    pixels = getattr(image, "image", image)  # a panoloc.views.View, or the image itself
    if isinstance(pixels, (bytes, bytearray)):
        return base64.b64encode(bytes(pixels)).decode("ascii")
    if isinstance(pixels, (str, Path)):
        return base64.b64encode(Path(pixels).read_bytes()).decode("ascii")
    if not hasattr(pixels, "shape"):
        raise TypeError(f"expected bytes, a path, a View or an image array, got {type(image).__name__}")
    import io
    from PIL import Image
    im = Image.fromarray(pixels)
    side = max(im.size)
    scale = (max_side / side if max_side and side > max_side else min_side / side if min_side and side < min_side
             else 1.0)
    if scale != 1.0:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.Resampling.BICUBIC)
    buffer = io.BytesIO()
    im.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# -- parsing and validation -------------------------------------------------------------------------

_CODE_RE = re.compile(r"\d{3,}|\d\s*[.,]\s*\d|[°′″]|https?:|www\.")  # house numbers, postcodes, coordinates, links
_GENERIC_NAMES = {normalise(n) for n in (*LANDMARK_KINDS, *SPECIAL, "unknown", "none", "n/a", "no", "yes", "null",
                                         "nothing", "landmark", "place", "city", "village", "road", "house", "tower")}


def parse_json(content):
    """The reply as a dict, or None when it isn't a JSON object (code fences are tolerated)."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def coerce_answer(key, raw):
    """A key's answer as one of its allowed values, or None. Only case and spacing are forgiven."""
    if not isinstance(raw, str):
        return None
    allowed = ITEMS[key].allowed
    text = raw.strip()
    if text in allowed:
        return text
    folded = re.sub(r"[\s\-]+", "_", text).casefold()
    return next((v for v in allowed if v.casefold() == folded), None)


def validate_landmarks(raw):
    """(kept, rejected): kept entries are {name, kind, confidence[, digits_unverified, coerced]}."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [{"raw": _short(raw), "reason": "not a list"}]
    kept, rejected, seen = [], [], set()
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            rejected.append({"raw": _short(entry), "reason": "no name"})
            continue
        name = " ".join(entry["name"].split())
        norm = normalise(name)
        if not norm or norm in _GENERIC_NAMES or len(name) > MAX_LANDMARK_CHARS:
            rejected.append({"raw": _short(entry), "reason": "generic, empty or too long"})
            continue
        if _CODE_RE.search(name):
            rejected.append({"raw": _short(entry), "reason": "contains a number, code or coordinate"})
            continue
        if norm in seen:
            continue
        seen.add(norm)
        item, coerced = {"name": name}, []
        for field_name, allowed, fallback in (("kind", LANDMARK_KINDS, "other"), ("confidence", CONFIDENCES, "low")):
            value = entry.get(field_name)
            if value not in allowed:  # the neutral kind and the lowest confidence, flagged as coerced
                value = fallback
                coerced.append(field_name)
            item[field_name] = value
        if any(ch.isdigit() for ch in name):
            item["digits_unverified"] = True  # e.g. "Ponte 25 de Abril": the name index must confirm it
        if coerced:
            item["coerced"] = coerced
        kept.append(item)
    return kept, rejected


def validate_reply(obj, keys, landmarks):
    """Check a parsed reply against its request: answers for every key (bad ones become "invalid")."""
    answers, invalid = {}, {}
    for key in keys:
        raw = obj.get(key)
        value = coerce_answer(key, raw)
        if value is None:
            answers[key], invalid[key] = INVALID, _short(raw) if key in obj else "<missing>"
        else:
            answers[key] = value
    kept, rejected = validate_landmarks(obj.get("landmarks")) if landmarks else ([], [])
    if landmarks and "landmarks" not in obj:
        invalid["landmarks"] = "<missing>"
    extra = sorted(k for k in obj if k not in keys and not (landmarks and k == "landmarks"))
    return {"answers": answers, "invalid": invalid, "landmarks": kept, "rejected_landmarks": rejected,
            "extra_keys": extra}


def _short(value, limit=120):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


# -- per view ---------------------------------------------------------------------------------------

@dataclass
class ViewResult:
    """The checklist answers for one view, merged over the plan's requests."""
    view: str
    yaw_deg: float | None
    pitch_deg: float | None
    fov_deg: float | None
    masked_fraction: float
    answers: dict                      # key -> value, for every key asked in this view
    landmarks: list = field(default_factory=list)
    invalid: dict = field(default_factory=dict)
    rejected_landmarks: list = field(default_factory=list)
    requests: list = field(default_factory=list)  # one timing entry per request
    latency_s: float = 0.0
    raw: list = field(default_factory=list)       # the replies as received, for vlm.json

    @property
    def seen(self):
        """The real answers: neither not_visible, other nor invalid."""
        return {k: v for k, v in self.answers.items() if v not in (NOT_VISIBLE, OTHER, INVALID)}

    def box(self):
        if self.yaw_deg is None or self.fov_deg is None:
            return None
        return {"yaw": round(self.yaw_deg, 2), "pitch": round(self.pitch_deg, 2), "w": self.fov_deg, "h": self.fov_deg}

    def counts(self):
        c = Counter(v if v in (NOT_VISIBLE, OTHER, INVALID) else "real" for v in self.answers.values())
        return {"asked": len(self.answers), "real": c["real"], NOT_VISIBLE: c[NOT_VISIBLE], OTHER: c[OTHER],
                INVALID: c[INVALID]}

    def to_dict(self, raw=True):
        doc = {"view": self.view, "yaw_deg": self.yaw_deg, "pitch_deg": self.pitch_deg, "fov_deg": self.fov_deg,
               "masked_fraction": round(self.masked_fraction, 4), "answers": self.answers, "seen": self.seen,
               "counts": self.counts(), "landmarks": self.landmarks, "invalid": self.invalid,
               "rejected_landmarks": self.rejected_landmarks, "requests": self.requests,
               "latency_s": self.latency_s}
        if raw:
            doc["raw"] = self.raw
        return doc


def _view_kind(view):
    return "ground" if getattr(view, "name", "") == "ground" or getattr(view, "pitch_deg", 0) <= -60 else "horizontal"


def ask(client, image_b64, request, text):
    """One request with up to client.retries retries for bad JSON or invalid values; returns
    (validated reply, timing, raw replies). Raises VLMInvalidResponse when no attempt parses."""
    schema = checklist_schema(request.keys, request.landmarks)
    best, raws, timings = None, [], []
    for _ in range(1 + client.retries):
        try:
            content, timing = client.chat(system_prompt(), text, schema, images=[image_b64],
                                          num_predict=CHECKLIST_MAX_TOKENS)
        except VLMError:
            if best is None:
                raise
            break  # the retry for invalid values failed: keep the usable reply we have

        raws.append(content)
        timings.append(timing)
        obj = parse_json(content)
        if obj is None or timing.get("done_reason") == "length":
            continue
        reply = validate_reply(obj, request.keys, request.landmarks)
        if best is None or len(reply["invalid"]) < len(best["invalid"]):
            best = reply
        if not best["invalid"]:
            break
    timing = {"request": request.name, "attempts": len(timings), **timings[-1],
              "wall_s": round(sum(t["wall_s"] for t in timings), 3)}
    if best is None:
        raise VLMInvalidResponse(f"{client.model} returned no usable JSON for {request.name} in {len(timings)} "
                                 f"attempts: {_short(raws[-1], 200)!r}", model=client.model,
                                 attempts=[{"ok": False, "error": "invalid JSON", **t} for t in timings])
    return best, timing, raws


def describe_view(client, view, *, plan=DEFAULT_PLAN):
    """Run the plan's requests for one view (a panoloc.views.View); returns a ViewResult."""
    kind = _view_kind(view)
    requests = PLANS[plan][kind]
    text = GROUND_TEXT if kind == "ground" else HORIZONTAL_TEXT
    image_b64 = encode_image(view)
    t0 = time.perf_counter()
    result = ViewResult(view.name, getattr(view, "yaw_deg", None), getattr(view, "pitch_deg", None),
                        getattr(view, "fov_deg", None), float(getattr(view, "masked_fraction", 0.0)), {})
    for request in requests:
        try:
            reply, timing, raws = ask(client, image_b64, request, text)
        except VLMError as exc:
            exc.view = view.name
            raise
        result.answers.update(reply["answers"])
        result.invalid.update(reply["invalid"])
        result.landmarks.extend(reply["landmarks"])
        result.rejected_landmarks.extend(reply["rejected_landmarks"])
        result.requests.append(timing)
        result.raw.extend(raws)
    result.latency_s = round(time.perf_counter() - t0, 3)
    return result


# -- across views -----------------------------------------------------------------------------------

def _rank(values, order):
    return sorted(values, key=lambda v: (-values[v], order.index(v) if v in order else len(order)))


def aggregate(view_results):
    """Per key: votes of the real answers, the majority value with its support and share, conflicts."""
    out = {}
    for item in CHECKLIST:
        asked = [r for r in view_results if item.key in r.answers]
        if not asked:
            continue
        answers = [(r.view, r.answers[item.key]) for r in asked]
        real = [(v, a) for v, a in answers if a not in (NOT_VISIBLE, OTHER, INVALID)]
        votes = Counter(a for _, a in real)
        ranked = _rank(votes, item.values)
        value = ranked[0] if ranked and (len(ranked) == 1 or votes[ranked[0]] > votes[ranked[1]]) else None
        implied = [set(item.option(v).countries) for v in ranked if item.option(v).countries]
        out[item.key] = {
            "group": item.group, "asked": len(asked), "answered": len(real),
            NOT_VISIBLE: sum(a == NOT_VISIBLE for _, a in answers), OTHER: sum(a == OTHER for _, a in answers),
            INVALID: sum(a == INVALID for _, a in answers),
            "votes": {v: votes[v] for v in ranked},
            "views": {v: [view for view, a in real if a == v] for v in ranked},
            "value": value, "support": votes[value] if value else 0,
            "share": round(votes[value] / len(real), 3) if value else None,
            "tied": ranked[:sum(votes[v] == votes[ranked[0]] for v in ranked)] if ranked and value is None else [],
            "conflict": len(ranked) > 1,
            "country_conflict": len(implied) > 1 and not set.intersection(*implied),
        }
    return out


def hints(agg):
    """Soft evidence from the aggregate: one hint per real value that points somewhere (COUNTRY_CLUES 7).

    Positive observations only: not_visible, other and invalid answers never make a hint.
    """
    out = []
    for key, entry in agg.items():
        item = ITEMS[key]
        for value, support in entry["votes"].items():
            option = item.option(value)
            if not (option.countries or option.regions):
                continue
            out.append({"key": key, "value": value, "countries": list(option.countries),
                        "regions": list(option.regions), "strength": option.strength,
                        "views": entry["views"][value], "support": support,
                        "share": round(support / entry["answered"], 3), "majority": value == entry["value"],
                        "conflict": entry["country_conflict"], "hard": item.hard, "note": option.note})
    order = {s: i for i, s in enumerate(STRENGTHS)}
    out.sort(key=lambda h: (order.get(h["strength"], len(STRENGTHS)), -h["support"], h["key"]))
    return out


def merge_landmarks(view_results):
    """Landmark hypotheses merged by normalised name: best confidence, kinds and the views naming them."""
    merged = {}
    for r in view_results:
        for lm in r.landmarks:
            key = normalise(lm["name"])
            m = merged.setdefault(key, {"key": key, "spellings": Counter(), "kinds": Counter(), "confidence": "low",
                                        "views": [], "digits_unverified": False})
            m["spellings"][lm["name"]] += 1
            m["kinds"][lm["kind"]] += 1
            if CONFIDENCES.index(lm["confidence"]) > CONFIDENCES.index(m["confidence"]):
                m["confidence"] = lm["confidence"]
            if r.view not in m["views"]:
                m["views"].append(r.view)
            m["digits_unverified"] |= bool(lm.get("digits_unverified"))
    out = []
    for m in merged.values():
        out.append({"name": m["spellings"].most_common(1)[0][0], "key": m["key"], "names": list(m["spellings"]),
                    "kind": m["kinds"].most_common(1)[0][0], "kinds": dict(m["kinds"]), "confidence": m["confidence"],
                    "views": m["views"], "support": len(m["views"]), "digits_unverified": m["digits_unverified"]})
    out.sort(key=lambda m: (-CONFIDENCES.index(m["confidence"]), -m["support"], m["key"]))
    return out


# -- the whole panorama -----------------------------------------------------------------------------

@dataclass
class PanoramaResult:
    model: str
    plan: str
    views: list                        # ViewResult, in the order asked
    settings: dict = field(default_factory=dict)
    load_s: float | None = None        # the load call: a cold load, or about 0 when already resident
    total_s: float = 0.0
    partial: bool = False
    error: dict | None = None
    aggregate: dict = field(default_factory=dict)
    hints: list = field(default_factory=list)
    landmarks: list = field(default_factory=list)

    def summarise(self):
        self.aggregate = aggregate(self.views)
        self.hints = hints(self.aggregate)
        self.landmarks = merge_landmarks(self.views)
        return self

    def timing(self):
        per_view = {r.view: r.latency_s for r in self.views}
        latencies = sorted(per_view.values())
        return {"load_s": self.load_s, "total_s": self.total_s, "views_s": round(sum(latencies), 3),
                "per_view_s": per_view, "median_view_s": latencies[len(latencies) // 2] if latencies else None,
                "requests": sum(len(r.requests) for r in self.views),
                "output_tokens": sum((t.get("output_tokens") or 0) for r in self.views for t in r.requests)}

    def not_visible_rate(self):
        asked = sum(len(r.answers) for r in self.views)
        nv = sum(v == NOT_VISIBLE for r in self.views for v in r.answers.values())
        return round(nv / asked, 3) if asked else None

    def to_dict(self, raw=True):
        return {"schema": SCHEMA, "model": self.model, "plan": self.plan, "settings": self.settings,
                "partial": self.partial, "error": self.error, "timing": self.timing(),
                "not_visible_rate": self.not_visible_rate(), "hints": self.hints, "landmarks": self.landmarks,
                "aggregate": self.aggregate, "views": [r.to_dict(raw) for r in self.views]}


def describe_panorama(views, client=None, *, plan=DEFAULT_PLAN, view_names=DEFAULT_VIEWS, run=None,
                      stage="describe", on_view=None):
    """Ask the checklist of every selected view; returns a PanoramaResult with aggregate, hints, landmarks.

    With run, each finished view is logged at once, the summary and landmarks at the end; on a VLMError
    the finished views' partial summary and a vlm_error event are logged before it is re-raised.
    """
    if plan not in PLANS:
        raise ValueError(f"plan must be one of {sorted(PLANS)}, got {plan!r}")
    client = client or OllamaClient()
    selected = [v for v in views if v.name in view_names]
    if not selected:
        raise ValueError(f"none of the views {[v.name for v in views]} is in {list(view_names)}")
    result = PanoramaResult(client.model, plan, [], settings={**client.settings(), "plan": plan,
                                                              "views": [v.name for v in selected],
                                                              "jpeg_quality": JPEG_QUALITY})
    t0 = time.perf_counter()
    ids = {}
    def done(r):
        result.views.append(r)
        if run is not None:
            ids[r.view] = log_view(run, r, client.model, stage)
        if on_view:
            on_view(r)

    workers = min(getattr(client, "parallel", 1), len(selected))  # API clients ask several views at once
    try:
        result.load_s = client.load()
        if workers <= 1:
            for view in selected:
                done(describe_view(client, view, plan=plan))
        else:
            with ThreadPoolExecutor(workers, thread_name_prefix="vlm") as pool:
                futures = [pool.submit(describe_view, client, view, plan=plan) for view in selected]
                try:
                    for future in futures:  # logged in view order, as in the sequential loop
                        done(future.result())
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise
    except VLMError as exc:
        result.total_s = round(time.perf_counter() - t0, 3)
        result.partial = True
        result.error = {"type": type(exc).__name__, "message": str(exc), "view": exc.view, "attempts": exc.attempts}
        result.summarise()
        exc.partial = result
        if run is not None:
            if result.views:
                log_summary(run, result, ids, stage)
            run.evidence("vlm_error", {**result.error, "views_done": [r.view for r in result.views],
                                       "observation": f"VLM stage failed: {exc}"[:300]},
                         stage=stage, model=client.model)
        raise
    result.total_s = round(time.perf_counter() - t0, 3)
    result.summarise()
    if run is not None:
        log_summary(run, result, ids, stage)
    return result


# -- run log ----------------------------------------------------------------------------------------

def _observation(r):
    seen = ", ".join(f"{k}={v}" for k, v in r.seen.items()) or "nothing on the checklist"
    c = r.counts()
    lm = f"; landmarks: {', '.join(x['name'] for x in r.landmarks)}" if r.landmarks else ""
    return f"{r.view}: {seen} ({c[NOT_VISIBLE]} of {c['asked']} not visible){lm}"[:400]


def log_view(run, r, model, stage="describe"):
    """One vlm_checklist evidence event for a view; returns its evidence ID."""
    return run.evidence("vlm_checklist", {
        "view": r.view, "box": r.box(), "answers": r.answers, "seen": r.seen, "counts": r.counts(),
        "landmarks": r.landmarks, "invalid": r.invalid, "rejected_landmarks": r.rejected_landmarks,
        "masked_fraction": round(r.masked_fraction, 4), "latency_s": r.latency_s, "requests": r.requests,
        "group": "vlm-checklist", "observation": _observation(r)}, stage=stage, model=model)


def log_summary(run, result, view_ids, stage="describe"):
    """One vlm_summary (aggregate + hints) and one landmark_hypothesis per merged landmark."""
    top = "; ".join(f"{h['key']}={h['value']} ({'/'.join(h['countries']) or ', '.join(h['regions'])}, {h['strength']}, "
                    f"{h['support']} view{'s' * (h['support'] > 1)})" for h in result.hints if h["majority"])
    summary_id = run.evidence("vlm_summary", {
        "views": [r.view for r in result.views], "plan": result.plan, "partial": result.partial,
        "aggregate": result.aggregate, "hints": result.hints, "landmarks": result.landmarks,
        "not_visible_rate": result.not_visible_rate(), "timing": result.timing(), "source_evidence": view_ids,
        "group": "vlm-checklist",
        "note": "Hints are positive observations only; an unseen feature is missing evidence, not absence.",
        "observation": (f"VLM checklist over {len(result.views)} views: " + (top or "no hint"))[:400]},
        stage=stage, model=result.model)
    landmark_ids = []
    for lm in result.landmarks:
        fields = {("place_kind" if k == "kind" else k): v for k, v in lm.items()}  # "kind" is the evidence kind
        landmark_ids.append(run.evidence("landmark_hypothesis", {
            **fields, "source_evidence": [view_ids[v] for v in lm["views"] if v in view_ids], "group": "vlm-landmark",
            "unverified": True, "observation": lm["name"],
            "note": "A name to resolve with the name index (panoloc.names); the model gave no coordinate."},
            stage=stage, model=result.model))
    return {"summary": summary_id, "landmarks": landmark_ids}


def log_results(run, result, stage="describe"):
    """Log a finished PanoramaResult into a Run: per-view vlm_checklist, vlm_summary, landmark_hypothesis."""
    view_ids = {r.view: log_view(run, r, result.model, stage) for r in result.views}
    return {"views": view_ids, **log_summary(run, result, view_ids, stage)}


# -- transcription for OCR checks -------------------------------------------------------------------

TRANSCRIBE_SYSTEM = (
    "You transcribe text from a photo exactly as written, character by character. Keep capitals, accents and "
    "punctuation; separate lines with \" / \". Do not correct spelling, translate, expand abbreviations or complete "
    "cut-off words. Write ? for each character you cannot read. If there is no legible text, answer legible \"no\" "
    "and text \"\".")
TRANSCRIBE_SCHEMA = {"type": "object", "properties": {
    "legible": {"type": "string", "enum": ["yes", "partly", "no"]},
    "text": {"type": "string", "maxLength": 300}}, "required": ["legible", "text"]}
TRANSCRIPTION_POLICY = ("unverified: a VLM reading, only to check OCR; never accept a digit or code here that "
                        "OCR did not also read")


def transcribe(image, client=None, *, max_side=1280, min_side=448):
    """Exact transcription of a sign crop, always marked unverified (MODEL_DECISIONS 4).

    image: encoded bytes, a path, a View or an RGB array. Returns {"text", "legible", "verified": False,
    "digit_runs", "policy", "model", "timing"}. The digits in it never count on their own.
    """
    client = client or OllamaClient()
    image_b64 = encode_image(image, max_side=max_side, min_side=min_side)
    obj, timing = None, None
    for _ in range(1 + client.retries):
        content, timing = client.chat(TRANSCRIBE_SYSTEM, "Transcribe the text in this photo.", TRANSCRIBE_SCHEMA,
                                      images=[image_b64], num_predict=TRANSCRIBE_MAX_TOKENS)
        obj = parse_json(content)
        if obj is not None and obj.get("legible") in ("yes", "partly", "no") and isinstance(obj.get("text"), str) \
                and timing.get("done_reason") != "length":
            break
        obj = None
    if obj is None:
        raise VLMInvalidResponse(f"{client.model} returned no usable transcription", model=client.model)
    text = obj["text"].strip()
    return {"text": text, "legible": obj["legible"], "verified": False, "source": "vlm_transcription",
            "digit_runs": re.findall(r"\d+", text), "policy": TRANSCRIPTION_POLICY, "model": client.model,
            "timing": timing}


# -- CLI --------------------------------------------------------------------------------------------

def main(argv=None):
    from panoloc.runlog import Run, atomic_write_json
    from panoloc.views import cut_views, load_panorama

    parser = argparse.ArgumentParser(prog="python -m panoloc.vlm",
                                     description="Ask the VLM checklist of a panorama's views and write vlm.json.")
    parser.add_argument("panorama", type=Path)
    parser.add_argument("--out", type=Path, help="output folder (default: runs/vlm/<panorama stem>/)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--plan", choices=sorted(PLANS), default=DEFAULT_PLAN)
    parser.add_argument("--views", default=",".join(DEFAULT_VIEWS), help="comma-separated view names (sky is off)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds per request")
    parser.add_argument("--unload", action="store_true", help="unload the model when done (keep_alive 0)")
    parser.add_argument("--log-run", action="store_true", help="also log the evidence into a Run under <out>/runs/")
    args = parser.parse_args(argv)
    out = args.out or REPO_ROOT / "runs" / "vlm" / args.panorama.stem
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    views = cut_views(load_panorama(args.panorama))
    cut_s = round(time.perf_counter() - t0, 3)
    client = OllamaClient(args.model, args.host, timeout_s=args.timeout)
    run = Run(args.panorama, out / "runs", versions={"vlm": args.model}) if args.log_run else None
    names = tuple(n.strip() for n in args.views.split(",") if n.strip())

    def progress(r):
        c = r.counts()
        print(f"  {r.view:<7} {r.latency_s:6.2f} s  real {c['real']:2d}  not_visible {c[NOT_VISIBLE]:2d}  "
              f"other {c[OTHER]:2d}  invalid {c[INVALID]}  {', '.join(f'{k}={v}' for k, v in r.seen.items())}"
              + (f"  | landmarks: {', '.join(x['name'] for x in r.landmarks)}" if r.landmarks else ""), flush=True)

    print(f"{args.panorama.name}: {len(names)} views, {args.model}, plan {args.plan} -> {out}", flush=True)
    status, result = 0, None

    def describe():
        nonlocal status, result
        try:
            result = describe_panorama(views, client, plan=args.plan, view_names=names, run=run, on_view=progress)
        except VLMError as exc:
            result, status = exc.partial, 2
            print(f"VLM stage failed: {type(exc).__name__}: {exc}")
            raise

    try:
        if run is not None:
            with run.stage("describe", optional=True, model=args.model):  # logs the failure and goes on
                describe()
            run.finish()
        else:
            describe()
    except VLMError:
        pass
    try:
        ps = [m for m in client.loaded() if m.get("name") == args.model or m.get("model") == args.model]
    except VLMError:
        ps = []
    if args.unload:
        try:
            client.unload()
        except VLMError as exc:
            print(f"unload failed: {exc}")
    if result is None:
        return status or 2
    doc = {"panorama": args.panorama.name, "source": str(args.panorama), **result.to_dict(),
           "cut_views_s": cut_s, "ollama_ps": ps, "run_log": str(run.log_path) if run else None}
    atomic_write_json(out / "vlm.json", doc)

    t = result.timing()
    print(f"load {t['load_s']} s, {t['requests']} requests, views {t['views_s']:.1f} s "
          f"(median {t['median_view_s']} s), total {t['total_s']:.1f} s, not_visible rate {result.not_visible_rate()}")
    if ps:
        print(f"resident: {ps[0].get('size_vram', 0) / 2**30:.2f} GiB VRAM, context {ps[0].get('context_length')}")
    for h in result.hints:
        where = "/".join(h["countries"]) + (f" ({', '.join(h['regions'])})" if h["regions"] else "")
        answered = result.aggregate[h["key"]]["answered"]
        print(f"  hint {h['key']}={h['value']}: {where}, {h['strength']}, {h['support']}/{answered} "
              f"views {','.join(h['views'])}{' CONFLICT' if h['conflict'] else ''}{' (hard)' if h['hard'] else ''}")
    for lm in result.landmarks:
        print(f"  landmark {lm['name']!r} ({lm['kind']}, {lm['confidence']}) in {', '.join(lm['views'])}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
