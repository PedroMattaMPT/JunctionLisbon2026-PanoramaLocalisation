# Tasks

The team's task tracker for the Albatroz panorama localisation challenge. [ROADMAP.md](ROADMAP.md) has the phases, gates and timeline; [PLAN.md](PLAN.md) says what each task means.

Change tasks with the `/task` skill in Claude Code, or with `python3 tools/tasks.py` (`list`, `show`, `add`, `update`, `delete`, `check`, `sync`; usage in its header). The script keeps the summary below and the PLAN.md section 5 checkboxes in step. If you edit by hand, keep one row per task with all nine cells and escape `|` as `\|`, then run `python3 tools/tasks.py sync`.

- **Status:** `todo`, `doing`, `blocked` (say why in Notes), `done` (say what proves it), `dropped` (say why).
- **Pri:** `P0` the phase's gate fails without it; `P1` core, should land in this phase; `P2` optional, only after a measured gain (PLAN.md 4.7).
- **Area:** `pipeline`, `perception`, `geo` and `pixel` are the four PLAN.md section 7 roles; also `ui` and `team`.
- **Needs:** tasks that must be done first. `python3 tools/tasks.py list --ready` shows the `todo` tasks with nothing left to wait on.

<!-- summary:start -->
| Phase | Done | Doing | Blocked | To do | Dropped | Gate |
|---|---:|---:|---:|---:|---:|---|
| A · Before the trial · Saturday until 19:00 | 10 / 25 | 4 | 0 | 11 | 0 | T25 open |
| B · Trial · Saturday 19:00–21:00 | 0 / 5 | 0 | 0 | 5 | 0 | T30 open |
| C · Overnight · Saturday 21:00 to Sunday 08:00 | 0 / 22 | 0 | 0 | 22 | 0 | T52 open |
| D · Freeze and rehearsal · Sunday 08:00–10:00 | 0 / 7 | 0 | 0 | 7 | 0 | T59 open |
| Run · Scoring and finals · Sunday from 10:00 | 0 / 4 | 0 | 0 | 4 | 0 |  |
| Backlog · Optional, only after a measured gain | 0 / 12 | 0 | 0 | 12 | 0 |  |
| **All** | 10 / 75 | 4 | 0 | 61 | 0 | |

Last change: Sat 19:30, T17 done.
<!-- summary:end -->
<!-- next-id: 76 -->

## A · Before the trial · Saturday until 19:00

**Gate A:** a complete coordinate output and a reviewable interaction log, including a skipped question and a failed optional stage. Passing it does not establish localisation accuracy.

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T01 | done | P0 | pixel | Download the OSV-5M PT/ES/FR photo bank (`tools/fetch_osv5m.sh`) | Pedro |  | Sat 17:10 | Verified 17:10: every file is a complete JPEG with a metadata row; 4.6 GB in `Data/osv5m/` (PLAN 4.1) |
| T02 | done | P0 | pixel | Re-fetch the 4,827 Portugal images that failed on the venue network | Pedro | T01 | Sat 17:00 | `Data/osv5m/fetch_retry.log`, 16:57–17:00: test 5,206, PT 51,551, ES/FR 50,000, 0 errors |
| T03 | done | P0 | geo | Save the Wikidata and GeoNames extracts for the name index | Pedro |  | Sat 17:56 | `Data/wikidata/wikidata_ptesfr.csv.gz`: 1,142,585 items (PT 37,516, ES 403,193, FR 702,599). GeoNames places and postcodes for PT/ES/FR in `Data/geo/geonames/` |
| T04 | done | P1 | geo | Finish the geographic downloads (`tools/fetch_geo.sh`) | Pedro |  | Sat 18:42 | Done: GeoNames, CAOP 2025, geoBoundaries, GHSL SMOD, OSM PT and ES, DEM PT (`Data/geo/downloads.log`). OSM France downloading since 18:03; DEM ES/FR runs after it · Sat 18:42: Data/geo/ 8.3 GB, Data/geo/fetch.log: OSM PT/ES/FR md5 OK; 262 GLO-90 tiles all readable; CAOP 2025 (mainland, Azores, Madeira); geoBoundaries PRT ADM0 + ESP/FRA ADM0-2; GHSL SMOD 2025 1 km; GeoNames places + postcodes |
| T05 | done | P1 | pipeline | Download the model weights listed in `tools/setup_env.sh` | Pedro |  | Sat 18:42 | `qwen3.5:9b` pulled. PE-Core, MegaLoc, StreetCLIP, CLIP ViT-L/14 and PLONK still downloading at 18:21 · Sat 18:42: qwen3.5:9b pulled (6.6 GB); HF/torch.hub/Ultralytics weights in ~/.cache; tools/setup_env.sh re-run skips everything (idempotent); facebook/sam3 gated, see T64 |
| T06 | doing | P1 | geo | Fetch the Commons landmark photos (`tools/fetch_commons.py`) | Pedro | T03 | Sat 18:42 | Restarted 18:19 with a contact User-Agent after Wikimedia 429s. All PT (17,287), then ES/FR capped at 30k each. Plan order puts heritage and much-linked items first, so a partial gallery is still useful · Sat 18:42: 18:42 PT running: 531/17,287, 0 throttles, contact UA https://github.com/PedroMattaMPT (user's choice), max 2 req/s; ES+FR 30k each follow overnight; detached, log Data/gallery/commons/fetch_PT.log |
| T07 | done | P1 | pixel | Fetch the Panoramax external test panoramas (about 100 per country) | Pedro |  | Sat 18:42 | PT 99 and ES 100 done; FR downloading since 18:20 (`Data/panoramax/fetch_FR.log`) · Sat 18:42: Data/panoramax/: PT 99, ES 100, FR 100 full-res 360s (1.4 GB), all JPEG OK; whole collections split val/final (PT 73/26, ES 67/33, FR 67/33); PT only covers 4 one-degree tiles (Lisbon, Oeste coast, Evora, Porto/Minho); sizes 4000x2000 to 12288x6144 |
| T08 | todo | P0 | team | Ask the organisers the PLAN section 8 questions on Discord; record the answers in RULES.md |  |  | Sat 18:25 | Most urgent: log schema (Q1), Urban labels (Q2), runtime external access (Q3), feedback (Q4). Our heading checks suggest filename times are UTC; confirm (Q5) |
| T09 | done | P0 | pipeline | Smoke-test the Python 3.12 env and model loading on sm_120 | Pedro |  | Sat 18:42 | torch 2.11.0+cu128, open_clip PE-Core, RapidOCR + OpenVINO, the Ollama VLM with an image and a JSON schema. Don't wait on the power cap (T48) · Sat 18:42: 18:40: 14 models load and run one forward pass on sm_120 with torch 2.11.0+cu128, offline from cache; qwen3.5:9b 5.6 GB, 0.7-1.4 s per warm request, 51-55 tok/s; nothing broke |
| T10 | done | P0 | pipeline | Implement the score calculator | Pedro |  | Sat 19:30 | Check against PLAN 1.2 (urban 25 m = 80%, 300 m = 25%) and the 16,050.52 maximum; d < 10 m counts as 0; Special One ×3 · Sat 19:26: Started with Claude (T10, T17 directly; T13, T16, T19 by parallel agents) · Sat 19:30: panoloc/scoring.py: haversine, theta, entry/list/max score, score_output on run-log outputs, expected_theta (known category or urban_probability), best_point; tests/test_scoring.py checks the PLAN 1.2 and 3.4 figures (16,050.52 max, 80% at 25 m urban, 15,248.00 ...) |
| T11 | done | P0 | pipeline | Implement the JSON event log, penalty tracker and fresh per-panorama state | Pedro |  | Sat 18:37 | Event types: `design_system_prompt.md`, Implementation targets. Answered question ×0.95, cue ×0.8, place-name conversion ×0.5, per-output snapshots; a skip changes nothing · Sat 18:33: Started with Claude: panoloc/runlog.py + tests + a sample log for T12 · Sat 18:37: panoloc/runlog.py (Run, penalties, stages, questions, cues, outputs, log.json export); 12 unittest cases pass on 3.13 and the 3.12 venv; sample: python3 tools/sample_log.py -> runs/sample/r-20261010-173722-98600a/log.json |
| T12 | todo | P0 | team | Send a sample JSON log to Discord |  | T11 | Sat 18:37 | Before 19:00, so the organisers can confirm the format before the trial · Sat 18:37: Sample ready: runs/sample/r-20261010-173722-98600a/log.json (invented run: failed optional stage, skipped + answered question, cue, two outputs with penalty snapshots) |
| T13 | doing | P0 | perception | Cut the views: filename parse, 8 horizontal views + sky + ground, photographer mask | Pedro |  | Sat 19:26 | `py360convert`. Mask the bottom ~15–20% but record what was masked (PLAN 3.1) · Sat 19:26: Started with Claude (T10, T17 directly; T13, T16, T19 by parallel agents) |
| T14 | todo | P0 | perception | Run PP-OCRv6 on the views with full-resolution rereads; parse postcodes, phones, plates |  | T13 | Sat 18:25 | RapidOCR + OpenVINO on the CPU; regexes in MODEL_DECISIONS 4. Never accept digits only the VLM saw |
| T15 | todo | P0 | perception | VLM checklist per view in JSON with `not_visible`, plus landmark hypotheses |  | T13 | Sat 18:25 | Use whichever VLM works first (`qwen3.5:9b` pulled, `gemma4:12b` fallback). Never ask it for coordinates |
| T16 | doing | P0 | geo | Name lookup: OCR names, postcodes and VLM landmarks to candidate coordinates | Pedro | T03 | Sat 19:26 | Exact + fuzzy match on Wikidata labels and aliases and GeoNames places and postcodes; keep ambiguous matches · Sat 19:26: Started with Claude (T10, T17 directly; T13, T16, T19 by parallel agents) |
| T17 | done | P0 | geo | Implement coordinate-source roles and the output contract, with a coarse fallback | Pedro |  | Sat 19:30 | Every candidate is `camera`, `landmark` or `area`; output records `output_method` and a nullable `position_uncertainty_m` (PLAN 3.3) · Sat 19:26: Started with Claude (T10, T17 directly; T13, T16, T19 by parallel agents) · Sat 19:30: panoloc/candidates.py: Candidate (camera/landmark/area, source, nullable accuracy/extent, group for correlated sources), Output contract (method, source role, sources, nullable uncertainty + its source) logged via Run.output, distinct() NMS, normalise(), coarse_output() with a Lisbon global fallback (placeholder prior until T39); tests/test_candidates.py |
| T18 | todo | P0 | geo | Simple fusion and score-aware output: one coordinate repeated in all 10 slots |  | T10, T16, T17 | Sat 18:25 | Maximise expected score (PLAN 1.1); score both Urban and non-Urban while the label is unknown (PLAN 1.3) |
| T19 | doing | P0 | pipeline | Question loop: up to 4 agent options with map links, answer or skip | Pedro | T11 | Sat 19:26 | Options cover the scope or include an explicit "none of these"; a skip is logged and changes nothing (RULES.md) · Sat 19:26: Started with Claude (T10, T17 directly; T13, T16, T19 by parallel agents) |
| T20 | todo | P0 | pipeline | Run one panorama end to end: views, OCR/VLM, names, fusion, question/skip, coordinates |  | T14, T15, T18, T19 | Sat 18:25 | Include one skipped question and one failed optional stage, as Gate A asks |
| T21 | todo | P1 | pixel | Start resumable PE-Core embeddings of the bank |  | T05 | Sat 18:25 | Batched, with image IDs and preprocessing version; measure throughput on a small batch first (PLAN 4.1) |
| T22 | todo | P1 | pixel | Select the external validation set and a separate final subset |  | T07 | Sat 18:25 | OSV-5M test split + Panoramax split by collection; PT/ES/FR, urban, rural, off-road, landmarks (PLAN 4.6) |
| T23 | todo | P1 | pipeline | Freeze the hash of `Data/warmup_locations.json` and set up the warm-up evaluator |  | T10 | Sat 18:25 | 19 precise references (5–12 m) for primary metrics, the 60 km one diagnostic only. Evaluation only: never in agent inputs, bank, training or calibration |
| T24 | todo | P1 | team | Freeze the PLAN 4.8 accuracy targets and evaluation policy; record the simple baseline |  | T20, T23 | Sat 18:25 | Targets, primary filenames, category sources, baseline hash, operator policy and time limits, before comparing configurations |
| T25 | todo | P0 | team | Gate A: coordinate output and reviewable log, with a skipped question and a failed optional stage |  | T20 | Sat 18:25 | PLAN section 5 |

## B · Trial · Saturday 19:00–21:00

**Gate B:** usable logs, a functioning human loop and a known operational time budget. Fix these before adding models.

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T26 | todo | P0 | pipeline | Run the baseline on each trial panorama independently and record total time |  | T20 | Sat 18:25 | Fresh state per panorama; nothing carried across panoramas (RULES.md) |
| T27 | todo | P0 | team | Submit a JSON log for organiser review |  | T11 | Sat 18:25 | The trial is recommended for checking that the logs comply (RULES.md) |
| T28 | todo | P1 | team | Record any feedback the organisers return; keep place estimates marked as estimates |  |  | Sat 18:25 |  |
| T29 | todo | P0 | team | List the concrete failures: missed text, missing areas, false matches, ambiguous coordinates, slow stages |  | T26 | Sat 18:25 | Turn each into a task for phase C |
| T30 | todo | P0 | team | Gate B: usable logs, a working human loop and a known time budget |  | T26, T27, T29 | Sat 18:25 | PLAN section 5 |

## C · Overnight · Saturday 21:00 to Sunday 08:00

**Gate C:** the PLAN 4.8 accuracy targets, the coordinate-branch checks and valid logging, with measured initial automated processing ≤ 150 s and peak GPU memory ≤ 14 GB on representative cases. The resource limits alone do not pass it.

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T31 | todo | P1 | geo | Build the full local name index: OSM names + Wikidata + GeoNames, with source IDs |  | T03, T04 | Sat 18:25 | OSM `name`, `alt_name` and `wikidata` tags from the Geofabrik extracts; Portugal first (PLAN 4.4) |
| T32 | todo | P1 | geo | Build the zone boundaries for questions from CAOP and geoBoundaries |  |  | Sat 18:25 | Options cover their scope without overlap; record versions and CRS, transform to WGS84 (PLAN 4.4) |
| T33 | todo | P1 | geo | Embed the Commons landmark photos with PE-Core |  | T21 | Sat 18:25 | Embed whatever T06 has fetched. Their coordinates are the landmark's, never the camera's (PLAN 4.5) |
| T34 | todo | P1 | pixel | Declare the bank partitions: training, validation, final test, reference gallery |  |  | Sat 18:25 | PT by sequence (13,407); ES/FR by ~10 km blocks (no sequence column); drop the 85 Ceuta/Melilla images; weight Madeira and the Azores (PLAN 4.1) |
| T35 | todo | P1 | pixel | Finish and verify the PE-Core embeddings of the bank |  | T21, T34 | Sat 18:25 |  |
| T36 | todo | P1 | pixel | Build the kNN index over the bank |  | T35 | Sat 18:25 | faiss-cpu or a torch matmul; retrieve per view and merge repeated locations and sequences (PLAN 3.2) |
| T37 | todo | P1 | pixel | Train and calibrate the mini-PIGEON linear head on frozen embeddings |  | T35 | Sat 18:25 | PT districts, ES communities, FR regions; split by sequence and space; report top-1 and top-4 region recall (PLAN 4.2) |
| T38 | todo | P1 | pixel | Run GeoCLIP with a PT/ES/FR gallery as an extra candidate generator |  |  | Sat 18:25 | Compare the restricted stock gallery, OSV-5M coordinates and the merged gallery (PLAN 4.5) |
| T39 | todo | P1 | geo | Compare candidate generators and fusion on external validation; calibrate the weights |  | T22, T36, T37, T38 | Sat 18:25 | Group the PE-Core sources and cap them; keep a global fallback (PLAN 3.2) |
| T40 | todo | P1 | pipeline | Run paired autonomous and assisted validation against the warm-up baseline |  | T20, T23 | Sat 18:25 | Nominal, radius-aware and human answer modes (PLAN 3.4); report radius sensitivity, place-option recall, answered and skipped counts |
| T41 | todo | P1 | geo | Validate MegaLoc + ALIKED/LightGlue on separate-capture examples |  | T33 | Sat 18:25 | Enable only where the gallery has coverage. A match is an approximate anchor, not a sub-10 m fix (PLAN 3.3) |
| T42 | todo | P1 | geo | Landmark/cell route: exhaustive cells, interior points, distance bounds, recovery option |  | T19, T32 | Sat 18:25 | Target bound ≤ 25 m urban or unknown, ≤ 1 km non-urban. A click picks the cell; the agent computes the coordinate (PLAN 3.3) |
| T43 | todo | P0 | team | Run the PLAN 4.8 accuracy gate and test each coordinate branch |  | T39, T40, T42 | Sat 18:25 | At least 9 of 17 urban references robustly within 100 m; mean conservative score ≥ 30% of the maximum |
| T44 | todo | P2 | perception | Add targeted detector crops (YOLOE) only where they fix observed failures |  | T29 | Sat 18:25 | Thresholds: MODEL_DECISIONS check 5 |
| T45 | todo | P2 | team | Decide on the backlog components once the phase C tasks meet their gates |  | T43 | Sat 18:25 | SAM 3, segmentation, solar checks, grid features, feature table (PLAN 4.7) |
| T46 | todo | P0 | pipeline | Rehearse the retained configuration: no network, module timeouts, unknown category |  | T20 | Sat 18:25 | Optional stages get deadlines; a failed model or missing network still leaves candidates and a log (PLAN 3.5) |
| T47 | todo | P1 | perception | Compare Qwen3.5-9B with Gemma 4 12B on ~20 real crops; keep the winner |  | T15 | Sat 18:25 | MODEL_DECISIONS check 2: Qwen keeps the role if it is at least as accurate, ≤ 9 GB resident and ≤ 60 s for 10 crops |
| T48 | todo | P1 | pipeline | Lift the GPU power cap (80 W of 175 W) |  |  | Sat 18:42 | Still 80 W at 18:11 (`nvidia-smi -q -d POWER`). Try Fn+P or the backports kernel. Not a baseline prerequisite (PLAN 5) · Sat 18:42: 18:40 still capped: power limit 80 W of 175 W max (nvidia-smi -q -d POWER) |
| T49 | todo | P1 | pipeline | Queue the panoramas: one GPU worker, fresh state per run ID, interactive work first |  | T20 | Sat 18:25 | PLAN 6; organiser question Q9 (T08) says whether they arrive together |
| T50 | todo | P1 | ui | Build the operator console v1 from `design_system_prompt.md`, driven by the event log |  | T11 | Sat 18:25 | Prefetched map tiles, no runtime CDNs; a replay just plays the log again |
| T51 | todo | P2 | team | Apply the PLAN section 9 corrections to MODEL_DECISIONS.md |  |  | Sat 18:25 | Until then PLAN.md wins where they disagree |
| T52 | todo | P0 | team | Gate C: 4.8 targets, branch checks, valid logs, ≤ 150 s initial processing, ≤ 14 GB GPU |  | T43, T46 | Sat 18:25 | PLAN section 5 |

## D · Freeze and rehearsal · Sunday 08:00–10:00

**Gate D:** Gate C has passed, and the team completes the unfamiliar six-panorama rehearsal within 60 minutes with valid outputs and logs, meeting the PLAN 4.8 targets under the declared reference assumptions.

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T53 | todo | P0 | team | Stop features at 08:00; freeze weights, config and dependencies; keep a working fallback |  |  | Sat 18:25 | `requirements.lock.txt` pins the packages |
| T54 | todo | P0 | pixel | Evaluate the retained version once on the reserved external subset |  | T53 | Sat 18:25 | Record assumptions and observed failures |
| T55 | todo | P0 | team | Rehearse six unfamiliar external panoramas within 60 minutes, with real human answers |  | T53 | Sat 18:25 | Separate logs, no carried-over evidence; include ES/FR, urban and non-urban (PLAN 4.8) |
| T56 | todo | P0 | pipeline | Confirm coordinate order, log export and the organisers' label and feedback format |  | T08 | Sat 18:25 |  |
| T57 | todo | P1 | team | Assign the Sunday roles: operator, finder, Street View checkers |  |  | Sat 18:25 | PLAN 6 |
| T58 | todo | P1 | pipeline | Empty /tmp and check free RAM and VRAM before the run |  |  | Sat 18:25 | /tmp is a 16 GB RAM-backed tmpfs |
| T59 | todo | P0 | team | Gate D: Gate C passed and the six-panorama rehearsal meets 4.8 within 60 minutes |  | T52, T54, T55, T56 | Sat 18:25 | PLAN section 5 |

## Run · Scoring and finals · Sunday from 10:00

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T60 | todo | P0 | team | Scoring run: 5 panoramas + the Special One in 60 minutes of solving |  |  | Sat 18:25 | Initial answer first, then refine; fresh state per panorama; skipping a question is free and means nothing (PLAN 6) |
| T61 | todo | P0 | pipeline | Submit each panorama's coordinates and its JSON log |  |  | Sat 18:25 | The selected coordinate in all 10 slots; per-output penalty snapshots in the log |
| T62 | todo | P1 | team | Prepare the presentation and its live panorama solve |  |  | Sat 18:25 |  |
| T63 | todo | P2 | team | Final: play the other challenge winners on a new panorama, live |  |  | Sat 18:25 | Only if we win Albatroz |

## Backlog · Optional, only after a measured gain

| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |
|---|---|---|---|---|---|---|---|---|
| T64 | todo | P2 | perception | SAM 3 presence check on detector boxes; request `facebook/sam3` access |  | T44 | Sat 18:42 | SAM3-LiteText-S0 until access is granted (MODEL_DECISIONS 3) · Sat 18:42: 18:40: facebook/sam3 not downloaded (gated): request access, hf auth login, then SAM3=1 tools/setup_env.sh. SAM3-LiteText-S0 works |
| T65 | todo | P2 | perception | EoMT-L segmentation: sea direction, skyline, scene proportions |  |  | Sat 18:25 | Segment the perspective views, not the raw panorama (MODEL_DECISIONS 7) |
| T66 | todo | P2 | geo | Solar heading check per candidate |  |  | Sat 18:25 | Filename times look like UTC; needs a reliable sun detection and timestamp (PLAN 4.4) |
| T67 | todo | P2 | geo | Grid features: GHSL urbanity, DEM elevation, coast distance |  | T04 | Sat 18:25 | Data in `Data/geo/` |
| T68 | todo | P2 | pixel | Feature likelihood table (PLAN 4.3) |  | T37 | Sat 18:25 | Keep only if it adds value beyond mini-PIGEON and kNN |
| T69 | todo | P2 | pipeline | gpt-oss-20b as a conflict checker |  |  | Sat 18:25 | Can't sit next to the VLM; a swap took 4–308 s (MODEL_DECISIONS 2) |
| T70 | todo | P2 | perception | Language ID ensemble: heliport + py3langid + CLD2 |  | T14 | Sat 18:25 | Must improve results on short, noisy OCR strings (PLAN 3.1) |
| T71 | todo | P2 | pixel | Compare encoders: PE-Core vs SigLIP 2 vs StreetCLIP |  |  | Sat 18:25 | MODEL_DECISIONS check 3 |
| T72 | todo | P2 | perception | Compare OCR: PP-OCRv6 medium vs small vs v5 Latin vs the VLM |  | T14 | Sat 18:25 | MODEL_DECISIONS check 6, on ~50 labelled sign crops |
| T73 | todo | P2 | pixel | PLONK as a second generator (OSV-5M vs YFCC weights) |  | T38 | Sat 18:25 | Only if GeoCLIP leaves gaps (PLAN 4.5) |
| T74 | todo | P2 | geo | Mapillary gallery near candidates |  |  | Sat 18:25 | Needs `$MAPILLARY_TOKEN`; `mapillary_grid_sample.py` is untested; runtime fetches wait on organiser question Q3 |
| T75 | todo | P2 | geo | Metric camera pose from a georeferenced 3D model |  |  | Sat 18:25 | A later enhancement, outside the first implementation (PLAN 3.3) |
