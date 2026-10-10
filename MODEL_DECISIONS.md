# Model decisions

**Status:** decided 2026-10-10, pending the day-one checks at the end of this file.
**Scope:** which open-weight model fills each role in the panorama geolocation pipeline (JunctionX Lisbon 2026, "Albatroz – Panorama Localisation"), how the models share the GPU, and what would make us change a pick.

**Markers:** **[L]** = measured on our laptop on 2026-10-10, with the GPU capped at 80 W and shared, so speeds are lower bounds. **[E]** = estimate. Unmarked numbers are published; the link is next to them.

## Constraints we decided against

- **Hardware:** RTX 5080 Laptop GPU (16 GB, Blackwell sm_120), 30 GB RAM (about 18 GB free), Core Ultra 9 275HX, Debian 13, driver 590.48.01.
- **Software:** Python 3.12 via uv, Ollama 0.34.4.
- **Memory budget:** models loaded together must fit in about 14 GB of VRAM.
- **Time budget:** 6 panoramas in about 60 minutes, so at most about 2–3 minutes of compute per panorama.
- **Rules:** open weights, run locally, no paid APIs.
- **Scoring:** urban answers lose half their score at 100 m of error, non-urban answers at 10 km. So we need strong top-4 candidates at region, then town, then exact spot.

## Decisions

| # | Role | Decision | Runs on | VRAM | Fallback | Status |
|---|---|---|---|---|---|---|
| 1 | Vision-language model (VLM) | **Qwen3.5-9B**, Ollama `qwen3.5:9b` (Q4_K_M, 6.6 GB) | GPU, resident | ~7–8 GB [E] | `gemma4:12b` (installed, verified [L]) | Validate on day one |
| 2 | Reasoning and multiple-choice questions | **The same Qwen3.5-9B**, text + JSON schema | GPU, resident | 0 extra | `gpt-oss:20b`, `think:"low"`, one batched pass | Decided |
| 3 | Open-vocabulary detector | **YOLOE-26-L** sweep → **SAM 3** presence check | GPU | 0.31 GB [L] + ~2 GB while loaded [E] | OWLv2-B/16 ensemble | Decided, tune thresholds |
| 4 | OCR | **PP-OCRv6-medium** via RapidOCR + OpenVINO | CPU | 0 | PP-OCRv5 Latin | Decided |
| 5 | Image–text embeddings | **PE-Core-L14-336** | GPU, resident | ~0.7 GB [E] | SigLIP 2 So400m/16-512, then StreetCLIP | Validate on day one |
| 6 | Image → GPS | **GeoCLIP** with a PT/ES/FR gallery + **PLONK_OSV_5M** + regional kNN | GPU | ~0.8 GB + 0.75–1.5 GB [E] | StreetCLIP zero-shot over admin units | Decided |
| 7 | Semantic segmentation | **EoMT-L on ADE20K** | GPU, resident | ~1 GB [E] | Mask2Former Swin-T/S (ADE20K) | Decided |
| 8 | Place recognition (urban pinpointing) | **MegaLoc v1.1** + **ALIKED+LightGlue** verification | GPU, resident | 1.1–1.5 GB [L] | BoQ-DINOv2 | Decided |
| 9 | Short-text language ID | **heliport + py3langid + CLD2** ensemble | CPU | 0 | py3langid + CLD2 + Lingua | Decided |

**Fusion is code, not a model.** Every role outputs evidence. We combine it as a product of experts over a precomputed grid (OSM, land cover, DEM, urbanity). The VLM then reads retrieved facts about the top cells, flags contradictions and writes the multiple-choice questions.

## Why, and how to run each one

### 1. VLM: Qwen3.5-9B
- **Why:** it has the best published ≤10B scores on everything the checklist touches: RealWorldQA 80.3, HallusionBench 69.3, OCRBench 892, CC-OCR 79.3, RefCOCO 89.7 ([card](https://huggingface.co/Qwen/Qwen3.5-9B)). It sees each 1024² crop at 1,024 tokens. Apache-2.0.
- **Run with:** `ollama pull qwen3.5:9b`. Send these on every request:
  - `think:false`
  - `temperature:0`
  - `format` = a compact enum JSON schema with `not_visible` on every field
  - `keep_alive:-1`
- **How to ask:** one request per crop. Ask about vegetation as a closed set and cross-check against the embedding prompts.
- **Never ask it for coordinates.** Open VLMs are rarely within 1 km. Qwen3-VL-8B scores 8.29% within 1 km on Im2GPS3k ([SpotAgent](https://arxiv.org/html/2602.09463v3)).
- **Risk:** not yet run on our laptop.
- **Fallback:** Gemma 4 12B, already verified with images plus a JSON schema [L]. Ollama caps its image budget at 441 tokens per image, so give it full-resolution zoom crops for reading text.
- **Hard-case swap-in:** Qwen3.6-35B-A3B through llama-server with `--n-cpu-moe` (UD-Q3_K_M, 16.6 GB). Only after unloading the VLM, and only once for a batch of panoramas.

### 2. Reasoning: no separate model on the critical path
- **Why:**
  - Qwen3.5-9B beats gpt-oss-20b on MMLU-Pro (82.5 vs 74.8) and MMLU-ProX (76.3 vs 67.3) ([card](https://huggingface.co/Qwen/Qwen3.5-9B)), and it is already loaded.
  - gpt-oss-20b needs 12.75 GB [L], so it cannot sit next to the VLM. Each swap costs 4–16 s, and took 97–308 s under RAM pressure [L].
- **Rules:**
  - Keep the probability arithmetic in code. gpt-oss once returned country probabilities that summed to 0.65 [L].
  - Validate and renormalise every JSON response.
  - Write the multiple-choice questions in two passes: free text first, then a JSON pass.
- **Fallback:** `gpt-oss:20b` at `think:"low"` (11.4 s per request [L]), run only when the evidence conflicts or the JSON fails.

### 3. Detector: YOLOE-26-L sweep, SAM 3 verifies
- **Why:** we chose on false positives rather than LVIS AP. In a photo of two cats, Grounding DINO, LLMDet and OmDet-Turbo "found" a licence plate at 0.37–0.51 [L]. YOLOE-26-L reported no absent objects, and SAM3-LiteText scored them ≤0.001 [L]. SAM 3's published presence score is IL_MCC 0.76 against 0.15–0.17 for those models ([paper](https://arxiv.org/html/2511.16719)).
- **Run with:** `uv pip install ultralytics` (8.4.175 tested) and `yoloe-26l-seg.pt`.
  - Run YOLOE on 32 perspective tiles (8 views at ~2048², cut 2×2) plus the 10 views, at confidence ≈0.1. That took 18.6 ms per view [L].
  - Run SAM 3 through transformers ≥5.6. Use `facebook/sam3` (gated: **request access now**) or `vil-uob/sam3-litetext-s0` until access is granted. LiteText took 481 ms per view for 10 prompts [L].
  - Keep a box if SAM 3 scores ≥0.5, or if both models score ≥0.3.
- **Prompting:** use two or three English paraphrases and take the maximum ("granary" / "raised granary on stone pillars", "tiled facade"). Non-English words such as "hórreo" can score 0 [L].
- **Ultralytics notes:**
  - Encode the prompts once; `set_classes()` reloads the text encoder on every call.
  - Telemetry is on by default: `yolo settings sync=False`.
  - The licence is AGPL-3.0.

### 4. OCR: PP-OCRv6 on the CPU, the VLM only checks
- **Why:**
  - One model covers pt, es, fr, ca, gl and eu, including `·` and `ŀ`.
  - It detects text far better than VLMs: detection Hmean 86.2 against 38.3 for Qwen3-VL-235B, and 93.8 vs 2.1 on rotated text ([PP-OCRv6 doc](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv6/PP-OCRv6.en.md)).
  - VLMs "correct" non-words into real words ([TextHalu-Bench](https://arxiv.org/abs/2506.05551)).
  - It runs on the CPU, so it uses no VRAM.
- **Run with:** `uv pip install rapidocr==3.10.0 openvino`. Keep PaddlePaddle off the GPU: it has open sm_120 bugs that return 0 boxes or CUDA error 719.
- **Steps:**
  1. Run OCR on the 10 views.
  2. Re-read small or low-confidence boxes from full-resolution crops.
  3. Parse with regexes:
     - Postcodes: PT `\d{4}-\d{3}`; ES 5 digits, first two 01–52 = province; FR 5 digits = département.
     - Phone prefixes: +351, +34, +33.
     - Plates: PT AA-00-AA, ES 1234 ABC, FR AA-123-AA.
  4. The VLM verifies the top 5–15 crops with a "transcribe exactly" schema.
- **Never accept digits that only the VLM saw.**
- **Second reader for stylised crops:** PaddleOCR-VL-1.6 (0.96B) via llama-server.

### 5. Embeddings: PE-Core-L14-336, with SigLIP 2 benchmarked against it
- **Why:** it has the strongest published zero-shot geographic score among general-purpose CLIP models: Country211 45.6 vs 40.1 for SigLIP 2 g-opt ([PE paper](https://arxiv.org/html/2504.13181)). It also has the best zero-shot iNaturalist score of that group. Apache-2.0.
- **Caveat:** nobody has measured which encoder best separates regions within Iberia, so this is a prior.
- **Run with:** open_clip ≥3.0, `hf-hub:timm/PE-Core-L-14-336`. Keep only the vision tower loaded and cache the text embeddings once.
  - Do not use Meta's `perception_models` repo: it pins torch 2.5.1 and xformers, which won't run on sm_120.
- **Also precompute:** SigLIP 2 (`google/siglip2-so400m-patch16-512`) and StreetCLIP (`geolocal/StreetCLIP`, non-commercial licence) embeddings for the same images.
- **Classifier:**
  - Admin-2 geocells merged to at least 50–100 images each, haversine label smoothing, and a linear head on frozen embeddings.
  - Refine with kNN inside the top cells, using faiss-cpu or one torch matmul. The `faiss-gpu` pip wheels lack sm_120.

### 6. Image → GPS: GeoCLIP + PLONK + kNN, restricted to PT/ES/FR
- **Why:** no open-weight model clearly beats GeoCLIP or StreetCLIP for Europe. The 2026 systems that do (Pinpoint, HierLoc, HoloGeo) have not released weights. The gain comes from the reference data:
  - kNN over OSV-5M with StreetCLIP features reaches 19.9% city accuracy, against 5.4% for PLONK ([OSV-5M](https://arxiv.org/html/2404.18873); [PLONK](https://arxiv.org/abs/2412.06781)).
  - A uniform gallery drops GeoCLIP to 0.02% within 1 km ([GeoCLIP](https://arxiv.org/abs/2309.16020)).
- **GeoCLIP:** `uv pip install geoclip==1.2.3` (pin 1.2.0 if it misbehaves).
  - Replace `model.gps_gallery` with real photo and road coordinates from OSV-5M PT/ES/FR plus OSM roads. Never use a uniform grid.
  - Refine the top hits with a 100–250 m local grid.
  - Sum log-softmax over the 8 views, and apply 1–5 km non-maximum suppression before taking the top 10.
- **PLONK:** `uv pip install diff-plonk==0.4`, then `PlonkPipeline("nicolas-dufour/PLONK_OSV_5M")` with `cfg≈2`.
  - Sample, keep the points inside the PT/ES/FR polygons, then take density peaks.
  - Low probability mass inside the region is itself a "hard to localise" signal.
- **kNN bank:** OSV-5M's 390,133 PT/ES/FR training images, fetched one by one with HTTP range requests (no 246 GB download).

### 7. Segmentation: EoMT-L on ADE20K
- **Why:**
  - ADE20K is the only label set with sea, river, lake, tree, grass, palm, field, mountain and sand as separate classes.
  - Mapillary Vistas has one Water and one Vegetation class, and Cityscapes has no water.
  - EoMT-L scores 59.5 mIoU on ADE20K ([EoMT zoo](https://github.com/tue-mps/eomt/blob/master/model_zoo/dinov3.md)), it is plain PyTorch, and it is MIT-tagged.
- **Run with:** `tue-mps/eomt-dinov3-ade-semantic-large-512` (transformers ≥5.1.0), or its DINOv2 twin `tue-mps/ade20k_semantic_eomt_large_512` (transformers ≥4.54.0).
  - Segment the perspective views, not the raw panorama: narrow-field-of-view models lose about 30 mIoU on 360° images.
  - Reproject the labels to equirectangular coordinates and weight each pixel by cos(latitude).
- **Derived measures:**
  - Sea direction: azimuth histogram of sea pixels near the horizon.
  - Skyline: the lowest sky pixel in each column.
  - Compass heading: centroid of the 98th-brightness-percentile sky blob, compared with `pvlib` solar azimuth at the timestamp in the filename (4.59° median error in [Hold-Geoffroy et al.](https://ar5iv.labs.arxiv.org/html/1611.06403)). **First check whether the EXIF/XMP already holds `PoseHeadingDegrees`.**
- **Do not use SegFormer:** its weights are licensed for research or evaluation only.

### 8. Place recognition: MegaLoc retrieves, LightGlue decides
- **Why:**
  - MegaLoc has the best one-protocol cross-device recall: SF-XL v1 95.3 vs 88.7 for SALAD, and 52.8 vs 46.1 at night ([MegaLoc](https://arxiv.org/abs/2502.17237)).
  - It is trained partly on Mapillary data. MIT licence.
  - 119–130 images/s at 1.1–1.5 GB [L, architecture replica].
- **Run with:** `torch.hub.load("gmberton/MegaLoc", "get_trained_model")`.
  - Query with the 8 horizontal views at 322².
  - Gallery: Mapillary images near each candidate. Cut `is_pano` panoramas into the same 8 views and score them by the best of 8 yaw shifts.
- **Verify:** ALIKED+LightGlue on the top 30–50 pairs, using the inlier count as confidence. Use RoMa v2 only for the top 5–10 ambiguous pairs; it pins `torch==2.11.0`.
- **Position:**
  1. Triangulate from at least 2 verified Mapillary images using their `computed_*` poses.
  2. Otherwise, take the inlier-weighted centroid.
  3. Snap to OSM and spread the 10 guesses at least 100 m apart.
- **Rejecting a wrong match matters more than refining a right one:** a 25 m error keeps 84% of the score, a 300 m error keeps 12.5% [E].

### 9. Language ID: three voters plus spelling rules
- **Why:** Lingua has no Galician (0 of 18 Galician signs [L]). heliport and py3langid each got 17 of 18. Restricted to our six languages, they scored 0.89 and 0.87 on 108 sign phrases [L].
- **Run with:** `heliport==1.0.1` (GPLv3), `py3langid==0.4.0` (restricted to pt/gl/es/ca/eu/fr) and `pycld2`.
  - Normalise each string first: NFC, lowercase, keep diacritics.
  - Boost with spelling rules: ã/õ/ção → pt, l·l/ny → ca, tz/tx → eu. These fired at 88% precision [L].
  - Sum over all signs in the panorama.
  - Ask the VLM only when the top probability is below ~0.6.
  - The official `fasttext` package breaks under NumPy 2, and `gcld3` has no Python 3.12 wheels.

## GPU memory plan

| Stage | Loaded | VRAM |
|---|---|---|
| Always loaded | Qwen3.5-9B (Ollama) + one PyTorch process with YOLOE, PE-Core vision tower, GeoCLIP, EoMT, MegaLoc, LightGlue | ~11–12 GB [E] |
| Detection stage | + SAM 3, unloaded afterwards | peak ~13–14 GB [E] |
| Geolocation stage | + PLONK, unloaded afterwards | peak ~13–14 GB [E] |
| Batched swaps only, VLM unloaded | gpt-oss:20b (12.75 GB [L]) or Qwen3.6-35B-A3B (offloaded) | one batch over all panoramas |

If Qwen3.5-9B turns out larger than estimated, replace SAM 3 with OWLv2 (0.40 GB peak [L]).

## Time budget per panorama (at 80 W)

| Step | Time |
|---|---|
| Reprojection into 10 views + 32 tiles | a few s [E] |
| Detection cascade | 10–20 s [L-derived] |
| OCR (CPU, overlapped with GPU work) | 6–16 s [E] |
| VLM checklist (10 crops, compact schema) | 15–45 s [E] |
| VLM OCR verification | 10–30 s [E] |
| Embeddings, geolocation, segmentation | under 10 s [E] |
| Reasoning and questions (same VLM) | 10–30 s [E] |
| Place recognition, urban only (excluding Mapillary download) | 15–50 s [L/E] |
| **Total** | **~50–135 s non-urban, ~65–185 s urban [E]** |

The VLM's speed is the biggest unknown. Mapillary downloads are the main wall-clock risk, so prefetch galleries while the team answers the questions.

## Platform decisions

| Item | Decision |
|---|---|
| GPU power | **Lift the 80 W cap before anything else.** It is locked at 80 W of 175 W ("SW Power Cap"). Try Fn+P with `nvidia-powerd`, or the trixie-backports kernel's `performance` platform profile. Both are untested; check with `nvidia-smi -q -d POWER`. |
| PyTorch | Python 3.12 uv venv with **torch 2.11.0+cu128 / torchvision 0.26.0**, the build verified on this GPU [L]. The upgrade path is 2.14.1 (cu130), untested here. Pin both in `uv.lock`. |
| transformers | ≥5.6 (5.19.0 tested [L]) |
| Ollama | **Stay on 0.34.4** for the event. 0.40.2 converts models in the background, and rolling back means re-pulling them. |
| llama.cpp | Prebuilt b11539 binary, for `--n-cpu-moe` and `--image-min-tokens` |
| Avoid on sm_120 | flash-attn, xformers, mmcv / mm* packages, detectron2, the original Grounding DINO repo, `faiss-gpu` pip, PaddlePaddle-GPU, vLLM, SGLang, official `fasttext`, gcld3 |
| Housekeeping | `/tmp` is a 16 GB RAM-backed tmpfs. Keep venvs, weights and datasets on disk, and empty `/tmp` before the run. |

## Rejected

| Option | Why not |
|---|---|
| Qwen2.5-VL-7B, MiniCPM-V 2.6 | Superseded (2025-01 and 2024-08). Qwen3.5-9B beats Qwen2.5-VL-7B on OCRBench (892 vs 864). |
| gpt-oss-20b as a per-panorama step | Can't sit next to the VLM; the swap cost isn't worth it given weaker knowledge benchmarks. |
| Grounding DINO, LLMDet, MM-GDINO, OmDet-Turbo, Florence-2 | Report absent objects with high scores [L]. Florence-2 also used up to 5.3 GB and 1.42 s per view [L]. |
| Grounding DINO 1.5/1.6, DINO-X, T-Rex2 | API only |
| OCR only through the VLM | Finds text poorly, invents words, gains nothing (OCR is on the CPU anyway) |
| HunyuanOCR | Licence excludes the EU |
| EasyOCR, MMOCR | Unmaintained, and EasyOCR lacks ca/gl/eu |
| GeoRanker, G3 | Published numbers rely on GPT-4V; GeoRanker re-ranking takes 288 s per image on an RTX 5090 ([Pinpoint](https://arxiv.org/abs/2606.04133)) |
| PIGEON / PIGEOTTO, Pinpoint, HierLoc | No public weights |
| SegFormer (any) | Non-commercial weights; Mapillary Vistas labels lack sea/tree/grass splits |
| SAM 3 as the segmenter | 39.0 mIoU on ADE-150 |
| SALAD + DAPR | DAPR (ECCV 2026) requires retraining and links no code or weights ([arXiv 2607.00090](https://arxiv.org/abs/2607.00090)); SALAD is GPL-3.0 |
| EfficientLoFTR | Licence changed 2026-09-15: organisations must register projects |
| Lingua alone | No Galician |
| Google Street View (any use) | Terms ban bulk download and training, testing or validating models |

## Day-one checks (settle these before the event)

| # | Check | Data | Keep the decision if… |
|---|---|---|---|
| 1 | Power cap lifted | `nvidia-smi -q -d POWER` | Power limit > 80 W |
| 2 | Qwen3.5-9B vs Gemma 4 12B | ~20 real Portuguese crops: exact-match OCR, checklist agreement, `not_visible` rate, tok/s, VRAM | Qwen3.5-9B is at least as accurate, ≤ 9 GB resident and ≤ 60 s for 10 crops; otherwise switch to Gemma 4 12B |
| 3 | PE-Core vs SigLIP 2 vs StreetCLIP | OSV-5M PT/ES/FR test split (5,206 images, 689 Portuguese), sequence-disjoint, ≥1 km buffer | PE-Core has the best region accuracy; otherwise use the winner, or an ensemble of the top two |
| 4 | GeoCLIP gallery vs PLONK vs kNN | Same split | Fusion beats each alone at 25 km; then set the fusion weights |
| 5 | Detector thresholds | 20–50 frames of real 360° data | Few false positives at SAM 3 ≥ 0.5 |
| 6 | OCR | ~50 labelled sign crops: v6-medium vs v6-small vs v5-Latin vs VLM | v6-medium is best or tied |
| 7 | Place recognition | Mapillary panoramas as pseudo-queries against Mapillary galleries | Correct spot within 100 m for most queries |
| 8 | End to end | One full panorama | ≤ 150 s compute, peak VRAM ≤ 14 GB |

## Revisit if

- Qwen3.5-9B fails check 2.
- SAM 3 access isn't granted (stay on SAM3-LiteText-S0).
- DAPR or Pinpoint weights are released.
- Peak VRAM exceeds 14 GB.
- End-to-end time exceeds 180 s with the power cap lifted.
