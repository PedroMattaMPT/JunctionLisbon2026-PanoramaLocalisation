# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Our entry for the Albatroz "Panorama Localisation" challenge at JunctionX Lisbon 2026: an AI agent, built from local open-weight models, that takes a 360° panorama from Portugal, Spain or France and returns up to 10 ranked `(lat, lng)` guesses. The team can only help through text cues and answers to the agent's multiple-choice questions, and both cost points.

- **`RULES.md`:** the scoring formula and all rules, including two partner clarifications that are **not in the PDF**. Read it before touching agent logic, questions, logging or anything that crosses panoramas.
- **`PLAN.md`:** the working plan (v2). It covers:
  - core vs. optional pipeline components
  - typed coordinate sources (camera / landmark / area) and the output contract
  - questions and the zone fallback
  - preparation (photo bank, mini-PIGEON, name index, gallery)
  - evaluation against `Data/warmup_locations.json` and the accuracy gates
  - the timeline with checkboxes, and the organiser questions

  Its section 5 checkboxes end with task tags such as `[T10, T11]`, and `tools/tasks.py` ticks them from `TASKS.md`: don't tick them by hand.
- **`MODEL_DECISIONS.md`:** which model fills each pipeline role, the GPU memory plan, the time budget, the platform pins, what was rejected and the open day-one checks. Where it disagrees with `PLAN.md`, `PLAN.md` wins: fusion, spreading the answers, the score examples, the bank size. `PLAN.md` section 9 lists the corrections.
- **`TASKS.md`:** every task with its phase, status, priority, area, owner and dependencies, plus a summary per phase. Change it only through the `/task` skill (`.claude/skills/task/`) or `python3 tools/tasks.py`. When you finish work that matches an open task, mark it done there with its evidence.
- **`ROADMAP.md`:** the phase windows (A–D, then the Sunday run), their gates, the critical path and the risks.
- **`COUNTRY_CLUES.md`:** how to tell Portugal, Spain and France and their regions apart (plates, signs, street furniture, buildings, language), taken from GeoGuessr guides, Rainbolt and official sources. It covers OCR regexes and lookups (postcode, phone, road number → place), a proposed VLM checklist and question vocabulary. Read it for the OCR parsing (T14), the checklist (T15) and the questions (T19). It uses external sources only, so it may go into the agent's knowledge base.

## State of the repo

Pipeline code has just started in `panoloc/`. So far there is only `panoloc/runlog.py`: per-panorama run state, the JSON event log and the penalty tracker. Every pipeline stage should log through its `Run`. Tests are in `tests/` (standard library `unittest`, see Commands). In the repo:

- the challenge PDFs
- `PLAN.md`, `MODEL_DECISIONS.md`, `RULES.md`, `TASKS.md`, `ROADMAP.md`
- the warm-up panoramas in `Data/Panorama Warm-Up/`, and the team's estimated locations for them in `Data/warmup_locations.json` (evaluation only, see below)
- `tools/`: the panorama viewer, the task tracker (`tasks.py`), `setup_env.sh` (the Python env and every model weight), plus the download scripts that rebuild every gitignored data folder (see Commands). Every script's usage is in its header.
- `requirements.lock.txt`: the exact package versions of `.venv/`.

Downloaded data (gitignored, rebuilt by the `tools/` scripts):

| Folder | Contents | Script |
|---|---|---|
| `Data/osv5m/` | OSV-5M photo bank: PT/ES/FR test split 5,206; PT train 51,551; ES + FR train 25k each | `fetch_osv5m.sh` |
| `Data/geo/` | GeoNames places and postcodes; CAOP 2025 and geoBoundaries outlines; GHSL urbanity; OSM extracts (PT, ES, FR); Copernicus GLO-90 elevation | `fetch_geo.sh` |
| `Data/wikidata/` | Every PT/ES/FR item with coordinates (1.14 M): labels and aliases in 7 languages, types, P18 photo, heritage status | `fetch_wikidata.py` |
| `Data/gallery/commons/` | Commons photos of those items (500 px): all PT, then ES/FR in priority order. Their coordinates are the landmark's, not the camera's | `fetch_commons.py` |
| `Data/panoramax/` | External 360° test panoramas with GPS (PT 99, ES 100, FR 100), whole collections split into `val` / `final` | `fetch_panoramax.py` |

Other local-only files (gitignored, so a fresh clone won't have them):

- `research_notes/Panorama geolocation model stack/`: per-role research notes, benchmark scripts and logs, plus dataset tooling:
  - `artifacts_datasets/scripts/osv5m_subset.py` (copy versioned as `tools/osv5m_subset.py`): `filter` / `index` / `fetch` OSV-5M PT/ES/FR images with HTTP range requests, avoiding the 259 GB download
  - `panoramax_360.py`: lists 360° Panoramax pictures in a bbox, no token needed
  - `mapillary_grid_sample.py`: **untested**, needs `$MAPILLARY_TOKEN`
  - Each script's usage is in its docstring.
- `research_notes/Country clues/`: the full sources behind `COUNTRY_CLUES.md`:
  - `portugal.md`, `spain.md`, `france.md`: complete mapping tables (e.g. 760 PT postcode prefixes → municipality, the 308 PT municipality codes, every ES road prefix, the 96 FR departments) and a source link on every clue
  - `geomastr.md`, `rainbolt.md` with `rainbolt_transcripts/`, and `img/`
- `reports/`, `deep_research_prompt.md`
- `Data/*.zip`, which is over GitHub's 100 MB file limit

## Commands

```bash
# Task tracker (TASKS.md), standard library only; the /task skill wraps it. Usage in the script header.
python3 tools/tasks.py list --ready                                   # what can be picked up now
python3 tools/tasks.py update T12 --status done --add-note "<evidence>"

# Tests (standard library only, run from the repo root), and a sample run log in runs/sample/ (gitignored)
python3 -m unittest discover -s tests
python3 tools/sample_log.py

# Every download script is resumable: re-run it to fill gaps. Logs sit next to the data.
# The venue Wi-Fi has DNS and TLS hostname-mismatch blips: retry, never disable certificate checks.

# OSV-5M reference photo bank in Data/osv5m/: PT/ES/FR test split, all PT train, a fixed 25k ES + 25k FR
# sample. Needs Data/osv5m/lists/ (the gz id lists from `tools/osv5m_subset.py filter`).
tools/fetch_osv5m.sh

# Geography in Data/geo/: GeoNames, CAOP + geoBoundaries outlines, GHSL urbanity, OSM extracts (md5-checked),
# GLO-90 elevation tiles
tools/fetch_geo.sh

# Wikidata extract (QLever endpoint), then the Commons landmark photos. Wikimedia requires contact info in
# the User-Agent: without it, 10 requests/min and a robot-policy 429. The user chose their public GitHub
# profile as the contact. The downloader allows at most 2 connections and backs off on every 429.
python3 -I tools/fetch_wikidata.py --out Data/wikidata
python3 -I tools/fetch_commons.py plan --extract Data/wikidata/wikidata_ptesfr.csv.gz --out Data/gallery/commons
python3 -I tools/fetch_commons.py fetch --dirs Data/gallery/commons/PT --contact https://github.com/PedroMattaMPT --max-rps 2
python3 -I tools/fetch_commons.py fetch --dirs Data/gallery/commons/ES,Data/gallery/commons/FR --cap 30000 --contact https://github.com/PedroMattaMPT --max-rps 2

# External 360° test panoramas (Panoramax, no token): list per 1° tile, sample inside the country outline
# across collections, fetch full resolution. Full examples in the script header.
python3 -I tools/fetch_panoramax.py list|sample|fetch ...

# Look around inside the panoramas (ports 8000 and 8765 are already taken on the dev laptop)
python3 -m http.server 8799            # from the repo root
# open http://localhost:8799/tools/viewer.html?dir=Data/Panorama%20Warm-Up/

# Python 3.12 env in .venv/ (system Python 3.13 is too new) plus every model weight, about 25 GB.
# Idempotent and resumable. SKIP_WEIGHTS=1 installs packages only; SAM3=1 adds the gated facebook/sam3
# (needs approved access and `hf auth login`). requirements.lock.txt pins torch==2.11.0+cu128, which isn't on
# PyPI: install through this script, never with `pip install -r`.
tools/setup_env.sh

nvidia-smi -q -d POWER                 # GPU is capped at 80 W of 175 W: timings measured under the cap are lower bounds
```

## Hardware and platform constraints

- **GPU:** RTX 5080 Laptop, **16 GB**, Blackwell **sm_120**. Models loaded together must fit in about 14 GB.
- **RAM:** 30 GB, about 18 GB free.
- **Doesn't work on sm_120** (see `MODEL_DECISIONS.md` → Platform decisions): flash-attn, xformers, mm* / detectron2, the original Grounding DINO repo, `faiss-gpu` pip wheels, PaddlePaddle-GPU, vLLM, SGLang.
- **Ollama:** stay on **0.34.4** for the event. Models already pulled:
  - `qwen3.5:9b`, the VLM: 5.6 GB at context 4096, 6.5 GB on the GPU, 0.7–1.4 s per warm request
  - `gemma4:12b`, `gpt-oss:20b`
- **`/tmp` is a 16 GB RAM-backed tmpfs.** Keep venvs, weights, datasets and image caches on disk.

## Running the models (every one smoke-tested on this GPU, 2026-10-10)

- **Run offline.**
  - Set `HF_HUB_OFFLINE=1`.
  - Load MegaLoc from its cached hub folder: `torch.hub.load(os.path.expanduser("~/.cache/torch/hub/gmberton_MegaLoc_main"), "get_trained_model", source="local")`.
  - PLONK_YFCC's DINOv2 loader contacts GitHub before it uses the cache, so it can stall on a flaky network.
- **PLONK brings its own encoder:** StreetCLIP for `PLONK_OSV_5M`, DINOv2 ViT-L/14-reg for `PLONK_YFCC`.
- **EoMT, DINOv3 checkpoint:** load it with `AutoModelForUniversalSegmentation`. `EomtForUniversalSegmentation` only warns, then returns garbage.
- **RapidOCR on the CPU:** set Det and Rec `engine_type=EngineType.OPENVINO`, `ocr_version=PPOCRV6`, `model_type=MEDIUM`, `lang_type="pt"` (this selects the multilingual models).
  - Fallback: PPOCRV5 + MOBILE, with Det `LangDet.MULTI` and Rec `LangRec.LATIN`.
  - The models live inside `.venv`, so recreating the venv downloads them again.
- **GPU memory, fp32 with full models (text towers included):**

  | Model | GB |
  |---|---|
  | GeoCLIP | 3.4 |
  | SAM3-LiteText | 3.3 |
  | EoMT | 2.6–3.2 |
  | PE-Core | 2.7 |
  | SigLIP 2 (fp16) | 2.4 |
  | ALIKED+LightGlue | 2.0 |
  | PLONK (each) | 1.4 |
  | MegaLoc | 1.0 |
  | YOLOE | 0.4 |

  Keeping the core resident next to Qwen within ~14 GB needs fp16 and vision-only towers.
- **Telemetry:** Ultralytics telemetry is off globally, and its weights live in `~/.cache/ultralytics/weights`, so YOLOE loads offline from any directory. OpenVINO telemetry is opted out.

## Pipeline architecture (planned, `PLAN.md` section 3)

Build the core path end to end first. Add a component only when it shows a measured gain (`PLAN.md` 4.7–4.8). Perception models write a per-panorama **evidence file** (JSON); code fuses it.

1. **Prepare views.** Parse the filename (date, time, shot counter) and cut 8 overlapping horizontal views + sky + ground with `py360convert`. The photographer appears in the bottom ~15–20% of almost every shot: mask it, but track what was masked rather than discarding ground clues.
2. **Read and describe.**
   - PP-OCRv6 (CPU) with full-resolution rereads → names, postcodes, phones.
   - One VLM (Qwen3.5-9B, unless Gemma 4 12B wins the comparison) answers a closed checklist in JSON with `not_visible` and gives landmark hypotheses.
   - The VLM never supplies coordinates or digits that OCR didn't see.
3. **Candidates.**
   - PE-Core embeddings → kNN over the OSV-5M bank + the mini-PIGEON region classifier.
   - GeoCLIP or PLONK as an extra generator.
   - The local name index (OSM, Wikidata, GeoNames) turns names into coordinates.
4. **Conservative fusion in code.**
   - A weighted combination calibrated on external validation data.
   - Correlated sources are grouped and capped, never multiplied as independent experts: everything built on PE-Core, and repeats across overlapping views.
   - Keep several distinct candidates plus a global fallback. Probability arithmetic always stays in code.
5. **Typed coordinates.** Every candidate says whether its coordinate is a `camera`, `landmark` or `area` position. A Wikidata point, an OSM shop or a postcode centroid is not a camera position.
   - Exact spots come from a verified match to a reference photo with camera GPS (MegaLoc + ALIKED/LightGlue, conditional), or from geographic cells narrowed by zone questions (target ≤ 25 m bound in urban scenes).
   - Otherwise output a coarse fallback with its uncertainty.
6. **Human loop.**
   - At most 4 agent-generated options.
   - Zone options must cover the whole scope, or include an explicit "none of these" / "outside".
   - Ask only when the expected gain beats the ×0.95 penalty (> 5.26%).
   - A skip changes nothing (see `RULES.md`).
7. **Output.** The agent produces the coordinates itself (a human converting a place name costs ×0.5). Also a penalty tracker with per-output snapshots, and the JSON log.

Optional, only after a measured benefit: YOLOE → SAM 3 detail crops, EoMT segmentation, sun position, rich grid features, the feature table, gpt-oss-20b.

## Scoring facts that shape the code

- **Repeat the coordinate with the highest expected score in all 10 slots, even when two candidates are nearly tied** (`PLAN.md` 1.1).
  - Each slot is scored independently with a fixed rank weight, and the rules give no bonus for diversity.
  - That coordinate is not always the single most likely spot.
  - This **overrides** the "spread the 10 guesses ≥ 100 m apart" rule and the top-10 non-maximum suppression in `MODEL_DECISIONS.md` §6 and §8.
  - Non-maximum suppression is right for picking the 4 **distinct** multiple-choice options.
- **Urban:** 25 m keeps 80% of the maximum and 300 m keeps 25%. **Non-urban:** about 5 km still keeps two thirds.
- **Never ask the VLM for coordinates.** Open VLMs are rarely within 1 km.

## Data facts (warm-up set, 20 panoramas)

- **No metadata.** EXIF, GPS and XMP are all stripped, so the filename is the only side information. Don't plan on `PoseHeadingDegrees`.
- **The camera seems to use interval mode.** Two files share the same timestamp with different shot counters, so a timestamp may mark the start of a series rather than the exact shot.
- **Scene mix:** many scenes are off-road or semi-indoor (castle walls, a river pier, a station café), and at least one looks French. Visible text and landmarks are the strongest clues: one warm-up panorama shows a building's name in large letters.
- **The warm-up zip has no Urban/non-Urban labels.**
- **`Data/warmup_locations.json` (and `.csv`) are the team's estimated locations, not ground truth.**
  - 19 references are precise, with a 5–12 m radius; one is coarse, with a 60 km radius.
  - They are for **evaluation only**. Never put them, or anything derived from them, into the agent's inputs or prompts, the photo bank, training, calibration or the galleries (`RULES.md`, `PLAN.md` 4.6).
