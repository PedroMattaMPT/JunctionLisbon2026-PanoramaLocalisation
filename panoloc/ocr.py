"""Read the text in a panorama and parse what it says about the place (PLAN.md 3.1, step 2).

Text is the strongest clue we have (COUNTRY_CLUES.md 0): a postcode, a landline number, a road
number or "Câmara Municipal de X" often names the municipality outright. This module reads the 10
standard views with PP-OCRv6 on the CPU (MODEL_DECISIONS.md 4), rereads small or unsure lines at the
panorama's own resolution, merges the copies of a sign that overlapping views see, and parses each
sign with the patterns of COUNTRY_CLUES.md 2. The name index (panoloc.names) and fusion take it from
there.

Engine: RapidOCR 3.10 with OpenVINO on the CPU, so no VRAM. PP-OCRv6-medium detection and
recognition (the multilingual model, lang "pt": pt, es, fr, ca, gl and eu, with · and ŀ) plus the
text-direction classifier, which turns upside-down lines. PP-OCRv5 Latin (recognition), PP-OCRv5
mobile (detection) and PP-OCRv6-small are selectable fallbacks. The ONNX files come from
tools/setup_env.sh: every path is passed explicitly and a download attempt raises.

Conventions:
- A hit is one OCR reading in one image (a view or a reread crop): text, confidence (RapidOCR's mean
  character probability, 0-1), the detector's quadrilateral in that image's pixels and its box on the
  sphere, {"yaw", "pitch", "w", "h"} in degrees (panoloc.views.box_to_sphere, the event-log format).
  The text drops CJK, kana and hangul glyphs, which the multilingual model outputs for shapes and
  texture; RapidOCR's own text stays in raw_text. A hit with no letter or digit left makes no sign.
- A sign is one piece of text after deduplication. The 8 horizontal views overlap two-fold, so most
  signs are read twice. Hits from different views merge when their boxes overlap on the sphere (across
  the 0/360 yaw seam) and their texts match, or one is a cut-off copy of the other, or the boxes
  coincide whatever the texts say; a sign takes at most one hit per view. Its reading is the most
  confident hit that is neither a cut-off part of a longer copy nor touching a view border (a border
  may cut the text); the other readings stay as alternatives. A sign whose box and text sit inside a
  longer sign is absorbed as a fragment.
- Rereads: a sign below REREAD_BELOW_CONF whose line is under REREAD_LARGE_PX tall in its view (a
  taller unsure line isn't short of pixels), any line under REREAD_SMALL_PX, and a sign cut by a border
  in every view, is cut again around its box (cut_view, fov just larger than the box) at the
  panorama's own resolution (crop_size) and read again; signs with digits go first, at most
  MAX_REREADS within REREAD_BUDGET_S. Only crop hits on the sign's line with a similar height count,
  and the reread replaces the reading only when they cover the box, are not much shorter and are more
  confident. Both readings are kept.
- The photographer zone (panoloc.views) is read like the rest: hits there are kept and flagged
  (in_photographer_zone), because a manhole cover at the photographer's feet can name the town.
- Items are what parse_text finds in a sign: kind, raw text, normalised value, the countries and
  regions it points to, a strength (strong / medium / weak, as in COUNTRY_CLUES.md 0), collision
  notes, details, and the sign it came from. An item narrows the place (a postcode area, a province, a
  municipality); it never marks the camera position. Signs under SIGN_MIN_CONF, and readings made of
  strokes only ("IIIl1": railings, bollards, road stripes), are kept in ocr.json but not parsed.
- Every digit comes from an OCR reading. The VLM may verify a crop later; it never adds digits.
- No state survives between panoramas (RULES.md): an Engine holds model weights and settings only.

  engine = Engine()                                     # PP-OCRv6-medium, about 1 s to load
  result = read_panorama(load_panorama(path), engine)   # views, OCR, rereads, dedup, parsing
  for sign in result.signs: print(sign.sign_id, sign.text, sign.confidence, sign.box, sign.views)
  for item in result.items: print(item["kind"], item["value"], item["countries"], item["strength"])
  parse_text("Tel. 239 123 456")                        # pure parsing, no OCR: [{"kind": "phone", ...}]
  with run.stage("read", model=engine.name):
      log_ocr(run, result)                              # one ocr_text evidence per sign, one per item

CLI: python -m panoloc.ocr <panorama.jpg> [--out DIR] [--debug] writes ocr.json (signs, items,
reread counts, timings and the raw hits) to runs/ocr/<panorama stem>/ and prints a summary. --debug
also draws the boxes on the views, on the reread crops and on a panorama overview, in debug/.
"""
import argparse
import json
import math
import os
import re
import time
import unicodedata
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc.names import STOPWORDS, normalise
from panoloc.views import (DEFAULT_MASK_PCT, DEFAULT_SIZE, MAX_CROP_SIZE, box_to_sphere, crop_size, cut_view,
                           cut_views, load_panorama, parse_filename, photographer_pitch_deg, sphere_to_pano_xy)

SCHEMA = "panoloc.ocr/1"
REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

# -- engine settings --------------------------------------------------------------------------------

DEFAULT_MODEL = "PP-OCRv6-medium"
DET_MODELS = {  # name -> (RapidOCR ocr_version, model_type, lang_type, ONNX file)
    "PP-OCRv6-medium": ("PP-OCRv6", "medium", "pt", "PP-OCRv6_det_medium.onnx"),
    "PP-OCRv6-small": ("PP-OCRv6", "small", "pt", "PP-OCRv6_det_small.onnx"),
    "PP-OCRv5-mobile": ("PP-OCRv5", "mobile", "multi", "ch_PP-OCRv5_det_mobile.onnx"),
}
REC_MODELS = {
    "PP-OCRv6-medium": ("PP-OCRv6", "medium", "pt", "PP-OCRv6_rec_medium.onnx"),
    "PP-OCRv6-small": ("PP-OCRv6", "small", "pt", "PP-OCRv6_rec_small.onnx"),
    "PP-OCRv5-latin": ("PP-OCRv5", "mobile", "latin", "latin_PP-OCRv5_rec_mobile.onnx"),
}
CLS_MODEL = ("PP-OCRv4", "mobile", "ch", "ch_ppocr_mobile_v2.0_cls_mobile.onnx")
RAW_MIN_SCORE = 0.3  # RapidOCR drops readings below this; low, so that a reread can still rescue them
MIN_DET_SIDE = 320   # RapidOCR's detector upscales images whose shorter side is below this

# -- reading, rereads and deduplication -------------------------------------------------------------

SIGN_MIN_CONF = 0.5         # signs below this after rereads are kept in ocr.json but not parsed or logged
_STROKES = frozenset("il1|!")  # a reading made only of these is a railing, bollards or stripes, not text
EDGE_PX = 2                 # a box this close to a view border may have its text cut off
ZONE_FLAG = 0.5             # share of a box inside the photographer zone that flags it
REREAD_BELOW_CONF = 0.9
REREAD_SMALL_PX = 32        # box height in the view, about twice the letters' (RapidOCR grows boxes by 1.6);
REREAD_LARGE_PX = 64        # an unsure box taller than this isn't short of pixels, so no reread. The panorama
                            # has 1.3-1.9x the pixels per degree of a 1024 px view
REREAD_MARGIN = 1.3         # reread fov = max(w, h) * margin + pad, doubled margin when cut in every view
REREAD_PAD_DEG = 1.5
REREAD_MIN_FOV, REREAD_MAX_FOV = 4.0, 45.0
REREAD_MIN_SIZE = MIN_DET_SIDE  # so the detector reads a reread crop at the crop's own resolution
REREAD_SCALE = 1.0          # 1 = the panorama's own resolution at the crop centre
REREAD_PICK_LINE = 0.35     # a crop hit reads the sign's line when its centre is this close (x line height) ...
REREAD_PICK_INSIDE = 0.5    # ... this much of its width is inside the sign's box (grown by a quarter) ...
REREAD_PICK_HEIGHT = 2.0    # ... and its line height is within this factor of the sign's
REREAD_MIN_COVERAGE = 0.8   # share of the sign's width the reread must cover to replace the reading ...
REREAD_MIN_LENGTH = 0.75    # ... and its share of the reading's length, unless that reading was below SIGN_MIN_CONF
MAX_REREADS = 16
REREAD_BUDGET_S = 5.0       # MODEL_DECISIONS.md budgets 6-16 s for all of OCR; the views take about 6
OVERLAP_MIN = 0.3           # intersection over the smaller box for two hits to be compared at all
OVERLAP_SAME = 0.7          # boxes this coincident merge whatever their texts say
SIMILAR_MIN = 0.6
FRAGMENT_INSIDE = 0.6       # a sign this much inside a longer one, with a similar text, is a fragment of it
FRAGMENT_SIMILAR = 0.8
FRAGMENT_LONGER = 1.25      # a reading is a cut-off part of a copy at least this much longer ...
FRAGMENT_CONF_GAP = 0.15    # ... and at most this much less confident
NAME_MIN_CONF = 0.7
ROAD_MIN_CONF = 0.8         # a bare one-letter road code ("D3", "A46") read less surely than this is dropped
STRENGTHS = ("strong", "medium", "weak")


# -- engine -----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Reading:
    """One raw RapidOCR result: the detector's quadrilateral (4 x 2, image pixels), text and confidence."""
    quad: np.ndarray
    text: str
    confidence: float


def models_dir():
    """Where tools/setup_env.sh put the RapidOCR ONNX files (inside the installed rapidocr package)."""
    import rapidocr
    return Path(rapidocr.__file__).resolve().parent / "models"


@contextmanager
def _no_downloads():
    """Make RapidOCR raise instead of downloading a model or a dictionary."""
    from rapidocr.utils.download_file import DownloadFile
    original = DownloadFile.__dict__["run"]

    def refuse(cls, params):
        raise RuntimeError(f"RapidOCR tried to download {params.file_url}; run tools/setup_env.sh instead")

    DownloadFile.run = classmethod(refuse)
    try:
        yield
    finally:
        DownloadFile.run = original


class Engine:
    """RapidOCR with OpenVINO on the CPU, loaded once and reused for every image of every panorama."""

    def __init__(self, det=DEFAULT_MODEL, rec=DEFAULT_MODEL, *, threads=None, text_score=RAW_MIN_SCORE,
                 min_side=MIN_DET_SIDE, model_dir=None):
        if det not in DET_MODELS:
            raise ValueError(f"det must be one of {sorted(DET_MODELS)}, got {det!r}")
        if rec not in REC_MODELS:
            raise ValueError(f"rec must be one of {sorted(REC_MODELS)}, got {rec!r}")
        t0 = time.perf_counter()
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import EngineType, ModelType, OCRVersion
        folder = Path(model_dir) if model_dir else models_dir()
        params = {"Global.log_level": "error", "Global.text_score": float(text_score), "Global.use_cls": True,
                  "Det.limit_type": "min", "Det.limit_side_len": int(min_side)}
        self.files = {}
        for section, (version, model_type, lang, filename) in (("Det", DET_MODELS[det]), ("Rec", REC_MODELS[rec]),
                                                               ("Cls", CLS_MODEL)):
            path = folder / filename
            if not path.is_file():
                raise FileNotFoundError(f"{path} is missing: run tools/setup_env.sh (RapidOCR must not download it)")
            self.files[section.lower()] = filename
            params.update({f"{section}.engine_type": EngineType.OPENVINO, f"{section}.ocr_version": OCRVersion(version),
                           f"{section}.model_type": ModelType(model_type), f"{section}.lang_type": lang,
                           f"{section}.model_path": str(path)})
        if threads:
            params["EngineConfig.openvino.inference_num_threads"] = int(threads)
        with _no_downloads():
            self._ocr = RapidOCR(params=params)
            # RapidOCR loads each model on first use; load them now so load_s is the whole cost
            self._ocr._load_det_model()
            self._ocr._load_cls_model()
            self._ocr._load_rec_model()
        self.det, self.rec, self.threads = det, rec, threads
        self.text_score, self.min_side = float(text_score), int(min_side)
        self.load_s = round(time.perf_counter() - t0, 3)

    @property
    def name(self):
        """The model name for the run log: "PP-OCRv6-medium", or "<det> det + <rec> rec" for a mix."""
        return self.det if self.det == self.rec else f"{self.det} det + {self.rec} rec"

    def settings(self):
        import importlib.metadata as metadata
        return {"model": self.name, "det": self.det, "rec": self.rec, "cls": "PP-OCR v2.0 mobile direction classifier",
                "files": self.files, "lang": "pt (PP-OCRv6 multilingual)" if self.rec.startswith("PP-OCRv6")
                else "latin", "runtime": f"rapidocr {metadata.version('rapidocr')}, openvino "
                f"{metadata.version('openvino')}, CPU", "threads": self.threads or "OpenVINO default",
                "text_score": self.text_score, "det_min_side": self.min_side, "load_s": self.load_s}

    def read(self, image):
        """OCR one RGB uint8 image: ([Reading], {"det_s", "rec_s", "other_s", "total_s"})."""
        bgr = np.ascontiguousarray(np.asarray(image)[..., ::-1])  # RapidOCR takes arrays as BGR
        t0 = time.perf_counter()
        out = self._ocr(bgr)
        wall = time.perf_counter() - t0
        elapse = list(getattr(out, "elapse_list", None) or [])
        if len(elapse) == 3 and all(isinstance(x, float) for x in elapse):
            det, rec = elapse[0], elapse[1] + elapse[2]  # direction classifier counted with recognition
        else:
            det, rec = wall, 0.0  # nothing was found, so only the detector ran
        readings = []
        if getattr(out, "txts", None):
            for quad, text, score in zip(out.boxes, out.txts, out.scores):
                readings.append(Reading(np.asarray(quad, float).reshape(4, 2), str(text), float(score)))
        return readings, {"det_s": det, "rec_s": rec, "other_s": max(0.0, wall - det - rec), "total_s": wall}


# -- hits and signs ---------------------------------------------------------------------------------

@dataclass(eq=False)
class Hit:
    """One OCR reading in one image, with its box on the sphere."""
    text: str
    confidence: float
    view: str                # the view's name, or "reread:<sign_id>"
    quad: list               # [[x, y]] * 4 in the image's pixels, as the detector returned it
    box: dict                # {"yaw", "pitch", "w", "h"} in degrees
    height_px: float         # the line's height in the image: the quad's shorter side
    zone_fraction: float     # share of the box's pixels in the photographer zone
    at_edge: bool            # the box touches an image border, so the text may be cut off
    source: str = "view"     # view | reread
    raw_text: str = None     # RapidOCR's own text, when clean_reading changed it

    @property
    def in_photographer_zone(self):
        return self.zone_fraction >= ZONE_FLAG

    def to_dict(self):
        return {"view": self.view, "text": self.text, "raw_text": self.raw_text, "confidence": self.confidence,
                "box": self.box,
                "quad": [[round(x, 1), round(y, 1)] for x, y in self.quad], "height_px": self.height_px,
                "zone_fraction": self.zone_fraction, "at_edge": self.at_edge, "source": self.source}


# Scripts no sign in PT/ES/FR is written in, which the multilingual recogniser still outputs for shapes and
# texture: CJK ideographs and punctuation, kana, hangul, Yi
_FOREIGN = re.compile("[\u2e80-\u2fff\u3000-\u303f\u3040-\u30ff\u3100-\u31ff\u3200-\u9fff\ua000-\ua4cf"
                      "\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f]+")
_FULLWIDTH = {cp: cp - 0xFEE0 for cp in range(0xFF01, 0xFF5F)}


def clean_reading(text):
    """A raw OCR text with fullwidth forms as ASCII, foreign-script glyphs removed and spaces collapsed."""
    return " ".join(_FOREIGN.sub(" ", unicodedata.normalize("NFC", str(text)).translate(_FULLWIDTH)).split())


def make_hit(view, reading, source="view"):
    """A Reading in a View -> Hit, with its sphere box, line height and photographer-zone share."""
    quad = np.asarray(reading.quad, float).reshape(4, 2)
    h, w = view.image.shape[:2]
    x0, y0 = np.clip(quad.min(axis=0), 0, [w - 1, h - 1])
    x1, y1 = np.clip(quad.max(axis=0), 0, [w - 1, h - 1])
    sides = np.linalg.norm(quad - np.roll(quad, -1, axis=0), axis=1)  # top, right, bottom, left
    line_height = min((sides[0] + sides[2]) / 2, (sides[1] + sides[3]) / 2)
    region = view.mask[int(y0):int(math.ceil(y1)) + 1, int(x0):int(math.ceil(x1)) + 1]
    at_edge = x0 <= EDGE_PX or y0 <= EDGE_PX or x1 >= w - 1 - EDGE_PX or y1 >= h - 1 - EDGE_PX
    text = clean_reading(reading.text)
    return Hit(text=text, confidence=round(float(reading.confidence), 4), view=view.name,
               quad=quad.tolist(), box=box_to_sphere(view, x0, y0, x1, y1), height_px=round(float(line_height), 1),
               zone_fraction=round(float(region.mean()) if region.size else 0.0, 3), at_edge=bool(at_edge),
               source=source, raw_text=reading.text if reading.text != text else None)


@dataclass(eq=False)
class Sign:
    """One piece of text after merging the hits of overlapping views; text and confidence may come from a reread."""
    sign_id: str
    text: str
    confidence: float
    box: dict          # the sphere box of hits[0], the hit the reading was chosen from
    hits: list         # every view hit merged here, hits[0] first
    source: str = "view"   # where text and confidence come from: view | reread
    reread: dict = None    # the reread's reading and outcome, when one was made

    @property
    def views(self):
        return sorted({h.view for h in self.hits}, key=_view_order)

    @property
    def height_px(self):
        return self.hits[0].height_px

    @property
    def truncated(self):
        """Every view that read it cut it at a border."""
        return all(h.at_edge for h in self.hits)

    @property
    def in_photographer_zone(self):
        return max(h.zone_fraction for h in self.hits) >= ZONE_FLAG

    @property
    def alternatives(self):
        """The other distinct readings (by text key), the most confident copy of each, best first."""
        chosen = text_key(self.text)
        best = {}
        readings = [(h.text, h.confidence, h.view) for h in self.hits]
        if self.reread and self.reread.get("text"):
            readings.append((self.reread["text"], self.reread["confidence"], "reread"))
        for text, conf, source in readings:
            key = text_key(text)
            if key and key != chosen and (key not in best or conf > best[key]["confidence"]):
                best[key] = {"text": text, "confidence": conf, "source": source}
        return sorted(best.values(), key=lambda a: -a["confidence"])

    def to_dict(self):
        return {"sign_id": self.sign_id, "text": self.text, "confidence": self.confidence, "source": self.source,
                "box": self.box, "views": self.views, "in_photographer_zone": self.in_photographer_zone,
                "truncated": self.truncated, "height_px": self.height_px, "alternatives": self.alternatives,
                "reread": self.reread,
                "hits": [{"view": h.view, "text": h.text, "confidence": h.confidence, "at_edge": h.at_edge}
                         for h in self.hits]}


def _view_order(name):
    order = {"sky": 900, "ground": 901}
    m = re.fullmatch(r"h(\d{3})", name)
    return (int(m.group(1)) if m else order.get(name, 999), name)


# -- sphere boxes and text similarity ---------------------------------------------------------------

def _offsets(a, b):
    """(dx, dy) in degrees from box a's centre to box b's: yaw wrapped to [-180, 180) and scaled by cos(pitch)."""
    lat = math.radians((a["pitch"] + b["pitch"]) / 2)
    dx = ((b["yaw"] - a["yaw"] + 180) % 360 - 180) * max(math.cos(lat), 0.05)
    return dx, b["pitch"] - a["pitch"]


def _intersection(a, b, inflate=1.0):
    dx, dy = _offsets(a, b)
    aw, ah = a["w"] * inflate, a["h"] * inflate
    ix = max(0.0, min(aw / 2, dx + b["w"] / 2) - max(-aw / 2, dx - b["w"] / 2))
    iy = max(0.0, min(ah / 2, dy + b["h"] / 2) - max(-ah / 2, dy - b["h"] / 2))
    return ix * iy


def box_overlap(a, b):
    """Intersection of two sphere boxes over the smaller one's area, in [0, 1]; handles the 0/360 yaw seam.

    Boxes are compared in a tangent plane at their mean pitch, which is close enough for boxes of a few
    tens of degrees away from the zenith and nadir.
    """
    smaller = min(a["w"] * a["h"], b["w"] * b["h"])
    return _intersection(a, b) / smaller if smaller > 0 else 0.0


def box_inside(a, b):
    """Share of box a's area that lies inside box b."""
    area = a["w"] * a["h"]
    return _intersection(b, a) / area if area > 0 else 0.0


def text_key(text):
    """Case-, accent-, spacing- and punctuation-free form, for comparing readings ("Gestão e" -> "gestaoe")."""
    return normalise(text).replace(" ", "")


def text_similarity(a, b):
    """1 for the same text (case, accents, spacing aside); about 0.95 when one is a cut-off copy of the other."""
    a, b = text_key(a), text_key(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
    short, long_ = sorted((a, b), key=len)
    if len(short) < 3 or len(short) == len(long_):
        return ratio
    n = len(short)
    partial = max(SequenceMatcher(None, short, long_[i:i + n], autojunk=False).ratio()
                  for i in range(len(long_) - n + 1))
    return max(ratio, 0.95 * partial)


def _match_score(a, b):
    """How well hit b fits as another view's copy of hit a; 0 when it doesn't."""
    overlap = box_overlap(a.box, b.box)
    if overlap < OVERLAP_MIN:
        return 0.0
    similarity = text_similarity(a.text, b.text)
    if similarity >= SIMILAR_MIN:
        return overlap * similarity
    areas = sorted((a.box["w"] * a.box["h"], b.box["w"] * b.box["h"]))
    if overlap >= OVERLAP_SAME and areas[0] > 0 and areas[1] / areas[0] <= 2:
        return 0.5 * overlap  # the same box read two ways
    return 0.0


def _hit_rank(hit):
    """Sort key, best first: complete before cut off, then confidence, then length."""
    return (hit.at_edge, -hit.confidence, -len(text_key(hit.text)))


def best_hit(hits):
    """The hit a sign is read by: not a cut-off part of a longer, about as confident copy (a view border can
    cut a line without its box touching the border), then by _hit_rank."""
    def part_of_another(h):
        n = len(text_key(h.text))
        return any(len(text_key(o.text)) >= FRAGMENT_LONGER * n and o.confidence >= h.confidence - FRAGMENT_CONF_GAP
                   and text_similarity(h.text, o.text) >= FRAGMENT_SIMILAR for o in hits if o is not h)
    whole = [h for h in hits if not part_of_another(h)] or hits
    return min(whole, key=_hit_rank)


def dedup(hits):
    """Merge view hits into signs (see the module docstring); returns signs without IDs, in no set order.

    Greedy, best hits first: a hit joins the sign it matches best that has no hit from its view yet,
    otherwise it starts a sign. Fragments inside longer signs are then absorbed.
    """
    groups = []
    for hit in sorted(hits, key=_hit_rank):
        best, best_score = None, 0.0
        for group in groups:
            if any(h.view == hit.view for h in group):
                continue
            score = max(_match_score(h, hit) for h in group)
            if score > best_score:
                best, best_score = group, score
        if best is None:
            groups.append([hit])
        else:
            best.append(hit)
    signs = []
    for group in groups:
        first = best_hit(group)
        group = [first] + [h for h in group if h is not first]
        signs.append(Sign("", first.text, first.confidence, first.box, group))
    return absorb_fragments(signs)


def absorb_fragments(signs):
    """Fold each sign whose box and text lie inside a sign at least as long (a fragment, or the same sign twice)
    into that sign: its hits become alternatives."""
    kept = []
    for sign in sorted(signs, key=lambda s: (-len(text_key(s.text)), -s.confidence)):
        host = next((k for k in kept if box_inside(sign.box, k.box) >= FRAGMENT_INSIDE
                     and text_similarity(sign.text, k.text) >= FRAGMENT_SIMILAR), None)
        if host is None:
            kept.append(sign)
        else:
            host.hits.extend(sign.hits)
    return kept


# -- rereads ----------------------------------------------------------------------------------------

def reread_fov(box, margin=REREAD_MARGIN):
    """The field of view of a reread crop around a sphere box: just larger than the box, within the limits."""
    return min(max(max(box["w"], box["h"]) * margin + REREAD_PAD_DEG, REREAD_MIN_FOV), REREAD_MAX_FOV)


def reread_view(pano, box, *, margin=REREAD_MARGIN, scale=REREAD_SCALE, name="reread",
                photographer_mask_pct=DEFAULT_MASK_PCT):
    """A square View centred on a sphere box, its fov just larger than the box, at the panorama's own
    resolution times scale (never under REREAD_MIN_SIZE px). Also usable for VLM verification crops."""
    fov = reread_fov(box, margin)
    size = int(min(max(round(crop_size(fov, pano.shape[1]) * scale), REREAD_MIN_SIZE), MAX_CROP_SIZE))
    pitch = min(max(float(box["pitch"]), -90.0), 90.0)
    return cut_view(pano, box["yaw"], pitch, fov, size, name=name, photographer_mask_pct=photographer_mask_pct)


def needs_reread(sign):
    """Unsure and not large, small, or cut off in every view; at least two letters or digits; and narrow
    enough for a reread crop to show the whole box."""
    if len(text_key(sign.text)) < 2 or max(sign.box["w"], sign.box["h"]) + REREAD_PAD_DEG > REREAD_MAX_FOV:
        return False
    unsure = sign.confidence < REREAD_BELOW_CONF and sign.height_px < REREAD_LARGE_PX
    return unsure or sign.height_px < REREAD_SMALL_PX or sign.truncated


def reread_priority(sign):
    """Sort key, first reread first: digits, then readable (>= SIGN_MIN_CONF), then least confident, then smallest."""
    return (not any(c.isdigit() for c in sign.text), sign.confidence < SIGN_MIN_CONF, sign.confidence,
            sign.height_px)


def picks_for(target, hit, extend=False):
    """Whether a reread crop's hit reads the target's line: on the same line (centres within REREAD_PICK_LINE
    line heights), mostly within the target's width, and about as tall. Detector boxes are taller than the
    spacing of stacked lines, and a big neighbouring sign must not stand in for a small line. With extend
    (a sign cut by a border in every view), a hit may run past the target's ends: the rest of the line."""
    dx, dy = _offsets(target, hit.box)
    tall = max(target["h"], hit.box["h"])
    half = 1.25 * target["w"] / 2
    within = max(0.0, min(half, dx + hit.box["w"] / 2) - max(-half, dx - hit.box["w"] / 2))
    needed = REREAD_PICK_INSIDE * (min(hit.box["w"], 2 * half) if extend else hit.box["w"])
    heights = sorted((max(hit.box["h"], 1e-9), max(target["h"], 1e-9)))
    return abs(dy) <= REREAD_PICK_LINE * tall and within >= needed and heights[1] / heights[0] <= REREAD_PICK_HEIGHT


def combine_reread(hits, target, extend=False):
    """The crop hits that read the target (picks_for), in reading order -> (text, confidence, coverage), or None.

    Coverage is the share of the target's width that the picked boxes span. Confidence is the mean of the
    picked hits' confidences weighted by their text length.
    """
    picked = [h for h in hits if picks_for(target, h, extend)]
    if not picked:
        return None
    lines = []
    for hit in sorted(picked, key=lambda h: -h.box["pitch"]):
        line = lines[-1] if lines else None
        if line and abs(line[0].box["pitch"] - hit.box["pitch"]) < 0.6 * max(line[0].box["h"], hit.box["h"]):
            line.append(hit)
        else:
            lines.append([hit])
    words = [h for line in lines for h in sorted(line, key=lambda h: _offsets(target, h.box)[0])]
    text = " ".join(h.text for h in words)
    weights = [max(len(text_key(h.text)), 1) for h in words]
    confidence = sum(h.confidence * n for h, n in zip(words, weights)) / sum(weights)
    spans = sorted((_offsets(target, h.box)[0] - h.box["w"] / 2, _offsets(target, h.box)[0] + h.box["w"] / 2)
                   for h in words)
    covered, end, half = 0.0, -target["w"] / 2, target["w"] / 2
    for lo, hi in spans:
        lo, hi = max(lo, end), min(hi, half)
        if hi > lo:
            covered += hi - lo
            end = hi
    coverage = covered / target["w"] if target["w"] > 0 else 0.0
    return text, round(confidence, 4), round(min(coverage, 1.0), 3)


def reread_sign(engine, pano, sign, *, scale=REREAD_SCALE, photographer_mask_pct=DEFAULT_MASK_PCT):
    """Reread one sign at full resolution; updates sign.reread (and the reading when the reread wins).

    Returns (View, crop hits, timing) for the debug drawing and the timing totals.
    """
    extend = sign.truncated
    margin = REREAD_MARGIN * (2 if extend else 1)
    t0 = time.perf_counter()
    view = reread_view(pano, sign.box, margin=margin, scale=scale, name=f"reread:{sign.sign_id}",
                       photographer_mask_pct=photographer_mask_pct)
    cut_s = time.perf_counter() - t0
    readings, timing = engine.read(view.image)
    hits = [h for h in (make_hit(view, r, "reread") for r in readings) if text_key(h.text)]
    combined = combine_reread(hits, sign.box, extend)
    record = {"fov_deg": round(view.fov_deg, 2), "size_px": int(view.image.shape[0]), "extend": extend,
              "native_px": crop_size(view.fov_deg, pano.shape[1]), "crop_hits": len(hits),
              "elapsed_s": round(cut_s + timing["total_s"], 3), "text": None, "confidence": None, "coverage": 0.0,
              "chosen": False, "changed": False, "agrees": False, "outcome": "not_found"}
    if combined:
        text, conf, coverage = combined
        agrees = text_key(text) == text_key(sign.text)
        partial = coverage < REREAD_MIN_COVERAGE or (sign.confidence >= SIGN_MIN_CONF and len(text_key(text))
                                                     < REREAD_MIN_LENGTH * len(text_key(sign.text)))
        chosen = not partial and conf > sign.confidence
        record.update(text=text, confidence=conf, coverage=coverage, agrees=agrees, chosen=chosen,
                      changed=chosen and not agrees, original={"text": sign.text, "confidence": sign.confidence},
                      outcome="chosen" if chosen else "partial" if partial else "not_better")
        if chosen:
            sign.text, sign.confidence, sign.source = text, conf, "reread"
    sign.reread = record
    timing = {**timing, "cut_s": cut_s}
    return view, hits, timing


def _reread_stats(candidates=0):
    return {"candidates": candidates, "attempted": 0, "chosen": 0, "changed": 0, "agrees": 0, "partial": 0,
            "not_better": 0, "not_found": 0, "skipped_limit": 0, "skipped_budget": 0, "mean_confidence_gain": None}


def _reread_timing():
    return {"rereads_s": 0.0, "reread_detection_s": 0.0, "reread_recognition_s": 0.0, "reread_cut_s": 0.0}


def reread_signs(engine, pano, signs, *, max_rereads=MAX_REREADS, budget_s=REREAD_BUDGET_S, scale=REREAD_SCALE,
                 photographer_mask_pct=DEFAULT_MASK_PCT, keep_images=False):
    """Reread the signs that need it, in priority order, within max_rereads and budget_s.

    Returns (stats, timing, images): stats counts the outcomes; images maps sign_id -> (View, hits) when
    keep_images is set.
    """
    todo = sorted((s for s in signs if needs_reread(s)), key=reread_priority)
    stats, timing = _reread_stats(len(todo)), _reread_timing()
    images, gains = {}, []
    t0 = time.perf_counter()
    for sign in todo:
        if stats["attempted"] >= max_rereads:
            stats["skipped_limit"] += 1
            continue
        if time.perf_counter() - t0 > budget_s:
            stats["skipped_budget"] += 1
            continue
        before = sign.confidence
        view, hits, t = reread_sign(engine, pano, sign, scale=scale, photographer_mask_pct=photographer_mask_pct)
        stats["attempted"] += 1
        stats[sign.reread["outcome"]] += 1
        stats["changed"] += sign.reread["changed"]
        stats["agrees"] += sign.reread["agrees"]
        if sign.reread["chosen"]:
            gains.append(sign.confidence - before)
        timing["reread_detection_s"] += t["det_s"]
        timing["reread_recognition_s"] += t["rec_s"]
        timing["reread_cut_s"] += t["cut_s"]
        if keep_images:
            images[sign.sign_id] = (view, hits)
    timing["rereads_s"] = time.perf_counter() - t0
    if gains:
        stats["mean_confidence_gain"] = round(sum(gains) / len(gains), 4)
    return stats, timing, images


# -- parsing: shared helpers ------------------------------------------------------------------------

_DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"})
_SPACES = str.maketrans({c: " " for c in "\u00a0\u2007\u202f\t\n\r"})
_DIGIT_DOTS = re.compile("(?<=\\d)[\u00b7\u2022\u2219\u2027](?=\\d)")  # 4700·123, 239•123•456


def _clean(text):
    """NFC with every dash variant, and a dot or bullet between digits, as "-" and odd spaces as " ": parsers
    work on this, and spans refer to it."""
    text = unicodedata.normalize("NFC", str(text or "")).translate(_DASHES).translate(_SPACES)
    return _DIGIT_DOTS.sub("-", text)


def _fold(text):
    """Lower case without accents, exactly one character per character of text, so regex spans carry over."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch)[:1] or ch
        low = base.lower()
        out.append(low if len(low) == 1 else base)
    return "".join(out)


def _item(kind, raw, value, span, *, countries=(), regions=(), strength="weak", notes=(), details=None):
    return {"kind": kind, "raw": raw, "value": value, "countries": list(countries), "regions": list(regions),
            "strength": strength, "notes": list(notes), "details": dict(details or {}), "span": [int(span[0]),
                                                                                                 int(span[1])]}


def _region(country, level, name, code=None, **extra):
    region = {"country": country, "level": level, "name": name}
    if code is not None:
        region["code"] = code
    region.update(extra)
    return region


def _weaker(strength):
    return STRENGTHS[min(STRENGTHS.index(strength) + 1, len(STRENGTHS) - 1)]


def _alnum(text):
    return sum(c.isalnum() for c in text)


def _standalone(text, span, share):
    """The match is most of the text: at least `share` of its letters and digits, a leading band letter aside."""
    total = _alnum(text)
    core = re.sub(r"^\s*(?:EU|[PEF])\s+", "", text)
    inside = _alnum(text[span[0]:span[1]])
    return total > 0 and inside / max(min(total, _alnum(core)) or total, 1) >= share


_REPAIRABLE = re.compile(r"[0-9OoIl|+().·/-]*\d[0-9OoIl|+().·/-]*\d[0-9OoIl|+().·/-]*")


def _repair_digits(text):
    """O/o -> 0 and I/l/| -> 1 inside tokens that are otherwise numbers (same length as text)."""
    def fix(m):
        token = m.group(0)
        if sum(c.isdigit() for c in token) < 2 or not re.search(r"[OoIl|]", token):
            return token
        return token.translate(str.maketrans("OoIl|", "00111"))
    return re.sub(r"(?<![^\W\d_])" + _REPAIRABLE.pattern + r"(?![^\W\d_])", fix, text)


def _with_repairs(text, parser):
    """parser(text) plus what parser finds once OCR look-alikes are read as digits, one strength weaker."""
    found = parser(text)
    repaired = _repair_digits(text)
    if repaired != text:
        values = {(it["kind"], it["value"]) for it in found}
        for it in parser(repaired):
            if (it["kind"], it["value"]) in values:
                continue
            it["raw"] = text[it["span"][0]:it["span"][1]]
            it["strength"] = _weaker(it["strength"])
            it["notes"].append("digits repaired from OCR look-alikes (O as 0, I or l as 1)")
            it["details"]["repaired"] = True
            found.append(it)
    return found


# -- parsing: reference tables (external sources only, COUNTRY_CLUES.md 2 and research_notes/Country clues) --

PT_POSTAL_REGIONS = {
    "1": "Lisbon city", "2": "Lisbon region, Setúbal peninsula, Santarém, Oeste",
    "3": "Aveiro, Coimbra, Viseu, north Leiria", "4": "Porto, Braga, Viana do Castelo",
    "5": "Vila Real, Bragança, Douro", "6": "Castelo Branco, Guarda",
    "7": "Alentejo (Beja, Évora, Portalegre, south Setúbal)", "8": "Algarve",
    "9": "Madeira (90-94) or the Azores (95-99)",
}

_PT_LANDLINES = """
Norte: 22 Porto (Porto), 251 Valença (Viana do Castelo), 252 Vila Nova de Famalicão (Braga), 253 Braga (Braga),
257 Braga (Braga), 254 Peso da Régua (Vila Real), 255 Penafiel (Porto), 256 São João da Madeira (Aveiro),
258 Viana do Castelo (Viana do Castelo), 259 Vila Real (Vila Real), 273 Bragança (Bragança), 276 Chaves (Vila Real),
278 Mirandela (Bragança), 279 Moncorvo (Bragança)
| Centro: 231 Mealhada (Aveiro), 232 Viseu (Viseu), 233 Figueira da Foz (Coimbra), 234 Aveiro (Aveiro),
235 Arganil (Coimbra), 236 Pombal (Leiria), 238 Seia (Guarda), 239 Coimbra (Coimbra), 244 Leiria (Leiria),
271 Guarda (Guarda), 272 Castelo Branco (Castelo Branco), 274 Proença-a-Nova (Castelo Branco),
275 Covilhã (Castelo Branco), 277 Idanha-a-Nova (Castelo Branco)
| Lisbon and Tejo: 21 Lisboa (Lisboa), 241 Abrantes (Santarém), 243 Santarém (Santarém), 249 Torres Novas (Santarém),
261 Torres Vedras (Lisboa), 262 Caldas da Rainha (Leiria), 263 Vila Franca de Xira (Lisboa), 265 Setúbal (Setúbal)
| Alentejo: 242 Ponte de Sor (Portalegre), 245 Portalegre (Portalegre), 266 Évora (Évora), 268 Estremoz (Évora),
269 Santiago do Cacém (Setúbal), 283 Odemira (Beja), 284 Beja (Beja), 285 Moura (Beja), 286 Castro Verde (Beja)
| Algarve: 281 Tavira (Faro), 282 Portimão (Faro), 289 Faro (Faro)
| Islands: 291 Funchal (Madeira), 292 Horta (Azores), 295 Angra do Heroísmo (Azores), 296 Ponta Delgada (Azores)
"""

_ES_PROVINCES = """
01 Álava/Araba|País Vasco|945; 02 Albacete|Castilla-La Mancha|967; 03 Alicante/Alacant|C. Valenciana|965 966;
04 Almería|Andalucía|950; 05 Ávila|Castilla y León|920; 06 Badajoz|Extremadura|924; 07 Illes Balears|Illes Balears|971;
08 Barcelona|Cataluña|93; 09 Burgos|Castilla y León|947; 10 Cáceres|Extremadura|927; 11 Cádiz|Andalucía|956;
12 Castellón/Castelló|C. Valenciana|964; 13 Ciudad Real|Castilla-La Mancha|926; 14 Córdoba|Andalucía|957;
15 A Coruña|Galicia|981; 16 Cuenca|Castilla-La Mancha|969; 17 Girona|Cataluña|972; 18 Granada|Andalucía|958;
19 Guadalajara|Castilla-La Mancha|949; 20 Gipuzkoa|País Vasco|943; 21 Huelva|Andalucía|959; 22 Huesca|Aragón|974;
23 Jaén|Andalucía|953; 24 León|Castilla y León|987; 25 Lleida|Cataluña|973; 26 La Rioja|La Rioja|941;
27 Lugo|Galicia|982; 28 Madrid|Madrid|91; 29 Málaga|Andalucía|951 952; 30 Murcia|Murcia|968; 31 Navarra|Navarra|948;
32 Ourense|Galicia|988; 33 Asturias|Asturias|984 985; 34 Palencia|Castilla y León|979; 35 Las Palmas|Canarias|928;
36 Pontevedra|Galicia|986; 37 Salamanca|Castilla y León|923; 38 Santa Cruz de Tenerife|Canarias|922;
39 Cantabria|Cantabria|942; 40 Segovia|Castilla y León|921; 41 Sevilla|Andalucía|954 955; 42 Soria|Castilla y León|975;
43 Tarragona|Cataluña|977; 44 Teruel|Aragón|978; 45 Toledo|Castilla-La Mancha|925;
46 Valencia|C. Valenciana|960 961 962 963; 47 Valladolid|Castilla y León|983; 48 Bizkaia|País Vasco|944 946;
49 Zamora|Castilla y León|980; 50 Zaragoza|Aragón|976; 51 Ceuta|Ceuta|; 52 Melilla|Melilla|
"""

_ES_PLATE_CODES = ("A Alicante; AB Albacete; AL Almería; AV Ávila; B Barcelona; BA Badajoz; BI Bizkaia; BU Burgos; "
                   "C A Coruña; CA Cádiz; CC Cáceres; CE Ceuta; CO Córdoba; CR Ciudad Real; CS Castellón; CU Cuenca; "
                   "GC Las Palmas; GE Girona; GI Girona; GR Granada; GU Guadalajara; H Huelva; HU Huesca; "
                   "IB Illes Balears; J Jaén; L Lleida; LE León; LO La Rioja; LU Lugo; M Madrid; MA Málaga; "
                   "ML Melilla; MU Murcia; NA Navarra; O Asturias; OR Ourense; OU Ourense; P Palencia; "
                   "PM Illes Balears; PO Pontevedra; S Cantabria; SA Salamanca; SE Sevilla; SG Segovia; SO Soria; "
                   "SS Gipuzkoa; T Tarragona; TE Teruel; TF Santa Cruz de Tenerife; TO Toledo; V Valencia; "
                   "VA Valladolid; VI Álava; Z Zaragoza; ZA Zamora")

_FR_DEPARTMENTS = """
Hauts-de-France: 02 Aisne, 59 Nord, 60 Oise, 62 Pas-de-Calais, 80 Somme
| Normandie: 14 Calvados, 27 Eure, 50 Manche, 61 Orne, 76 Seine-Maritime
| Bretagne: 22 Côtes-d'Armor, 29 Finistère, 35 Ille-et-Vilaine, 56 Morbihan
| Pays de la Loire: 44 Loire-Atlantique, 49 Maine-et-Loire, 53 Mayenne, 72 Sarthe, 85 Vendée
| Centre-Val de Loire: 18 Cher, 28 Eure-et-Loir, 36 Indre, 37 Indre-et-Loire, 41 Loir-et-Cher, 45 Loiret
| Île-de-France: 75 Paris, 77 Seine-et-Marne, 78 Yvelines, 91 Essonne, 92 Hauts-de-Seine, 93 Seine-Saint-Denis,
94 Val-de-Marne, 95 Val-d'Oise
| Grand Est: 08 Ardennes, 10 Aube, 51 Marne, 52 Haute-Marne, 54 Meurthe-et-Moselle, 55 Meuse, 57 Moselle, 67 Bas-Rhin,
68 Haut-Rhin, 88 Vosges
| Bourgogne-Franche-Comté: 21 Côte-d'Or, 25 Doubs, 39 Jura, 58 Nièvre, 70 Haute-Saône, 71 Saône-et-Loire, 89 Yonne,
90 Territoire de Belfort
| Auvergne-Rhône-Alpes: 01 Ain, 03 Allier, 07 Ardèche, 15 Cantal, 26 Drôme, 38 Isère, 42 Loire, 43 Haute-Loire,
63 Puy-de-Dôme, 69 Rhône, 73 Savoie, 74 Haute-Savoie
| Nouvelle-Aquitaine: 16 Charente, 17 Charente-Maritime, 19 Corrèze, 23 Creuse, 24 Dordogne, 33 Gironde, 40 Landes,
47 Lot-et-Garonne, 64 Pyrénées-Atlantiques, 79 Deux-Sèvres, 86 Vienne, 87 Haute-Vienne
| Occitanie: 09 Ariège, 11 Aude, 12 Aveyron, 30 Gard, 31 Haute-Garonne, 32 Gers, 34 Hérault, 46 Lot, 48 Lozère,
65 Hautes-Pyrénées, 66 Pyrénées-Orientales, 81 Tarn, 82 Tarn-et-Garonne
| Provence-Alpes-Côte d'Azur: 04 Alpes-de-Haute-Provence, 05 Hautes-Alpes, 06 Alpes-Maritimes, 13 Bouches-du-Rhône,
83 Var, 84 Vaucluse
| Corse: 2A Corse-du-Sud, 2B Haute-Corse
"""

FR_PHONE_ZONES = {
    "1": "Île-de-France",
    "2": "north-west: Bretagne, Normandie, Pays de la Loire, Centre-Val de Loire",
    "3": "north-east: Hauts-de-France, Grand Est, Bourgogne-Franche-Comté",
    "4": "south-east: Auvergne-Rhône-Alpes, Provence-Alpes-Côte d'Azur, Corse, Languedoc-Roussillon (11, 30, 34, 48, 66)",
    "5": "south-west: Nouvelle-Aquitaine, Midi-Pyrénées (09, 12, 31, 32, 46, 65, 81, 82)",
}

# Official 3-letter municipality codes (DL 209/98 annex, via portugal.md 4.6): trail signs, E-REDES plates,
# CTT postal designations
_PT_MUNICIPAL_CODES = """
ABF Albufeira (Faro); ABT Abrantes (Santarém); ACB Alcobaça (Leiria); ACH Alcochete (Setúbal); ACN Alcanena (Santarém);
ACT Alcoutim (Faro); ADL Alandroal (Évora); ADV Almodôvar (Beja); AFE Alfândega da Fé (Bragança);
AGB Aguiar da Beira (Guarda); AGD Águeda (Aveiro); AGH Angra do Heroísmo (Açores); AGN Arganil (Coimbra);
AJT Aljustrel (Beja); AJZ Aljezur (Faro); ALB Albergaria-a-Velha (Aveiro); ALD Almeida (Guarda); ALJ Alijó (Vila Real);
ALM Almada (Setúbal); ALQ Alenquer (Lisboa); ALR Almeirim (Santarém); ALT Alter do Chão (Portalegre);
AMD Amadora (Lisboa); AMM Armamar (Viseu); AMR Amares (Braga); AMT Amarante (Porto); AND Anadia (Aveiro);
ANS Ansião (Leiria); APC Alpiarça (Santarém); ARC Arouca (Aveiro); ARL Arraiolos (Évora); ARR Arronches (Portalegre);
ARV Arruda dos Vinhos (Lisboa); ASL Alcácer do Sal (Setúbal); AVR Aveiro (Aveiro); AVS Avis (Portalegre);
AVT Alvito (Beja); AVV Arcos de Valdevez (Viana do Castelo); AVZ Alvaiázere (Leiria); AZB Azambuja (Lisboa);
BAO Baião (Porto); BBR Bombarral (Leiria); BCL Barcelos (Braga); BGC Bragança (Bragança); BJA Beja (Beja);
BMT Belmonte (Castelo Branco); BNV Benavente (Santarém); BRB Borba (Évora); BRC Barrancos (Beja); BRG Braga (Braga);
BRR Barreiro (Setúbal); BTC Boticas (Vila Real); BTL Batalha (Leiria); CBA Cuba (Beja);
CBC Cabeceiras de Basto (Braga); CBR Coimbra (Coimbra); CBT Celorico de Basto (Braga); CCH Coruche (Santarém);
CDN Condeixa-a-Nova (Coimbra); CDR Castro Daire (Viseu); CDV Cadaval (Lisboa); CHM Chamusca (Santarém);
CHT Calheta (São Jorge, Açores); CHV Chaves (Vila Real); CLB Celorico da Beira (Guarda); CLD Caldas da Rainha (Leiria);
CLT Calheta (Madeira); CML Câmara de Lobos (Madeira); CMN Caminha (Viana do Castelo); CMR Campo Maior (Portalegre);
CNF Cinfães (Viseu); CNS Constância (Santarém); CNT Cantanhede (Coimbra); CPR Castanheira de Pera (Leiria);
CPV Castelo de Paiva (Aveiro); CRS Carregal do Sal (Viseu); CRT Crato (Portalegre); CRV Corvo (Açores);
CRZ Carrazeda de Ansiães (Bragança); CSC Cascais (Lisboa); CTB Castelo Branco (Castelo Branco); CTM Castro Marim (Faro);
CTX Cartaxo (Santarém); CVD Castelo de Vide (Portalegre); CVL Covilhã (Castelo Branco); CVR Castro Verde (Beja);
ELV Elvas (Portalegre); ENT Entroncamento (Santarém); EPS Esposende (Braga); ESP Espinho (Aveiro);
ETR Estarreja (Aveiro); ETZ Estremoz (Évora); EVR Évora (Évora); FAF Fafe (Braga); FAG Fornos de Algodres (Guarda);
FAL Ferreira do Alentejo (Beja); FAR Faro (Faro); FCR Figueira de Castelo Rodrigo (Guarda);
FEC Freixo de Espada à Cinta (Bragança); FIG Figueira da Foz (Coimbra); FLG Felgueiras (Porto); FNC Funchal (Madeira);
FND Fundão (Castelo Branco); FTR Fronteira (Portalegre); FVN Figueiró dos Vinhos (Leiria);
FZZ Ferreira do Zêzere (Santarém); GAV Gavião (Portalegre); GDL Grândola (Setúbal); GDM Gondomar (Porto);
GLG Golegã (Santarém); GMR Guimarães (Braga); GOI Góis (Coimbra); GRD Guarda (Guarda); GVA Gouveia (Guarda);
HRT Horta (Açores); IDN Idanha-a-Nova (Castelo Branco); ILH Ílhavo (Aveiro); LAG Lagoa (São Miguel, Açores);
LGA Lagoa (Algarve, Faro); LGF Lajes das Flores (Açores); LGP Lajes do Pico (Açores); LGS Lagos (Faro);
LLE Loulé (Faro); LMG Lamego (Viseu); LNH Lourinhã (Lisboa); LRA Leiria (Leiria); LRS Loures (Lisboa);
LSA Lousã (Coimbra); LSB Lisboa (Lisboa); LSD Lousada (Porto); MAC Mação (Santarém); MAD Madalena (Açores);
MAI Maia (Porto); MBR Moimenta da Beira (Viseu); MCD Macedo de Cavaleiros (Bragança); MCH Machico (Madeira);
MCN Marco de Canaveses (Porto); MCQ Monchique (Faro); MCV Miranda do Corvo (Coimbra); MDB Mondim de Basto (Vila Real);
MDL Mirandela (Bragança); MDR Miranda do Douro (Bragança); MED Mêda (Guarda); MFR Mafra (Lisboa);
MFT Monforte (Portalegre); MGD Mogadouro (Bragança); MGL Mangualde (Viseu); MGR Marinha Grande (Leiria);
MIR Mira (Coimbra); MLD Mealhada (Aveiro); MLG Melgaço (Viana do Castelo); MMN Montemor-o-Novo (Évora);
MMV Montemor-o-Velho (Coimbra); MNC Monção (Viana do Castelo); MOR Mora (Évora); MOU Mourão (Évora); MRA Moura (Beja);
MRS Murtosa (Aveiro); MRT Mortágua (Viseu); MRV Marvão (Portalegre); MSF Mesão Frio (Vila Real); MTA Moita (Setúbal);
MTG Manteigas (Guarda); MTJ Montijo (Setúbal); MTL Mértola (Beja); MTR Montalegre (Vila Real); MTS Matosinhos (Porto);
MUR Murça (Vila Real); NIS Nisa (Portalegre); NLS Nelas (Viseu); NRD Nordeste (Açores); NZR Nazaré (Leiria);
OAZ Oliveira de Azeméis (Aveiro); OBD Óbidos (Leiria); OBR Oliveira do Bairro (Aveiro); ODM Odemira (Beja);
ODV Odivelas (Lisboa); OER Oeiras (Lisboa); OFR Oliveira de Frades (Viseu); OHP Oliveira do Hospital (Coimbra);
OLH Olhão (Faro); OLR Oleiros (Castelo Branco); ORM Ourém (Santarém); ORQ Ourique (Beja); OVR Ovar (Aveiro);
PBL Pombal (Leiria); PCR Paredes de Coura (Viana do Castelo); PCT Penalva do Castelo (Viseu); PCV Penacova (Coimbra);
PDL Ponta Delgada (Açores); PFR Paços de Ferreira (Porto); PGR Pedrógão Grande (Leiria); PLM Palmela (Setúbal);
PMS Porto de Mós (Leiria); PMZ Porto Moniz (Madeira); PNC Penamacor (Castelo Branco); PND Penedono (Viseu);
PNF Penafiel (Porto); PNH Pinhel (Guarda); PNI Peniche (Leiria); PNL Penela (Coimbra);
PNV Proença-a-Nova (Castelo Branco); PPS Pampilhosa da Serra (Coimbra); PRD Paredes (Porto);
PRG Peso da Régua (Vila Real); PRL Portel (Évora); PRS Vila Nova de Poiares (Coimbra); PRT Porto (Porto);
PSR Ponte de Sor (Portalegre); PST Porto Santo (Madeira); PTB Ponte da Barca (Viana do Castelo);
PTG Portalegre (Portalegre); PTL Ponte de Lima (Viana do Castelo); PTM Portimão (Faro); PTS Ponta do Sol (Madeira);
PVC Povoação (Açores); PVL Póvoa de Lanhoso (Braga); PVZ Póvoa de Varzim (Porto); RBR Ribeira Brava (Madeira);
RDD Redondo (Évora); RGR Ribeira Grande (Açores); RMR Rio Maior (Santarém); RMZ Reguengos de Monsaraz (Évora);
RPN Ribeira de Pena (Vila Real); RSD Resende (Viseu); SAT Sátão (Viseu); SBA São Brás de Alportel (Faro);
SBG Sabugal (Guarda); SBR Sabrosa (Vila Real); SCD Santa Comba Dão (Viseu); SCF Santa Cruz das Flores (Açores);
SCG Santa Cruz da Graciosa (Açores); SCR Santa Cruz (Madeira); SEI Seia (Guarda); SJM São João da Madeira (Aveiro);
SJP São João da Pesqueira (Viseu); SLV Silves (Faro); SMA Sobral de Monte Agraço (Lisboa);
SMG Salvaterra de Magos (Santarém); SMP Santa Marta de Penaguião (Vila Real); SNS Sines (Setúbal); SNT Sintra (Lisboa);
SPS São Pedro do Sul (Viseu); SRD Sardoal (Santarém); SRE Soure (Coimbra); SRN Sernancelhe (Viseu); SRP Serpa (Beja);
SRQ São Roque do Pico (Açores); SRT Sertã (Castelo Branco); SSB Sesimbra (Setúbal); SSL Sousel (Portalegre);
STB Setúbal (Setúbal); STC Santiago do Cacém (Setúbal); STN Santana (Madeira); STR Santarém (Santarém);
STS Santo Tirso (Porto); SVC São Vicente (Madeira); SVV Sever do Vouga (Aveiro); SXL Seixal (Setúbal);
TBC Tabuaço (Viseu); TBR Terras de Bouro (Braga); TBU Tábua (Coimbra); TCS Trancoso (Guarda);
TMC Torre de Moncorvo (Bragança); TMR Tomar (Santarém); TND Tondela (Viseu); TNV Torres Novas (Santarém);
TRC Tarouca (Viseu); TRF Trofa (Porto); TVD Torres Vedras (Lisboa); TVR Tavira (Faro); VBP Vila do Bispo (Faro);
VCD Vila do Conde (Porto); VCT Viana do Castelo (Viana do Castelo); VDG Vidigueira (Beja);
VFC Vila Franca do Campo (Açores); VFL Vila Flor (Bragança); VFR Santa Maria da Feira (Aveiro);
VFX Vila Franca de Xira (Lisboa); VGS Vagos (Aveiro); VIS Viseu (Viseu); VIZ Vizela (Braga);
VLC Vale de Cambra (Aveiro); VLF Vila Nova de Foz Côa (Guarda); VLG Valongo (Porto); VLN Valença (Viana do Castelo);
VLP Valpaços (Vila Real); VLR Vila de Rei (Castelo Branco); VLS Velas (Açores); VMS Vimioso (Bragança);
VNB Vila Nova da Barquinha (Santarém); VNC Vila Nova de Cerveira (Viana do Castelo); VND Vendas Novas (Évora);
VNF Vila Nova de Famalicão (Braga); VNG Vila Nova de Gaia (Porto); VNH Vinhais (Bragança);
VNP Vila Nova de Paiva (Viseu); VNT Viana do Alentejo (Évora); VPA Vila Pouca de Aguiar (Vila Real);
VPT Vila do Porto (Açores); VPV Praia da Vitória (Açores); VRL Vila Real (Vila Real); VRM Vieira do Minho (Braga);
VRS Vila Real de Santo António (Faro); VVC Vila Viçosa (Évora); VVD Vila Verde (Braga);
VVR Vila Velha de Ródão (Castelo Branco); VZL Vouzela (Viseu)
"""

# Hyphenated Spanish road prefixes (spain.md 4.4); a prefix not listed here is not read as a Spanish road
ES_ROAD_PREFIXES = {
    "AP": "national toll motorway", "A": "national autovía, or a regional road in Andalucía, Aragón or Álava",
    "N": "national road", "R": "Madrid radial toll road", "AS": "Asturias", "CA": "Cantabria or Cádiz",
    "CM": "Castilla-La Mancha", "CL": "Castilla y León", "C": "Cataluña (or an old comarcal road)",
    "EX": "Extremadura", "AG": "Galicia (motorway)", "VG": "Galicia (high-capacity road)", "M": "Madrid",
    "RM": "Murcia", "MU": "Murcia", "NA": "Navarra", "LR": "La Rioja",
    "CV": "C. Valenciana (or a camino vecinal)", "Ma": "Mallorca", "Me": "Menorca", "EI": "Ibiza",
    "PM": "Formentera", "GC": "Gran Canaria", "TF": "Tenerife", "LZ": "Lanzarote", "FV": "Fuerteventura",
    "LP": "La Palma or Lleida (provincial)", "HI": "El Hierro", "GM": "La Gomera", "AL": "Almería",
    "ALP": "Almería", "CO": "Córdoba", "CP": "Córdoba or A Coruña (provincial)", "GR": "Granada",
    "HU": "Huesca or Huelva", "HV": "Huelva", "HF": "Huelva", "H": "Huelva", "JA": "Jaén", "JV": "Jaén",
    "JF": "Jaén", "MA": "Málaga", "SE": "Sevilla", "TE": "Teruel", "Z": "Zaragoza", "ZP": "Zaragoza",
    "AB": "Albacete", "CR": "Ciudad Real", "CU": "Cuenca", "CUV": "Cuenca", "GU": "Guadalajara", "TO": "Toledo",
    "AV": "Ávila", "BU": "Burgos", "LE": "León", "P": "Palencia", "PP": "Palencia", "SA": "Salamanca",
    "DSA": "Salamanca", "SG": "Segovia", "SO": "Soria", "VA": "Valladolid", "VP": "Valladolid", "ZA": "Zamora",
    "B": "Barcelona", "BV": "Barcelona", "BP": "Barcelona", "GI": "Girona or Gipuzkoa", "GIV": "Girona",
    "GIP": "Girona", "L": "Lleida", "LV": "Lleida", "LL": "Lleida", "T": "Tarragona", "TV": "Tarragona",
    "TP": "Tarragona", "BA": "Badajoz", "CC": "Cáceres", "AC": "A Coruña", "DP": "A Coruña", "LU": "Lugo",
    "OU": "Ourense", "PO": "Pontevedra", "EP": "Pontevedra", "BI": "Bizkaia", "PA": "Pamplona",
    "S": "Santander (Cantabria)", "O": "Oviedo (Asturias)", "GJ": "Gijón", "AI": "Avilés",
    "SC": "Santiago de Compostela", "FE": "Ferrol", "CT": "Cartagena", "EL": "Elche", "CS": "Castellón",
    "V": "Valencia", "PT": "Puertollano", "LO": "Logroño", "CE": "Ceuta", "ML": "Melilla",
}
_ES_SINGLE_LETTER = {"A", "N", "R", "M", "C", "B", "H", "L", "P", "S", "T", "V", "Z", "O"}

# City access and ring roads (spain.md 4.4); "a..b" is every number from a to b
_ES_CITY_ROADS = ("AB-20 Albacete; AC-10/11/12/14/15 A Coruña; AI-81/82/83 Avilés; AL-12/14 Almería; AV-20 Ávila; "
                  "B-10/20/23/30/40 Barcelona; BA-11/20 Badajoz; BI-10/11/20/30 Bilbao; BU-11/12/30 Burgos; "
                  "CA-31/32 El Puerto de Santa María; CA-33..37 Cádiz bay; CC-11 Cáceres; CO-31/32 Córdoba; "
                  "CS-20/22 Castellón; CT-31..34 Cartagena; CU-11 Cuenca; EL-20 Elche; FE-11..15 Ferrol; "
                  "GI-11/20/21/40/41 San Sebastián; GJ-10/20/81/82 Gijón; GR-12/30/43 Granada; GR-14/16 Motril; "
                  "H-30/31 Huelva; HU-20 Huesca; LE-11/12/20/30 León; LL-11/12 Lleida; LO-20 Logroño; "
                  "LU-11/12 Lugo; M-11..50 Madrid; MA-20..30 Málaga; MU-30/32/33 Murcia; O-11/12/14 Oviedo; "
                  "OU-11 Ourense; P-11/12 Palencia; PA-30..36 Pamplona; NA-30/32 Pamplona; PO-10/11/12 Pontevedra; "
                  "PT-10 Puertollano; S-10/20/21/30 Santander; SA-11/20 Salamanca; SC-11/20/21/30 Santiago de "
                  "Compostela; SE-20/30/40 Sevilla; SG-20 Segovia; SO-20 Soria; T-11 Reus; TO-20..23 Toledo; "
                  "V-11..31 Valencia; VA-11/12/20/30 Valladolid; VG-11/20 Vigo; VG-21/31/41 Vitoria-Gasteiz; "
                  "Z-30/40/50 Zaragoza; ZA-11/12/13/20 Zamora")


def _load_tables():
    landlines = {}
    for block in _PT_LANDLINES.split("|"):
        macro, entries = block.split(":", 1)
        for code, area, district in re.findall(r"(\d{2,3}) ([^,(]+?) \(([^)]+)\)", entries):
            landlines[code] = {"area": area, "district": district, "macro_region": macro.strip()}
    provinces, es_phone = {}, {}
    for entry in _ES_PROVINCES.replace("\n", " ").split(";"):
        code, rest = entry.strip().split(" ", 1)
        name, community, phones = rest.split("|")
        provinces[code] = {"name": name, "community": community}
        for prefix in phones.split():
            es_phone[prefix] = code
    plate_codes = dict(e.strip().split(" ", 1) for e in _ES_PLATE_CODES.split(";"))
    departments = {}
    for block in _FR_DEPARTMENTS.replace("\n", " ").split("|"):
        region, entries = block.split(":", 1)
        for entry in entries.split(","):
            code, name = entry.strip().split(" ", 1)
            departments[code] = {"name": name, "region": region.strip()}
    municipal = {code: {"municipality": name, "district": district}
                 for code, name, district in re.findall(r"([A-Z]{3}) ([^;(]+?) \(([^)]+)\)", _PT_MUNICIPAL_CODES)}
    city_roads = {}
    for entry in _ES_CITY_ROADS.split(";"):
        m = re.fullmatch(r"\s*([A-Z]+)-([\d/.]+) (.+?)\s*", entry)
        prefix, numbers, city = m.groups()
        if ".." in numbers:
            lo, hi = map(int, numbers.split(".."))
            nums = range(lo, hi + 1)
        else:
            nums = map(int, numbers.split("/"))
        for n in nums:
            city_roads[(prefix, n)] = city
    return landlines, provinces, es_phone, plate_codes, departments, municipal, city_roads


(PT_LANDLINES, ES_PROVINCES, ES_PHONE_PREFIXES, ES_PLATE_CODES, FR_DEPARTMENTS, PT_MUNICIPAL_CODES,
 ES_CITY_ROADS) = _load_tables()

_ES_NONGEOGRAPHIC = {"800", "803", "806", "807", "900", "901", "902", "905", "907", "908", "909", "940"}
_FIVE_DIGIT_COLLISIONS = {  # COUNTRY_CLUES.md 2, "Collisions to resolve with the language or other cues"
    "17": "17 is Charente-Maritime or Girona", "20": "20 is Corsica or Gipuzkoa",
    "31": "31 is Haute-Garonne or Navarra",
}


# -- parsing: postcodes -----------------------------------------------------------------------------

_PT_POSTCODE = re.compile(r"(?<!\d)([1-9]\d{3})(?: ?- ?| (?=\d{3} +[A-ZÀ-Ý]{3}))(\d{3})(?!\d)(?! ?-\d)")
_PT_LOCALITY = re.compile(r" +([A-ZÀ-Ý][A-ZÀ-Ý'. -]{1,30}[A-ZÀ-Ý])")
_FIVE_DIGITS = re.compile(r"(?<![\d,/])(?<!\d\.)(\d{5})(?![\d/])(?![.,]\d)")
_ES_POSTCODE_CONTEXT = re.compile(r"(?:\bc ?\. ?p\b ?\.?|\bcp\b|\bc/p|codigo postal|cod\. ?postal|codi postal"
                                  r"|posta kodea|(?<![a-z])e ?-)\s*[:.]?\s*$")
_FR_POSTCODE_CONTEXT = re.compile(r"(?:code postal|(?<![a-z])f ?-)\s*[:.]?\s*$")
_NUMBER_CONTEXT = re.compile(r"(?:\btel|\btlf|\bfax|\bn|\bno|\bnum|\bref|\blote|\bkm|\bcif|\bnif)\b\s*\.?\s*[:.º°o]?\s*$")
_NAME_AFTER = re.compile(r"[ ,-]*\(? *([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+(?: +[A-Za-zÀ-ÿ'’-]+){0,4})")
_UNIT_WORDS = frozenset("km m kg g l eur euro euros habitantes hab pts ptas m2 ha cv kw w v mm cm tel fax ano anos "
                        "an ans".split())


def _name_after(text, pos):
    m = _NAME_AFTER.match(text, pos)
    if not m:
        return None
    first = _fold(m.group(1).split()[0])
    return None if first in _UNIT_WORDS or len(first) < 2 else m.group(1)


def parse_postcodes(text):
    """PT 4-3 postcodes (strong), and 5-digit ES/FR codes only with context (COUNTRY_CLUES.md 2).

    A 5-digit code counts when "C.P." / "Código Postal" / "E-" (Spain), "Code postal" / "F-" / CEDEX
    (France) or a following name ("28013 Madrid", "75011 PARIS") goes with it. Prefixes 01-52 fit
    both countries unless the context says which.
    """
    return _with_repairs(_clean(text), _postcodes)


def _postcodes(text):
    folded = _fold(text)
    items = []
    for m in _PT_POSTCODE.finditer(text):
        prefix, value = m.group(1), f"{m.group(1)}-{m.group(2)}"
        hyphen = "-" in m.group(0)
        locality = _PT_LOCALITY.match(text, m.end())
        if not hyphen and (not locality or _fold(locality.group(1).split()[0]) in _UNIT_WORDS):
            continue  # without its hyphen, a 4-3 code counts only before a locality in capitals, as CTT writes it
        region = PT_POSTAL_REGIONS[prefix[0]]
        if prefix[0] == "9":
            region = "Madeira" if int(prefix[:2]) <= 94 else "Azores"
        details = {"prefix": prefix, "fourth_digit": {"0": "municipality seat", "5": "not a seat"}.get(
            prefix[3], "large designated recipient")}
        if locality:
            details["locality"] = locality.group(1).strip()
        notes = ["the 4-digit prefix gives the municipality: resolve with names.postcode()"]
        if not hyphen:
            notes.append("read without its hyphen, which OCR can drop")
        items.append(_item("postcode", m.group(0), value, m.span(), countries=["PT"],
                           regions=[_region("PT", "postal region", region, prefix[0])],
                           strength="strong" if hyphen else "medium", notes=notes, details=details))
    for m in _FIVE_DIGITS.finditer(text):
        code = m.group(1)
        prefix = int(code[:2])
        es_ok, fr_ok = 1 <= prefix <= 52, 1 <= prefix <= 95
        before, after = folded[max(0, m.start() - 24):m.start()], folded[m.end():]
        if not (es_ok or fr_ok) or _NUMBER_CONTEXT.search(before):
            continue
        es_ctx = bool(_ES_POSTCODE_CONTEXT.search(before))
        fr_ctx = bool(_FR_POSTCODE_CONTEXT.search(before)) or bool(re.match(r"[^\d]{0,40}\bcedex\b", after))
        name = _name_after(text, m.end())
        if not (es_ctx or fr_ctx or name):
            continue
        countries = [c for c, ok in (("ES", es_ok), ("FR", fr_ok)) if ok]
        if es_ctx != fr_ctx:
            countries = [c for c in countries if c == ("ES" if es_ctx else "FR")]
        if not countries:
            continue
        regions, notes, details = [], [], {"context": "postcode word" if es_ctx or fr_ctx else "name after it"}
        if name:
            details["name_after"] = name
        if "ES" in countries:
            province = ES_PROVINCES[code[:2]]
            regions.append(_region("ES", "province", province["name"], code[:2], community=province["community"]))
            if code[2] == "0":
                details["es_capital_area"] = "a third digit of 0 marks the provincial capital"
        if "FR" in countries:
            dept = ("2B" if code[2] in "246" else "2A") if code[:2] == "20" else code[:2]  # 20700 AJACCIO CEDEX 9
            info = FR_DEPARTMENTS[dept]
            regions.append(_region("FR", "department", info["name"], dept, region=info["region"]))
            n = int(code)
            if code.endswith("000"):
                details["fr_prefecture"] = "xx000 is the prefecture"
            if 75001 <= n <= 75020 or n == 75116 or 69001 <= n <= 69009 or 13001 <= n <= 13016:
                details["fr_arrondissement"] = int(code[3:])
            if code.endswith("900"):
                notes.append("xx900 is a La Banque Postale centre: not geographic")
        if len(countries) == 2:
            notes.append(f"5-digit codes 01-52 are a Spanish province or a French department; decide with the "
                         f"language or the name")
            if code[:2] in _FIVE_DIGIT_COLLISIONS:
                notes.append(_FIVE_DIGIT_COLLISIONS[code[:2]])
        items.append(_item("postcode", m.group(0), code, m.span(), countries=countries, regions=regions,
                           strength="strong" if len(countries) == 1 else "medium", notes=notes, details=details))
    return items


# -- parsing: phone numbers -------------------------------------------------------------------------

_PHONE_PATTERNS = (  # (country, regex): the national number is group "num"; "intl" is the country code
    ("PT", re.compile(r"(?<![\d+])(?P<intl>\(?(?:\+|00) ?351\)?[ .-]?)?(?P<num>(?:2\d|9[01236])(?:[ .-]?\d){7})(?!\d)")),
    ("PT", re.compile(r"(?<![\d+])(?P<intl>\(?(?:\+|00) ?351\)?[ .-]?)?(?P<num>(?:70[78]|76\d|80[089])(?:[ .-]?\d){6})"
                      r"(?!\d)")),
    ("ES", re.compile(r"(?<![\d+])(?P<intl>\(?(?:\+|00) ?34\)?[ .-]?)?(?P<num>[6789](?:[ .-]?\d){8})(?!\d)")),
    ("FR", re.compile(r"(?<![\d+])(?P<intl>\(?(?:\+|00) ?33\)? ?(?:\(0\) ?)?)(?P<num>[1-9](?:[ .-]?\d{2}){4})(?!\d)")),
    ("FR", re.compile(r"(?<![\d+])(?P<intl>)(?P<num>0[1-9](?:[ .-]?\d{2}){4})(?!\d)")),
)
_PHONE_CONTEXT = re.compile(r"\b(?:tel|telf|telef|telefone|telefono|telephone|tlf|tlm|telm|tm|movel|telemovel|movil"
                            r"|mobile|portable|fax|contacto|contactos|contacte|contactar|contact|reservas|reservations"
                            r"|whatsapp|informacoes|informaciones|renseignements|ligue|llame|appelez|vende|aluga"
                            r"|arrenda|trespassa|vendo|alugo|alquila|alquiler|vendre|louer|tfno|tlfno)\b|[☎✆📞]")
_NOT_PHONE_CONTEXT = re.compile(r"\b(?:nif|nipc|contribuinte|cif|nie|siret|siren|tva|iban|nib|alvara|licenca|registo"
                                r"|rnal|rnet|ref|proc|processo)\b[^\d]{0,6}$")


def _pt_phone(d):
    """9 national digits -> (interpretation, region or None, geographic?)."""
    if d[0] == "2":
        code = d[:2] if d[:2] in ("21", "22") else d[:3]
        info = PT_LANDLINES.get(code)
        if info:
            return f"landline, area {code} {info['area']}", _region("PT", "landline area", info["area"], code,
                                                                    district=info["district"],
                                                                    macro_region=info["macro_region"]), True
        return f"landline, unassigned area code {code}", None, False
    if d[:2] in ("90", "91", "92", "93", "96"):
        return "mobile (no region)", None, False
    return "non-geographic (707/708/76x shared cost, 800 freephone, 808/809 shared cost)", None, False


def _es_phone(d):
    if d[0] == "6" or (d[0] == "7" and d[1] != "0"):
        return "mobile (no region)", None, False
    if d[:2] == "70" or d[:3] in _ES_NONGEOGRAPHIC:
        return "non-geographic", None, False
    if d[:2] in ("91", "81"):
        code = "28"
    elif d[:2] in ("93", "83"):
        code = "08"
    else:
        code = ES_PHONE_PREFIXES.get("9" + d[1:3])
    if code is None:
        return "landline, unknown province", None, False
    province = ES_PROVINCES[code]
    note = {"956": " (also Ceuta)", "952": " (also Melilla)"}.get("9" + d[1:3], "")
    return (f"landline, {province['name']}{note}",
            _region("ES", "province", province["name"], code, community=province["community"]), True)


def _fr_phone(d10):
    zone = d10[1]
    if zone in FR_PHONE_ZONES:
        return f"landline, zone 0{zone}", _region("FR", "phone zone", FR_PHONE_ZONES[zone], "0" + zone), True
    return {"6": "mobile (no region)", "7": "mobile (no region)", "8": "special or freephone",
            "9": "VoIP (non-geographic)"}.get(zone, "unknown"), None, False


def _grouping(raw):
    return [len(g) for g in re.split(r"[ .-]+", re.sub(r"^\(?(?:\+|00) ?\d+\)?", "", raw).replace("(0)", "").strip())
            if g]


def parse_phones(text, context=""):
    """PT, ES and FR numbers (COUNTRY_CLUES.md 2): landline area -> region, mobiles give the country only.

    A 9-digit number starting 90-93 or 96 without +351/+34 is a Portuguese mobile or a Spanish landline
    (91 Madrid, 93 Barcelona, 96x Valencia/Alicante): both stay, with the digit grouping as a hint. A
    number with neither a country code nor a phone word (Tel., Tlm., Vende-se ...) in the text or in
    `context` (the other lines of the same panel) is one strength weaker.
    """
    return _with_repairs(_clean(text), lambda t: _phones(t, context))


def _phones(text, context=""):
    folded = _fold(text)
    found = []
    for country, rx in _PHONE_PATTERNS:
        for m in rx.finditer(text):
            if _NOT_PHONE_CONTEXT.search(folded[max(0, m.start() - 20):m.start()]):
                continue
            digits = re.sub(r"\D", "", m.group("num"))
            if len(set(digits.lstrip("0"))) <= 1:
                continue  # 666 666 666: a placeholder, or texture read as digits (as _STROKES for letters)
            found.append({"country": country, "span": m.span(), "num_span": m.span("num"),
                          "intl": bool(m.group("intl")), "digits": digits})
    # An explicit country code settles the country: drop every other reading of the same digits
    accepted = [f for f in found if f["intl"]]
    rest = [f for f in found if not f["intl"] and not any(_overlaps(f["num_span"], a["num_span"]) for a in accepted)]
    groups = [[a] for a in accepted]
    for f in rest:
        group = next((g for g in groups if g[0]["num_span"] == f["num_span"]), None)
        if group is None:
            groups.append([f])
        elif all(x["country"] != f["country"] for x in group):
            group.append(f)
    phone_word = ("same line" if _PHONE_CONTEXT.search(folded) else
                  "same panel" if context and _PHONE_CONTEXT.search(_fold(_clean(context))) else None)
    items = []
    for group in sorted(groups, key=lambda g: g[0]["num_span"]):
        start, end = min(f["span"][0] for f in group), max(f["span"][1] for f in group)
        raw = text[start:end]
        countries, regions, readings, geographic = [], [], {}, []
        for f in group:
            d = f["digits"]
            if f["country"] == "FR":
                d = d if d.startswith("0") else "0" + d
                reading, region, geo = _fr_phone(d)
            elif f["country"] == "PT":
                reading, region, geo = _pt_phone(d)
            else:
                reading, region, geo = _es_phone(d)
            countries.append(f["country"])
            readings[f["country"]] = reading
            geographic.append(geo)
            if region:
                regions.append(region)
        digits = group[0]["digits"]
        if len(countries) == 1:
            code = {"PT": "+351", "ES": "+34", "FR": "+33"}[countries[0]]
            value = f"{code} {digits[1:] if countries[0] == 'FR' and digits.startswith('0') else digits}"
        else:
            value = digits
        notes = []
        grouping = _grouping(raw)
        if set(countries) == {"PT", "ES"} and digits[0] != "9":
            notes.append("a Portuguese non-geographic number (707, 760, 800, 808) or a Spanish 7xx/8xx number")
        elif set(countries) == {"PT", "ES"}:
            notes.append("91x/92x/93x/96x: a Portuguese mobile or a Spanish landline (91 Madrid, 93 Barcelona); "
                         "PT writes 3-3-3, ES often 2-3-2-2")
            if grouping == [3, 3, 3]:
                notes.append("written 3-3-3, as Portuguese numbers are")
            elif grouping in ([2, 3, 2, 2], [2, 2, 2, 3], [3, 2, 2, 2]):
                notes.append(f"written {'-'.join(map(str, grouping))}, as Spanish landlines often are")
        if "FR" in countries and any(geographic):
            notes.append("French landlines can move anywhere since 2023/24: the zone is a strong prior, not proof")
        if not any(geographic):
            strength = "weak" if all("non-geographic" in r or "special" in r or "VoIP" in r for r in readings.values()) \
                else ("strong" if len(countries) == 1 else "medium")
        else:
            strength = "strong" if len(countries) == 1 else "medium"
        if len(grouping) > 1 and grouping[0] >= 5:
            strength = _weaker(strength)
            notes.append(f"written {'-'.join(map(str, grouping))}, which no national style uses: probably a misread")
        if not group[0]["intl"] and not phone_word:
            strength = _weaker(strength)
            notes.append("no phone word (Tel., Tlm., Móvil, Vende-se ...) on its panel")
        items.append(_item("phone", raw.strip(), value, (start, end), countries=countries, regions=regions,
                           strength=strength, notes=notes,
                           details={"readings": readings, "international_prefix": group[0]["intl"],
                                    "grouping": grouping, "phone_word": phone_word}))
    return items


def _overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


# -- parsing: plates, roads, trails, hunting zones, municipal codes ---------------------------------

_SEP = r"[ \-·.•]?"
_PLATE_PATTERNS = (  # (country, format, era, regex)
    ("PT", "00-00-AA", "1992-2005", rf"\d{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}"),
    ("PT", "00-AA-00", "2005-2020", rf"\d{{2}}{_SEP}[A-Z]{{2}}{_SEP}\d{{2}}"),
    ("PT", "AA-00-AA", "since 2020", rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}"),
    ("PT", "AA-00-00", "1937-1992", rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}"),
    ("ES", "0000 BBB", "since 2000", rf"\d{{4}}{_SEP}[BCDFGHJKLMNPRSTVWXYZ]{{3}}"),
    ("FR", "AA-123-AA", "SIV, since 2009", rf"[A-HJ-NP-TV-Z]{{2}}{_SEP}\d{{3}}{_SEP}[A-HJ-NP-TV-Z]{{2}}"),
)
_PLATE_RES = [(c, f, e, re.compile(rf"(?<![A-Z0-9])(?:{rx})(?![A-Z0-9])")) for c, f, e, rx in _PLATE_PATTERNS]
_PLATE_NOTES = {"PT": "plates give the country and era, not the region; cars travel",
                "ES": "the national series since 2000 has no region; cars travel",
                "FR": "Italian plates share this pattern; the department on the band is the owner's choice"}


def parse_plates(text):
    """Number plates (weak, country only): only when the plate is most of the text, as on a plate."""
    text = _clean(text)
    items = []
    for country, fmt, era, rx in _PLATE_RES:
        for m in rx.finditer(text):
            if not _standalone(text, m.span(), 0.7):
                continue
            parts = re.findall(r"\d+|[A-Z]+", m.group(0))
            value = " ".join(parts) if country == "ES" else "-".join(parts)
            items.append(_item("plate", m.group(0), value, m.span(), countries=[country], strength="weak",
                               notes=[_PLATE_NOTES[country]], details={"format": fmt, "era": era}))
    return items


_ES_ROAD = re.compile(r"(?<![A-Za-z0-9-])(?:(?P<exa>EX-A)(?P<exnum>\d{1,2})|(?P<pre>[A-Z][A-Za-z]{0,2}(?:-[PV])?)-"
                      r"(?P<num>\d{1,4}(?:\.\d{1,2})?|[IVX]{1,4}))(?![A-Za-z0-9]|-[A-Za-z0-9])")
_ROAD = re.compile(r"(?<![A-Za-z0-9-])(?P<pre>IP|IC|EN|ER|EM|CM|RN|RD|A|N|R|M|D|T) ?(?P<num>\d{1,4})"
                   r"(?P<sub> ?- ?\d{1,2}|\.\d{1,2})?(?![A-Za-z0-9]|-[A-Za-z0-9])")
_ROAD_CONTEXT = re.compile(r"\b(?:estrada|itinerario|autoestrada|saida|carretera|ctra|autovia|autopista|salida"
                           r"|route|autoroute|sortie|direction|km|pk)\b|[→←↑↗↖]")


def _road_meaning(pre, n, sub):
    """(countries, strength, meaning) for an unhyphenated road number, or None when it isn't one."""
    if pre == "IP":
        return (["PT"], "strong", "Itinerário Principal") if 1 <= n <= 9 else None
    if pre == "IC":
        return (["PT"], "strong", "Itinerário Complementar") if 1 <= n <= 37 else None
    if pre in ("EN", "ER"):
        return ["PT"], "strong", "Estrada Nacional" if pre == "EN" else "Estrada Regional"
    if pre == "EM":
        return (["PT"], "strong", "Estrada Municipal (numbers repeat in every district)") if 500 <= n <= 999 else None
    if pre == "CM":
        return (["PT"], "strong", "Caminho Municipal (numbers repeat in every district)") if n >= 1000 else None
    if pre in ("RD", "D"):
        strength = "strong" if pre == "RD" or n >= 10 else "medium"
        return ["FR"], strength, "route départementale (numbers repeat in every department)"
    if pre == "RN":
        return ["FR"], "strong", "route nationale"
    if pre == "T":
        return (["FR"], "medium", "Corsican route territoriale") if 10 <= n <= 59 or 100 <= n <= 599 else None
    if pre == "A":
        return (["PT", "FR"] if n <= 44 else ["FR"]), "medium", "autoestrada / autoroute"
    if pre == "N":
        return (["PT", "FR"] if n <= 398 else ["FR"]), "medium", "estrada nacional / route nationale"
    if pre == "R":
        return ["PT"], "weak", "Estrada Regional (keeps the old EN number)"
    if pre == "M":
        countries = (["PT"] if 500 <= n <= 999 else []) + ["FR", "ES"]
        return countries, "weak", "a PT municipal road, a French métropole road or a Madrid km marker"
    return None


def parse_roads(text, confidence=1.0):
    """Road numbers (COUNTRY_CLUES.md 2): IP/IC/EN mean PT, a hyphen means ES (whitelisted prefixes), D means FR.

    Bare A and N fit PT and FR. A road number that is not most of the text, without a road word next
    to it, is one strength weaker. Without a road word, a one-letter code (A, N, R, M, D, T) also needs
    70% of the text and a reading at least ROAD_MIN_CONF sure: OCR makes "D3 LA" out of "DE LA" and
    "A46" out of a crowd.
    """
    text = _clean(text)
    context = bool(_ROAD_CONTEXT.search(_fold(text)))
    items = []
    for m in _ES_ROAD.finditer(text):
        if m.group("exa"):
            pre, num = "EX-A", m.group("exnum")
            meaning, base = "Extremadura (regional motorway)", "EX"
            value = f"EX-A{num}"
        else:
            pre, num = m.group("pre"), m.group("num")
            base = pre.split("-")[0]
            if base not in ES_ROAD_PREFIXES or (base.upper() != base and base not in ("Ma", "Me")):
                continue
            meaning = ES_ROAD_PREFIXES[base]
            value = f"{pre}-{num}"
        strength = "medium" if base in _ES_SINGLE_LETTER else "strong"
        details = {"prefix": pre, "number": num, "meaning": meaning}
        city = ES_CITY_ROADS.get((base, int(num))) if num.isdigit() else None
        regions = [_region("ES", "road prefix", meaning)]
        if city:
            details["city_road"] = city
            if city != meaning:
                regions.append(_region("ES", "city", city))
        notes = ["a hyphen between prefix and number is the Spanish style"]
        if " or " in meaning:
            notes.append(f"{base} is ambiguous: {meaning}")
        if not (_standalone(text, m.span(), 0.5) or context):
            strength = _weaker(strength)
        items.append(_item("road", m.group(0), value, m.span(), countries=["ES"], regions=regions,
                           strength=strength, notes=notes, details=details))
    for m in _ROAD.finditer(text):
        if any(_overlaps(m.span(), it["span"]) for it in items):
            continue
        pre, num, sub = m.group("pre"), m.group("num"), (m.group("sub") or "").replace(" ", "")
        meaning = _road_meaning(pre, int(num), sub)
        if meaning is None:
            continue
        countries, strength, what = meaning
        notes = []
        if pre in ("A", "N"):
            notes.append("bare A and N numbers fit Portugal and France")
        if pre == "M":
            notes.append("M + number: a PT municipal road, a French métropole road or a Madrid km marker")
        if len(pre) == 1 and not context and (confidence < ROAD_MIN_CONF or not _standalone(text, m.span(), 0.7)):
            continue
        if not (_standalone(text, m.span(), 0.5) or context):
            strength = _weaker(strength)
        items.append(_item("road", m.group(0), f"{pre}{num}{sub}", m.span(), countries=countries, strength=strength,
                           notes=notes, details={"prefix": pre, "number": num, "branch": sub or None,
                                                 "meaning": what}))
    return items


_TRAIL = re.compile(r"(?<![A-Za-z0-9])(PR|GR|PL) ?-? ?(\d{1,3}) ?-? ?([A-Z]{3})(?![A-Za-z0-9])")
_EREDES = re.compile(r"(?<![A-Za-z0-9-])([A-Z]{3})-[A-Z]-\d{3,4}(?![A-Za-z0-9])")
_CTT_DESIGNATION = re.compile(r"(?<!\d)[1-9]\d{3} ?- ?\d{3} +[A-ZÀ-Ý][A-ZÀ-Ý' -]*? ([A-Z]{3}) *$")
# A whole reading that is a locality in capitals and a municipal code: "SERZEDELO GMR", a postal designation
# whose postcode OCR read on another line, or a locality sign (knowledge_base municipal-code-pt)
_LOCALITY_CODE = re.compile(r"^ *[A-ZÀ-Ý][A-ZÀ-Ý'. -]{2,40}?[A-ZÀ-Ý] +([A-Z]{3}) *$")
_CODE_WORDS = {"AND", "ALT"}  # municipal codes that are also common sign words: not trusted without a postcode


def _municipal_region(code):
    info = PT_MUNICIPAL_CODES[code]
    return _region("PT", "municipality", info["municipality"], code, district=info["district"])


def parse_trails(text):
    """Pequena/Grande Rota trail codes; PT's municipal code (PR18 LLE = Loulé) names the municipality."""
    text = _clean(text)
    items = []
    for m in _TRAIL.finditer(text):
        kind, number, code = m.groups()
        value = f"{kind}{number} {code}"
        if code in PT_MUNICIPAL_CODES:
            items.append(_item("trail", m.group(0), value, m.span(), countries=["PT"],
                               regions=[_municipal_region(code)], strength="strong",
                               details={"trail": f"{kind}{number}", "municipal_code": code}))
        else:
            items.append(_item("trail", m.group(0), value, m.span(), strength="weak",
                               notes=[f"{code} is not a Portuguese municipal code; GR/PR trails exist in all three "
                                      f"countries"], details={"trail": f"{kind}{number}", "code": code}))
    return items


def parse_municipal_codes(text):
    """PT 3-letter municipal codes on E-REDES plates (PNI-D-0011), after a postcode (4765-123 LORDELO GMR), and
    after a locality in capitals filling the whole reading (SERZEDELO GMR: medium, and not for codes that are
    common words). Only the code's span is taken, so the locality stays a name candidate: looked up nationally,
    the municipality's region then favours the namesake inside it."""
    text = _clean(text)
    items = []
    for rx, source, strength in ((_EREDES, "E-REDES installation plate", "medium"),
                                 (_CTT_DESIGNATION, "CTT postal designation", "strong"),
                                 (_LOCALITY_CODE, "locality and municipal code", "medium")):
        for m in rx.finditer(text):
            code = m.group(1)
            if code not in PT_MUNICIPAL_CODES or (rx is _LOCALITY_CODE and code in _CODE_WORDS):
                continue
            if any(_overlaps(m.span(1), it["span"]) for it in items):
                continue
            items.append(_item("municipal_code", code, code, m.span(1), countries=["PT"],
                               regions=[_municipal_region(code)], strength=strength, details={"source": source}))
    return items


_PT_HUNT = re.compile(r"(?:proc(?:esso)?\.?\s*(?:n\.?\s*[o°]?\.?)?\s*)?(?<![\d-])(\d{1,4}) ?- ?(icnf|dgf|afn|dgrf)\b")
_PT_HUNT_TYPE = re.compile(r"\bzona\s+de\s+caca\s+(municipal|associativa|turistica|nacional)\b")
_ES_COTO = re.compile(r"\bcoto\s+(?:privado\s+|deportivo\s+|local\s+|social\s+|intensivo\s+|municipal\s+)?de\s+caza\b")
_ES_COTO_PLATE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,2}) ?-? ?(1\d\.\d{3}|1\d{4})(?![\d.])")


def parse_hunting_zones(text):
    """PT hunting-zone process numbers (3475-ICNF: the zone polygon in ICNF's map service) and ES coto plates."""
    text = _clean(text)
    folded = _fold(text)
    items = []
    for m in _PT_HUNT.finditer(folded):
        number, agency = m.group(1), m.group(2).upper()
        items.append(_item("hunting_zone", text[m.start():m.end()].strip(), f"{number}-{agency}", m.span(),
                           countries=["PT"], strength="strong",
                           notes=["look up num_def in ICNF's BDG/zonas_caca layer (prefetch it before the run)"],
                           details={"process_number": int(number), "agency": agency}))
    for m in _PT_HUNT_TYPE.finditer(folded):
        if not any(_overlaps(m.span(), it["span"]) for it in items):
            items.append(_item("hunting_zone", text[m.start():m.end()], f"ZC{m.group(1)[0].upper()}", m.span(),
                               countries=["PT"], strength="medium", details={"type": m.group(1)}))
    coto = _ES_COTO.search(folded)
    for m in _ES_COTO_PLATE.finditer(text):
        prefix, number = m.groups()
        if prefix not in ES_PLATE_CODES or not (coto or "." in number):
            continue
        province = ES_PLATE_CODES[prefix]
        items.append(_item("hunting_zone", m.group(0), f"{prefix}-{number}", m.span(), countries=["ES"],
                           regions=[_region("ES", "province", province, prefix)],
                           strength="strong" if coto else "medium", details={"source": "coto de caza plate"}))
    if coto and not any(it["countries"] == ["ES"] for it in items):
        items.append(_item("hunting_zone", text[coto.start():coto.end()], "coto de caza", coto.span(),
                           countries=["ES"], strength="medium"))
    return items


# -- parsing: municipalities, organisations, domains ------------------------------------------------

_NAME_CONNECTORS = frozenset("de do da dos das e y i la le les el los las del dels sur sous en lès lez d' l' a o "
                             "as os".split())
_NAME_STOP = re.compile(r"[,;:|/()\[\]\"!?•]| - |\d")
_WORD = re.compile(r"[^\W\d_][\w'’.·-]*")


def _take_name(text, start, max_words=6):
    """The place name that starts at text[start] -> (name, end), or None: capitalised words and connectors,
    up to punctuation or a digit. In all-capitals text every word up to the punctuation counts; in mixed
    case the name stops at the first lower-case word that isn't a connector."""
    stop = _NAME_STOP.search(text, start)
    limit = stop.start() if stop else len(text)
    letters = [c for c in text[start:limit] if c.isalpha()]
    all_caps = bool(letters) and all(c.isupper() for c in letters)
    words = []
    for m in _WORD.finditer(text, start, limit):
        word = m.group(0).rstrip(".-")
        if not (_fold(word) in _NAME_CONNECTORS or all_caps or word[0].isupper()):
            break
        words.append((word, m.start()))
        if sum(_fold(w) not in _NAME_CONNECTORS for w, _ in words) >= max_words:
            break
    while words and _fold(words[-1][0]) in _NAME_CONNECTORS:
        words.pop()
    if not words:
        return None
    return " ".join(w for w, _ in words), words[-1][1] + len(words[-1][0])


_MUNICIPALITY_PHRASES = (  # (folded regex ending where the name starts, country, unit, community or None, strength)
    (r"\bcamara\s+municipal\s+d[eoa]s?\s+", "PT", "municipality", None, "strong"),
    (r"\bmunicipio\s+d[eoa]s?\s+", "PT", "municipality", None, "strong"),
    (r"\bc\.\s?m\.\s+d[eoa]s?\s+", "PT", "municipality", None, "medium"),
    (r"\bjunta\s+de\s+freguesia\s+d[eoa]s?\s+", "PT", "parish", None, "strong"),
    (r"\bj\.\s?f\.\s+d[eoa]s?\s+", "PT", "parish", None, "medium"),
    (r"\buniao\s+(?:das\s+)?freguesias\s+d[eoa]s?\s+", "PT", "parish union", None, "strong"),
    (r"\bu\.\s?f\.\s+d[eoa]s?\s+", "PT", "parish union", None, "medium"),
    (r"\bfreguesia\s+d[eoa]s?\s+", "PT", "parish", None, "medium"),
    (r"\b(?:excmo\.?\s+)?ayuntamiento\s+de\s+", "ES", "municipality", None, "strong"),
    (r"\bayto\.?\s+de\s+", "ES", "municipality", None, "medium"),
    (r"\bajuntament\s+(?:de\s+|d['’]\s?)", "ES", "municipality",
     "Catalan-speaking: Cataluña, C. Valenciana or Illes Balears", "strong"),
    (r"\bconcello\s+(?:de|da|do|das|dos)\s+", "ES", "municipality", "Galicia", "strong"),
    (r"\bmairie\s+(?:de\s+|d['’]\s?|du\s+|des\s+)", "FR", "commune", None, "strong"),
    (r"\bville\s+(?:de\s+|d['’]\s?)", "FR", "commune", None, "medium"),
    (r"\bcommune\s+(?:de\s+|d['’]\s?)", "FR", "commune", None, "medium"),
)
_MUNICIPALITY_RES = [(re.compile(rx), *rest) for rx, *rest in _MUNICIPALITY_PHRASES]
_BASQUE_TOWN_HALL = re.compile(r"\b([a-z][a-z-]+?)(?:ko|go)\s+udala\b")


def parse_municipalities(text):
    """"Câmara Municipal de X", "Junta de Freguesia de X", "União das Freguesias de X e Y", "Ayuntamiento /
    Ajuntament / Concello de X", "X-ko Udala", "Mairie de X" -> X, strong (COUNTRY_CLUES.md 2)."""
    text = _clean(text)
    folded = _fold(text)
    items, taken = [], []
    for rx, country, unit, community, strength in _MUNICIPALITY_RES:
        for m in rx.finditer(folded):
            if any(_overlaps(m.span(), t) for t in taken):
                continue
            taken_name = _take_name(text, m.end())
            if not taken_name:
                continue
            name, end = taken_name
            # French du/des and Galician da/do/das/dos hold the article of the name: Le Mans, A Coruña
            article = re.search(r"\b(du|des|da|do|das|dos)\s+$", folded[m.start():m.end()])
            if article and (country == "FR" or community == "Galicia"):
                name = {"du": "Le", "des": "Les", "da": "A", "do": "O", "das": "As", "dos": "Os"}[article.group(1)] \
                    + " " + name
            details = {"unit": unit, "phrase": text[m.start():m.end()].strip()}
            if unit == "parish union":
                details["parts"] = [p.strip() for p in re.split(r"\s+e\s+", name) if p.strip()]
            regions = [_region(country, "community", community)] if community else []
            items.append(_item("municipality", text[m.start():end], name, (m.start(), end), countries=[country],
                               regions=regions, strength=strength, details=details))
            taken.append((m.start(), end))
    for m in _BASQUE_TOWN_HALL.finditer(folded):
        if any(_overlaps(m.span(), t) for t in taken):
            continue
        name = text[m.start(1):m.end(1)]
        items.append(_item("municipality", text[m.start():m.end()], name[:1].upper() + name[1:], m.span(),
                           countries=["ES"], regions=[_region("ES", "community", "País Vasco or Navarra")],
                           strength="strong", details={"unit": "municipality", "phrase": "Udala (Basque)"}))
    return items


_ORGANISATIONS = (  # (folded pattern, name, countries, region or None, strength)
    ("carris metropolitana", "Carris Metropolitana", "PT", "Lisbon metropolitan area", "strong"),
    ("carris", "Carris", "PT", "Lisbon", "medium"),
    ("stcp", "STCP", "PT", "Porto", "strong"),
    ("unir", "UNIR", "PT", "Porto metropolitan area", "weak"),
    ("vamus(?: algarve)?", "Vamus Algarve", "PT", "Algarve", "strong"),
    ("ctt", "CTT", "PT", None, "strong"),
    ("multibanco", "Multibanco", "PT", None, "strong"),
    ("gnr", "GNR", "PT", None, "strong"),
    ("psp", "PSP", "PT", None, "medium"),
    ("e-?redes", "E-REDES", "PT", "mainland Portugal", "medium"),
    ("correos", "Correos", "ES", None, "strong"),
    ("guardia civil", "Guardia Civil", "ES", None, "strong"),
    ("mossos(?: d'esquadra)?", "Mossos d'Esquadra", "ES", "Cataluña", "strong"),
    ("ertzaintza", "Ertzaintza", "ES", "País Vasco", "strong"),
    ("policia foral", "Policía Foral", "ES", "Navarra", "strong"),
    ("policia canaria", "Policía Canaria", "ES", "Canarias", "strong"),
    ("renfe", "Renfe", "ES", None, "strong"),
    ("mercadona", "Mercadona", "ES", None, "medium"),
    ("once", "ONCE", "ES", None, "weak"),
    ("cta", "CTA", "ES", "Asturias", "weak"),
    ("emt", "EMT", "ES", None, "weak"),
    ("xunta(?: de galicia)?", "Xunta de Galicia", "ES", "Galicia", "strong"),
    ("junta de andalucia", "Junta de Andalucía", "ES", "Andalucía", "strong"),
    ("junta de castilla y leon", "Junta de Castilla y León", "ES", "Castilla y León", "strong"),
    ("junta de extremadura", "Junta de Extremadura", "ES", "Extremadura", "strong"),
    ("junta de comunidades de castilla-la mancha", "Junta de Comunidades de Castilla-La Mancha", "ES",
     "Castilla-La Mancha", "strong"),
    ("generalitat de catalunya", "Generalitat de Catalunya", "ES", "Cataluña", "strong"),
    ("generalitat valenciana", "Generalitat Valenciana", "ES", "C. Valenciana", "strong"),
    ("govern de les illes balears", "Govern de les Illes Balears", "ES", "Illes Balears", "strong"),
    ("gobierno de canarias", "Gobierno de Canarias", "ES", "Canarias", "strong"),
    ("gobierno de aragon", "Gobierno de Aragón", "ES", "Aragón", "strong"),
    ("gobierno de navarra|nafarroako gobernua", "Gobierno de Navarra", "ES", "Navarra", "strong"),
    ("eusko jaurlaritza|gobierno vasco", "Gobierno Vasco", "ES", "País Vasco", "strong"),
    ("gobierno de cantabria", "Gobierno de Cantabria", "ES", "Cantabria", "strong"),
    ("principado de asturias", "Principado de Asturias", "ES", "Asturias", "strong"),
    ("gobierno de la rioja", "Gobierno de La Rioja", "ES", "La Rioja", "strong"),
    ("region de murcia", "Región de Murcia", "ES", "Murcia", "strong"),
    ("comunidad de madrid", "Comunidad de Madrid", "ES", "Madrid", "strong"),
    ("pacos do concelho", "Paços do Concelho", "PT", None, "strong"),
    ("casa consistorial", "Casa Consistorial", "ES", None, "medium"),
    ("udaletxea", "Udaletxea", "ES", "País Vasco or Navarra", "strong"),
    ("hotel de ville", "Hôtel de Ville", "FR", None, "strong"),
    ("la poste", "La Poste", "FR", None, "strong"),
    ("gendarmerie", "Gendarmerie", "FR", None, "strong"),
    ("police municipale", "Police municipale", "FR", None, "strong"),
    ("tabac", "Tabac", "FR", None, "medium"),
    ("breizhgo", "BreizhGo", "FR", "Bretagne", "strong"),
    ("aleop", "Aléop", "FR", "Pays de la Loire", "strong"),
    ("mobigo", "Mobigo", "FR", "Bourgogne-Franche-Comté", "medium"),
    ("remi", "Rémi", "FR", "Centre-Val de Loire", "weak"),
    ("nomad", "Nomad", "FR", "Normandie", "weak"),
    ("fluo", "Fluo", "FR", "Grand Est", "weak"),
    ("lio", "liO", "FR", "Occitanie", "weak"),
    ("zou", "Zou !", "FR", "Provence-Alpes-Côte d'Azur", "weak"),
    ("region sud", "Région Sud", "FR", "Provence-Alpes-Côte d'Azur", "strong"),
    ("ouest-? ?france", "Ouest-France", "FR", "Bretagne, Normandie, Pays de la Loire", "medium"),
    ("sud-? ?ouest", "Sud Ouest", "FR", "Nouvelle-Aquitaine (16, 17, 24, 33, 40, 47, 64)", "medium"),
    ("la depeche(?: du midi)?", "La Dépêche du Midi", "FR", "Occitanie (09, 11, 12, 31, 32, 46, 47, 65, 81, 82)",
     "medium"),
    ("midi libre", "Midi Libre", "FR", "Occitanie (11, 12, 30, 34, 48, 66)", "medium"),
    ("la voix du nord", "La Voix du Nord", "FR", "Nord, Pas-de-Calais", "medium"),
    ("le parisien", "Le Parisien", "FR", "Île-de-France and Oise", "medium"),
    ("le telegramme", "Le Télégramme", "FR", "Finistère, Côtes-d'Armor, Morbihan", "medium"),
    ("le progres", "Le Progrès", "FR", "Rhône, Loire, Haute-Loire, Ain, Jura", "medium"),
    ("le dauphine(?: libere)?", "Le Dauphiné libéré", "FR", "Alps and Rhône valley", "medium"),
    ("nice-? ?matin", "Nice-Matin", "FR", "Alpes-Maritimes", "medium"),
    ("var-? ?matin", "Var-Matin", "FR", "Var", "medium"),
    ("corse-? ?matin", "Corse-Matin", "FR", "Corse", "medium"),
    ("l'est republicain", "L'Est républicain", "FR", "Lorraine and Franche-Comté", "medium"),
    ("dernieres nouvelles d'alsace", "Dernières Nouvelles d'Alsace", "FR", "Bas-Rhin", "medium"),
)
_ORGANISATION_RES = [(re.compile(rf"(?<![a-z0-9])(?:{rx})(?![a-z0-9])"), *rest) for rx, *rest in _ORGANISATIONS]


def parse_organisations(text):
    """Transport brands, post, police, regional governments and newspapers that point to a country or region."""
    text = _clean(text)
    folded = _fold(text).replace("’", "'")
    matches = [(m.span(), name, country, region, strength) for rx, name, country, region, strength in _ORGANISATION_RES
               for m in rx.finditer(folded)]
    items, taken = [], []
    for span, name, country, region, strength in sorted(matches, key=lambda x: (x[0][0] - x[0][1], x[0][0])):
        if any(_overlaps(span, t) for t in taken):
            continue
        taken.append(span)
        regions = [_region(country, "area", region)] if region else []
        items.append(_item("organisation", text[span[0]:span[1]], name, span, countries=[country], regions=regions,
                           strength=strength))
    return sorted(items, key=lambda it: it["span"])


DOMAIN_TLDS = {  # TLD -> (countries, region or None, strength); generic TLDs give no country
    "pt": (["PT"], None, "strong"), "es": (["ES"], None, "strong"), "fr": (["FR"], None, "strong"),
    "cat": (["ES"], "Catalan-speaking area", "medium"), "gal": (["ES"], "Galicia", "medium"),
    "eus": (["ES", "FR"], "Basque Country", "medium"), "bzh": (["FR"], "Bretagne", "medium"),
    "corsica": (["FR"], "Corse", "medium"), "alsace": (["FR"], "Alsace (Grand Est)", "medium"),
    "paris": (["FR"], "Paris", "medium"), "madrid": (["ES"], "Madrid", "medium"),
    "barcelona": (["ES"], "Barcelona", "medium"), "bcn": (["ES"], "Barcelona", "medium"),
    **{tld: ([], None, "weak") for tld in "com net org info eu biz io app online shop store site pro travel".split()},
}
REGIONAL_DOMAINS = {  # spain.md 3.0: regional-government domains seen on boards
    "xunta.gal": "Galicia", "juntadeandalucia.es": "Andalucía", "jcyl.es": "Castilla y León",
    "castillalamancha.es": "Castilla-La Mancha", "gva.es": "C. Valenciana", "caib.es": "Illes Balears",
    "euskadi.eus": "País Vasco", "navarra.es": "Navarra", "aragon.es": "Aragón", "asturias.es": "Asturias",
    "cantabria.es": "Cantabria", "larioja.org": "La Rioja", "carm.es": "Murcia", "comunidad.madrid": "Madrid",
    "gobcan.es": "Canarias", "govern.cat": "Cataluña", "gencat.cat": "Cataluña", "juntaex.es": "Extremadura",
}
_MUNICIPAL_DOMAINS = (  # (regex on the domain, country, unit, strength)
    (re.compile(r"(?:^|\.)cm-([a-z0-9-]+)\.pt$"), "PT", "municipality", "strong"),
    (re.compile(r"(?:^|\.)jf-([a-z0-9-]+)\.pt$"), "PT", "parish", "strong"),
    (re.compile(r"(?:^|\.)(?:mairie|ville)-([a-z0-9-]+)\.fr$"), "FR", "commune", "medium"),
    (re.compile(r"(?:^|\.)ayto-?([a-z0-9-]+)\.(?:es|org|com)$"), "ES", "municipality", "medium"),
)
_DOMAIN = re.compile(r"(?<![\w@.-])(?:https?://)?(?:[\w.+-]+@)?((?:www\.)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
                     r"([a-z]{2,10}))(?![\w-])", re.IGNORECASE)


def parse_domains(text):
    """Web and e-mail domains: .pt/.es/.fr give the country, .cat/.gal/.eus and regional-government domains
    the region, cm-X.pt / jf-X.pt / mairie-X.fr / ayto-X.es name the municipality."""
    text = _clean(text)
    items = []
    for m in _DOMAIN.finditer(text):
        domain, tld = m.group(1).lower(), m.group(2).lower()
        if tld not in DOMAIN_TLDS or domain.count(".") < 1:
            continue
        bare = domain[4:] if domain.startswith("www.") else domain
        countries, region, strength = DOMAIN_TLDS[tld]
        regions = [_region(countries[0], "area", region)] if region else []
        for suffix, community in REGIONAL_DOMAINS.items():
            if bare == suffix or bare.endswith("." + suffix):
                countries, strength = ["ES"], "strong"
                regions = [_region("ES", "community", community)]
        items.append(_item("domain", m.group(0), bare, m.span(), countries=countries, regions=regions,
                           strength=strength, details={"tld": tld}))
        for rx, country, unit, mstrength in _MUNICIPAL_DOMAINS:
            slug = rx.search(bare)
            if slug:
                name = " ".join(w if w in _NAME_CONNECTORS else w.capitalize() for w in slug.group(1).split("-"))
                items.append(_item("municipality", m.group(0), name, m.span(), countries=[country],
                                   strength=mstrength, details={"unit": unit, "phrase": f"web domain {bare}"}))
    return items


# -- parsing: language hints and name candidates ----------------------------------------------------

_LANGUAGE_CUES = (  # (regex on the lower-case text, language, cue); weak hints only, language ID is T70
    (r"[ãõ]", "pt", "ã/õ"),
    (r"ções\b|ção\b", "pt", "-ção"),
    (r"ñ", "es", "ñ (also Galician)"),
    (r"ciones\b|ción\b", "es", "-ción"),
    (r"[¿¡]", "es", "¿/¡"),
    (r"l·l|ŀl|l\.l(?=[a-zà-ÿ])", "ca", "l·l"),
    (r"tx|tz", "eu", "tx/tz"),
    (r"œ", "fr", "œ"),
    (r"[ùûëïîÿ]", "fr", "ù/û/ë/ï/î"),
    (r"c['’]h", "br", "c'h (Breton)"),
)
_LANGUAGE_RES = [(re.compile(rx), lang, cue) for rx, lang, cue in _LANGUAGE_CUES]
LANGUAGE_COUNTRIES = {"pt": ["PT"], "es": ["ES"], "ca": ["ES", "FR"], "eu": ["ES", "FR"], "fr": ["FR"],
                      "br": ["FR"]}


def language_hints(text):
    """Spelling cues (ã/õ -> pt, ñ -> es, l·l -> ca, tx/tz -> eu, œ -> fr ...): one weak item per language."""
    text = _clean(text)
    lower = text.lower()
    found = {}
    for rx, lang, cue in _LANGUAGE_RES:
        for m in rx.finditer(lower):
            entry = found.setdefault(lang, {"cues": [], "span": m.span()})
            if cue not in entry["cues"]:
                entry["cues"].append(cue)
    return [_item("language", text[e["span"][0]:e["span"][1]], lang, e["span"], countries=LANGUAGE_COUNTRIES[lang],
                  strength="weak", details={"cues": e["cues"]}) for lang, e in found.items()]


_BOILERPLATE = frozenset("""
entrada saida aberto fechado empurre puxe empurrar puxar proibido proibida privado privada perigo atencao aviso obras
saldos promocao promocoes oferta ofertas venda vende arrenda aluga wc homens senhoras informacao informacoes horario
servico servicos loja cafe bar restaurante snack pastelaria padaria farmacia hotel hostel parque estacionamento livre
ocupado completo rua avenida praca largo travessa estrada bairro numero tel telefone telemovel fax email site km metros
minutos euros desde bem vindo vindos obrigado salida abierto cerrado empujar tirar empuje tire prohibido peligro
atencion rebajas venta alquiler alquila aseos servicios caballeros damas senoras informacion tienda cafeteria
aparcamiento parking libre calle plaza paseo carretera telefono movil bienvenido bienvenidos gracias entree sortie
ouvert ferme poussez tirez interdit interdite prive privee danger attention travaux soldes promo promotion location
louer toilettes hommes femmes information informations horaires magasin boutique pharmacie occupe complet rue place
boulevard chemin route telephone bienvenue merci open closed push pull exit entrance entry stop sale toilets toilet
info welcome free private caution warning the and of for to in on at no yes off new now here
camara municipal municipio junta freguesia uniao ayuntamiento ajuntament concello mairie ville commune informa
zona caca coto caza associativa turistica nacional cedex codex se vendo alugo trespassa trespasse vendre louer
alquila
""".split())


_TRIMMED = re.compile(r"[^\W_](?:.*[^\W_])?")  # from the first to the last letter or digit


def name_candidates(text, taken=(), confidence=1.0):
    """The pieces of text between the other items' spans that look like names worth looking up.

    Each piece: letters, 4-60 characters, at most 8 words, mostly letters, and not only generic sign
    words (_BOILERPLATE) or articles. Weak: a name is a query for panoloc.names, not evidence by itself.
    """
    text = _clean(text)
    if confidence < NAME_MIN_CONF:
        return []
    bounds = sorted(taken)
    pieces, start = [], 0
    for a, b in bounds:
        pieces.append((start, a))
        start = max(start, b)
    pieces.append((start, len(text)))
    items = []
    for a, b in pieces:
        m = _TRIMMED.search(text, a, b) if b > a else None
        if not m:
            continue
        value = " ".join(w for w in m.group(0).split() if _fold(w).strip(".,") not in ("cedex", "codex"))
        letters, digits = sum(c.isalpha() for c in value), sum(c.isdigit() for c in value)
        words = normalise(value).split()
        content = [w for w in words if len(w) >= 2 and w not in STOPWORDS and not w.isdigit()]
        if not (4 <= len(value) <= 60 and letters >= 4 and letters >= 0.6 * (letters + digits) and len(words) <= 8):
            continue
        if not content or all(w in _BOILERPLATE for w in content) or (len(content) == 1 and len(content[0]) < 4):
            continue
        letters_only = "".join(c for c in normalise(value) if c.isalpha())
        if not re.search(r"[aeiouy]", letters_only) or len(set(letters_only)) < 3:
            continue
        items.append(_item("name", m.group(0), value, m.span(), strength="weak", details={"query": value}))
    return items


# -- parsing: everything ----------------------------------------------------------------------------

_PARSERS = (parse_domains, parse_hunting_zones, parse_postcodes, parse_phones, parse_trails, parse_municipal_codes,
            parse_municipalities, parse_organisations, parse_plates, parse_roads)


def parse_text(text, *, names=True, confidence=1.0, context=""):
    """Every item in one OCR reading (pure; no OCR). Kinds, in priority order when spans overlap:
    domain, hunting_zone, postcode, phone, trail, municipal_code, municipality, organisation, plate, road;
    then language hints and, for confident readings, name candidates from the rest of the text.
    context is the text of the other lines on the same panel; only the phone parser uses it."""
    text = _clean(text)
    if not text.strip():
        return []
    items, taken = [], []
    for parser in _PARSERS:
        found = (parser(text, context) if parser is parse_phones else
                 parser(text, confidence) if parser is parse_roads else parser(text))
        found = [it for it in found if not any(_overlaps(it["span"], t) for t in taken)]
        items.extend(found)
        taken.extend(it["span"] for it in found)
    items.extend(language_hints(text))
    if names:
        items.extend(name_candidates(text, taken, confidence))
    return items


def panel_context(sign, signs):
    """The texts of the signs stacked with this one (overlapping in width, centres within 3 line heights):
    probably the same panel, as "VENDE-SE" above a phone number."""
    texts = []
    for other in signs:
        if other is sign:
            continue
        dx, dy = _offsets(sign.box, other.box)
        if abs(dy) <= 3 * max(sign.box["h"], other.box["h"]) and abs(dx) < (sign.box["w"] + other.box["w"]) / 2:
            texts.append(other.text)
    return " | ".join(texts)


def parse_sign(sign, context=""):
    """Items from a sign's reading, plus those that only an alternative reading shows (source "alternative").

    readings counts the sign's independent readings (each view's hit and the reread) that give the same
    (kind, value): agreement across views. context: panel_context(), for the phone parser.
    """
    cache = {}

    def parsed(text, primary):
        if (text, primary) not in cache:
            cache[(text, primary)] = parse_text(text, names=primary, confidence=sign.confidence, context=context)
        return cache[(text, primary)]

    items, seen = [], set()
    for text, source, primary in [(sign.text, "reading", True)] + [(a["text"], "alternative", False)
                                                                    for a in sign.alternatives]:
        for item in parsed(text, primary):
            key = (item["kind"], item["value"])
            if key in seen or (item["kind"] == "language" and not primary):
                continue
            seen.add(key)
            items.append({**item, "source": source, "sign_id": sign.sign_id,
                          "in_photographer_zone": sign.in_photographer_zone})
    texts = [h.text for h in sign.hits] + ([sign.reread["text"]] if sign.reread and sign.reread.get("text") else [])
    for item in items:
        item["readings"] = sum(any((it["kind"], it["value"]) == (item["kind"], item["value"])
                                   for it in parsed(t, True)) for t in texts)
    return items


# -- the panorama -----------------------------------------------------------------------------------

@dataclass(eq=False)
class OcrResult:
    """Everything read_panorama found; to_dict() is the body of ocr.json."""
    signs: list                  # Signs at or above SIGN_MIN_CONF, parsed and logged
    low_confidence: list         # Signs below SIGN_MIN_CONF, kept for review only
    items: list                  # parsed items (dicts with item_id and sign_id)
    hits: list                   # every view hit, as read: the raw readings
    rereads: dict                # outcome counts
    timing: dict
    engine: dict
    views: list                  # view metadata
    images: dict = field(default_factory=dict, repr=False)  # views and reread crops when keep_images was set

    def sign(self, sign_id):
        """The sign with this ID (kept or low-confidence), or None."""
        return next((s for s in self.signs + self.low_confidence if s.sign_id == sign_id), None)

    def to_dict(self):
        return {"engine": self.engine, "signs": [s.to_dict() for s in self.signs],
                "items": self.items, "rereads": self.rereads, "timing": self.timing,
                "low_confidence": [s.to_dict() for s in self.low_confidence], "views": self.views,
                "hits": [h.to_dict() for h in self.hits]}


def read_panorama(pano, engine, *, views=None, view_size=DEFAULT_SIZE, rereads=True, max_rereads=MAX_REREADS,
                  reread_budget_s=REREAD_BUDGET_S, reread_scale=REREAD_SCALE,
                  photographer_mask_pct=DEFAULT_MASK_PCT, keep_images=False):
    """OCR one panorama (an H x W x 3 RGB array): read the views, dedup, reread, parse. Returns an OcrResult.

    views defaults to cut_views(pano, view_size): the 8 horizontal views plus sky and ground.
    """
    timing = {"cpu_count": os.cpu_count(), "load_average_1m": round(os.getloadavg()[0], 2)}
    t0 = time.perf_counter()
    if views is None:
        views = cut_views(pano, size=view_size, photographer_mask_pct=photographer_mask_pct)
    t1 = time.perf_counter()
    hits, det_s, rec_s, other_s = [], 0.0, 0.0, 0.0
    for view in views:
        readings, t = engine.read(view.image)
        hits.extend(make_hit(view, r) for r in readings)
        det_s, rec_s, other_s = det_s + t["det_s"], rec_s + t["rec_s"], other_s + t["other_s"]
    t2 = time.perf_counter()
    signs = dedup([h for h in hits if text_key(h.text)])
    _number(signs)
    t2b = time.perf_counter()
    stats, reread_timing, crops = _reread_stats(), _reread_timing(), {}
    if rereads:
        stats, reread_timing, crops = reread_signs(engine, pano, signs, max_rereads=max_rereads,
                                                   budget_s=reread_budget_s, scale=reread_scale,
                                                   photographer_mask_pct=photographer_mask_pct,
                                                   keep_images=keep_images)
    t3 = time.perf_counter()
    signs = sorted(absorb_fragments(signs), key=lambda s: int(s.sign_id[1:]))  # IDs stay: crops are named by them
    kept = [s for s in signs if s.confidence >= SIGN_MIN_CONF and not looks_like_strokes(s.text)]
    low = [s for s in signs if s not in kept]
    items = []
    for sign in kept:
        items.extend(parse_sign(sign, panel_context(sign, kept)))
    for i, item in enumerate(items, 1):
        item["item_id"] = f"i{i}"
    t4 = time.perf_counter()
    timing.update({"views_s": t1 - t0, "read_views_s": t2 - t1, "detection_s": det_s, "recognition_s": rec_s,
                   "view_other_s": other_s, **reread_timing, "dedup_parse_s": (t2b - t2) + (t4 - t3), "total_s": t4 - t0})
    timing = {k: round(v, 3) if isinstance(v, float) else v for k, v in timing.items()}
    images = {"views": views, "rereads": crops} if keep_images else {}
    return OcrResult(kept, low, items, hits, stats, timing, engine.settings(), [v.meta() for v in views], images)


def looks_like_strokes(text):
    """A reading made only of I, l, 1 and | ("IIIl1"): OCR's usual answer to railings, bollards or stripes."""
    key = text_key(text)
    return len(key) >= 2 and set(key) <= _STROKES


def _number(signs):
    """Give signs IDs s1, s2, ... in panorama order (yaw from 0 to 360, then top to bottom), once: signs
    absorbed later leave gaps."""
    signs.sort(key=lambda s: (round(s.box["yaw"] % 360, 1), -s.box["pitch"]))
    for n, sign in enumerate(signs, 1):
        sign.sign_id = f"s{n}"


# -- run log ----------------------------------------------------------------------------------------

def log_ocr(run, result, *, stage="read", model=None):
    """Write the result into a panoloc.runlog.Run: one ocr_text evidence per sign, then one evidence per
    parsed item (kind = the item's kind) linked to its sign's evidence by ocr_evidence_id.

    Returns {sign_id: evidence_id}. Low-confidence signs are not logged (they stay in ocr.json).
    """
    model = model or result.engine.get("model")
    ids = {}
    for sign in result.signs:
        reread = None
        if sign.reread:
            reread = {k: sign.reread.get(k) for k in ("text", "confidence", "coverage", "chosen", "changed", "outcome")}
        ids[sign.sign_id] = run.evidence("ocr_text", {
            "sign_id": sign.sign_id, "text": sign.text, "confidence": sign.confidence, "box": sign.box,
            "views": sign.views, "alternatives": sign.alternatives, "reread": reread, "source": sign.source,
            "in_photographer_zone": sign.in_photographer_zone}, stage=stage, model=model)
    by_id = {s.sign_id: s for s in result.signs}
    for item in result.items:
        sign = by_id[item["sign_id"]]
        payload = {k: item[k] for k in ("item_id", "sign_id", "value", "raw", "countries", "regions", "strength",
                                        "notes", "details", "source", "readings")}
        payload.update(text=item["raw"], ocr_evidence_id=ids[sign.sign_id], confidence=sign.confidence, box=sign.box,
                       in_photographer_zone=sign.in_photographer_zone)
        run.evidence(item["kind"], payload, stage=stage, model=model)
    return ids


# -- debug drawing ----------------------------------------------------------------------------------

def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()


def _colour(sign, hit, kept):
    if not kept:
        return (150, 150, 150)
    if hit.in_photographer_zone:
        return (230, 60, 60)
    return (40, 200, 70) if hit is sign.hits[0] else (240, 200, 40)


def draw_debug(result, pano, out):
    """Draw the boxes: debug/<view>.jpg, debug/rereads/<sign_id>.jpg and debug/panorama.jpg (sphere boxes).

    Green: the hit a sign's reading came from; yellow: another view's copy; red: photographer zone;
    grey: not parsed (low confidence or strokes). In reread crops, blue marks the hits picked for the reread.
    """
    from PIL import ImageDraw
    out = Path(out) / "debug"
    (out / "rereads").mkdir(parents=True, exist_ok=True)
    font = _font(15)
    kept = {id(s) for s in result.signs}
    signs = {s.sign_id: s for s in result.signs + result.low_confidence}
    by_view = defaultdict(list)
    for sign in signs.values():
        for hit in sign.hits:
            by_view[hit.view].append((sign, hit))
    for view in result.images.get("views", []):
        im = Image.fromarray(view.image)
        draw = ImageDraw.Draw(im)
        for sign, hit in by_view[view.name]:
            colour = _colour(sign, hit, id(sign) in kept)
            draw.polygon([tuple(p) for p in hit.quad], outline=colour, width=3)
            x, y = min(p[0] for p in hit.quad), min(p[1] for p in hit.quad)
            draw.text((x, max(0, y - 18)), f"{sign.sign_id} {hit.confidence:.2f} {hit.text}", fill=colour, font=font,
                      stroke_width=2, stroke_fill=(0, 0, 0))
        im.save(out / f"{view.name}.jpg", quality=90)
    for sign_id, (view, hits) in result.images.get("rereads", {}).items():
        sign = signs.get(sign_id)
        if sign is None:  # absorbed into another sign after its reread
            continue
        im = Image.fromarray(view.image)
        draw = ImageDraw.Draw(im)
        for hit in hits:
            picked = picks_for(sign.box, hit, bool(sign.reread and sign.reread.get("extend")))
            colour = (60, 140, 255) if picked else (150, 150, 150)
            draw.polygon([tuple(p) for p in hit.quad], outline=colour, width=2)
            x, y = min(p[0] for p in hit.quad), min(p[1] for p in hit.quad)
            draw.text((x, max(0, y - 18)), f"{hit.confidence:.2f} {hit.text}", fill=colour, font=font, stroke_width=2,
                      stroke_fill=(0, 0, 0))
        im.save(out / "rereads" / f"{sign_id}.jpg", quality=90)
    width = 3040
    height = width // 2
    im = Image.fromarray(pano).resize((width, height), Image.BILINEAR)
    draw = ImageDraw.Draw(im)
    zone_y = sphere_to_pano_xy(0, photographer_pitch_deg(), width, height)[1]
    draw.line([(0, zone_y), (width, zone_y)], fill=(230, 60, 60), width=1)
    for sign in signs.values():
        box = sign.box
        x, y = sphere_to_pano_xy(box["yaw"], box["pitch"], width, height)
        half_w = box["w"] / 2 / max(math.cos(math.radians(box["pitch"])), 0.05) * width / 360
        half_h = box["h"] / 2 * height / 180
        colour = _colour(sign, sign.hits[0], id(sign) in kept)
        for shift in (-width, 0, width):  # a box across the seam is drawn on both sides
            if x + shift + half_w >= 0 and x + shift - half_w <= width:
                draw.rectangle([x + shift - half_w, y - half_h, x + shift + half_w, y + half_h], outline=colour,
                               width=2)
                draw.text((x + shift - half_w, max(0, y - half_h - 17)), f"{sign.sign_id} {sign.text}", fill=colour,
                          font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(out / "panorama.jpg", quality=88)
    return out


# -- CLI --------------------------------------------------------------------------------------------

def _summary_line(item):
    regions = "; ".join(r["name"] + (f" ({r['country']})" if len(item["countries"]) > 1 else "")
                        for r in item["regions"])
    countries = "/".join(item["countries"]) or "-"
    zone = "  [photographer zone]" if item.get("in_photographer_zone") else ""
    return (f"  {item['sign_id']:<4} {item['kind']:<14} {item['value']!s:<28} {countries:<8} {item['strength']:<7}"
            f"{'  ' + regions if regions else ''}{zone}")


def main(argv=None, *, engine=None):
    parser = argparse.ArgumentParser(prog="python -m panoloc.ocr",
                                     description="OCR a panorama's views, reread small text, dedup and parse it.")
    parser.add_argument("panorama", type=Path)
    parser.add_argument("--out", type=Path, help="output folder (default: runs/ocr/<panorama stem>/)")
    parser.add_argument("--det", default=DEFAULT_MODEL, choices=sorted(DET_MODELS))
    parser.add_argument("--rec", default=DEFAULT_MODEL, choices=sorted(REC_MODELS))
    parser.add_argument("--threads", type=int, help="OpenVINO inference threads (default: OpenVINO's choice)")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help=f"view side in pixels (default {DEFAULT_SIZE})")
    parser.add_argument("--max-rereads", type=int, default=MAX_REREADS)
    parser.add_argument("--reread-budget", type=float, default=REREAD_BUDGET_S, help="seconds for all rereads")
    parser.add_argument("--reread-scale", type=float, default=REREAD_SCALE,
                        help="reread resolution relative to the panorama's own (default 1)")
    parser.add_argument("--no-rereads", action="store_true")
    parser.add_argument("--mask-pct", type=float, default=DEFAULT_MASK_PCT,
                        help=f"photographer zone, bottom percent of the rows (default {DEFAULT_MASK_PCT})")
    parser.add_argument("--debug", action="store_true", help="draw the boxes on the views, crops and panorama")
    args = parser.parse_args(argv)
    out = args.out or REPO_ROOT / "runs" / "ocr" / args.panorama.stem

    if engine is None:
        engine = Engine(args.det, args.rec, threads=args.threads)
    t0 = time.perf_counter()
    pano = load_panorama(args.panorama)
    decode_s = time.perf_counter() - t0
    result = read_panorama(pano, engine, view_size=args.size, rereads=not args.no_rereads,
                           max_rereads=args.max_rereads, reread_budget_s=args.reread_budget,
                           reread_scale=args.reread_scale, photographer_mask_pct=args.mask_pct, keep_images=args.debug)
    result.timing["decode_s"] = round(decode_s, 3)
    result.timing["load_s"] = engine.load_s
    out.mkdir(parents=True, exist_ok=True)
    doc = {"schema": SCHEMA, "panorama": args.panorama.name, "source": str(args.panorama),
           "panorama_size": {"width": pano.shape[1], "height": pano.shape[0]},
           "filename": parse_filename(args.panorama).to_dict(), **result.to_dict()}
    (out / "ocr.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.debug:
        draw_debug(result, pano, out)

    t = result.timing
    print(f"{args.panorama.name}  {pano.shape[1]} x {pano.shape[0]}  ->  {out}")
    print(f"engine {engine.name} (+ direction classifier), OpenVINO on {t['cpu_count']} CPU cores, "
          f"loaded in {engine.load_s:.2f} s")
    print(f"signs: {len(result.signs)} kept, {len(result.low_confidence)} below {SIGN_MIN_CONF}, "
          f"from {len(result.hits)} view hits")
    for s in result.signs:
        flags = (" [photographer zone]" if s.in_photographer_zone else "") + (" [reread]" if s.source == "reread"
                                                                               else "")
        print(f"  {s.sign_id:<4} {s.confidence:.3f} yaw {s.box['yaw']:6.1f} pitch {s.box['pitch']:6.1f} "
              f"{','.join(s.views):<12} {s.text!r}{flags}")
    print(f"items: {len(result.items)}")
    for item in result.items:
        print(_summary_line(item))
    r = result.rereads
    if not args.no_rereads:
        print(f"rereads: {r['attempted']} of {r['candidates']} candidates ({r['skipped_limit']} over the limit, "
              f"{r['skipped_budget']} over the budget): {r['chosen']} replaced the reading ({r['changed']} changed "
              f"the text), {r['agrees']} read the same text, {r['partial']} partial, {r['not_better']} not better, "
              f"{r['not_found']} found nothing matching")
    print(f"timing: decode {t['decode_s']:.2f} s, views {t['views_s']:.2f} s, read {t['read_views_s']:.2f} s "
          f"(detection {t['detection_s']:.2f}, recognition {t['recognition_s']:.2f}), rereads "
          f"{t.get('rereads_s', 0):.2f} s (detection {t.get('reread_detection_s', 0):.2f}, recognition "
          f"{t.get('reread_recognition_s', 0):.2f}), dedup+parse {t['dedup_parse_s']:.2f} s, total {t['total_s']:.2f} s"
          f" (excluding decode and load; CPU load average {t['load_average_1m']} at the start)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
