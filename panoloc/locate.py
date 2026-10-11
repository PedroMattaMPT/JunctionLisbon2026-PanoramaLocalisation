"""Locating agent for the local VLM: the exact camera position with tools (T83), through Ollama tool calls.

The same tools and prompt as the plugin's refine step: crops with a yaw scale (look), the OSM map around a point
(osm_map), the name index (search_places), aerial imagery (aerial) and bearing resection in code (triangulate),
ending with submit. The local model has an 8k context, so crops and imagery are small and only the latest images
stay in the conversation. The pipeline calls refine_run when pipeline.REFINE_LOCAL is on.

  from panoloc.locate import refine_run
  result = refine_run(models, pano, fused, reasoned, log)    # dict with lat, lng, confidence ... or None
"""
import base64
import io
import json
import math
import time
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np

MAX_STEPS = 16
DEADLINE_S = 180.0  # wall time per panorama; the caller keeps its output when it runs out
CALL_TIMEOUT_S = 90.0
EFFORT = "medium"
MAX_TOKENS = 16000
OSM_API = "https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}"
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
USER_AGENT = "panoloc/1.0 (JunctionX Lisbon 2026 hackathon; https://github.com/PedroMattaMPT)"
HTTP_TIMEOUT_S = 8.0
M_PER_DEG_LAT = 110_540.0

SYSTEM = """\
Context: this is the "Panorama Localisation" challenge run by Albatroz at the JunctionX Lisbon 2026 hackathon. The \
organisers took 360-degree panoramas in public places in Portugal, Spain and France and score each team's agent by \
the distance between its coordinate and their recorded camera position: within 25 m keeps 80% of the points in \
towns, 300 m only 25%. You are the final step of our agent. The task is about places only: never identify or \
describe any person in the images.

Earlier steps already suggest the place. Your job is to find the exact camera position with the tools:
- look: a perspective crop of the panorama at a yaw and pitch, with a yaw scale drawn on it (at pitch 0, every \
vertical line is one yaw, so read a building corner's yaw off the scale).
- osm_map: OpenStreetMap buildings, streets, paths and named points around a point, as local east/north metres.
- search_places: our place-name index (OSM, Wikidata, GeoNames).
- aerial: satellite imagery around a point, with the point marked and a scale bar.
- triangulate: give at least 3 (better 4-6) matches between a yaw you measured in the panorama and the map \
position of the same feature (a building corner, a tower, a gate, a lamp post, a pier); it solves the camera \
position and the panorama's heading by least squares and reports the residuals. Spread the features around the \
horizon, prefer sharp vertical corners, and drop matches with large residuals.
- submit: your final camera coordinate with a confidence.

You have about 3 minutes and up to 14 tool calls: use them. Confirm the place, fetch the map around it, measure \
yaws of 3-6 distinctive features you can match to map nodes (zoom in with look to read corners precisely), \
triangulate, check the residuals (under about 2 degrees RMS is good; drop or replace bad matches and solve again), \
and submit. Do not submit a map estimate before you have tried to triangulate, or at least checked the estimate \
against the aerial image and the directions of two or more mapped features. If you cannot \
match features, submit your best estimate of where the camera stood (for example from where the visible \
buildings and streets must be) with a lower confidence. If the place itself is wrong or unknown, submit the \
starting point with confidence low. Always end with submit."""

TOOLS = [
    {"name": "look", "description": "A perspective crop of the panorama, 1024 px, with a yaw scale.",
     "input_schema": {"type": "object", "properties": {
         "yaw": {"type": "number", "description": "centre yaw in degrees, 0-360, as on the overview's scale"},
         "pitch": {"type": "number", "description": "degrees up (+) or down (-); 0 gives an exact yaw scale"},
         "fov": {"type": "number", "description": "field of view in degrees, 10-120 (small = zoom in)"}},
         "required": ["yaw"]}},
    {"name": "osm_map", "description": "OpenStreetMap features within radius_m of a point (max 250 m), with node "
                                       "positions as east/north metres from that point.",
     "input_schema": {"type": "object", "properties": {
         "lat": {"type": "number"}, "lng": {"type": "number"}, "radius_m": {"type": "number"}},
         "required": ["lat", "lng"]}},
    {"name": "search_places", "description": "Look up a place name in our index; optionally near a point.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "near_lat": {"type": "number"}, "near_lng": {"type": "number"},
         "radius_km": {"type": "number"}}, "required": ["name"]}},
    {"name": "aerial", "description": "Satellite image around a point (about 150 m across at zoom 19), the point "
                                      "marked with a red cross, north up.",
     "input_schema": {"type": "object", "properties": {
         "lat": {"type": "number"}, "lng": {"type": "number"}, "zoom": {"type": "integer"}},
         "required": ["lat", "lng"]}},
    {"name": "triangulate", "description": "Camera position from yaw-to-map matches (bearing resection).",
     "input_schema": {"type": "object", "properties": {
         "matches": {"type": "array", "items": {"type": "object", "properties": {
             "yaw": {"type": "number"}, "lat": {"type": "number"}, "lng": {"type": "number"},
             "label": {"type": "string"}}, "required": ["yaw", "lat", "lng"]}}},
         "required": ["matches"]}},
    {"name": "submit", "description": "The final camera coordinate.",
     "input_schema": {"type": "object", "properties": {
         "lat": {"type": "number"}, "lng": {"type": "number"},
         "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
         "method": {"type": "string", "description": "a few words: triangulated / map estimate / starting point"}},
         "required": ["lat", "lng", "confidence", "method"]}},
]


# -- geometry ---------------------------------------------------------------------------------------

def _local(lat0, lng0):
    k = math.cos(math.radians(lat0)) * 111_320.0
    to_xy = lambda lat, lng: ((lng - lng0) * k, (lat - lat0) * M_PER_DEG_LAT)
    to_ll = lambda x, y: (lat0 + y / M_PER_DEG_LAT, lng0 + x / k)
    return to_xy, to_ll


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def triangulate(matches):
    """Least-squares bearing resection: camera (lat, lng), heading of yaw 0, RMS and per-match residuals (deg)."""
    from scipy.optimize import least_squares
    pts = [(float(m["yaw"]), float(m["lat"]), float(m["lng"]), m.get("label", "")) for m in matches]
    if len(pts) < 3:
        return {"error": "need at least 3 matches"}
    lat0 = sum(p[1] for p in pts) / len(pts)
    lng0 = sum(p[2] for p in pts) / len(pts)
    to_xy, to_ll = _local(lat0, lng0)
    xy = np.array([to_xy(p[1], p[2]) for p in pts])
    yaw = np.array([p[0] for p in pts])

    def resid(v, sel=slice(None)):
        b = np.degrees(np.arctan2(xy[sel, 0] - v[0], xy[sel, 1] - v[1]))
        return np.radians((b - yaw[sel] - v[2] + 180.0) % 360.0 - 180.0)

    def solve(sel):
        best = None
        for x in np.linspace(-400, 400, 33):
            for y in np.linspace(-400, 400, 33):
                b = np.degrees(np.arctan2(xy[sel, 0] - x, xy[sel, 1] - y))
                d = np.radians(b - yaw[sel])
                h = math.degrees(math.atan2(np.sin(d).mean(), np.cos(d).mean()))
                r = resid((x, y, h), sel)
                cost = float((r ** 2).sum())
                if best is None or cost < best[0]:
                    best = (cost, (x, y, h))
        fit = least_squares(lambda v: resid(v, sel), best[1], x_scale=[10, 10, 5])
        return fit.x

    v = solve(slice(None))
    r = np.degrees(resid(v))
    lat, lng = to_ll(v[0], v[1])
    out = {"lat": round(lat, 7), "lng": round(lng, 7), "heading_of_yaw0_deg": round(v[2] % 360, 1),
           "rms_deg": round(float(np.sqrt((r ** 2).mean())), 2),
           "residuals_deg": [{"label": p[3], "yaw": p[0], "residual": round(float(x), 2)} for p, x in zip(pts, r)]}
    if len(pts) >= 4:
        shifts = []
        for i in range(len(pts)):
            sel = np.array([j for j in range(len(pts)) if j != i])
            w = solve(sel)
            shifts.append(round(float(math.hypot(w[0] - v[0], w[1] - v[1])), 1))
        out["leave_one_out_shift_m"] = shifts
    dist = [math.hypot(*(xy[i] - v[:2])) for i in range(len(pts))]
    out["feature_distances_m"] = [round(d, 1) for d in dist]
    return out


# -- images ---------------------------------------------------------------------------------------

def _b64(img):
    from PIL import Image
    im = img if hasattr(img, "save") else Image.fromarray(img)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _image_block(img):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(img)}}


def overview(pano, width=2048):
    """The equirectangular panorama with a yaw scale every 10 degrees (labels every 30)."""
    from PIL import Image, ImageDraw
    im = Image.fromarray(pano).resize((width, width // 2), Image.Resampling.BICUBIC)
    d = ImageDraw.Draw(im)
    for yaw in range(0, 360, 10):
        x = width / 2 + (_wrap(yaw) / 360.0) * width
        major = yaw % 30 == 0
        d.line([(x, 0), (x, 18 if major else 9)], fill=(255, 255, 0), width=2)
        d.line([(x, width // 2 - (18 if major else 9)), (x, width // 2)], fill=(255, 255, 0), width=2)
        if major:
            d.text((x + 3, 20), str(yaw), fill=(255, 255, 0))
    return im


def look(pano, yaw, pitch=0.0, fov=60.0, size=1024):
    """A crop with a yaw scale; at pitch 0 each vertical line is a constant yaw (pinhole, level camera)."""
    from PIL import Image, ImageDraw
    from panoloc.views import crop
    fov = float(min(120.0, max(10.0, fov)))
    img = Image.fromarray(crop(pano, float(yaw), float(pitch), fov, size))
    d = ImageDraw.Draw(img)
    f = (size / 2) / math.tan(math.radians(fov / 2))
    step = 1 if fov <= 20 else 2 if fov <= 40 else 5 if fov <= 90 else 10
    label = step * (5 if step < 5 else 2)
    lo, hi = yaw - fov / 2, yaw + fov / 2
    for a in range(int(math.floor(lo / step) * step), int(math.ceil(hi / step) * step) + 1, step):
        x = size / 2 + f * math.tan(math.radians(a - yaw))
        if not 0 <= x < size:
            continue
        major = a % label == 0
        d.line([(x, 0), (x, 16 if major else 8)], fill=(255, 255, 0), width=2)
        d.line([(x, size - (16 if major else 8)), (x, size)], fill=(255, 255, 0), width=2)
        if major:
            d.text((x + 2, 18), f"{a % 360:g}", fill=(255, 255, 0))
            if abs(pitch) < 1e-6:
                d.line([(x, 30), (x, size - 30)], fill=(255, 255, 0), width=1)
    d.text((6, size - 30), f"yaw {yaw % 360:.0f} pitch {pitch:.0f} fov {fov:.0f}"
                           + ("" if abs(pitch) < 1e-6 else " (scale approximate off pitch 0)"), fill=(255, 255, 0))
    return img


# -- map tools ------------------------------------------------------------------------------------

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
        return r.read()


KEEP_TAGS = ("building", "amenity", "historic", "man_made", "tourism", "leisure", "railway", "highway", "barrier",
             "bridge", "waterway", "natural", "shop", "place", "landuse", "public_transport", "power")


def osm_map(lat, lng, radius_m=150.0, max_chars=14000):
    """Text listing of OSM ways and named nodes near a point, in metres east/north of it."""
    r = float(min(250.0, max(30.0, radius_m or 150.0)))
    dlat = r / M_PER_DEG_LAT
    dlng = r / (math.cos(math.radians(lat)) * 111_320.0)
    raw = _get(OSM_API.format(w=lng - dlng, s=lat - dlat, e=lng + dlng, n=lat + dlat))
    root = ET.fromstring(raw)
    to_xy, _ = _local(lat, lng)
    nodes, lines = {}, []
    for n in root.iter("node"):
        nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")))
    named = []
    for n in root.iter("node"):
        tags = {t.get("k"): t.get("v") for t in n.iter("tag")}
        if tags and any(k in tags for k in KEEP_TAGS + ("name",)):
            x, y = to_xy(*nodes[n.get("id")])
            named.append((math.hypot(x, y), f"node {_tagtext(tags)} at E{x:+.1f} N{y:+.1f} "
                                            f"({nodes[n.get('id')][0]:.6f}, {nodes[n.get('id')][1]:.6f})"))
    ways = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        if not tags or not any(k in tags for k in KEEP_TAGS):
            continue
        refs = [nd.get("ref") for nd in w.iter("nd") if nd.get("ref") in nodes]
        if len(refs) < 2:
            continue
        pts = [nodes[x] for x in refs]
        xy = [to_xy(*p) for p in pts]
        d = min(math.hypot(*p) for p in xy)
        if "building" in tags and refs[0] == refs[-1]:
            xy, pts = xy[:-1], pts[:-1]
        if len(xy) > 14:
            idx = np.linspace(0, len(xy) - 1, 14).round().astype(int)
            xy, pts = [xy[i] for i in idx], [pts[i] for i in idx]
        coords = " ".join(f"[E{x:+.1f} N{y:+.1f}]" for x, y in xy)
        ways.append((d, f"way {_tagtext(tags)}: {coords}"))
    ways.sort()
    named.sort()
    lines = [f"OSM around ({lat:.6f}, {lng:.6f}), radius {r:.0f} m; E/N metres from that point. "
             f"lat = {lat:.6f} + N/{M_PER_DEG_LAT:.0f}, lng = {lng:.6f} + E/{math.cos(math.radians(lat)) * 111320:.0f}."]
    for _, t in named[:60]:
        lines.append(t)
    for _, t in ways:
        lines.append(t)
    text = "\n".join(lines)
    return text[:max_chars] + ("\n... (truncated; ask a smaller radius around the camera)" if len(text) > max_chars else "")


def _tagtext(tags):
    keys = [k for k in ("name", "building", "amenity", "historic", "man_made", "tourism", "leisure", "railway",
                        "highway", "barrier", "bridge", "shop", "natural", "public_transport", "height",
                        "building:levels") if k in tags]
    return "{" + ", ".join(f"{k}={tags[k]}" for k in keys) + "}"


def _tile(lat, lng, z):
    n = 2 ** z
    x = (lng + 180.0) / 360.0 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def aerial(lat, lng, zoom=19):
    """A 512 px north-up mosaic of 2x2 imagery tiles centred on the point, with a cross and a 25 m scale bar."""
    from PIL import Image, ImageDraw
    z = int(min(20, max(15, zoom or 19)))
    fx, fy = _tile(lat, lng, z)
    x0, y0 = int(math.floor(fx - 0.5)), int(math.floor(fy - 0.5))
    mosaic = Image.new("RGB", (512, 512))
    for i in range(2):
        for j in range(2):
            data = _get(ESRI.format(z=z, x=x0 + i, y=y0 + j))
            mosaic.paste(Image.open(io.BytesIO(data)).convert("RGB"), (256 * i, 256 * j))
    px, py = (fx - x0) * 256, (fy - y0) * 256
    d = ImageDraw.Draw(mosaic)
    d.line([(px - 10, py), (px + 10, py)], fill=(255, 0, 0), width=2)
    d.line([(px, py - 10), (px, py + 10)], fill=(255, 0, 0), width=2)
    m_per_px = 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)
    bar = 25.0 / m_per_px
    d.line([(10, 500), (10 + bar, 500)], fill=(255, 255, 255), width=3)
    d.text((10, 484), "25 m", fill=(255, 255, 255))
    return mosaic, round(m_per_px, 3)


# -- the loop (Ollama tool calls) -------------------------------------------------------------------

LOCAL_LOOK_SIZE = 640
LOCAL_MAX_STEPS = 10
LOCAL_KEEP_IMAGES = 2
LOCAL_NUM_PREDICT = 800


def _ollama_tools():
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in TOOLS]


def _local_tool(name, args, pano, names):
    """(text, images) for one tool call; images are base64 JPEGs for the next user turn."""
    if name == "look":
        img = look(pano, float(args.get("yaw", 0)), float(args.get("pitch", 0) or 0), float(args.get("fov", 60) or 60),
                   size=LOCAL_LOOK_SIZE)
        return f"crop at yaw {float(args.get('yaw', 0)):.0f} attached", [_b64(img)]
    if name == "aerial":
        img, mpp = aerial(float(args["lat"]), float(args["lng"]), int(args.get("zoom") or 19))
        return f"aerial image attached, {mpp} m per pixel, north up", [_b64(img)]
    if name == "osm_map":
        return osm_map(float(args["lat"]), float(args["lng"]), float(args.get("radius_m") or 150), max_chars=6000), []
    if name == "search_places":
        near = None
        if args.get("near_lat") is not None and args.get("near_lng") is not None:
            near = (float(args["near_lat"]), float(args["near_lng"]), float(args.get("radius_km") or 20) * 1000)
        found = names.lookup(str(args.get("name", "")), limit=6, near=near)
        return "\n".join(f"{c.label} ({c.lat:.6f}, {c.lng:.6f}) {c.role} {c.country}" for c in found) or "no match", []
    if name == "triangulate":
        return json.dumps(triangulate(args.get("matches") or [])), []
    return f"unknown tool {name}", []


def refine_local(client, pano, context, start, *, log=None, deadline_s=DEADLINE_S):
    """The agent loop on an OllamaClient; returns the submitted dict or None."""
    from panoloc.names import NameIndex
    t0 = time.perf_counter()
    first = {"role": "user", "images": [_b64(overview(pano, width=1536))],
             "content": f"The panorama overview is attached (yaw scale on top and bottom; yaw 0 at the centre).\n\n"
                        f"Earlier steps found:\n{context}\n\nStarting point (our current answer): "
                        f"{start[0]:.6f}, {start[1]:.6f}. Find the camera position and submit it."}
    messages = [{"role": "system", "content": SYSTEM}, first]
    tools_used = []
    with NameIndex.open() as names:
        for step in range(LOCAL_MAX_STEPS):
            remaining = deadline_s - (time.perf_counter() - t0)
            if remaining < 15:
                break
            if step >= LOCAL_MAX_STEPS - 2 or remaining < 50:
                messages.append({"role": "user", "content": "Time is nearly up: call submit now."})
            with_images = [m for m in messages if m.get("images")]
            for m in with_images[:-LOCAL_KEEP_IMAGES]:  # the context is small: older images go
                m.pop("images")
                m["content"] = (m.get("content") or "") + " (image no longer attached)"
            payload = {"model": client.model, "messages": messages, "tools": _ollama_tools(), "stream": False,
                       "keep_alive": client.keep_alive, "options": client.options(LOCAL_NUM_PREDICT)}
            if client.think is not None:
                payload["think"] = client.think
            response, _ = client._call("POST", "/api/chat", payload, max(10.0, remaining - 5), "a refine turn")
            message = response.get("message") or {}
            calls = message.get("tool_calls") or []
            messages.append({"role": "assistant", "content": message.get("content") or "",
                             **({"tool_calls": calls} if calls else {})})
            if not calls:
                messages.append({"role": "user", "content": "Use the tools; end with submit."})
                continue
            new_images = []
            for call in calls:
                fn = call.get("function") or {}
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                if name == "submit":
                    try:
                        return {"lat": float(args["lat"]), "lng": float(args["lng"]),
                                "confidence": args.get("confidence", "low"), "method": str(args.get("method", "")),
                                "steps": step + 1, "tools": tools_used, "elapsed_s": round(time.perf_counter() - t0, 1)}
                    except (KeyError, TypeError, ValueError):
                        messages.append({"role": "tool", "content": "submit needs numeric lat and lng", "tool_name": "submit"})
                        continue
                try:
                    text, images = _local_tool(name, args, pano, names)
                    ok = True
                except Exception as exc:  # a failing tool is reported back, not fatal
                    text, images, ok = f"{name} failed: {type(exc).__name__}: {exc}"[:300], [], False
                entry = {"tool": name, "input": {k: v for k, v in args.items() if k != "matches"}
                         | ({"matches": len(args.get("matches", []))} if name == "triangulate" else {}), "ok": ok}
                if name == "triangulate" and ok:
                    entry["result"] = json.loads(text)
                tools_used.append(entry)
                if log:
                    log(entry)
                messages.append({"role": "tool", "content": text, "tool_name": name})
                new_images += images
            if new_images:
                messages.append({"role": "user", "content": "Images from the tools above.", "images": new_images})
    return None


def refine_run(models, pano, fused, reasoned, log):
    """The pipeline hook for the local VLM (pipeline.REFINE_LOCAL)."""
    places = "; ".join(f"{p['name']} ({p.get('municipality')}, {p['country']}) p={p['probability']:.2f}"
                       for p in (reasoned or {}).get("places", []))
    hyps = "; ".join(f"{h.label or h.source} ({h.lat:.5f}, {h.lng:.5f}) w={h.weight:.2f}" for h in fused.hypotheses[:6])
    context = f"Places named from the whole panorama: {places or 'none'}\nOur combined candidates: {hyps}"
    tool_log = lambda t: log({"observation": f"{t['tool']} {json.dumps(t['input'])[:200]}"
                              + ("" if t["ok"] else " (failed)"), **t})
    return refine_local(models.vlm_local(), pano, context, (fused.output.lat, fused.output.lng), log=tool_log)
