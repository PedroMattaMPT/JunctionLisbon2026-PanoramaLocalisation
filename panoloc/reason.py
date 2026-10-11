"""Place reasoning: the VLM looks at the whole panorama with every other result and names the place.

The checklist (panoloc.vlm) asks one 90-degree view at a time for closed answers and "do not guess" landmarks, which
keeps a small local model honest but leaves a strong model silent: on the warm-up, every panorama where the VLM
named no place missed by 15 to 394 km. This stage gives the VLM all the views at once, a panorama overview and the
pipeline's other findings (OCR text and its parses, checklist answers, photo-bank regions, GeoCLIP, gallery
matches), lets it reason, and asks for ranked named places, the street the camera stands in, and the OCR texts that
do not say where the camera is (a tile panel depicting another town, a destination on a road sign, a brand). It
still never gives coordinates: places go through the name index, near the municipality it names when there is one.

  from panoloc.reason import reason_place, clues_from_reasoning
  doc = reason_place(client, pano, context)           # dict; raises panoloc.vlm.VLMError
  clues = clues_from_reasoning(doc, names)             # fusion.Clue list, group "vlm"
  drop = is_misleading(clue.text, misleading_keys(doc))  # an OCR text it ruled out
"""
import inspect
import json
import time
import unicodedata

from panoloc import fusion
from panoloc.vlm import VLMInvalidResponse, encode_image

# FULL_CONTEXT adds the name index's matches, a combined estimate before the answer, zone names for generator
# points, the sky and ground views and close-ups of OCR signs. Off (Sun 09:07): warm-up 56.0% -> 57.6% but val
# first 30 43.1% -> 38.4%, so the measured context (views, OCR, checklist, generators, gallery) stays.
FULL_CONTEXT = False
VERSION = "v4"  # FULL_CONTEXT's perception-cache name: a new context or prompt must not reuse older answers


def cache_name(model, local=False):
    samples = SAMPLES_LOCAL if local else SAMPLES
    tag = (f"{VERSION}-" if FULL_CONTEXT else "") + (f"s{samples}-" if samples > 1 else "")
    return f"reason-{tag}{model}.json"
MAX_PLACES = 5
# The local VLM runs with an 8k context (vlm.DEFAULT_NUM_CTX) at about 1,000 tokens per megapixel: a smaller
# overview and views keep the request near 6k tokens; one answer, since its calls share one GPU.
LOCAL_OVERVIEW_SIZE = (1536, 768)
LOCAL_VIEW_SIZE = 512
LOCAL_MAX_TOKENS = 1500
SAMPLES_LOCAL = 1
MAX_SIGN_CROPS = 8
SIGN_CROP_SIZE = 768
OVERVIEW_SIZE = (2048, 1024)
VIEW_SIZE = 1280
TIMEOUT_S = 100.0
EFFORT = "medium"  # for clients whose chat() takes an effort; others ignore it
MAX_TOKENS = 16000
NEAR_RADIUS_M = 25_000
KINDS = ("building", "monument", "church", "castle", "bridge", "square", "street", "station", "town", "village",
         "park", "beach", "natural_feature", "other")
CONFIDENCE = {"high": 0.6, "medium": 0.3}  # probability at or above -> fusion's VLM landmark confidence label
RELIABILITY_SCALE = 1.0  # times fusion's VLM landmark reliability for that label (capped at 1)
# The same for the local VLM, whose stated probabilities run high (0.95 on wrong places). Fitted on val first 30
# (Sun 10:50, scale 0 / 0.1 / 0.25 / 0.5 / 1: 1.7 / 6.3 / 8.8 / 13.9 / 12.7%); warm-up 29.1% -> 30.8% at 0.5.
RELIABILITY_SCALE_LOCAL = 0.5
# Independent answers asked in parallel and averaged (probability per place name, absent = 0). 3 (Sun 09:26): one
# answer moves +-3 points run to run (val 43.1/40.3/40.1%, warm-up 56.0/53.6/59.9%); 3 averaged gave warm-up 61.7%
# (095 Moustey found at 17 m) and val 39.3%, within that noise. Higher effort (59.0/41.4%) did not stand out.
SAMPLES = 3

SYSTEM = """\
You are the landmark-recognition step of a team's entry in the Albatroz "Panorama Localisation" challenge at the \
JunctionX Lisbon 2026 hackathon. The organisers photographed public places in Portugal, Spain and France with a \
360-degree camera. You get one such panorama as an overview plus eight 90-degree views around the horizon, and \
the findings of other tools. Name the landmarks and places you can see; the team's code looks the names up. \
This is about places only: never identify or describe any person in the images.

Look at all the views together: read every legible text yourself (shop names, street plates, station boards, \
plaques, monument inscriptions), recognise buildings, monuments, castles, walls, churches, bridges, stations, \
squares and streets, and use architecture, pavement, street furniture, vegetation and terrain to decide between \
similar candidates. Judge the other tools' findings: OCR can misread, and a text can name something that is not \
here (a tile panel or poster depicting another town, a destination on a direction sign, a brand).

List up to five landmarks or places you can see, by the names they have on maps in the local language (e.g. \
"Castelo de Leiria", "Estação de Vilar Formoso", "Rua Augusta"), most specific first, each with the municipality \
and country it is in and your probability that it is right. Name a place even when you are not certain, with an \
honest probability; when nothing specific is recognisable, name the most specific town or area the scene fits, \
with a low probability. For each, the evidence is a short phrase naming the visible clue (at most 15 words). \
Give names only, never coordinates. Also give the name of the street or square the views \
look along if you can read or recognise it, and the OCR texts that name something that is not here."""

SCHEMA = {
    "type": "object",
    "properties": {
        "country": {"type": "string", "enum": ["PT", "ES", "FR", "unknown"]},
        "places": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "kind": {"type": "string", "enum": list(KINDS)},
                           "municipality": {"type": "string"}, "country": {"type": "string",
                                                                          "enum": ["PT", "ES", "FR"]},
                           "probability": {"type": "number"}, "evidence": {"type": "string"}},
            "required": ["name", "kind", "municipality", "country", "probability", "evidence"]}},
        "camera_street": {"type": "string"},
        "misleading_texts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["country", "places", "camera_street", "misleading_texts"],
}


def _fmt_cands(cands, n=5):
    out = []
    for c in cands[:n]:
        region = (c.details or {}).get("region") or c.label
        out.append(f"{c.country or '?'} {region} ({c.weight:.2f})" if c.weight is not None else f"{c.country} {region}")
    return "; ".join(out)


def _sign(s):
    """(text, confidence, yaw) from a panoloc.ocr Sign, its dict, or the pipeline's cached namespace."""
    get = s.get if isinstance(s, dict) else lambda k, d=None: getattr(s, k, d)
    box = get("box") or {}
    yaw = box.get("yaw") if isinstance(box, dict) else getattr(box, "yaw", None)
    return str(get("text") or ""), float(get("confidence") or 0), yaw


def _where(zones, c):
    """'parish, municipality, district (PT)' for a candidate point, or its label when zones are missing."""
    loc = zones.locate(c.lat, c.lng) if zones is not None else None
    if loc is None:
        return f"{c.country or '?'} {(c.details or {}).get('region') or ''}".strip()
    names = [z.short_name or z.name for z in loc.chain[1:]][::-1]
    return f"{', '.join(dict.fromkeys(names[:3]))} ({loc.chain[0].country})"


def build_context(*, filename=None, ocr=None, vlm=None, clues=(), hints=(), zones=None):
    """The other tools' findings as text for the prompt. ocr: panoloc.ocr result (signs, items); vlm: the
    checklist result (landmarks, hints); clues: every fusion.Clue so far (names, retrieval, GeoCLIP, gallery);
    hints: fusion country hints; zones: panoloc.zones.Zones to name generator points."""
    lines = []
    if filename:
        lines.append(f"File name (capture date and time, UTC): {filename}")
    if ocr is not None:
        signs = [_sign(s) for s in getattr(ocr, "signs", [])]
        signs = [s for s in signs if s[0].strip()]
        if signs:
            lines.append("OCR text read in the panorama (confidence, yaw where it was seen):")
            for text, conf, yaw in sorted(signs, key=lambda s: -s[1])[:40]:
                lines.append(f"  - {text!r} ({conf:.2f}" + (f", yaw {yaw:.0f}" if yaw is not None else "") + ")")
        items = [i for i in getattr(ocr, "items", []) if i.get("kind")]
        if items:
            lines.append("OCR parses (kind, value, strength, countries, notes):")
            for i in items[:30]:
                lines.append(f"  - {i.get('kind')} {i.get('value')!r} {i.get('strength')} {i.get('countries') or ''} "
                             f"{'; '.join(i.get('notes') or [])[:120] if isinstance(i.get('notes'), list) else ''}")
    if vlm is not None:
        checklist = [f"{h.get('key')}={h.get('value')} -> {h.get('countries') or ''}" for h in (vlm.hints or [])]
        if checklist:
            lines.append("Checklist answers that point to countries: " + "; ".join(checklist[:20]))
        lms = [f"{lm.get('name')} ({lm.get('confidence')})" for lm in (vlm.landmarks or [])]
        if lms:
            lines.append("Landmarks recognised in single views: " + "; ".join(lms))
    looked_up = [c for c in clues if c.kind.startswith(("ocr_", "vlm_")) and c.candidates] if FULL_CONTEXT else []
    if looked_up:
        lines.append("Our name index (OSM, Wikidata, GeoNames) matched these texts and names to places "
                     "(a match is only as good as the text; generic words match many places):")
        for c in looked_up[:15]:
            top = sorted(c.candidates, key=lambda x: -(x.weight or 0))[:4]
            lines.append(f"  - {c.text!r} ({c.kind}): " + "; ".join(f"{x.label} in {_where(zones, x)}" for x in top)
                         + (f" ... {len(c.candidates)} matches" if len(c.candidates) > 4 else ""))
    by_kind = {}
    for c in clues:
        by_kind.setdefault(c.kind, []).extend(c.candidates)
    names = {"region_head": "Photo-bank region classifier (coarse)", "knn": "Nearest photo-bank images (coarse)",
             "geoclip": "GeoCLIP estimates (coarse)", "landmark_gallery": "Similar Commons landmark photos (unverified)",
             "landmark_verified": "Commons landmark photos matched geometrically (strong)"}
    for kind, label in names.items():
        cands = sorted(by_kind.get(kind, []), key=lambda c: -(c.weight or 0))
        if not cands:
            continue
        if not FULL_CONTEXT:
            lines.append(f"{label}: " + ("; ".join(f"{c.label} ({c.country})" for c in cands[:5])
                                         if kind.startswith("landmark") else _fmt_cands(cands)))
        elif kind.startswith("landmark"):
            lines.append(f"{label}: " + "; ".join(f"{c.label} in {_where(zones, c)}" for c in cands[:5]))
        elif kind == "region_head":
            lines.append(f"{label}: {_fmt_cands(cands)}")
        else:
            lines.append(f"{label}: " + "; ".join(f"{_where(zones, c)} ({c.weight:.2f})" for c in cands[:5]))
    if not FULL_CONTEXT:
        return "\n".join(lines) or "No other findings."
    try:
        fused = fusion.fuse(list(clues), list(hints))
        top = fused.hypotheses[:8]
        if top:
            lines.append("Our combined estimate before your answer (weights; often wrong when no text was read):")
            for h in top:
                lines.append(f"  - {h.label or h.source} in {_where(zones, h)} ({h.weight:.2f})")
    except Exception as exc:  # the context must never cost the run
        lines.append(f"(combined estimate unavailable: {type(exc).__name__}: {exc})")
    return "\n".join(lines) or "No other findings."


def _sign_box(s):
    get = s.get if isinstance(s, dict) else lambda k, d=None: getattr(s, k, d)
    box = get("box") or {}
    return box if isinstance(box, dict) else {}


def _images(pano, signs=(), local=False):
    """(images, captions): the overview, the 8 horizontal views, sky and ground, then close-ups of the most
    confident OCR signs (a box a little larger than the sign, at SIGN_CROP_SIZE). local: the smaller sizes."""
    from panoloc.views import cut_view, cut_views
    import numpy as np
    from PIL import Image
    size = LOCAL_OVERVIEW_SIZE if local else OVERVIEW_SIZE
    overview = np.asarray(Image.fromarray(pano).resize(size, Image.Resampling.BICUBIC))
    views = cut_views(pano, size=LOCAL_VIEW_SIZE if local else VIEW_SIZE)
    images = [encode_image(overview)] + [encode_image(v) for v in views]
    captions = ["the equirectangular overview (yaw 0 at the centre, increasing to the right)"] + [
        f"view {v.name} (yaw {v.yaw_deg:.0f}, pitch {v.pitch_deg:.0f})" for v in views]
    ranked = sorted((s for s in signs if len(_sign(s)[0].strip()) >= 3 and _sign_box(s).get("yaw") is not None),
                    key=lambda s: -_sign(s)[1])
    for s in ranked[:MAX_SIGN_CROPS]:
        box, (text, conf, _) = _sign_box(s), _sign(s)
        fov = min(40.0, max(8.0, 1.8 * max(float(box.get("w") or 0), float(box.get("h") or 0))))
        try:
            crop = cut_view(pano, float(box["yaw"]), float(box.get("pitch") or 0), fov, SIGN_CROP_SIZE)
        except Exception:  # a crop that cannot be cut is left out
            continue
        images.append(encode_image(crop))
        captions.append(f"close-up of the sign OCR read as {text!r} (yaw {float(box['yaw']):.0f})")
    return images, captions


def _chat_kwargs(client):
    params = inspect.signature(client.chat).parameters
    return {k: v for k, v in (("effort", EFFORT), ("max_tokens", MAX_TOKENS), ("num_predict", LOCAL_MAX_TOKENS))
            if k in params}


def is_local(client):
    """The local (Ollama) VLM: its chat takes num_predict, not an effort."""
    return "num_predict" in inspect.signature(client.chat).parameters


def reason_place(client, pano, context, signs=()):
    """One reasoning request; returns the parsed reply plus timing. Raises panoloc.vlm.VLMError."""
    local = is_local(client)
    if FULL_CONTEXT:
        images, captions = _images(pano, signs, local)
        listing = "\n".join(f"Image {i}: {c}" for i, c in enumerate(captions, 1))
    else:
        images, captions = _images(pano, local=local)
        images, names = images[:9], [c.split()[1] for c in captions[1:9]]
        listing = ("Image 1 is the equirectangular overview (yaw 0 at the centre, increasing to the right). Images 2-9 "
                   f"are the views {', '.join(names)} (yaw in degrees).")
    text = (f"{listing}\n\nOther tools found:\n{context}\n\n"
            "Which landmarks and places can you see? Fill in the JSON.")
    t0 = time.perf_counter()

    def ask(_):
        content, timing = client.chat(SYSTEM, text, SCHEMA, images=images, timeout_s=TIMEOUT_S, **_chat_kwargs(client))
        try:
            return json.loads(content), timing
        except (TypeError, ValueError) as exc:
            raise VLMInvalidResponse(f"place reasoning: no JSON in the reply: {exc}", model=client.model) from exc

    samples = SAMPLES_LOCAL if local else SAMPLES
    if samples <= 1:
        doc, timing = ask(0)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(samples) as pool:
            futures = [pool.submit(ask, i) for i in range(samples)]
        replies = [f.result() for f in futures if f.exception() is None]
        if not replies:
            futures[0].result()  # raises the first failure
        doc, timing = _merge([d for d, _ in replies]), replies[0][1]
    places = []
    for p in doc.get("places") or []:
        name = (p.get("name") or "").strip()
        if not name or p.get("country") not in ("PT", "ES", "FR"):
            continue
        prob = min(1.0, max(0.0, float(p.get("probability") or 0)))
        places.append({**p, "name": name[:120], "probability": prob})
    doc["places"] = places[:MAX_PLACES]
    doc["misleading_texts"] = [t for t in doc.get("misleading_texts") or [] if isinstance(t, str) and t.strip()]
    doc["model"] = client.model
    doc["local"] = local
    doc["timing"] = {**(timing or {}), "total_s": round(time.perf_counter() - t0, 2)}
    doc["context"] = context
    return doc


def _merge(docs):
    """Several replies as one: each place's probability is its mean over the replies (0 where absent), fields
    from its first mention; misleading texts named by at least half; the country and street of the first."""
    merged, order = {}, []
    for d in docs:
        for p in d.get("places") or []:
            key = (_norm(p.get("name")), p.get("country"))
            if key not in merged:
                merged[key] = {**p, "probability": 0.0}
                order.append(key)
            merged[key]["probability"] += float(p.get("probability") or 0) / len(docs)
    places = sorted((merged[k] for k in order), key=lambda p: -p["probability"])
    counts = {}
    for d in docs:
        for t in {_norm(t): t for t in d.get("misleading_texts") or [] if isinstance(t, str)}.items():
            counts.setdefault(t[0], [0, t[1]])[0] += 1
    return {**docs[0], "places": places, "samples": len(docs),
            "misleading_texts": [t for n, t in counts.values() if 2 * n >= len(docs)]}


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def misleading_keys(doc):
    """The normalised OCR texts the reasoning said do not name the place."""
    return {k for k in (_norm(t) for t in (doc or {}).get("misleading_texts") or []) if k}


def is_misleading(text, keys):
    value = _norm(text)
    return bool(value) and any(value == b or (len(value) >= 4 and value in b) or (len(b) >= 4 and b in value)
                               for b in keys)


def _context_point(names, municipality, country):
    if not municipality:
        return None
    found = names.lookup(municipality, countries=[country], limit=5, fuzzy=False)
    areas = [c for c in found if c.role == "area"] or found
    return (areas[0].lat, areas[0].lng) if areas else None


def clues_from_reasoning(doc, names):
    """One clue per reasoned place, looked up near its municipality when it resolves, else country-wide;
    reliability from the stated probability through fusion's VLM landmark table. Group "vlm"."""
    clues = []
    for i, p in enumerate((doc or {}).get("places") or [], 1):
        prob = p["probability"]
        label = next((k for k, v in CONFIDENCE.items() if prob >= v), "low")
        local = doc.get("local", ":" in str(doc.get("model", "")))  # Ollama names carry a tag (qwen3.5:9b)
        scale = RELIABILITY_SCALE_LOCAL if local else RELIABILITY_SCALE
        reliability = min(1.0, fusion.VLM_LANDMARK_RELIABILITY.get(label, 0.15) * scale)
        country = p["country"]
        point = _context_point(names, p.get("municipality"), country)
        found = []
        if point is not None:
            found = names.lookup(p["name"], countries=[country], limit=fusion.LOOKUP_LIMIT,
                                 near=(point[0], point[1], NEAR_RADIUS_M))
        if not found:
            found = names.lookup(p["name"], countries=[country], limit=fusion.LOOKUP_LIMIT)
        found = fusion.clean_name_candidates(found, p["name"])
        if not found and point is not None and p.get("municipality"):
            found = fusion.clean_name_candidates(
                names.lookup(p["municipality"], countries=[country], limit=5, fuzzy=False), p["municipality"])
        if found:
            clues.append(fusion._lookup_clue(f"vlm:reason:{i}", "vlm_landmark", "vlm", reliability,
                                             f"{p['name']}, {p.get('municipality') or ''}".strip(", "), found))
    return clues
