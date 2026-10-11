# Evaluation policy

**Frozen:** Saturday 2026-10-10, 22:30 WEST (21:30 UTC), before any configuration in the results table was scored (PLAN.md 4.8). **Task:** T24 (policy and baseline), T40 (assisted runs).

Everything in the first five sections is frozen. A later change gets a dated line under "Changes", with its reason. It never relabels an earlier run, and it never turns a failed run into a pass.

## Targets

From PLAN.md 4.8, as the constants in `panoloc/evaluate.py`. They are provisional planning targets, not predictions.

| Target | Rule | Constant |
|---|---|---|
| Urban camera accuracy | The final selected coordinate is within 100 m throughout the reference radius (`d_ref + error_radius_m <= 100 m`) for at least 50% of the urban primary references: **9 of 17** with the inferred categories | `TARGET_URBAN_HIT_M = 100`, `TARGET_URBAN_HIT_SHARE = 0.5` |
| Mean conservative score | At least **30%** of the unpenalised exact maximum (4,815.16 of 16,050.52), averaged over all 19 primary cases. Each case is scored at `d_max = d_ref + radius`, with the actual rank factors and per-output penalties, under its reference category. A missing case counts 0 | `TARGET_MEAN_CONSERVATIVE_SHARE = 0.30` |
| Time | At most **150 s** of initial automated processing per panorama: run start to the first `output.produced` in the log (Gate C). Refinement and answer time are recorded separately | |
| GPU memory | At most 14 GB peak (Gate C) | |

Only the retained configuration's realistic human-assisted runs can pass the accuracy targets. Autonomous, oracle and simulated-human runs are reported against them, but cannot pass (PLAN.md 4.8).

## Reference set

- **Warm-up reference:** `Data/warmup_locations.json` and `.csv`, the team's estimated locations, not ground truth. `panoloc.evaluate` refuses to load them unless their sha256 match `WARMUP_SHA256`:
  - json `7027b8c7620b9a46fc79781f55990beba4913eb8675257bbf89c5848bc5754b7`
  - csv `7aa38e54a6fb511c13fda53bcb04818baf7161d77d9da3c5f29eb5b4e3e2c5a7`
- **Primary:** the 19 references with confidence "high" (radii 5 to 12 m). `IMG_20241213_120841_00_059.jpg` (60 km radius) is diagnostic only and never enters the primary numbers.
- **Category sources:** warm-up, the file's own `urban` estimate, source "inferred" (17 urban and 2 non-urban among the primary). External `val` / `final`, GHSL-inferred (`tools/build_splits.py`). Both categories are always scored as well (PLAN.md 1.3).
- **Radius sensitivity:** nominal at `d_ref`, conservative (lower) at `d_ref + r`, upper at `max(0, d_ref - r)` (PLAN.md 4.6).
- **Reserved:** the Panoramax `final` split and the OSV-5M `test` partition are for the single final run (T54), never for these comparisons.

The 19 primary filenames:

```text
IMG_20250104_082423_00_095.jpg
IMG_20250125_142313_00_141.jpg
IMG_20250125_142634_00_170.jpg
IMG_20250125_142634_00_209.jpg
IMG_20250125_144630_00_319.jpg
IMG_20250125_151032_00_611.jpg
IMG_20260510_121401_00_179.jpg
IMG_20260510_122142_00_194.jpg
IMG_20260510_124804_00_218.jpg
IMG_20260510_124840_00_220.jpg
IMG_20260605_092457_00_064.jpg
IMG_20260605_092536_00_066.jpg
IMG_20260813_112252_00_681.jpg
IMG_20260813_112936_00_683.jpg
IMG_20260813_113355_00_685.jpg
IMG_20260813_115036_00_695.jpg
IMG_20260911_125512_00_749.jpg
IMG_20260911_132916_00_754.jpg
IMG_20260922_172452_00_779.jpg
```

## Operator policy

Simulated operators live in `panoloc/oracle.py` (evaluation code; the pipeline never imports it). Each one is built per panorama from that panorama's reference, obtained only through `panoloc.evaluate.load_set`, and passed as `operator=` to `pipeline.run_panorama`. The pipeline receives only an option ID, or nothing for a skip.

| Mode | Answer policy | Parameters |
|---|---|---|
| autonomous | No question is asked (`operator="never"`) | |
| nominal oracle | The option that holds the reference point. A place option holds it when the point is within the option's stated `radius_m` of the option's point: the matching tolerance is that stated radius, with no extra slack. A zone option holds it when its cell (box) or region (polygon) contains the point. Otherwise the explicit "None of these" / "Outside this area" option; without one, a skip. Feature questions are skipped | |
| radius-aware oracle | Answers only when the whole reference disc (radius `error_radius_m`) lies in one option, or outside every listed option when a "None of these" / "Outside" option exists. Otherwise skips | Place options: exact disc-in-disc test. Zones: the centre and 72 points on the disc's edge must all fall in the same option |
| simulated human | Per question: the nominal oracle's answer with probability 0.70, a wrong option (uniform among the others) 0.10, a skip 0.20. When the nominal oracle would skip, it skips | Seeded per panorama: `sha256("2026:" + filename)`, so results do not depend on the order of the panoramas |

Settings shared by every mode, so the runs are paired: the same `Models` settings as the autonomous baseline and the same perception cache (`runs/perception/`); at most 4 questions (`pipeline.MAX_QUESTIONS`); a question is asked only when the pipeline's own expected-gain rule says it is worth its x0.95 (`ask_anyway` off); the category unknown, with `urban_probability = 0.5` (`fusion.DEFAULT_URBAN_PROBABILITY`). Each mode also reruns the autonomous configuration with the same code, and the paired differences are taken against that run.

**Place-option recall:** whether any place option offered held the reference within its stated radius. Reported for the first place question the initial hypotheses give (built whether or not the pipeline asked it) and for the place questions actually asked. Coordinate proximity alone does not prove the place was recognised (PLAN.md 4.6).

## How runs are recorded

- **Code fingerprint:** sha256 over `panoloc/*.py` (each relative name and its bytes, sorted), plus `Models.versions()` from the run logs. The fingerprint is recorded per panorama, because other sessions edit the code while runs are going.
- **Time per panorama:** from each run log, initial (run start to the first output) and total. The GPU is capped at 80 W and shared with other jobs (bank embedding, the Panoramax val baseline, other VLM users), so measured speed is a lower bound and times are upper bounds. Runs that reuse cached OCR and VLM results do not measure the time limit.

## Results

Scores are against the estimated warm-up references, never organiser measurements. "Urban robust" counts urban primary cases with `d_ref + r <= 100 m` for the first coordinate of the final list. "Mean cons." is the mean conservative score as a share of the maximum. Nominal means are the mean list score over the 19 primary cases under each category.

| Config | Date (UTC) | Code sha256 | Operator | Report | Urban robust ≤100 m | Mean cons. | Median d1 | Nominal mean urban / non-urban | Answered / skipped | Time per panorama |
|---|---|---|---|---|---|---|---|---|---|---|
| B0: OCR, VLM, names, fusion (`tools.eval_assisted:predict_no_retrieval`) | 2026-10-10 23:17 | b5a7815b0d52 | autonomous | `runs/eval/warmup-20261010-231712/report.json` | 0/17 | 2.7% | 257.5 km | 389 / 2,740 | 0 / 0 | Initial 53 s median, 56 s max, 0 of 6 over 150 s (uncached, timing run at 23:09 UTC) |
| B1: B0 + PE-Core kNN, region head, GeoCLIP (`tools.eval_assisted:predict`) | 2026-10-10 23:16 | 22f118fa1a02 | autonomous | `runs/eval/warmup-20261010-231558/report.json` | 0/17 | 8.9% | 122.2 km | 1,403 / 5,993 | 0 / 0 | B0 + 1.2 s: kNN and region head 0.7 s, GeoCLIP 0.5 s (first panorama +9 s of loading) |
| T40 autonomous, B1 settings | 2026-10-10 23:19 | b5a7815b0d52 | autonomous | `runs/eval/assisted-b1cfg/autonomous/report.json` | 0/17 | 8.9% | 122.2 km | 1,403 / 5,993 | 0 / 0 | Cached perception: not timed |
| T40 nominal oracle, B1 settings | 2026-10-10 23:19 | b5a7815b0d52 | nominal oracle | `runs/eval/assisted-b1cfg/nominal/report.json` | 0/17 | 14.7% | 703 m | 2,092 / 9,429 | 54 / 0 | Cached perception: not timed |
| T40 radius-aware oracle, B1 settings | 2026-10-10 23:19 | b5a7815b0d52 | radius-aware oracle | `runs/eval/assisted-b1cfg/radius/report.json` | 0/17 | 14.8% | 703 m | 2,106 / 9,536 | 51 / 1 | Cached perception: not timed |
| T40 simulated human, B1 settings | 2026-10-10 23:19 | b5a7815b0d52 | simulated human | `runs/eval/assisted-b1cfg/human/report.json` | 0/17 | 11.8% | 4.3 km | 1,868 / 8,349 | 39 / 13 | Cached perception: not timed |
| B0, organiser-checked references | 2026-10-11 00:24 | b5a7815b0d52 | autonomous | `runs/eval/warmup-20261010-231712/report_organiser_checked.json` | 0/17 | 2.7% | 257.5 km | 389 / 2,740 | 0 / 0 | Re-scored, no rerun |
| B1, organiser-checked references | 2026-10-11 00:24 | 22f118fa1a02 (edited during the run: verify.py) | autonomous | `runs/eval/warmup-20261010-231558/report_organiser_checked.json` | 0/17 | 8.9% | 122.2 km | 1,403 / 5,993 | 0 / 0 | Re-scored, no rerun |
| T40 autonomous, B1 settings, organiser-checked references | 2026-10-11 00:24 | b5a7815b0d52 | autonomous | `runs/eval/assisted-b1cfg/autonomous/report_organiser_checked.json` | 0/17 | 8.9% | 122.2 km | 1,403 / 5,993 | 0 / 0 | Re-scored, no rerun |
| T40 nominal oracle, B1 settings, organiser-checked references | 2026-10-11 00:24 | b5a7815b0d52 | nominal oracle | `runs/eval/assisted-b1cfg/nominal/report_organiser_checked.json` | 0/17 | 14.6% | 703 m | 2,092 / 9,429 | 54 / 0 | Re-scored, no rerun |
| T40 radius-aware oracle, B1 settings, organiser-checked references | 2026-10-11 00:24 | b5a7815b0d52 | radius-aware oracle | `runs/eval/assisted-b1cfg/radius/report_organiser_checked.json` | 0/17 | 14.7% | 703 m | 2,106 / 9,536 | 51 / 1 | Re-scored, no rerun |
| T40 simulated human, B1 settings, organiser-checked references | 2026-10-11 00:24 | b5a7815b0d52 | simulated human | `runs/eval/assisted-b1cfg/human/report_organiser_checked.json` | 0/17 | 11.8% | 4.3 km | 1,868 / 8,349 | 39 / 13 | Re-scored, no rerun |
| T79 recommended gate (min_gain 0.0526, max_questions 4), val_first100 (ES/FR) | 2026-10-11 00:23 | 467c33e94a1b | simulated human, seed 2026 | `runs/eval/sweep-val100-final/g0.0526-q4/report.json` | 4/60 nominal (autonomous 2/60) | 13.2% nominal (autonomous 8.1%) | 41.0 km | 1,208 / 5,043 | 397 / 99 | Cached perception: not timed |
| T79 recommended gate (min_gain 0.0526, max_questions 4), val_pt30 (PT) | 2026-10-11 00:23 | 467c33e94a1b | simulated human, seed 2026 | `runs/eval/sweep-pt30-final/g0.0526-q4/report.json` | 5/19 nominal (autonomous 2/19) | 28.3% nominal (autonomous 26.2%) | 2.9 km | 2,652 / 8,528 | 96 / 22 | Cached perception: not timed |
| 9c app batch v2, warm-up via the app (nominal oracle: reported, cannot pass) | 2026-10-11 01:19 | app build of about 02:02 WEST | nominal oracle | `runs/app/batch-20261011-020232-v2/report.json` | 8/17 nominal (radius-aware 8/17) | 32.5% nominal (conservative 30.1%) | 109 m | 4,936 / 8,601 | 131 / 0 | First output 48.2 s median, 50.3 s max, live perception |
| T79 secondary check, val_130, defaults (2, True), `pipeline.py` 02:42:10 (nominal oracle: reported, cannot pass) | 2026-10-11 01:50 | 6a3cf2da906a | nominal oracle | `runs/eval/sweep130-secondary-0240-nominal/g0.0526-q6/report.json` | val, nominal | 36.2% nominal (gap-fix run 31.9%) | 346 m | — | 985 / 0 | Cached perception: not timed |
| T79 secondary check, val_130, defaults (2, True), `pipeline.py` 02:42:10 (simulated human, D3; on val, not the Gate C set) | 2026-10-11 01:50 | 6a3cf2da906a | simulated human, seed 2026 | `runs/eval/sweep130-secondary-0240-human/g0.0526-q6/report.json` | val, nominal | 16.8% nominal (gap-fix run 16.8%) | 23.5 km | — | 504 / 124 | Cached perception: not timed |
| **Gate C run (D3): warm-up via the app, simulated human, landmarks on** | 2026-10-11 01:40 | app build, `pipeline.py` 02:36:41 WEST | simulated human (70/10/20, seed 2026) | `runs/app/batch-20261011-024036-human/report.json` | 5/17 nominal (robust 4/17) | 24% nominal (conservative 22%) | 7.3 km | own-category mean 3,828 | 58 / 23 | 46–54 s, live perception |
| **Gate C run (D3), sticky skips: warm-up via the app, landmarks on, skip retries 2/2** | 2026-10-11 02:19 | app build, `pipeline.py` 03:16:48 WEST, `ocr.py` 03:11:53 | simulated human (70/10/20, sticky_skip 0.75, seed 2026) | `runs/app/batch-20261011-031901-human-sticky/report.json` | 5/17 nominal (robust 4/17) | 22% nominal (conservative 20%) | 7.3 km | own-category mean 3,469 | 64 / 58 | 45–50 s, live perception |
| Gate C run (D3), sticky skips, first RECOVERY trigger (not adopted) | 2026-10-11 02:35 | app build, `pipeline.py` 03:28:12 WEST | simulated human (70/10/20, sticky_skip 0.75, seed 2026) | `runs/app/batch-20261011-033542-human-sticky-recovery/report.json` | 5/17 nominal (robust 4/17) | 22% nominal (conservative 21%) | 7.3 km | own-category mean 3,590 | 70 / 60 | Live perception |

- **First RECOVERY trigger, not adopted.** `runs/app/batch-20261011-033542-human-sticky-recovery` has the same setup as the sticky-skip run below, plus the first wrong-answer recovery trigger. It added 121 points per panorama on the warm-up (3,469 → 3,590). The coordinator turned RECOVERY off at 03:50, because on val_130 that trigger dropped 87 correct answers against 50 wrong ones fixed. Gate C still fails: 5/17 urban within 100 m and 22%. Answers: 70 answered (36 with the reference inside the option, 28 right complements, 6 mistakes); 60 skipped (28 first-time, 28 skipped again on a re-ask, 4 for a coarse reference). Re-asks cost about 1.4 prompts per panorama that are skipped a second time, as in the sticky-skip run.
- **Gate C, sticky-skip run (D3): FAIL.** `runs/app/batch-20261011-031901-human-sticky` is the first Gate C run with the conservative simulator, as agreed after the T79 retry sweep, where independent skips overstate retries. It ran on the 03:20 defaults (skip retries 2/2, ANSWER_SLACK 0, ANSWER_ACCURACY 0.9) and the OCR parsing fixes, all 20 panoramas, 0 errors.
  - Targets, on nominal distances: 5 of 17 urban within 100 m (robust 4/17) against 9 needed, and a 22% mean (conservative 20%) against 30%.
  - Distances over the 19 primary cases: 2 within 25 m, 5 within 100 m, 8 within 1 km, 16 within 100 km; median 7.3 km, mean 63.3 km.
  - Answers: 64 answered (33 with the reference inside the option, 25 right complements, 6 simulated mistakes); 58 skipped (27 first-time simulated skips, 27 skipped again on a re-ask, 4 for a coarse reference).
  - It isn't a like-for-like comparison with the first run: the code and the simulator both changed.
- **Gate C, first eligible run (D3): FAIL.** `runs/app/batch-20261011-024036-human` started at 02:40:36 WEST, after the user's 02:39 decision, so it is the first run that could pass Gate C. It ran all 20 panoramas with 0 errors.
  - Targets, on nominal distances (D2): 5 of 17 urban within 100 m against the 9 needed (141 59 m, 209 96 m, 611 12 m, 218 15 m, 220 19 m), and a 24% mean against the 30% needed. Robust 4/17, conservative 22%.
  - Distances over the 19 primary cases: 3 within 25 m, 8 within 1 km, 16 within 100 km; median 7.3 km.
  - Answers: 58 answered (29 right with the reference inside the option, 21 right complements, 8 simulated mistakes); 23 skipped (21 simulated, 2 for a coarse reference).
  - The largest losses follow simulated wrong answers: 749 reached 1,140 km, 064 394 km, 683 130 km, and 179 72.5 km (90 m with the nominal oracle in the v2 batch).
- **Organiser-checked references (T81):** the rows so marked re-score the same runs after the organisers' correction of the warm-up references (see Changes, 2026-10-11 01:13). The wider error bounds lower the conservative shares by about 0.1 pt; no verdict changes.
- **T79 rows** are on external validation sets (Panoramax camera GPS, radius unknown), so their urban and mean-share figures are nominal, not robust, and they cannot be read against the warm-up gate.
- **Gate (PLAN.md 4.8): every configuration fails both targets.** None has an urban reference robustly within 100 m (9 of 17 needed), and the best mean conservative score is 14.8% (30% needed). The oracle and simulated-human rows could not pass in any case.
- **B0** was scored again at 23:17 UTC with B1's code, because fusion had changed since its timing run (T31 name cleaning). The scores came out identical. Its times come from the timing run at 23:09 UTC (`runs/eval/warmup-20261010-230907`): 6 uncached panoramas took 52 to 56 s from start to first output. No other VLM client was running, but the GPU was capped at 80 W and may have been shared with agent C's T41 job, so speed is a lower bound. An earlier attempt under heavy contention (the bank embedding, plus a second VLM client on Ollama's single slot) measured 86 to 202 s, with 2 of 12 over 150 s (`runs/eval/warmup-20261010-212215`, superseded: older fusion code).
- **B1 holds three candidate generators, not PLAN.md 4.8's one:** PE-Core kNN and the region head (group `pe-core`) and GeoCLIP (group `geoclip`), over 12 views of 60°, with weights uncalibrated until T39. On 100 Panoramax val panoramas (ES/FR only), these three took the own-category mean score from 346 to 1,235 (coordinator's run). On the warm-up set, B1 puts 6 of 19 within 1 km (B0: 2) and raises the own-category mean from 438 to 1,469.
- **Code sha256:** the fingerprint each run loaded. Files edited while a run went on (`cells.py`, `pipeline.py`, `oracle.py` during the B0 timing run; `verify.py` during B1) were not reloaded by the running process. B0's rerun and B1 differ only in `verify.py`, which the pipeline does not import.

### T40: paired assisted runs, B1 settings

The runs, from `tools/eval_assisted.py run --retrieval`, are in `runs/eval/assisted-b1cfg/`: `summary.json`, then per mode a `report.json` and per case an `oracle.json` with the operator's decisions. In every mode, the first output matches the autonomous run's on 19 of 19 panoramas, and the autonomous rerun reproduces B1's report on 19 of 19, so the differences come from the questions alone. A place counts as held within its stated radius, and the reference radii are 5 to 12 m.

| Mode | Mean cons. (paired Δ) | Nominal / upper | Better / worse / same | Asked / answered / skipped | Right / wrong | Robust ≤1 km | Robust ≤10 km |
|---|---|---|---|---|---|---|---|
| autonomous | 8.9% | 9.2% / 9.4% | | 0 / 0 / 0 | | 6/19 | 7/19 |
| nominal oracle | 14.7% (+5.7 pt) | 15.0% / 15.2% | 10 / 9 / 0 | 54 / 54 / 0 | 54 / 0 | 11/19 | 13/19 |
| radius-aware oracle | 14.8% (+5.8 pt) | 15.0% / 15.3% | 10 / 9 / 0 | 52 / 51 / 1 | 51 / 0 | 11/19 | 13/19 |
| simulated human | 11.8% (+2.9 pt) | 12.1% / 12.4% | 7 / 10 / 2 | 52 / 39 / 13 | 34 / 5 | 9/19 | 12/19 |

- **Place-option recall:** every panorama's initial hypotheses give a place question. Its places hold the reference in 8 of 19, but never a place with a radius of 1 km or less (0 of 19). The nearest place offered lies a median 9.7 km from the reference. Of the 34 place questions the nominal oracle answered, 18 got "None of these".
- **Radius sensitivity:** the reference radii move the mean share by about 0.3 pt (conservative against upper). The radius-aware oracle skipped 1 question of 52 and otherwise answered like the nominal one.
- **Where answers lose:** under the nominal oracle, the 9 "worse" cases are of two kinds. Six were already within 111 to 739 m (141, 179, 209, 218, 319, 611), where correct answers only confirmed the chosen candidate and still cost x0.95 each: on 179, four answers cost 8.5 pt. The other three ended 133 to 267 km off (066, 095, 683), at 0.1 pt or less. Two of them ended farther away than they started, despite four correct answers.
- **Where answers win:** country and district answers moved six outputs from 118 to 434 km off to 179 to 579 m: 170 (+22.0 pt), 194 (+29.6), 681 (+13.0), 685 (+16.0) and 695 (+13.1). The sixth, 749 (non-urban), went from 260 km to 16 km (+27.7).
- **Question loop:** 36 place and 22 named-zone questions under the nominal oracle. Zone answers reached country (8), district (11), region or community (2) and municipality (1) level within the 4-question cap, and every final output is still a `coarse_candidate`, because no answered cell produces a coordinate yet (T42).

Per primary panorama, the paired difference in conservative share from the autonomous run (percentage points), with the questions answered / skipped:

| Panorama | Cat. | Autonomous d1, cons. | nominal: Δ cons., ans/skip | radius: Δ cons., ans/skip | human: Δ cons., ans/skip |
|---|---|---|---|---|---|
| `IMG_20250104_082423_00_095.jpg` | U | 122.2 km, 0.1% | -0.1 pt, 4/0 | -0.1 pt, 4/0 | -0.1 pt, 4/0 |
| `IMG_20250125_142313_00_141.jpg` | U | 739 m, 11.8% | -0.6 pt, 1/0 | -0.6 pt, 1/0 | -0.6 pt, 1/0 |
| `IMG_20250125_142634_00_170.jpg` | U | 434.2 km, 0.0% | +22.0 pt, 1/0 | +22.0 pt, 1/0 | +22.0 pt, 1/0 |
| `IMG_20250125_142634_00_209.jpg` | U | 267 m, 26.7% | -1.3 pt, 1/0 | -1.3 pt, 1/0 | -1.3 pt, 1/0 |
| `IMG_20250125_144630_00_319.jpg` | U | 198 m, 32.7% | -1.6 pt, 1/0 | -1.6 pt, 1/0 | -3.2 pt, 2/2 |
| `IMG_20250125_151032_00_611.jpg` | U | 223 m, 30.5% | -1.5 pt, 1/0 | -1.5 pt, 1/0 | -1.5 pt, 1/0 |
| `IMG_20260510_121401_00_179.jpg` | U | 111 m, 45.6% | -8.5 pt, 4/0 | -8.5 pt, 4/0 | -6.5 pt, 3/1 |
| `IMG_20260510_122142_00_194.jpg` | U | 254.8 km, 0.0% | +29.6 pt, 3/0 | +29.6 pt, 3/0 | +29.6 pt, 3/0 |
| `IMG_20260510_124804_00_218.jpg` | U | 711 m, 12.2% | -2.2 pt, 4/0 | -0.5 pt, 1/1 | -10.1 pt, 1/0 |
| `IMG_20260510_124840_00_220.jpg` | U | 4.9 km, 2.0% | +1.0 pt, 3/0 | +1.0 pt, 3/0 | -0.9 pt, 1/2 |
| `IMG_20260605_092457_00_064.jpg` | U | 394.3 km, 0.0% | +0.0 pt, 4/0 | +0.0 pt, 4/0 | +0.0 pt, 0/2 |
| `IMG_20260605_092536_00_066.jpg` | U | 91.3 km, 0.1% | -0.1 pt, 4/0 | -0.1 pt, 4/0 | -0.1 pt, 4/0 |
| `IMG_20260813_112252_00_681.jpg` | U | 156.9 km, 0.1% | +13.0 pt, 3/0 | +13.0 pt, 3/0 | +13.0 pt, 3/0 |
| `IMG_20260813_112936_00_683.jpg` | U | 130.6 km, 0.1% | -0.0 pt, 4/0 | -0.0 pt, 4/0 | +0.0 pt, 0/2 |
| `IMG_20260813_113355_00_685.jpg` | U | 176.9 km, 0.1% | +16.0 pt, 2/0 | +16.0 pt, 2/0 | +0.1 pt, 2/0 |
| `IMG_20260813_115036_00_695.jpg` | U | 118.2 km, 0.1% | +13.1 pt, 2/0 | +13.1 pt, 2/0 | +12.4 pt, 3/1 |
| `IMG_20260911_125512_00_749.jpg` | N | 259.7 km, 3.7% | +27.7 pt, 4/0 | +27.7 pt, 4/0 | -0.5 pt, 3/1 |
| `IMG_20260911_132916_00_754.jpg` | N | 226.6 km, 4.2% | +1.4 pt, 4/0 | +1.4 pt, 4/0 | +1.7 pt, 3/1 |
| `IMG_20260922_172452_00_779.jpg` | U | 267.7 km, 0.0% | +0.8 pt, 4/0 | +0.8 pt, 4/0 | +0.8 pt, 3/1 |

### T79: question-gate sweep on external validation (simulated human)

`tools/eval_assisted.py sweep`, from the perception cache only (OCR, VLM, retrieval, GeoCLIP, landmarks) with the GPU hidden. Tuned on external validation only, never the warm-up set (PLAN.md 4.6).

- **Sets:** `runs/eval/val_first100.json` (ES 67, FR 33; GHSL categories, 60 urban) and `runs/eval/val_pt30.json` (30 PT panoramas over 30 collections; 19 urban). Camera GPS from Panoramax with unknown accuracy, so every score here is nominal. No panorama was skipped as uncached.
- **Code:** `pipeline.py` and `fusion.py` as of 2026-10-11 01:08:58 WEST (fingerprint 467c33e94a1b, unchanged during the run; only `evaluate.py` changed, for T81). `LANDMARK_RELIABILITY = 0.05`, `VERIFIED_RELIABILITY = 0.7`, T42 cell coordinates on, and the T80 urban probability (`urban_probability=None`, estimated from the hypotheses).
- **Gate:** `min_gain` gates every question, cell questions included. Since T42, `max_questions` caps place and zone questions only, and cell questions keep their own budget (`MAX_CELL_QUESTIONS = 12`).
- **Operator:** the simulated human of the operator policy (0.70 right, 0.10 wrong, 0.20 skip), seed 2026, with paired differences against the autonomous run of the same code.

Combined over both sets (130 panoramas). Mean own-category score; Δ is the mean paired difference from autonomous:

| Config | Mean own score | % of max | Paired Δ (pts, % of max) | Better / worse | Answered / skipped / wrong | Median d1 |
|---|---|---|---|---|---|---|
| autonomous | 1,967 | 12.3% | | | 0 / 0 / 0 | 102.3 km |
| g0.0526-q2 | 2,308 | 14.4% | +340 (+2.12) | 49 / 80 | 301 / 66 / 44 | 59.3 km |
| **g0.0526-q4** | **2,681** | **16.7%** | **+714 (+4.45)** | 64 / 65 | 493 / 121 / 71 | 22.4 km |
| g0.1-q2 | 2,186 | 13.6% | +219 (+1.36) | 46 / 82 | 270 / 61 / 42 | 54.8 km |
| g0.1-q4 | 2,500 | 15.6% | +533 (+3.32) | 58 / 70 | 425 / 106 / 61 | 31.5 km |
| g0.2-q2 | 2,176 | 13.6% | +209 (+1.30) | 42 / 85 | 231 / 49 / 35 | 49.3 km |
| g0.2-q4 | 2,433 | 15.2% | +466 (+2.90) | 52 / 75 | 361 / 84 / 51 | 33.0 km |
| g0.3-q2 | 2,288 | 14.2% | +321 (+2.00) | 39 / 85 | 197 / 43 / 32 | 49.3 km |
| g0.3-q4 | 2,500 | 15.6% | +533 (+3.32) | 48 / 76 | 306 / 69 / 47 | 33.0 km |
| g0.5-q2 | 2,140 | 13.3% | +172 (+1.07) | 32 / 67 | 151 / 30 / 23 | 69.8 km |
| g0.5-q4 | 2,234 | 13.9% | +266 (+1.66) | 39 / 60 | 220 / 46 / 35 | 41.8 km |

Per set, paired Δ in points (own-category mean of the autonomous run in brackets):

| Config | val_first100, ES/FR (1,298) | val_pt30, PT (4,197) |
|---|---|---|
| g0.0526-q2 | +350 | +307 |
| **g0.0526-q4** | **+826** | **+338** |
| g0.1-q2 | +296 | −41 |
| g0.1-q4 | +684 | +32 |
| g0.2-q2 | +316 | −146 |
| g0.2-q4 | +617 | −39 |
| g0.3-q2 | +371 | +152 |
| g0.3-q4 | +594 | +326 |
| g0.5-q2 | +152 | +242 |
| g0.5-q4 | +261 | +285 |

- **PT seeds:** the two best PT settings, rerun with seeds 2027 and 2028, gave g0.0526-q4 +338, +18 and +380 (mean +245, positive on every seed) and g0.3-q4 +326, −476 and +654 (mean +168). On 30 panoramas the simulated human's mistakes and skips dominate: one seed cannot rank close settings.
- **Recommendation:** keep the defaults, `min_gain = 0.0526` (`questions.BREAK_EVEN`) and `max_questions = 4`. Both sets put it first. On PT, the set preferred when they disagree, it is the one of the two best settings that gains on all three seeds (the others ran with one seed). A setting of 4 beats 2 at every `min_gain` on both sets. The default asks a median of 4 questions per panorama (at most 13, cells included), so about 24 for six panoramas. The PT evidence is thin: 30 panoramas, with differences close to the seed noise.
- **Side notes, not results:** before the 00:58 fix (unverified Commons hits at reliability 0.2) and before T42/T80, the same grid with seed 2026 favoured the highest gate, g0.5-q4 (+973 combined), and q4 over q2 (`runs/eval/sweep-*-prefix`). Runs on the 00:58 code were stopped when T42 and T80 landed (`runs/eval/sweep-*-preT42T80*`, incomplete). With the regression, the autonomous own-category mean on val_first100 was 661, against 1,298 now.

**Containment of answers** (`tools/eval_assisted.py containment`, no reference read): does the option the team picked hold the output produced right after the answer?

- **T40 logs** (151 answered questions): 3 violations, all from the soft update (`apply_answer` only scales the other hypotheses):
  - 218 (nominal), q4: "None of these" was answered, yet the next output is option a's own point.
  - 319 (human), q3: "Portugal (residual: Lisbon area)" was picked by mistake (a disc with a 720 m radius), and the next output is a GeoCLIP point outside it.
  - 179 (human), q2: "France" was picked by mistake, and the next output stays in Lisbon.
- **T40 earlier answers:** 8 outputs contradict an answer given earlier in the same run. For example, on 066 the q3 answer "Distrito da Guarda" jumps to the coarse "Guarda (PT)" area inside it, which is consistent, but q4's correct "None of these" then sends the output back to an Aveiro photo-bank match outside that district. Two of the 8 (179 and 749, human) are the run recovering from a mistaken "France" answer through a later "Elsewhere". On 095, every output stays inside every chosen option. There, the Nouvelle-Aquitaine answer (85,180 km²) moved the output to another photo-bank camera match inside the region, not to a coarse area hypothesis.
- **T79 final-code logs** (3,244 answered questions; `runs/eval/sweep-final-containment.txt`): 84 violations (2.6%).
  - Kinds: place discs 47, named zones 24, "Outside this area" 10, "None of these" 3.
  - When a T42 cell was picked, the next output was always inside it.
  - 508 outputs contradict an earlier answer: partly the designed "Outside" recovery path, and partly the same soft update compounding over answers.

- **Fit check after the 01:38:51 re-selection fix** (code 4eabd43ceec6; default gate g0.0526-q4, seed 2026; `runs/eval/fitcheck-containment-*.txt`):
  - Direct violations: 4 of 839 answers under the nominal oracle and 2 of 470 under the simulated human.
  - Of those, 3 were flagged as unrestricted choices. The other 3 are hypotheses outside PT/ES/FR (a Commons road hit in Sicily, a GeoCLIP point near Geneva) accepted as "France", because `RegionQuestion.option_for` maps them to the nearest country.
  - Contradictions of an earlier answer, under the nominal oracle: 24, of which 11 unrestricted and 13 from T42 cell routes not clipped to earlier answers.
  - Under the simulated human: 122, of which 35 unrestricted and 79 involving one of its own wrong answers.
  - Own-category means, side note only: simulated human 2,678 combined (2,681 before the fix); nominal oracle 4,888 (30.4% of the maximum).

- **Cap 4 against 6** (min_gain 0.0526, val_130; `pipeline.py` 02:02:30, `cells.py` 01:57:05, code c57d4670f649; `runs/eval/sweep130-cap-tables.md`):
  - Simulated human, seed 2026: paired gain over autonomous +596 at cap 4 and +761 at cap 6 (own-category mean 2,563 and 2,728; 16.0% and 17.0% of the maximum). On ES/FR +606 against +815; on PT +562 against +580.
  - PT seeds 2027 and 2028: +145 against +480, and +982 against +1,044. Cap 6 is ahead on all three PT seeds.
  - Cap 6 asked a 5th place or zone question on 50 of 130 panoramas and a 6th on 43. Where the 5th was asked, cap 6 scored 430 points more than cap 4 on average, with 22 panoramas better and 22 worse.
  - Nominal oracle: own-category mean 5,036 at cap 4 and 5,220 at cap 6. Cap 6 gains on ES/FR (+271) but loses on PT (−109), where only 5 panoramas reached a 5th question.
  - Recommendation: 6. It is ahead in every simulated-human run; the nominal PT loss rests on 5 panoramas.
  - Containment: no real violation of the chosen option. Besides "nothing fits every answer" cases and the simulated human's own wrong answers, the contradictions of earlier answers are:
    - 24 where a zone answer re-selects into cells that an earlier "Outside this area" cell answer excluded (6 panoramas): re-selection does not yet count earlier cell answers.
    - 4 open cell-route cases (2 coastal panoramas whose references are on land).
    - No pier or offshore cases, and no sea points.

- **Gap-fix confirmation** (val_130, cap 6; `pipeline.py` 02:12:32, `cells.py` and `zones.py` 02:15:51, code b9a942028ed8; `pipeline.py` changed again at 02:21:44, mid-run, and was not reloaded; `runs/eval/sweep130-gapfix-containment-*.txt`):
  - No real violations.
  - No earlier-cell-answer gap (6 before the fix, under the nominal oracle), no sub-cell "Outside" contradicting its parent, and no sea, pier or land-band points.
  - What remains: "nothing fits every answer" (19 under the nominal oracle, 84 under the simulated human) and the simulated human's own wrong answers (30).
  - The classifier now treats any wrong answer up to the current one as the cause of what follows, from `oracle.json`. With that rule, the cap check's 4 open cell-route cases (_015, _017) are the simulated human's own wrong answers.
  - Own-category means, side note only: nominal oracle 5,128 and simulated human 2,691 (5,220 and 2,728 in the cap check).

- **Question-loop constants, 2×2** (val_130, cap 6, min_gain 0.0526; constants set at runtime in the eval process; `runs/eval/sweep130-const-tables-*.md`):
  - Grid: `MAX_PLACE_MISSES` {2, 99} × `ROUTE_URBAN_REESTIMATE` {True, False}.
  - Code: the nominal-oracle and seed-2026 legs ran on `pipeline.py` 02:24:28 (51ad74c82e17), and PT seeds 2027 and 2028 together on 02:36:41 (261533abc483).
  - The warm-up leg was skipped: no warm-up panorama has `landmarks.json` in the cache, and computing it would need the GPU before 04:00.
  - The default (2, True) wins with the nominal oracle on every set. Its combined own-category mean is 5,373 (33.5%); against it, (2, False) is −58, (99, True) −245 and (99, False) −283, with PT at −142, −230 and −338.
  - Simulated human, seed 2026, combined: (2, False) +51, (99, True) −1 and (99, False) +49. On PT: −7, −145 and −152.
  - PT seeds 2027 and 2028: (2, False) −54 and −108; (99, True) 0 and +60; (99, False) −54 and −48.
  - How often each mechanism fired: two place misses in a row in 51 of 130 nominal runs and 40 of 130 seed-2026 runs, with a place or zone question always following. P(urban) moved at 85 of 91 and 80 of 87 route starts with re-estimation on, and never with it off.
  - Containment: no real violations. The rest are "nothing fits every answer" and the simulated human's own wrong answers.
  - Recommendation: keep both defaults, `MAX_PLACE_MISSES = 2` and `ROUTE_URBAN_REESTIMATE = True`. Turning re-estimation off loses on PT in all four readings, and turning the place-miss cap off loses with the nominal oracle on every set.
- **Secondary check on the current code** (`pipeline.py` 02:42:10, code 6a3cf2da906a, defaults; `runs/eval/sweep130-secondary-0240-tables.md`):
  - Against the gap-fix run, the nominal oracle reaches 5,807 (36.2%), up from 5,128 (31.9%): +679, with ES/FR +458 and PT +1,416 (PT now 52.3% of the maximum, median 93 m).
  - The simulated human reaches 2,693 (16.8%), up from 2,691: +2, with ES/FR −100 and PT +341. No regression overall.
  - Containment: no real violations. "Nothing fits every answer" falls from 19 to 4 under the nominal oracle and from 84 to 40 under the simulated human; the simulated human's own wrong answers stay at 30.

- **Skip retries and answer slack** (val_130, cap 6, defaults otherwise; switches set at runtime; the drivers loaded `pipeline.py` 02:54:27; `runs/eval/sweep130-slack-tables.md`):
  - Settings: S0 is everything off (it reproduces the 02:42:10 check exactly); S1 one cell retry and one main retry; S2 two of each; S3 is S1 plus slack 1; S4 slack 1 alone.
  - Simulated human, seed 2026, paired against S0: S1 +736, S2 +1,106, S3 +735, S4 +10. On PT: +1,402, +1,723, +1,408 and +116.
  - PT seeds 2027 and 2028: S1 +1,170 and +603, S2 +1,386 and +1,020, S3 +1,148 and +701, S4 −66 and +19.
  - Sticky skips, the conservative reading: an identical re-asked question is skipped again with probability 0.75 (`oracle.py`, `sticky_skip`). With them, S1 is −19 and S2 +248 (PT +176).
  - Nominal oracle: S3 and S4 are both −45, so slack costs a little when every answer is right.
  - How often each path fired, simulated human seed 2026: cell retries 53 times in 52 runs (S1) and 89 times in 51 runs (S2); main retries 57 in 57 runs and 76 in 57 runs; slack 78 outputs in 36 runs (S3) and 54 in 26 runs (S4).
  - Containment: no real violations; every case is "nothing fits every answer" (slack outputs included, which by design break one answer) or the simulated human's own wrong answer.
  - Recommendation: `ANSWER_SLACK = 0`. Retries help only under the independent-skip simulator, which re-asks into an 80% answer rate. If retries are adopted, take S2 (2 and 2) and expect about +250 points (+1.6 pt) with a real team, not +1,100. It also adds about 1.3 skipped prompts per panorama. A Gate C pass under D3 that rests on the independent simulator would overstate retries.

- **Wrong-answer recovery** (val_130, cap 6, `RECOVERY` True against False set at runtime, `RECOVERY_SHARE` 0.15, retries 2/2, slack 0; `pipeline.py` 03:28:12, code 53f7db4215a1, one version throughout; `runs/eval/sweep130-recov-tables.md`):
  - Simulated human with sticky skips, seed 2026: +247 combined (ES/FR +125, PT +654); urban within 100 m 14 → 15 of 79.
  - PT seeds 2027 and 2028: −331 and −98.
  - With sticky mistakes as well, the conservative reading (`oracle.py` `sticky_mistake` 0.5): +118 combined (PT +255); PT seeds −72 and −98.
  - Nominal oracle: −266 (ES/FR −287, PT −196); urban within 100 m 52 → 49 of 79.
  - Overrides: they correct a simulated wrong answer about as often as they drop a correct one. At seed 2026 there were 39 overrides, 20 correcting a wrong answer and 19 dropping a correct one. All 31 overrides under the nominal oracle dropped a correct answer, and over every run 87 overrides dropped a correct answer against 50 corrections. The trigger, nothing fitting every answer, also fires when every answer is right but no candidate lies in the answered area.
  - Containment, consistent with every answer not overridden: no real violations. The overridden answers are counted apart and the overrides of correct answers flagged (`*-containment.txt`).
  - Reading: the val check does not support recovery as built (D2: the warm-up stays primary, where the coordinator measured +2.0 pt with sticky skips and −0.35 pt with the oracle). The trigger would need to tell a wrong answer from candidates that miss the answered area.

- **Recovery with the refined trigger** (`pipeline.py` 03:45:29, code 3af4250c4d82, one version; `RECOVERY` True against False set at runtime; `runs/eval/sweep130-recov2-tables.md`):
  - Simulated human with sticky skips, seed 2026: +182 combined (ES/FR +143, PT +312); urban within 100 m 14/79 either way.
  - PT seeds 2027 and 2028: −158 and −134, so the PT mean over three seeds is about +7.
  - With sticky mistakes as well: +90 combined (ES/FR +129, PT −39).
  - Nominal oracle: 0 overrides, so the trigger no longer drops correct answers, yet −125 combined (ES/FR −110, PT −174) and urban 52 → 50 of 79. That loss comes from re-offering contradicting hypotheses in later questions, not from overrides.
  - Overrides at seed 2026: 25, of which 16 corrected a wrong answer and 9 dropped a correct one (20 and 19 with the old trigger). With sticky mistakes: 14 and 5.
  - Containment: no real violations; the overrides of correct answers are flagged in `*recov2*-containment.txt`.
  - Reading: val does not agree. The combined human gain rests on seed 2026, PT is negative on the other two seeds and under sticky mistakes, and the nominal oracle loses. Keep `RECOVERY` off.

- **Recovery with the evidence-gated pool** (`RECOVERY_EVIDENCE` True; `RECOVERY` True against False set at runtime; `runs/eval/sweep130-recov3-tables.md`):
  - Code: the processes loaded `pipeline.py` 04:12:19 (code 59f31c491d63) at 04:17:50. That is before the VLM default change at 04:18:40 and 04:19:30, so every VLM result came from the Qwen cache and no plugin VLM cache file exists.
  - Simulated human with sticky skips, seed 2026: −17 combined (ES/FR +43, PT −217); urban within 100 m 14 → 13 of 79.
  - PT seeds 2027 and 2028: −353 and −231.
  - Nominal oracle: −47 (ES/FR 0, PT −204, 3 panoramas worse and none better), with 0 overrides; urban 52 → 51.
  - Overrides at seed 2026: 11 corrected a wrong answer and 9 dropped a correct one (PT seeds: 4 and 3, 2 and 1).
  - Questions offering an option that contradicts an earlier answer: 202 with recovery on against 163 off at seed 2026; under the nominal oracle, 47 against 44.
  - Containment: no real violations; the overrides of correct answers are flagged in `*recov3*-containment.txt`.
  - Against the coordinator's rule, both conditions fail: the nominal oracle shows a loss, and the simulated human is worse. Keep `RECOVERY` off.
  - Every later evaluation process runs with `PANOLOC_VLM=local`.

D1 debt: no unit tests for the sweep, summary and containment code in `tools/eval_assisted.py` (one smoke test, then the full suite: 382 tests pass); usage lines only; one seed for val_first100; `max_questions` above 4 and the cell budget were not swept.

## Changes

- **2026-10-11 02:39 WEST, who can pass Gate C (decision D3, ROADMAP.md):** asked "Can the script team's run pass Gate C?", the user answered "Yes".
  - Runs of the retained configuration answered by the simulated human can now pass Gate C. That is `panoloc.oracle`'s human mode: 70% right, 10% wrong, 20% skipped, seeded per panorama.
  - Gate D is unchanged: its rehearsal still needs the real team answering six unfamiliar panoramas (T55).
  - Nominal-oracle and autonomous runs still cannot pass and stay reported only.
  - Timing: the first realistic batch, `runs/app/batch-20261011-023634-human` (started 02:36), was aborted unscored after 4 panoramas when `pipeline.py` changed at 02:36:41; it is marked `ABORTED.txt`. The batch that counts is `runs/app/batch-20261011-024036-human`, started at 02:40:36 on `pipeline.py` 02:36:41, after the decision, so it falls under the new rule. The rule does not apply to any run scored before the decision (PLAN.md 4.8: no retrospective passes).
  - D2's reading on nominal distances applies to these runs as well.
- **2026-10-11 02:30 WEST, how the targets are read (decision D2, ROADMAP.md):** the user judged the organiser-checked warm-up references good enough as ground truth. A change is now judged on the warm-up by plain Haversine distance from each output coordinate to its reference, and by the challenge score at that distance. Both targets above are read on these nominal distances: at least 9 of 17 urban references within 100 m (`d_ref <= 100 m`), and a mean score of at least 30% of the maximum. The robust and conservative readings (`d_ref + radius`) stay as secondary columns. D2 doesn't change who can pass: as frozen above, only realistic human-assisted runs of the retained configuration can pass, and autonomous, oracle and simulated-human runs are only reported against the targets. Also unchanged:
  - The references stay evaluation-only and never reach the agent.
  - Numeric weights are still fitted on external validation (T39), which becomes the secondary check.
  - Fixes stay generic.

  Diagnosing a warm-up failure by comparing its coordinates and answers with its reference is now allowed, inside evaluation code. No row above passes on either reading: none reaches the 30% mean.
- **2026-10-11 01:13 WEST, reference correction from the organisers (T81):** RULES.md, "Organiser feedback on our warm-up references". The coordinator applied it in `panoloc/evaluate.py`, as an overlay read from `Data/warmup_feedback.json` (sha256 9e040870b5de...); `Data/warmup_locations.json` and its frozen hash are unchanged. For the 17 checked references, the error bound is now the organisers' distance: 10 m where they found under 10 m, and 18, 14, 30 and 24 m for 095, 141, 681 and 749. 141 and 681 (urban) and 749 (non-urban) now have category source "official"; the categories themselves did not change. 059, 064 and 066 remain team estimates, and 059 remains the 60 km diagnostic reference. This corrects the references; it does not change the targets. Every result above the T81 rows was scored with the team's 5 to 12 m radii and inferred categories. The rows marked "organiser-checked references" re-score the same runs, and no earlier fail becomes a pass (PLAN.md 4.8).
- **2026-10-11 00:12 WEST, operator policy, clarification:** T32's zone options (`questions.ZoneOption`) carry an outline simplified for display and a `contains_fn`, the zone index's own test (unsimplified leaves, 1 km snap). The oracle decides with `contains_fn`, not the outline. No run with named zones had been scored.
- **2026-10-10 22:58 WEST, operator policy, clarification:** T32's named zones (`panoloc/zones.py`) snap a point outside every zone, such as a pier or a beach, to the zone within 1 km. For zone options, a reference outside every drawn region now goes to the region option the question's own `option_for` gives before the "Outside" option. Boxes and place discs answer as before. No run with named zones had been scored.
