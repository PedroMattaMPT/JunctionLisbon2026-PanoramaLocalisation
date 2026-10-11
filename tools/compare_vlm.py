#!/usr/bin/env python3
"""Compare two Ollama VLMs on the checklist and on exact sign transcription (T47, MODEL_DECISIONS.md check 2).

Check 2 keeps qwen3.5:9b as the VLM if it is at least as accurate as gemma4:12b, at most 9 GB resident and
at most 60 s for 10 crops; otherwise the role goes to Gemma. This tool measures that on about 20 views cut
from external Panoramax panoramas of the val split (never the final split, never the warm-up set) and on
the signs legible in them, against labels written by hand from the images before any answer was read.

Steps, all under runs/vlm_compare/ (gitignored):
  sheets  contact sheets of candidate val panoramas (their 8 horizontal views, small) to pick views by
          eye: sheets/sheet_NN.jpg and sheets.json
  crops   picks.json -> crops/<crop>.jpg, the exact JPEG the pipeline sends for that view (views.cut_views,
          then vlm.encode_image), and signs/<sign>.jpg for each sign box drawn on a view: ocr.reread_view
          at the panorama's own resolution, encoded as vlm.transcribe encodes it; plus crops.json
          (panorama, view, GPS, country)
  run     one model over every crop (vlm.describe_view: the pipeline's request, plan "single", num_ctx
          8192) and every sign (vlm.transcribe); writes outputs/<model>.json. It prints timings only,
          never answers, so the labels stay blind. --window brackets a model the other sessions must not
          meet: it writes .gemma_window (this PID) first, sends keep_alive 10m instead of -1 (a crash can't
          leave the model resident for good), and on success, failure, Ctrl-C or SIGTERM unloads it
          (keep_alive 0, then `ollama stop`), waits until /api/ps no longer lists it, and only then
          deletes the marker
  score   labels.json + outputs/*.json -> report.json and a table

picks.json: {"views": [{"crop": "PT-01", "id": <Panoramax id>, "view": "h045", "why": ..., "signs":
[[x0, y0, x1, y1], ...]}]}, sign boxes in the 1024 px view's pixels.
labels.json: {"crops": {crop: {key: value | [values] | "not_visible" | "unsure"}}, "signs": {sign: [lines]}};
keys starting with "_" are notes. A list holds visible values that all fit what the crop shows (pines on
flat land are maritime_pine and flat_pine_monoculture), and any of them matches. A key left out counts as
unsure, and unsure keys are not scored. A sign's lines are the ones fully legible in its crop, written as
vlm.transcribe is told to write them: capitals, accents and punctuation as on the sign.

Scoring conventions:
- Agreement: answer == label over the scored (crop, key) pairs. A visible label (an option or "other")
  answered not_visible is a false-invisible; a not_visible label answered with anything else is a
  false-visible; two different visible values are a wrong value; "invalid" is its own outcome. Agreement
  on the visible labels alone is reported too, since most keys are not visible in most crops.
- Groups: large features (LARGE_KEYS: sign language, walls and facades, roofs, pavement), where T15 found
  qwen reliable, and small road furniture (SMALL_KEYS: poles, delineators and guardrail reflectors, sign
  rims, crossing-sign stripes), where it did not; the other keys.
- Paired: on the pairs both models were scored on, how many only one model got right, with an exact
  two-sided sign test. Twenty crops are few: a gap of a handful of pairs is noise.
- Country call per crop: the hints vlm.hints derives from that crop alone, each adding its strength weight
  (STRENGTH_WEIGHT) split evenly over its countries; the top country, none when tied or without hints. It
  is scored against the country whose outline the panorama's GPS lies in (Panoramax sampled it there),
  with the precision of the hints themselves. The same call from the labels shows what there was to see.
- Landmarks: a labelled place counts as named when a hypothesis holds all its key tokens (after
  panoloc.names.normalise); naming a place in a crop with none labelled is counted apart.
- Transcription: a sign crop usually holds several pieces of text, and a whole-crop exact match would
  hinge on reading order, so each legible line is scored: found exactly in the transcription (case,
  accents and punctuation kept; Unicode NFC, straight quotes, line breaks and spaces collapsed; not inside
  a longer word), found ignoring case, and its character error rate against the closest substring.
- Time: per crop, Ollama's prompt + generation durations ("compute") and the wall time less any load;
  "10 crops" is 10 x the mean. tokens/s is eval_count / eval_duration. The GPU is capped at 80 W and shared
  with other sessions (embedding jobs; other requests queue in the same runner), so these are upper bounds
  on time, the wall times more so.
- VRAM: Ollama's size_vram (/api/ps) for the model, and nvidia-smi's memory for the Ollama runner process
  serving it (found by its model blob in the command line), sampled every SAMPLE_S seconds.

Usage, from the repo root, with the venv:
  .venv/bin/python tools/compare_vlm.py sheets [--n PT=20,ES=8,FR=8] [--seed 0] [--skip PT=20 --name sheets2]
  .venv/bin/python tools/compare_vlm.py crops
  .venv/bin/python tools/compare_vlm.py run --model gemma4:12b --window --evict qwen3.5:9b
  .venv/bin/python tools/compare_vlm.py run --model qwen3.5:9b
  .venv/bin/python tools/compare_vlm.py score [--a qwen3.5:9b --b gemma4:12b]
"""
import argparse
import base64
import csv
import inspect
import io
import json
import math
import os
import random
import re
import signal
import statistics
import unicodedata
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from panoloc import vlm  # noqa: E402
from panoloc.names import normalise  # noqa: E402
from panoloc.runlog import atomic_write_json  # noqa: E402

SCHEMA = "panoloc.compare_vlm/1"
OUT = ROOT / "runs" / "vlm_compare"
PANORAMAX = ROOT / "Data" / "panoramax"
COUNTRIES = ("PT", "ES", "FR")
SPLIT = "val"  # the final split is reserved for one run (T54)
WINDOW_MARKER = ".gemma_window"
WINDOW_KEEP_ALIVE = "10m"
MIN_FREE_MIB = 8192  # gemma4:12b at num_ctx 8192 needs about 8 GB once qwen is evicted
SHEET_VIEW_PX = 320
SAMPLE_S = 2.0
UNSURE = "unsure"
OUTCOMES = ("match", "false_visible", "false_invisible", "wrong_value", "invalid")
LARGE_KEYS = ("sign_language", "wall_finish", "roof", "pavement")
SMALL_KEYS = ("utility_pole", "bollard", "guardrail_reflectors", "red_sign_rim", "pedestrian_sign")
KEY_GROUPS = {"all": vlm.KEYS, "large": LARGE_KEYS, "small": SMALL_KEYS,
              "rest": tuple(k for k in vlm.KEYS if k not in LARGE_KEYS + SMALL_KEYS)}
STRENGTH_WEIGHT = {"strong": 4, "medium-strong": 3, "medium": 2, "weak": 1}
OLLAMA_FIELDS = ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count",
                 "eval_duration", "done_reason")
TRANSCRIBE_SIDES = {k: inspect.signature(vlm.transcribe).parameters[k].default for k in ("max_side", "min_side")}
CHECK2 = {"resident_gb": 9.0, "ten_crops_s": 60.0}
DEFAULT_A, DEFAULT_B = vlm.DEFAULT_MODEL, vlm.FALLBACK_MODEL


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def slug(model):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def ratio(a, b, digits=3):
    return round(a / b, digits) if b else None


# -- candidates and crops ---------------------------------------------------------------------------

def read_rows():
    """Every Panoramax row by id, with the country whose outline it was sampled in."""
    rows = {}
    for country in COUNTRIES:
        with open(PANORAMAX / f"{country}.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows[row["id"]] = {**row, "country": country}
    return rows


def image_path(row):
    return PANORAMAX / "images" / row["country"] / f"{row['id']}.jpg"


def sample_candidates(counts, seed=0, rows=None, skip=None):
    """Val panoramas to look at: per country, one per collection, collections in a seeded random order,
    after the first skip[country] of that order (a later batch of the same order)."""
    rows = rows or read_rows()
    rng = random.Random(seed)
    out = []
    for country, n in counts.items():
        first = (skip or {}).get(country, 0)
        by_collection = {}
        for row in sorted(rows.values(), key=lambda r: r["id"]):
            if row["country"] == country and row["split"] == SPLIT and image_path(row).exists():
                by_collection.setdefault(row["collection"], []).append(row)
        collections = sorted(by_collection)
        rng.shuffle(collections)
        out += [rng.choice(by_collection[c]) for c in collections[:first + n]][first:]
    return out


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_sheets(counts, seed=0, out=OUT, per_sheet=2, skip=None, name="sheets"):
    from PIL import Image, ImageDraw
    from panoloc.views import cut_views, load_panorama
    font, s, head = _font(18), SHEET_VIEW_PX, 28
    candidates = sample_candidates(counts, seed, skip=skip)
    (out / name).mkdir(parents=True, exist_ok=True)
    doc = {"schema": SCHEMA, "split": SPLIT, "seed": seed, "counts": counts, "skip": skip or {}, "sheets": []}
    for i in range(0, len(candidates), per_sheet):
        group = candidates[i:i + per_sheet]
        sheet = Image.new("RGB", (4 * s, len(group) * (2 * s + head)), "white")
        draw = ImageDraw.Draw(sheet)
        entries = []
        for j, row in enumerate(group):
            tag, y0 = f"{row['country']}-c{i + j:02d}", j * (2 * s + head)
            views = [v for v in cut_views(load_panorama(image_path(row)), size=s) if v.name.startswith("h")]
            draw.text((4, y0 + 4), f"{tag}  {row['id'][:8]}  {row['camera_model']}", fill="black", font=font)
            for k, v in enumerate(views):
                x, y = (k % 4) * s, y0 + head + (k // 4) * s
                sheet.paste(Image.fromarray(v.image), (x, y))
                draw.text((x + 4, y + 4), v.name, fill="yellow", font=font, stroke_width=2, stroke_fill="black")
            entries.append({"tag": tag, "country": row["country"], "id": row["id"], "collection": row["collection"]})
        file = f"{name}/sheet_{i // per_sheet:02d}.jpg"
        sheet.save(out / file, quality=85)
        doc["sheets"].append({"file": file, "panoramas": entries})
        print(file, " ".join(e["tag"] for e in entries), flush=True)
    atomic_write_json(out / f"{name}.json", doc)
    return doc


def make_crops(out=OUT):
    """picks.json -> the crops and sign crops as the pipeline would send them, and crops.json."""
    from PIL import Image
    from panoloc.ocr import reread_view
    from panoloc.views import box_to_sphere, cut_views, load_panorama
    picks = load_json(out / "picks.json")["views"]
    rows = read_rows()
    for folder in ("crops", "signs"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    by_panorama = {}
    for pick in picks:
        by_panorama.setdefault(pick["id"], []).append(pick)
    crops, signs = [], []
    for pid, group in by_panorama.items():
        row = rows[pid]
        if row["split"] != SPLIT:
            raise SystemExit(f"{pid} is in the {row['split']} split; only {SPLIT} panoramas may be used")
        pano = load_panorama(image_path(row))
        views = {v.name: v for v in cut_views(pano)}
        for pick in group:
            view = views[pick["view"]]
            file = f"crops/{pick['crop']}.jpg"
            (out / file).write_bytes(base64.b64decode(vlm.encode_image(view)))
            crops.append({"crop": pick["crop"], "file": file, "country": row["country"], "id": pid,
                          "collection": row["collection"], "lat": float(row["lat"]), "lon": float(row["lon"]),
                          "panorama": str(image_path(row).relative_to(ROOT)), "camera": row["camera_model"],
                          "panorama_size": [int(pano.shape[1]), int(pano.shape[0])], "view": view.name,
                          "yaw_deg": view.yaw_deg, "pitch_deg": view.pitch_deg, "fov_deg": view.fov_deg,
                          "size_px": int(view.image.shape[0]), "masked_fraction": round(view.masked_fraction, 4),
                          "why": pick.get("why", "")})
            for k, box in enumerate(pick.get("signs", []), 1):
                sign = f"{pick['crop']}-s{k}"
                sphere = box_to_sphere(view, *box)
                reread = reread_view(pano, sphere, name=sign)
                data = base64.b64decode(vlm.encode_image(reread, **TRANSCRIBE_SIDES))
                (out / "signs" / f"{sign}.jpg").write_bytes(data)
                with Image.open(io.BytesIO(data)) as im:
                    sent = list(im.size)
                signs.append({"sign": sign, "crop": pick["crop"], "file": f"signs/{sign}.jpg", "box_view_px": box,
                              "box": sphere, "fov_deg": round(reread.fov_deg, 2),
                              "reread_px": int(reread.image.shape[0]), "sent_px": sent})
        del pano, views
    order = {p["crop"]: i for i, p in enumerate(picks)}
    crops.sort(key=lambda c: order[c["crop"]])
    signs.sort(key=lambda s: (order[s["crop"]], s["sign"]))
    doc = {"schema": SCHEMA, "split": SPLIT, "built": now(),
           "crops_note": "the exact JPEG bytes the pipeline sends for each view (vlm.encode_image of views.cut_views)",
           "signs_note": f"ocr.reread_view around each box, encoded as vlm.transcribe does ({TRANSCRIBE_SIDES})",
           "crops": crops, "signs": signs}
    atomic_write_json(out / "crops.json", doc)
    print(f"{len(crops)} crops ({dict(Counter(c['country'] for c in crops))}), {len(signs)} signs -> {out}")
    return doc


# -- GPU and Ollama state ---------------------------------------------------------------------------

def _num(text):
    try:
        return float(text)
    except ValueError:
        return None


def nvidia_smi():
    def query(what):
        result = subprocess.run(["nvidia-smi", what, "--format=csv,noheader,nounits"], capture_output=True,
                                text=True, timeout=15)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    try:
        used, total, util, power = (x.strip() for x in
                                    query("--query-gpu=memory.used,memory.total,utilization.gpu,power.draw")[0].split(","))
        procs = []
        for line in query("--query-compute-apps=pid,process_name,used_memory"):
            parts = [p.strip() for p in line.split(",")]
            procs.append({"pid": int(parts[0]), "name": ",".join(parts[1:-1]), "mib": int(parts[-1])})
        return {"used_mib": int(used), "total_mib": int(total), "util_pct": _num(util), "power_w": _num(power),
                "procs": procs}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        return {"error": str(exc)}


def ollama_get(host, path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(host + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_ps(host):
    """The models Ollama holds now, or None when it doesn't answer."""
    try:
        models = ollama_get(host, "/api/ps").get("models", [])
    except (OSError, ValueError):
        return None
    return [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length", "expires_at")} for m in models]


def resident(ps, model):
    return [m for m in (ps or []) if m.get("name") == model]


def model_blob(host, model):
    """The model's weights file, which its runner process names in its command line."""
    try:
        modelfile = ollama_get(host, "/api/show", {"model": model}).get("modelfile", "")
    except (OSError, ValueError):
        return None
    match = re.search(r"^FROM\s+(\S*sha256-[0-9a-f]+)", modelfile, re.MULTILINE)
    return match.group(1) if match else None


def runner_pids(blob):
    if not blob:
        return []
    try:
        lines = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(line.split(None, 1)[0]) for line in lines.splitlines() if blob in line and "--model" in line]


def _cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()[:160]
    except OSError:
        return None


def gpu_snapshot(host, blob=None):
    smi = nvidia_smi()
    for proc in smi.get("procs", []):
        proc["cmd"] = _cmdline(proc["pid"])  # nvidia-smi only says ".venv/bin/python"
    return {"t": round(time.time(), 1), "smi": smi, "ps": ollama_ps(host), "runner_pids": runner_pids(blob)}


class GPUSampler(threading.Thread):
    """nvidia-smi, /api/ps and the model's runner PIDs every SAMPLE_S seconds while a pass runs."""

    def __init__(self, host, blob):
        super().__init__(daemon=True)
        self.host, self.blob, self.samples = host, blob, []
        self._halt = threading.Event()

    def run(self):
        while not self._halt.is_set():
            self.samples.append(gpu_snapshot(self.host, self.blob))
            self._halt.wait(SAMPLE_S)

    def stop(self):
        self._halt.set()
        self.join(timeout=30)


def gpu_summary(samples, model):
    """Peaks over the samples: the model's size_vram, its runner's nvidia-smi memory, the whole GPU; and the
    other processes on the GPU (another model's runner, embedding jobs), with the share of samples each was
    in, which says how comparable two passes' timings are."""
    size_vram = [m["size_vram"] for s in samples for m in resident(s.get("ps"), model) if m.get("size_vram")]
    runner_mib, others, other_totals = [], {}, []
    for s in samples:
        procs = s.get("smi", {}).get("procs", [])
        mine = [p["mib"] for p in procs if p["pid"] in s.get("runner_pids", [])]
        if mine:
            runner_mib.append(sum(mine))
        rest = [p for p in procs if p["pid"] not in s.get("runner_pids", [])]
        other_totals.append(sum(p["mib"] for p in rest))
        for p in rest:
            o = others.setdefault(p["pid"], {"pid": p["pid"], "name": p["name"], "cmd": p.get("cmd"), "mib_peak": 0,
                                             "samples": 0})
            o["mib_peak"], o["samples"] = max(o["mib_peak"], p["mib"]), o["samples"] + 1
    used = [s["smi"]["used_mib"] for s in samples if "used_mib" in s.get("smi", {})]
    util = [s["smi"]["util_pct"] for s in samples if s.get("smi", {}).get("util_pct") is not None]
    return {"samples": len(samples),
            "size_vram_gb": round(max(size_vram) / 1e9, 2) if size_vram else None,
            "size_vram_gib": round(max(size_vram) / 2**30, 2) if size_vram else None,
            "runner_gb": round(max(runner_mib) * 2**20 / 1e9, 2) if runner_mib else None,
            "runner_mib": max(runner_mib) if runner_mib else None,
            "gpu_used_mib_peak": max(used) if used else None,
            "gpu_util_pct_mean": round(statistics.mean(util), 1) if util else None,
            "other_mib_peak": max(other_totals) if other_totals else None,
            "other_share": ratio(sum(t > 0 for t in other_totals), len(other_totals)),
            "other_processes": [{**{k: v for k, v in o.items() if k != "samples"}, "share": ratio(o["samples"], len(samples))}
                                for o in others.values()]}


def free_after_evict(snapshot):
    """Free GPU memory once Ollama evicts what it holds (Ollama's runners are the evictable part)."""
    smi = snapshot.get("smi", {})
    if "used_mib" not in smi:
        return None
    runners = sum(p["mib"] for p in smi["procs"] if "ollama" in p["name"] or "llama-server" in p["name"])
    return smi["total_mib"] - smi["used_mib"] + runners


# -- one model's pass -------------------------------------------------------------------------------

def _terminate(signum, frame):
    raise SystemExit(128 + signum)  # so the finally clauses unload the model and remove the marker


def unload_and_confirm(client, host, wait_s=90):
    """keep_alive 0, then `ollama stop` if the model is still listed halfway; True once /api/ps drops it."""
    doc = {"keep_alive_0": None, "ollama_stop": None, "gone": False}
    try:
        client.unload()
        doc["keep_alive_0"] = "sent"
    except vlm.VLMError as exc:
        doc["keep_alive_0"] = f"failed: {exc}"
    start, stopped = time.monotonic(), False
    while time.monotonic() - start < wait_s:
        ps = ollama_ps(host)
        if ps is not None and not resident(ps, client.model):
            doc["gone"] = True
            break
        if not stopped and time.monotonic() - start > wait_s / 3:
            stopped = True
            try:
                doc["ollama_stop"] = subprocess.run(["ollama", "stop", client.model], capture_output=True,
                                                    text=True, timeout=60).returncode
            except (OSError, subprocess.SubprocessError) as exc:
                doc["ollama_stop"] = f"failed: {exc}"
        time.sleep(1)
    doc["ps"], doc["at"] = ollama_ps(host), now()
    return doc


def _requests_timing(reqs):
    def total(k):
        return sum((q.get(k) or 0) for q in reqs)
    return {"requests": len(reqs), "load_s": round(total("load_duration") / 1e9, 3),
            "prompt_tokens": total("prompt_eval_count"), "prompt_s": round(total("prompt_eval_duration") / 1e9, 3),
            "output_tokens": total("eval_count"), "output_s": round(total("eval_duration") / 1e9, 3)}


def describe_crop(client, crop, captured, out=OUT):
    """The pipeline's checklist request for one crop, from the JPEG bytes the pipeline would send."""
    view = SimpleNamespace(name=crop["view"], yaw_deg=crop["yaw_deg"], pitch_deg=crop["pitch_deg"],
                           fov_deg=crop["fov_deg"], masked_fraction=crop["masked_fraction"],
                           image=(out / crop["file"]).read_bytes())
    start = len(captured)
    try:
        r = vlm.describe_view(client, view)
    except (vlm.VLMTimeout, vlm.VLMInvalidResponse) as exc:
        return {"error": {"type": type(exc).__name__, "message": str(exc)}, "ollama": captured[start:]}
    return {"answers": r.answers, "invalid": r.invalid, "landmarks": r.landmarks,
            "rejected_landmarks": r.rejected_landmarks, "requests": r.requests, "latency_s": r.latency_s,
            "raw": r.raw, "ollama": captured[start:]}


def transcribe_sign(client, sign, captured, out=OUT):
    start, t0 = len(captured), time.perf_counter()
    try:
        r = vlm.transcribe((out / sign["file"]).read_bytes(), client)
    except (vlm.VLMTimeout, vlm.VLMInvalidResponse) as exc:
        return {"error": {"type": type(exc).__name__, "message": str(exc)}, "ollama": captured[start:]}
    return {"text": r["text"], "legible": r["legible"], "latency_s": round(time.perf_counter() - t0, 3),
            "ollama": captured[start:]}


def run_pass(model, *, host=vlm.DEFAULT_HOST, window=False, force=False, timeout_s=vlm.DEFAULT_TIMEOUT_S,
             evict=(), out=OUT):
    """Checklist on every crop, then transcription of every sign, with one model; writes outputs/<model>.json.

    evict: models to unload (keep_alive 0) right before the load. Ollama 0.34.4 never evicts a model held
    with keep_alive -1 (the pipeline's setting) to make room for another one: a plain gemma4:12b load next to
    an idle qwen3.5:9b waited out its 5 minutes, and with --evict qwen3.5:9b it took 8 s (2026-10-11). A
    client still sending requests to the evicted model reloads it, so other VLM users must be quiet.
    """
    crops_doc = load_json(out / "crops.json")
    captured = []

    def transport(method, url, payload, timeout):
        response = vlm._post_json(method, url, payload, timeout)
        if url.endswith("/api/chat"):
            captured.append({k: response.get(k) for k in OLLAMA_FIELDS})
        return response

    client = vlm.OllamaClient(model, host, num_ctx=vlm.DEFAULT_NUM_CTX, timeout_s=timeout_s, transport=transport,
                              keep_alive=WINDOW_KEEP_ALIVE if window else -1)
    doc = {"schema": SCHEMA, "model": model, "settings": client.settings(), "window": window, "started": now(),
           "crops": {}, "signs": {}, "error": None}
    marker = out / WINDOW_MARKER
    blob = model_blob(host, model)
    sampler = GPUSampler(host, blob)
    previous = signal.signal(signal.SIGTERM, _terminate)
    if window:
        marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        print(f"window open: {marker.relative_to(ROOT)} holds PID {os.getpid()}", flush=True)
    try:
        doc["ollama_version"] = client.version()
        doc["gpu_before"] = gpu_snapshot(host, blob)
        free = free_after_evict(doc["gpu_before"])
        doc["free_mib_after_evict"] = free
        print(f"{model}: GPU {doc['gpu_before']['smi'].get('used_mib')} MiB used, {free} MiB free once Ollama "
              f"evicts its models; resident: {[m['name'] for m in doc['gpu_before']['ps'] or []]}", flush=True)
        if window and free is not None and free < MIN_FREE_MIB and not force:
            raise SystemExit(f"only {free} MiB would be free for {model}; need {MIN_FREE_MIB} (--force to try)")
        sampler.start()
        doc["evicted"] = []
        for other in evict:
            try:
                vlm.OllamaClient(other, host, retries=0).unload()
                doc["evicted"].append({"model": other, "at": now()})
            except vlm.VLMError as exc:
                doc["evicted"].append({"model": other, "error": str(exc)})
        t0 = time.perf_counter()
        loader = vlm.OllamaClient(model, host, num_ctx=vlm.DEFAULT_NUM_CTX, keep_alive=client.keep_alive, retries=0,
                                  load_timeout_s=vlm.DEFAULT_LOAD_TIMEOUT_S, transport=transport)
        doc["load_s"] = loader.load()  # one attempt: VLMTimeout after vlm.DEFAULT_LOAD_TIMEOUT_S (5 min)
        doc["ps_after_load"] = ollama_ps(host)
        print(f"loaded in {doc['load_s']} s: {resident(doc['ps_after_load'], model)}", flush=True)
        for crop in crops_doc["crops"]:
            rec = doc["crops"][crop["crop"]] = describe_crop(client, crop, captured, out)
            t = _requests_timing(rec["ollama"])
            print(f"  {crop['crop']:<7} {rec.get('latency_s', 0):6.2f} s  load {t['load_s']:5.2f}  prompt "
                  f"{t['prompt_tokens']:5d} tok {t['prompt_s']:5.2f} s  out {t['output_tokens']:4d} tok "
                  f"{t['output_s']:5.2f} s  requests {t['requests']}" + (f"  ERROR {rec['error']['type']}"
                                                                         if rec.get("error") else ""), flush=True)
        for sign in crops_doc["signs"]:
            rec = doc["signs"][sign["sign"]] = transcribe_sign(client, sign, captured, out)
            t = _requests_timing(rec["ollama"])
            print(f"  {sign['sign']:<10} {rec.get('latency_s', 0):6.2f} s  prompt {t['prompt_tokens']:5d} tok  out "
                  f"{t['output_tokens']:4d} tok" + (f"  ERROR {rec['error']['type']}" if rec.get("error") else ""),
                  flush=True)
        doc["pass_s"] = round(time.perf_counter() - t0, 3)
        doc["ps_after_pass"] = ollama_ps(host)
    except vlm.VLMError as exc:
        doc["error"] = {"type": type(exc).__name__, "message": str(exc), "at": now()}
        print(f"pass failed: {type(exc).__name__}: {exc}", flush=True)
    finally:
        sampler.stop()
        if window:
            doc["unload"] = unload_and_confirm(client, host)
            marker.unlink(missing_ok=True)
            print(f"window closed: {model} gone from ollama ps: {doc['unload']['gone']}", flush=True)
        signal.signal(signal.SIGTERM, previous)
        doc["finished"] = now()
        doc["gpu_samples"] = sampler.samples
        doc["gpu"] = gpu_summary(sampler.samples, model)
        (out / "outputs").mkdir(parents=True, exist_ok=True)
        atomic_write_json(out / "outputs" / f"{slug(model)}.json", doc)
    t = timing_summary(doc)
    g = doc["gpu"]
    print(f"{model}: {t['crops']} crops, compute {t['compute_s_mean']} s/crop (10 crops {t['ten_crops_compute_s']} s), "
          f"wall {t['wall_s_mean']} s/crop (10 crops {t['ten_crops_wall_s']} s), {t['output_tok_s']} tok/s; "
          f"VRAM {g['size_vram_gb']} GB (ollama ps), runner {g['runner_gb']} GB (nvidia-smi); other GPU jobs in "
          f"{g['other_share']} of the samples, up to {g['other_mib_peak']} MiB: "
          + "; ".join(f"{o['pid']} {o['cmd'] or o['name']} ({o['mib_peak']} MiB, {o['share']})" for o in g["other_processes"]))
    return doc


# -- scoring ----------------------------------------------------------------------------------------

def compare_answer(answer, label):
    """One answer against one label: None when the label is unsure or missing, else one of OUTCOMES.
    A list label holds several values that all fit what the crop shows; any of them matches."""
    if label is None or label == UNSURE:
        return None
    if answer == label or (isinstance(label, list) and answer in label):
        return "match"
    if answer is None or answer == vlm.INVALID:
        return "invalid"
    if label == vlm.NOT_VISIBLE:
        return "false_visible"
    if answer == vlm.NOT_VISIBLE:
        return "false_invisible"
    return "wrong_value"


def check_labels(labels):
    """Raise on a key or value the checklist doesn't have: a typo must not become a scored label."""
    problems = []
    for crop, keys in labels.get("crops", {}).items():
        for key, value in keys.items():
            if key.startswith("_"):
                continue
            values = value if isinstance(value, list) else [value]
            if key not in vlm.ITEMS:
                problems.append(f"{crop}: unknown key {key}")
            elif isinstance(value, list) and (not value or vlm.NOT_VISIBLE in value or UNSURE in value):
                problems.append(f"{crop}: {key}: a list holds visible values only")
            elif any(v != UNSURE and v not in vlm.ITEMS[key].allowed for v in values):
                problems.append(f"{crop}: {key}={value} is not an option")
    if problems:
        raise ValueError("bad labels: " + "; ".join(problems))


def outcomes(answers_by_crop, labels_by_crop):
    """{(crop, key): outcome} over the labelled crops and their scored keys; a crop with no answers (a failed
    request) is "invalid" on every scored key."""
    out = {}
    for crop, labels in labels_by_crop.items():
        answers = answers_by_crop.get(crop) or {}
        for key in vlm.KEYS:
            outcome = compare_answer(answers.get(key), labels.get(key))
            if outcome is not None:
                out[(crop, key)] = outcome
    return out


def summarise(outcome_map, labels_by_crop, keys):
    pairs = [((crop, key), o) for (crop, key), o in outcome_map.items() if key in keys]
    counts = Counter(o for _, o in pairs)
    visible = [o for (crop, key), o in pairs if labels_by_crop[crop].get(key) != vlm.NOT_VISIBLE]
    n, n_vis = len(pairs), len(visible)
    n_nv = n - n_vis
    return {"n": n, "match": counts["match"], "agreement": ratio(counts["match"], n),
            "visible_n": n_vis, "visible_match": visible.count("match"),
            "visible_agreement": ratio(visible.count("match"), n_vis), "not_visible_n": n_nv,
            **{o: counts[o] for o in OUTCOMES[1:]},
            "false_visible_rate": ratio(counts["false_visible"], n_nv),
            "false_invisible_rate": ratio(counts["false_invisible"], n_vis)}


def not_visible_rate(answers_by_crop):
    values = [v for answers in answers_by_crop.values() for v in answers.values()]
    return ratio(sum(v == vlm.NOT_VISIBLE for v in values), len(values))


def sign_test(a, b):
    """Exact two-sided sign test on a vs b discordant pairs."""
    n = a + b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 4)


def paired(outcomes_a, outcomes_b):
    common = outcomes_a.keys() & outcomes_b.keys()
    a_only = sum(outcomes_a[k] == "match" and outcomes_b[k] != "match" for k in common)
    b_only = sum(outcomes_b[k] == "match" and outcomes_a[k] != "match" for k in common)
    return {"n": len(common), "a_only_right": a_only, "b_only_right": b_only, "sign_test_p": sign_test(a_only, b_only)}


def country_scores(answers):
    """(hints, {country: score}) from one crop's answers alone; values outside the schema are dropped."""
    clean = {k: v for k, v in answers.items() if k in vlm.ITEMS and v in vlm.ITEMS[k].allowed}
    found = vlm.hints(vlm.aggregate([vlm.ViewResult("crop", None, None, None, 0.0, clean)]))
    scores = Counter()
    for h in found:
        for country in h["countries"]:
            scores[country] += STRENGTH_WEIGHT.get(h["strength"], 1) / len(h["countries"])
    return found, scores


def country_call(scores):
    ranked = scores.most_common()
    if not ranked or (len(ranked) > 1 and math.isclose(ranked[0][1], ranked[1][1])):
        return None
    return ranked[0][0]


def score_countries(answers_by_crop, truth):
    """Crop-level country calls and hint precision against the GPS country of each crop."""
    calls, rows = {}, []
    hint_n = hint_ok = strong_n = strong_ok = 0
    for crop, country in truth.items():
        found, scores = country_scores(answers_by_crop.get(crop) or {})
        call = country_call(scores)
        calls[crop] = {"call": call, "truth": country, "scores": {k: round(v, 2) for k, v in scores.items()}}
        for h in found:
            if not h["countries"]:
                continue
            hint_n += 1
            hint_ok += country in h["countries"]
            if h["strength"] == "strong":
                strong_n += 1
                strong_ok += country in h["countries"]
        rows.append((call, country))
    made = [(c, t) for c, t in rows if c is not None]
    correct = sum(c == t for c, t in made)
    return {"crops": len(rows), "calls": len(made), "correct": correct, "accuracy_of_calls": ratio(correct, len(made)),
            "accuracy_of_crops": ratio(correct, len(rows)), "hints": hint_n, "hints_right": hint_ok,
            "hint_precision": ratio(hint_ok, hint_n), "strong_hints": strong_n, "strong_hints_right": strong_ok,
            "strong_hint_precision": ratio(strong_ok, strong_n), "per_crop": calls}


_LINE_BREAK = re.compile(r"\s+/\s+|\s*\n\s*")
_QUOTES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"'})


def norm_text(text, fold=False):
    """NFC, straight quotes, line breaks (" / ", newlines) and runs of spaces as one space."""
    text = unicodedata.normalize("NFC", text or "").translate(_QUOTES)
    text = " ".join(_LINE_BREAK.sub(" ", text).split())
    return text.casefold() if fold else text


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def substring_distance(needle, hay):
    """Fewest edits that turn needle into some substring of hay (free start and end in hay)."""
    if not needle:
        return 0
    previous = [0] * (len(hay) + 1)
    for i, cn in enumerate(needle, 1):
        current = [i]
        for j, ch in enumerate(hay, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (cn != ch)))
        previous = current
    return min(previous)


def line_found(line, text, fold=False):
    """The line appears in the transcription as written, not inside a longer word."""
    line, text = norm_text(line, fold), norm_text(text, fold)
    return bool(line) and re.search(r"(?<!\w)" + re.escape(line) + r"(?!\w)", text) is not None


def sign_lines(value):
    """A sign's label: a list of lines, a single string, or {"lines": [...]}; None when unsure."""
    lines = value.get("lines") if isinstance(value, dict) else value
    if lines in (None, UNSURE):
        return None
    return [lines] if isinstance(lines, str) else list(lines)


def score_transcriptions(sign_outputs, sign_labels):
    """Per labelled line: found exactly (case and accents kept), found ignoring case, and the edit distance
    to the closest substring of the transcription over the line's length."""
    rows = {}
    for sign, value in sign_labels.items():
        lines = None if sign.startswith("_") else sign_lines(value)
        if not lines:
            continue
        out = sign_outputs.get(sign) or {}
        text = out.get("text") or ""
        per_line = [{"line": line, "exact": line_found(line, text), "exact_ci": line_found(line, text, fold=True),
                     "cer": round(substring_distance(norm_text(line), norm_text(text)) / len(norm_text(line)), 3),
                     "digits": any(ch.isdigit() for ch in line)} for line in lines]
        rows[sign] = {"text": text, "legible": out.get("legible"), "error": out.get("error"), "lines": per_line,
                      "all_exact": all(r["exact"] for r in per_line)}
    lines = [r for row in rows.values() for r in row["lines"]]
    digit_lines = [r for r in lines if r["digits"]]
    return {"signs": len(rows), "signs_all_lines_exact": sum(r["all_exact"] for r in rows.values()),
            "lines": len(lines), "lines_exact": sum(r["exact"] for r in lines),
            "exact_rate": ratio(sum(r["exact"] for r in lines), len(lines)),
            "lines_exact_ci": sum(r["exact_ci"] for r in lines),
            "exact_ci_rate": ratio(sum(r["exact_ci"] for r in lines), len(lines)),
            "line_cer_mean": round(statistics.mean(r["cer"] for r in lines), 3) if lines else None,
            "digit_lines": len(digit_lines), "digit_lines_exact": sum(r["exact"] for r in digit_lines),
            "per_sign": rows}


def landmark_named(name, tokens):
    words = set(normalise(name).split())
    return all(t in words for t in tokens)


def score_landmarks(crop_outputs, crop_labels):
    """Landmark hypotheses against the places labelled in a crop (_landmarks: {place: tokens}): crops with a
    labelled place the model named, and crops without one where it named something anyway."""
    rows, right, named_without = {}, 0, 0
    for crop, keys in crop_labels.items():
        expected = keys.get("_landmarks") or {}
        named = [lm["name"] for lm in ((crop_outputs.get(crop) or {}).get("landmarks") or [])]
        hits = sorted(place for place, tokens in expected.items() if any(landmark_named(n, tokens) for n in named))
        right += bool(hits)
        named_without += bool(named) and not expected
        if expected or named:
            rows[crop] = {"expected": sorted(expected), "named": named, "hits": hits}
    with_place = sum(bool(keys.get("_landmarks")) for keys in crop_labels.values())
    return {"crops_with_place": with_place, "named_right": right, "crops_without_place": len(crop_labels) - with_place,
            "named_without_place": named_without, "per_crop": rows}


def timing_summary(doc):
    """Per-crop compute (Ollama's prompt + generation durations) and wall time less load; 10-crop figures."""
    per = []
    for rec in doc.get("crops", {}).values():
        if rec.get("error") or not rec.get("ollama"):
            continue
        t = _requests_timing(rec["ollama"])
        per.append({**t, "compute_s": t["prompt_s"] + t["output_s"], "wall_s": rec["latency_s"] - t["load_s"]})
    sign_t = [_requests_timing(r["ollama"]) for r in doc.get("signs", {}).values() if r.get("ollama")]

    def mean(k, rows=per):
        return round(statistics.mean(r[k] for r in rows), 3) if rows else None
    out_s = sum(r["output_s"] for r in per)
    prompt_s = sum(r["prompt_s"] for r in per)
    return {"crops": len(per), "compute_s_mean": mean("compute_s"),
            "compute_s_median": round(statistics.median(r["compute_s"] for r in per), 3) if per else None,
            "compute_s_max": round(max(r["compute_s"] for r in per), 3) if per else None,
            "wall_s_mean": mean("wall_s"), "ten_crops_compute_s": round(10 * mean("compute_s"), 1) if per else None,
            "ten_crops_wall_s": round(10 * mean("wall_s"), 1) if per else None,
            "prompt_tokens_mean": mean("prompt_tokens"), "output_tokens_mean": mean("output_tokens"),
            "output_tok_s": round(sum(r["output_tokens"] for r in per) / out_s, 1) if out_s else None,
            "prompt_tok_s": round(sum(r["prompt_tokens"] for r in per) / prompt_s, 1) if prompt_s else None,
            "retried_crops": sum(r["requests"] > 1 for r in per),
            "mid_pass_load_s_max": round(max(r["load_s"] for r in per), 3) if per else None,
            "signs": len(sign_t), "sign_compute_s_mean": round(statistics.mean(t["prompt_s"] + t["output_s"]
                                                                               for t in sign_t), 3) if sign_t else None,
            "load_s": doc.get("load_s")}


def score_model(doc, labels, truth):
    answers = {c: r["answers"] for c, r in doc.get("crops", {}).items() if r.get("answers")}
    crop_labels = {c: {k: v for k, v in keys.items() if not k.startswith("_")} for c, keys in labels["crops"].items()}
    found = outcomes(answers, crop_labels)
    per_key = {}
    for key in vlm.KEYS:
        s = summarise(found, crop_labels, (key,))
        if s["n"]:
            per_key[key] = s
    errors = {c: r["error"] for c, r in doc.get("crops", {}).items() if r.get("error")}
    return {"model": doc["model"], "crops_answered": len(answers), "crop_errors": errors,
            "groups": {g: summarise(found, crop_labels, keys) for g, keys in KEY_GROUPS.items()},
            "per_key": per_key, "not_visible_rate": not_visible_rate(answers),
            "invalid_answers": sum(v == vlm.INVALID for a in answers.values() for v in a.values()),
            "landmarks": score_landmarks(doc.get("crops", {}), labels["crops"]),
            "country": score_countries(answers, truth),
            "transcription": score_transcriptions(doc.get("signs", {}), labels.get("signs", {})),
            "timing": timing_summary(doc), "vram": doc.get("gpu"),
            "conditions": {"window": doc.get("window"), "started": doc.get("started"), "finished": doc.get("finished"),
                           "ollama_version": doc.get("ollama_version"), "error": doc.get("error"),
                           "unload": {k: v for k, v in (doc.get("unload") or {}).items() if k != "ps"}}}, found


def check2(a, b):
    """MODEL_DECISIONS check 2 for model a (qwen) against model b (gemma), as measured here."""
    ga, gb = a["groups"]["all"], b["groups"]["all"]
    ta, tb = a["transcription"], b["transcription"]
    accurate = {"checklist_agreement": (ga["agreement"] or 0) >= (gb["agreement"] or 0),
                "transcription_exact": (ta["exact_rate"] or 0) >= (tb["exact_rate"] or 0)}
    sizes = [x for x in ((a["vram"] or {}).get("size_vram_gb"), (a["vram"] or {}).get("runner_gb")) if x is not None]
    resident = max(sizes) if sizes else None  # the larger of Ollama's figure and the runner's nvidia-smi memory
    ten = a["timing"]["ten_crops_compute_s"]
    ok_vram = resident is not None and resident <= CHECK2["resident_gb"]
    ok_time = ten is not None and ten <= CHECK2["ten_crops_s"]
    keep = all(accurate.values()) and ok_vram and ok_time
    mixed = any(accurate.values()) and not all(accurate.values())
    return {"model": a["model"], "against": b["model"], "at_least_as_accurate": accurate,
            "resident_gb": resident, "resident_ok": ok_vram, "ten_crops_compute_s": ten,
            "ten_crops_wall_s": a["timing"]["ten_crops_wall_s"], "time_ok": ok_time,
            "rule_literal": "keep" if keep else ("mixed accuracy: team call" if mixed and ok_vram and ok_time
                                                 else "switch")}


def score(out=OUT, model_a=DEFAULT_A, model_b=DEFAULT_B):
    labels = load_json(out / "labels.json")
    check_labels(labels)
    crops_doc = load_json(out / "crops.json")
    truth = {c["crop"]: c["country"] for c in crops_doc["crops"] if c["crop"] in labels["crops"]}
    models, found = {}, {}
    for model in (model_a, model_b):
        path = out / "outputs" / f"{slug(model)}.json"
        if path.exists():
            models[model], found[model] = score_model(load_json(path), labels, truth)
    label_country = score_countries({c: {k: v[0] if isinstance(v, list) else v for k, v in keys.items()
                                         if not k.startswith("_")} for c, keys in labels["crops"].items()}, truth)
    label_country.pop("per_crop")
    report = {"schema": SCHEMA, "scored": now(), "crops": len(truth), "signs": len(labels.get("signs", {})),
              "countries": dict(Counter(truth.values())), "key_groups": {g: list(k) for g, k in KEY_GROUPS.items()},
              "labels_not_visible_rate": ratio(sum(v == vlm.NOT_VISIBLE for keys in labels["crops"].values()
                                                   for k, v in keys.items() if not k.startswith("_")),
                                               sum(1 for keys in labels["crops"].values() for k in keys
                                                   if not k.startswith("_"))),
              "labels_unsure": sum(v == UNSURE for keys in labels["crops"].values() for v in keys.values()),
              "labels_with_alternatives": sum(isinstance(v, list) for keys in labels["crops"].values()
                                              for v in keys.values()),
              "country_from_labels": label_country, "models": models}
    if len(models) == 2:
        report["paired"] = {g: paired({k: o for k, o in found[model_a].items() if k[1] in keys},
                                      {k: o for k, o in found[model_b].items() if k[1] in keys})
                            for g, keys in KEY_GROUPS.items()}
        report["paired_note"] = f"a = {model_a}, b = {model_b}"
        report["check2"] = check2(models[model_a], models[model_b])
    atomic_write_json(out / "report.json", report)
    print_table(report)
    return report


def print_table(report):
    models = list(report["models"].values())
    if not models:
        print("no outputs to score")
        return
    names = [m["model"] for m in models]
    rows = []
    for g in KEY_GROUPS:
        rows.append((f"agreement {g} (n)", [f"{m['groups'][g]['agreement']} ({m['groups'][g]['n']})" for m in models]))
        rows.append((f"  visible labels {g} (n)", [f"{m['groups'][g]['visible_agreement']} "
                                                   f"({m['groups'][g]['visible_n']})" for m in models]))
    all_ = [m["groups"]["all"] for m in models]
    rows += [("false-visible / not_visible labels", [f"{a['false_visible']}/{a['not_visible_n']}" for a in all_]),
             ("false-invisible / visible labels", [f"{a['false_invisible']}/{a['visible_n']}" for a in all_]),
             ("wrong value / invalid", [f"{a['wrong_value']} / {a['invalid']}" for a in all_]),
             ("not_visible rate (labels " + str(report["labels_not_visible_rate"]) + ")",
              [str(m["not_visible_rate"]) for m in models]),
             ("country calls right / made / crops", [f"{m['country']['correct']}/{m['country']['calls']}/"
                                                     f"{m['country']['crops']}" for m in models]),
             ("hint precision (strong)", [f"{m['country']['hint_precision']} ({m['country']['strong_hint_precision']})"
                                          for m in models]),
             ("sign lines exact / ignoring case / n", [f"{m['transcription']['lines_exact']}/"
                                                      f"{m['transcription']['lines_exact_ci']}/{m['transcription']['lines']}"
                                                      for m in models]),
             ("signs with every line exact", [f"{m['transcription']['signs_all_lines_exact']}/"
                                              f"{m['transcription']['signs']}" for m in models]),
             ("line CER mean; digit lines exact", [f"{m['transcription']['line_cer_mean']}; "
                                                   f"{m['transcription']['digit_lines_exact']}/"
                                                   f"{m['transcription']['digit_lines']}" for m in models]),
             ("landmarks named right / crops with one", [f"{m['landmarks']['named_right']}/"
                                                        f"{m['landmarks']['crops_with_place']}" for m in models]),
             ("landmarks named where none / crops", [f"{m['landmarks']['named_without_place']}/"
                                                     f"{m['landmarks']['crops_without_place']}" for m in models]),
             ("compute s / crop (median)", [f"{m['timing']['compute_s_mean']} ({m['timing']['compute_s_median']})"
                                            for m in models]),
             ("10 crops: compute / wall s", [f"{m['timing']['ten_crops_compute_s']} / {m['timing']['ten_crops_wall_s']}"
                                             for m in models]),
             ("output tok/s (prompt tok/s)", [f"{m['timing']['output_tok_s']} ({m['timing']['prompt_tok_s']})"
                                              for m in models]),
             ("prompt / output tokens per crop", [f"{m['timing']['prompt_tokens_mean']} / "
                                                  f"{m['timing']['output_tokens_mean']}" for m in models]),
             ("VRAM GB: ollama ps / runner", [f"{(m['vram'] or {}).get('size_vram_gb')} / "
                                              f"{(m['vram'] or {}).get('runner_gb')}" for m in models]),
             ("other GPU jobs: share / peak MiB / util %", [f"{(m['vram'] or {}).get('other_share')} / "
                                                           f"{(m['vram'] or {}).get('other_mib_peak')} / "
                                                           f"{(m['vram'] or {}).get('gpu_util_pct_mean')}"
                                                           for m in models])]
    width = max(len(r[0]) for r in rows) + 2
    print(f"{'':<{width}}" + "".join(f"{n:<24}" for n in names))
    for label, values in rows:
        print(f"{label:<{width}}" + "".join(f"{v:<24}" for v in values))
    lc = report["country_from_labels"]
    print(f"country calls from the labels: {lc['correct']}/{lc['calls']}/{lc['crops']}")
    for g, p in report.get("paired", {}).items():
        print(f"paired {g}: {p['n']} pairs, only a right {p['a_only_right']}, only b right {p['b_only_right']}, "
              f"sign test p {p['sign_test_p']}  ({report['paired_note']})")
    if "check2" in report:
        print("check 2:", json.dumps(report["check2"]))


# -- CLI --------------------------------------------------------------------------------------------

def _counts(text):
    counts = {}
    for part in text.split(","):
        country, n = part.split("=")
        counts[country.strip().upper()] = int(n)
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/compare_vlm.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sheets", help="contact sheets of candidate val panoramas")
    p.add_argument("--n", type=_counts, default={"PT": 20, "ES": 8, "FR": 8})
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--skip", type=_counts, default={}, help="skip the first N of each country's order, e.g. PT=20")
    p.add_argument("--name", default="sheets", help="folder and JSON name (default sheets)")
    sub.add_parser("crops", help="picks.json -> crops, sign crops and crops.json")
    p = sub.add_parser("run", help="one model over every crop and sign")
    p.add_argument("--model", required=True)
    p.add_argument("--host", default=vlm.DEFAULT_HOST)
    p.add_argument("--window", action="store_true", help="marker file, keep_alive 10m, always unload at the end")
    p.add_argument("--force", action="store_true", help="load even when the free-VRAM check fails")
    p.add_argument("--timeout", type=float, default=vlm.DEFAULT_TIMEOUT_S)
    p.add_argument("--evict", action="append", default=[], metavar="MODEL",
                   help="unload this resident model (keep_alive 0) just before the load; repeatable")
    p = sub.add_parser("score", help="labels.json + outputs -> report.json")
    p.add_argument("--a", default=DEFAULT_A, help=f"the incumbent (default {DEFAULT_A})")
    p.add_argument("--b", default=DEFAULT_B, help=f"the challenger (default {DEFAULT_B})")
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.command == "sheets":
        make_sheets(args.n, args.seed, skip=args.skip, name=args.name)
    elif args.command == "crops":
        make_crops()
    elif args.command == "run":
        doc = run_pass(args.model, host=args.host, window=args.window, force=args.force, timeout_s=args.timeout,
                       evict=args.evict)
        return 1 if doc.get("error") else 0
    else:
        score(model_a=args.a, model_b=args.b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
