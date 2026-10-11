# Panorama localisation plan

**Updated:** 2026-10-10.
**Status:** the working plan (v2). It replaced the first plan on Saturday 2026-10-10; section 9 records what changed and why.
**Related:** [RULES.md](RULES.md), [MODEL_DECISIONS.md](MODEL_DECISIONS.md), [CLAUDE.md](CLAUDE.md).

Build a complete, local panorama localisation agent before expanding its model stack. Keep mini-PIGEON as a core preparation task, use several plausible candidates, and give precise coordinate generation an explicit place in the pipeline.

Preparation builds reusable assets from independent external data. Each challenge panorama then runs with its own evidence, conversation, questions and temporary gallery. Warm-up validation uses [Data/warmup_locations.json](Data/warmup_locations.json) as the canonical coordinate baseline, including its reported error radii and annotation provenance.

## 1. Goal and strategy

For each panorama, return up to 10 `(lat, lng)` guesses. The score is the sum over entries:

```text
entry_score = 1000 × 0.95^(rank - 1) × theta(distance) × penalties × special_factor

distance < 10 m: use distance = 0
Urban:     theta(distance) = 2 / (1 + distance / 100)
non-Urban: theta(distance) = 2 / (1 + distance / 10000)
special_factor = 3 for the Special One, otherwise 1
```

Penalties apply when the relevant interaction occurred before that candidate was produced. Record a penalty snapshot for every output; do not assume that earlier outputs retain full value without organiser confirmation.

### 1.1 Choose coordinates by expected points

Select the coordinate that maximises expected score under the current location hypotheses. The single most likely location is not always the coordinate with the best expected distance score.

Given hypothesis coordinates `y_j` with normalised weights `p_j`, evaluate:

```text
utility(x, scale) = sum_j p_j × 2 / (1 + effective_distance(x, y_j) / scale)

scale = 100 for Urban; 10000 for non-Urban
effective_distance = 0 below 10 m, otherwise Haversine distance in metres
```

Hypothesis weights are model estimates, not verified probabilities of correctness. Evaluate plausible camera positions as well as coarse region centres; a centroid between distant alternatives may represent an implausible location.

**Repeat the coordinate with the highest expected score in all 10 slots.** Each slot has a positive rank weight and the same distance objective. The stated rules offer no diversity bonus, so nearly tied candidates do not justify spreading guesses to increase expected points. Keep distinct alternatives for questions and internal reasoning.

### 1.2 Precision determines priorities

| Distance error | Urban score as % of maximum | non-Urban score as % of maximum |
|---|---:|---:|
| 25 m | 80.0% | 99.8% |
| 100 m | 50.0% | 99.0% |
| 1 km | 9.1% | 90.9% |
| 5 km | 2.0% | 66.7% |
| 10 km | 1.0% | 50.0% |

Urban cases need a credible route from region or landmark identity to the camera position. A 2 km grid is useful for narrowing the search, but its cell centres cannot supply reliable street-level answers. Non-urban cases can retain substantial points with a few kilometres of error.

Ten exact guesses yield approximately 16,050.52 points before interaction penalties, or 48,151.57 for the Special One.

### 1.3 Missing Urban labels remain explicit uncertainty

The PDF says panoramas will have Urban/non-Urban labels, but the supplied warm-up files have none. Do not assume a category is available or that a visual approximation matches the organisers' definition.

- Store the category and its source: `official`, `inferred` or `unknown`.
- While unknown, calculate both scoring scenarios and record whether they favour different coordinates.
- An inferred category may guide effort, but remains an assumption in evaluation results.
- If using a weighted combination of the two scenarios for selection, record the assumed Urban probability and check sensitivity to it. It is not a verified label.

For warm-up validation, use the JSON baseline's `urban` field as the default category estimate and report both score scenarios as a sensitivity check. This provides a usable benchmark while preserving the distinction between our annotations and official category labels.

## 2. Rules and uncertainty that shape the code

The organiser rules and partner clarifications in [RULES.md](RULES.md) govern interactions. Open weights, local execution and no paid APIs are also project constraints from the repository context.

- Only text and multiple-choice clicks from the team go into the agent, in addition to its assigned panorama. Do not feed it screenshots, galleries or photographs collected by humans during the run.
- Log every interaction in JSON. Typed cues are limited to 1000 characters and may not directly or indirectly identify a place.
- Each panorama starts with a new conversation, empty evidence, independent candidates and questions, and its own temporary downloads. Do not infer one location from another panorama or from capture-order patterns.
- Frozen assets prepared from independent external data can be reused: weights, reference photos, classifier, name index and geographic metadata.
- Warm-up/trial panoramas, estimated challenge locations and evaluation reports never enter the retrieval bank, classifier training, feature table or preloaded runtime knowledge. The current run receives only its assigned panorama and allowed interactions. Keep evaluation reports and other panorama logs out of its prompts.
- A skipped question causes no belief update and no penalty. Do not interpret silence, delay or a skip as an answer. Other evidence arriving independently must be logged as its own event.
- Questions have at most four options, generated by the agent. If needed, use three alternatives plus an explicit "none of these", or four options that together cover the whole remaining area (section 3.4).
- The agent resolves coordinates itself. Human conversion of an agent's place-name answer incurs the stated ×0.5 penalty.

**True challenge locations are never revealed.** The supplied warm-up JSON is our best available coordinate baseline and is close enough, with its reported error estimates, to support useful localisation validation. Report errors and scores against that baseline, together with sensitivity to `error_radius_m`; do not label them as organiser-measured results. Place identity, camera position and Urban category retain their recorded or inferred provenance.

Use external validation data for training choices and fusion calibration. Use warm-up and trial panoramas for evaluation, plausibility review and operational rehearsal, consistent with the repository's rule interpretation.

## 3. Runtime pipeline for each panorama

**Core** means part of the intended final pipeline. The first working baseline may run before bank preparation finishes. **Conditional** means enable after checking benefit and prerequisites. **Optional** means lower priority than completing and validating the core.

| Step | Component | Priority | Output and purpose |
|---|---|---|---|
| 0 | Input validation and filename parsing | Core | Image identity, timestamp with uncertainty, official category if supplied; fresh run state |
| 1 | `py360convert` perspective views | Core | Eight overlapping horizontal views, sky and ground; camera-relative yaw/pitch and photographer mask |
| 2 | PP-OCRv6, with tested fallback | Core | Raw text, boxes, confidence and full-resolution rereads; name, postcode and phone candidates |
| 3 | One working VLM | Core | Compact scene checklist with `not_visible`, landmark hypotheses and selective text verification |
| 4 | PE-Core embeddings + kNN + mini-PIGEON | Core once prepared | Similar reference photos, candidate GPS and several plausible regions |
| 5 | GeoCLIP or PLONK | Validate early | Additional candidate locations; start with one working model and compare the second later |
| 6 | Local name index and coordinate resolution | Core | Candidate landmarks, addresses and plausible camera positions with source identifiers |
| 7 | Conservative fusion in code | Core | Ranked hypotheses, supporting evidence, contradictions and estimated uncertainty |
| 8 | Agent-generated multiple-choice questions | Core | Human-answerable distinctions between candidates; unchanged beliefs on skip |
| 9 | MegaLoc + ALIKED/LightGlue | Conditional, high urban priority | Retrieve and geometrically check candidate places against prepared external imagery |
| 10 | Score-aware coordinate selection and output | Core | Selected coordinate repeated up to 10 times, penalty snapshots and JSON log |
| Extra | YOLOE, then selective SAM 3 checks | Conditional / optional | Useful detail crops if they improve OCR or localisation enough to justify their cost |
| Extra | EoMT segmentation, grid enrichment, solar geometry, feature likelihood table, separate reasoning model | Optional | Add only after evidence of a useful contribution |

Steps 6–9 may repeat when new evidence or an answered question changes the candidates. Precise matching is useful beyond strictly urban scenes when the expected gain justifies it.

### 3.1 Perception and model selection

Use the locally working VLM first. Compare Qwen3.5-9B with the installed Gemma 4 12B on representative crops before switching. Published general benchmarks do not establish which model best recognises these scenes.

Preserve the original panorama and use full-resolution crops for small text. The bottom 15–20% mask is a starting heuristic for the photographer, not a reason to discard useful ground information blindly. Track masked areas when deriving scene proportions.

OCR should retain raw readings and competing interpretations. The VLM checks difficult crops but does not supply invented digits or unverified coordinates. Deduplicate the same sign appearing in overlapping views.

Language, vehicle plates and architecture are usually soft evidence: visitors, imported vehicles and multilingual signs are possible. A place name on an illustration, advertisement or directional sign need not name the camera's current location. Prefer independently supported names and visual context over a single regex match.

The heliport/py3langid/CLD2 ensemble remains a candidate CPU addition. Start with the tested path that fits the schedule; extra voters must improve results on noisy short OCR strings.

Keep gpt-oss-20b as an optional conflict-checking experiment. Validate JSON and retry with the resident VLM before loading another reasoning model. The reported swaps under RAM pressure can consume minutes, so a second model must demonstrate a useful contribution within the full memory and time budget.

### 3.2 Fusion and candidate retention

Start with a small weighted combination calibrated on external validation cases. Attach regional support, retrieval similarity and verified-match evidence to common candidate IDs, combine them, then normalise the resulting candidate weights. Retain several geographically distinct alternatives. Keep a global retrieval fallback so a mistaken region prediction cannot permanently remove the correct candidate.

Start panorama aggregation with an average of per-view classifier outputs, rather than a product that assumes independent views. Retrieve neighbours per view and merge repeated reference locations/sequences. Compare aggregation choices on external validation data.

Evidence should retain its source crop, model, confidence, reference coordinates and links to supporting observations. Separate observed text from interpretations and estimated positions.

Do not multiply every output as an independent probability:

- PE-Core kNN, mini-PIGEON and PE-Core feature prompts share an encoder and training/reference data.
- Overlapping views and repeated detections often contain the same clue.
- Different geolocation models still share scene information and can make correlated mistakes.
- Cosine similarity and model confidence are not automatically calibrated geographic probabilities.

Group related evidence and limit its combined influence. Give verified specific matches more weight than general scene resemblance. Use soft geographic checks unless an exclusion is well supported. A naive product of experts can become confidently wrong.

### 3.3 Precise coordinate generation

Coordinate resolution is a required capability, even if exact localisation is not possible for every image.

**Type coordinate sources before using them.** Every geographic candidate must declare whether its source coordinate represents a `camera`, a `landmark` or an `area`, with the source ID, coordinate system and any supplied position accuracy. Use WGS84 for output. Missing accuracy remains unknown; it must not become a zero-metre error estimate. A Wikidata landmark point, an OSM shop/building point and a postcode centroid are not reference-camera GPS.

Use the following branches in the first implementation:

| Available evidence | Coordinate method | What establishes precision |
|---|---|---|
| Verified scene match to a reference photo with camera GPS | Propose that reference's camera coordinate as an approximate anchor; compare it with other supported camera candidates using expected score | Reference GPS accuracy and evidence that the query was taken near that viewpoint; account for possible camera displacement |
| Recognised landmark/address, but only object or area coordinates | Resolve its footprint and surroundings, generate geographic cells, and refine through agent-generated zone questions | The selected cell's extent and representative point; recognition alone establishes the place, not the camera position |
| Reliable geographic region, without a precise reference or confirmed place | Keep the broader scope, use the same cell questions if answerable, otherwise choose a supported coordinate by expected score | The remaining geographic uncertainty; retain a coarse result when refinement is unsupported |

**Reference-camera branch.** Retrieve nearby prepared imagery with MegaLoc where validated. After ALIKED/LightGlue matching, apply geometric verification such as RANSAC appropriate to the perspective crops; use externally validated checks on inlier support and spatial distribution. Repeated façade textures or a shared building identity alone are insufficient. LightGlue outputs corresponding image keypoints, so geographic coordinates must come from reference metadata or a separate localisation method. [LightGlue documentation](https://github.com/cvg/LightGlue)

A valid match may still be photographed from another side of a square or a distant viewpoint. Include source GPS error and estimated viewpoint displacement in the anchor's position uncertainty. If displacement cannot be bounded, record unknown uncertainty and treat the GPS as an approximate candidate, then refine through cells if useful. Do not equate a good image match with a sub-10 m camera fix, or average incompatible reference viewpoints.

**Landmark and cell branch.** Search the local name/place index using OCR and independently supported landmark hypotheses; retain ambiguous matches. Use a sourced footprint or extent when available to define an initial search scope, while preserving an explicit recovery option outside it. For a point-only entry, attach an externally chosen search extent and record that assumption rather than treating the point as the camera. Include plausible streets, squares, paths, accessible grounds and off-road positions; road proximity remains a soft preference.

Partition the selected scope into up to four disjoint cells whose union covers it, following section 3.4. Generate boundaries and representative points in code using metre-based geometry, then transform to WGS84. Every point must lie inside its cell. Compute a conservative maximum distance from the output point to any location in that cell; cell width alone is not a radius. Show human-readable boundaries and map links so the team can select an agent-generated option. A click selects the cell, and the agent calculates its coordinate; teammates do not supply or convert coordinates.

For Urban or unknown-category precision refinement, target a terminal cell with a maximum point-to-cell distance of **≤25 m**. For a known non-Urban case, **≤1 km** is a useful initial target. These are geometric targets conditional on selecting the correct cell, not guarantees that the location is in it. Stop earlier if further questions do not justify their penalty or time. Evaluate supported points using section 1.1, recompute the bound for the actual selected point, and log that bound and the category assumption before repeating the coordinate in the final list. The bound must cover the cell's full area, including map/projection tolerances.

**Fallback and output contract.** If no precise match or reliable cell answer exists, return the best supported coordinate with its broader or unknown uncertainty. Record `output_method` (`reference_camera`, `geographic_cell` or `coarse_candidate`), source IDs, the source coordinate role, `position_uncertainty_m` (nullable), and whether that uncertainty comes from a geometric bound, a source estimate, an estimated offset or remains unknown. Do not label an output precise solely because it has many decimal places.

Metric camera-pose estimation or triangulation is a later enhancement requiring suitable camera geometry and geographic anchoring, such as a prepared, georeferenced 3D model. Matching two images alone does not supply an absolute camera GPS position. Keep this enhancement outside the first implementation's prerequisites. [Hierarchical localisation pipeline](https://github.com/cvg/Hierarchical-Localization)

Prepare an offline gallery. Runtime Mapillary or OSM fetches remain disabled until the organisers clarify whether they are allowed; online retrieval then becomes an additional route with a timeout and offline fallback. Keep each runtime gallery isolated to its panorama.

Gallery coverage is essential: MegaLoc retrieves from supplied imagery, and cannot recover a missing reference simply because its benchmark recall is high. Its official documentation recommends perspective crops for panoramas. [MegaLoc documentation](https://github.com/gmberton/MegaLoc)

Do not force every answer onto a road. The challenge includes open fields and other off-road scenes. Road proximity can be a prior, not a hard output constraint.

### 3.4 Questions and stopping

Choose questions from differences between current candidates, then let the VLM phrase them. Use observable features or geographic alternatives that the team can check on other equipment. Broad questions that do not change the eventual coordinate have little value.

For one answered question, ignoring time and assuming the same penalty history for the compared final outputs:

```text
0.95 × expected_utility_after > expected_utility_before
expected improvement must exceed 1 / 0.95 - 1 ≈ 5.26%
```

Account for possible wrong answers. This is a planning threshold, not a live guarantee: the location posterior and expected answer quality are themselves uncertain. Stop asking when likely improvement is small or the time budget is exhausted. The same logic gives a 25% break-even improvement for a ×0.8 typed cue, subject to its stricter content restrictions.

The Special One's multiplier increases the value of useful refinement and time allocation; it does not change the relative 5.26% question threshold.

**Questions can be an efficient route to precision when a teammate identifies the place.** Teammates may use tools on other equipment, so a finder using Google Lens or Street View may locate it before the agent does. The question loop must let the team select agent-generated geographic alternatives even when the initial place candidates miss the location.

The following urban examples assume ten repeated guesses, no other penalties and an ordinary panorama. They illustrate the payoff of useful questions rather than predicting what every human answer achieves:

| Answered questions | Final distance error | Score | Fraction of unpenalised exact maximum |
|---:|---:|---:|---:|
| 1 | Below 10 m | 15,248.00 | 95.0% |
| 1 | 20 m | 12,706.66 | 79.2% |
| 0 | 1.5 km | 1,003.16 | 6.25% |
| 15 | Below 10 m | 7,436.07 | 46.3% |

**Zone fallback.** Place options may omit the true location. An explicit "none of these" answer can reveal that gap; a skip cannot. Use a recovery path based on agent-generated zones:

1. Start from the full allowed geography, with some support outside the current retrieval/model hits. Offer up to four mutually exclusive options whose union covers the stated search scope. A country question can have three options. Four chosen districts do not cover Portugal: group all districts into at most four clearly named sets or use geographic partitions.
2. Prefer similar posterior mass when practical, but prioritise understandable names and boundaries. Show which places or areas belong to each option. Candidate confidence alone must not remove low-weight areas from coverage.
3. Refine through administrative areas where useful, then subdivide the selected geometry into spatial cells. A list of four street-level points is not an exhaustive geographic partition; the finer search must also cover unnamed streets, paths and open ground. Cell representatives supply coordinates, with uncertainty reflecting the cell extent.
4. Preserve parent scopes and support recovery after an explicit answer or independent new evidence contradicts an earlier choice. Where necessary, use three subzones plus an outside-parent option covering the rest of the allowed area. Earlier answered questions keep their penalties even if a choice is later corrected.
5. Do not expand a search area, alter beliefs or infer "outside the candidates" because a question was skipped. Question rotation may follow a predefined schedule without extracting location information from silence.

The PDF permits geographic-zone questions. Show the organisers concrete grouped-region and spatial-cell examples when checking the interaction format (section 8).

**Checkable options.** Build the first question loop with names, relevant coordinates, Google Maps/Street View links and supporting evidence. Zone options need their boundary or extent and a clearly labelled representative point; that point is not a proposed camera position. Mark unavailable Street View coverage rather than treating a nearby view as the exact target.

**Simulated operator.** Evaluate both an ideal operator and more realistic answer behaviour. The evaluator alone reads the current panorama's reference from the JSON baseline or external validation data. The agent receives only the selected option or a skip; it never receives raw reference coordinates, heading, place text or sibling annotations.

| Evaluation mode | Answer policy | Interpretation |
|---|---|---|
| Nominal oracle | Select the correct option using the reference point and explicit place/zone semantics; choose "none of these" or an outside option when appropriate | Optimistic assisted result against the supplied baseline |
| Radius-aware oracle | Answer only when the reference's reported uncertainty area supports a single option; skip genuinely ambiguous boundaries or unsupported place choices | Sensitivity to coordinate uncertainty |
| Human rehearsal / simulation | Include unanswered, uncertain and wrong answers; record the actual or assumed mistake/availability policy | Operational or scenario performance, not guaranteed oracle performance |

For point choices, define the matching tolerance in the evaluation report instead of assuming a coordinate must exactly equal the reference. Report answered and skipped questions separately, time spent, final baseline score and uncertainty sensitivity. An oracle result is not a forecast of actual human performance.

### 3.5 Reliability, logging and budget

Target **≤150 seconds of initial automated processing** and **≤14 GB peak GPU memory** on the actual laptop. These are acceptance targets, not measured performance. Record subsequent refinement time separately and include it in total time per panorama.

Measure cold loading, image decoding, OCR, VLM requests, matching and downloads. Compute-only estimates do not establish the complete wall-clock budget. Stage model loading where necessary instead of assuming the whole proposed stack fits simultaneously.

Give optional stages deadlines. A failed model or unavailable network must leave a usable candidate list and log. Produce an initial coordinate result before spending the remaining time on questions and refinement. Freeze dependency versions after the rehearsal.

The log should capture the assigned image and run identity, model/data versions, evidence, candidates, uncertainty source, every question and response/skip, typed cues, penalty counters and per-output snapshots, final coordinates, timings, failures and fallback decisions. The exact organiser schema is still pending.

## 4. Preparation before Sunday

### 4.1 Photo bank and embeddings

Downloaded with `tools/fetch_osv5m.sh` into `Data/osv5m/` (4.6 GB) and verified on Saturday at 17:10: every file below is a complete JPEG, and every image has a metadata row with its GPS and region.

| Data | Images | Purpose |
|---|---:|---|
| PT/ES/FR official test split | 5,206 | External final evaluation; never reference imagery or classifier training |
| Portugal training photos | 51,551 | Source pool for reference bank and classifier training |
| Mainland Spain and France training sample, 25k each, seed 0 | 50,000 | Source pool for reference bank and classifier training |

The training-image source pool is **101,551 images**. The full PT/ES/FR dataset described elsewhere is larger; it is not the actual selected bank. Usable bank counts may be smaller after validation holdouts, corrupt files and duplicates are removed.

Found while verifying, to handle when declaring the partitions:

- **The Spain/France metadata has no `sequence` column**, only id, lat, lon, country, region and land cover. Group Spain/France images by spatial blocks of about 10 km instead; Portugal has real sequence IDs (13,407 sequences).
- **12% of the Portugal pool is islands:** Madeira has 5,471 images, the largest Portuguese class, and the Azores 565. Weight or separate them so they don't dominate the region prior.
- **France's `region` uses the 22 regions from before 2016.** 85 Spain images are in Ceuta and Melilla in Africa; drop them.

```text
Download and verify independent external images + metadata
                    |
                    v
Declare training, validation, final-test and reference-gallery partitions
                    |
                    v
Compute PE-Core embeddings once, with image IDs and preprocessing version
                    |
                    +--> kNN index and candidate GPS
                    +--> mini-PIGEON training and validation
                    +--> optional feature-scoring experiment
```

Cache embeddings in batches so interrupted preparation can resume. Use faiss-cpu or a tested tensor search; GPU FAISS is unnecessary for the first bank. Verify actual completion, failed downloads and metadata joins before declaring the bank ready.

OSV-5M contains perspective roadside images. Its size does not guarantee nearby references for castles, waterfronts, cafés or fields. Add independently sourced panoramas and landmark imagery where practical, keeping their evaluation partitions separate. Do not mix test panoramas into the bank to improve apparent accuracy.

Measure throughput on a small batch before estimating completion time. Benchmark PE-Core first; full-bank embeddings for several alternative encoders are optional until a representative comparison justifies them.

### 4.2 Mini-PIGEON: retain as core preparation

**Train the small classifier.** With frozen embeddings already needed for kNN and region labels derived from external GPS/metadata, this is a useful experiment with low additional training cost. The benefit remains to be measured.

1. Start with a linear head and well-supported country/region classes. Use PT districts, ES communities and FR regions as the initial granularity, keeping their country identity explicit. These administrative classes have different geographic sizes.
2. Split training and validation by sequence and spatial grouping. Avoid letting many adjacent images from one route dominate either the fit or reported results.
3. Inspect class imbalance and geographic coverage. Sample counts reflect the collection process and do not automatically define challenge-location priors.
4. Calibrate outputs on external validation data and measure top-1 plus top-4 region recall. Keep several regions and test whether they improve downstream candidate coverage and score scenarios.
5. Compare kNN alone, classifier alone and their combination. Treat their evidence as correlated. Preserve some global candidates rather than searching only the classifier's top region.
6. Save weights, class definitions, training IDs, preprocessing, calibration and measured timings. Fine geocells, a shallow MLP or geographic label smoothing are later experiments if the simple head underperforms.

Mini-PIGEON predicts a regional prior; it does not establish an exact camera position. It has higher preparation priority than the hand-designed feature likelihood table.

### 4.3 Feature table: optional after the classifier

Keep the original vegetation, soil, architecture and road-feature ideas as a possible experiment and as useful vocabulary for questions. Building a 40–60-feature likelihood model is not required for the first pipeline.

If implemented:

- Calibrate feature scores against independent labels or fit their relationship to region on validation data. Raw text-image similarity is not `P(feature | region)`.
- Qwen's agreement with PE-Core is a consistency check, not ground truth. Audit a small diverse sample manually; both models can agree and be wrong.
- Model score distributions or use a small supervised combination instead of treating arbitrary thresholds and smoothed counts as reliable probabilities.
- Limit influence from correlated features and from other PE-Core components. Dampening eucalyptus/pine alone does not address dependence between whole models.
- Handle unobserved or masked features as missing evidence, rather than evidence of absence.
- Use only external training data and retain the table only if it adds value beyond mini-PIGEON and kNN.

### 4.4 Geographic assets and rare-feature rules

Build the local OSM name/place index before a rich geographic grid. It provides a direct path from readable names to coordinate candidates. Combine three sources, Portugal first, and keep each entry's source identifier:

- **OSM** (Geofabrik extracts): shops, businesses, streets and places, with `name`, `alt_name` and `wikidata` tags.
- **Wikidata:** landmarks with available names and aliases in pt/es/fr/en, coordinates, type and an optional photo (P18). These resolve the VLM's landmark hypotheses and seed the gallery in section 4.5. Preserve missing fields and ambiguous names rather than assuming every item has an image or every language.
- **GeoNames:** populated places and postcodes for PT, ES and FR, to resolve OCR postcode hits. Postal coordinates narrow an area rather than fix the camera: some are estimated from place names or neighbouring postcodes. [Postal-data documentation](https://download.geonames.org/export/zip/readme.txt)

Add administrative boundaries (district or region, municipality, parish) for the zone questions in section 3.4, for example CAOP for Portugal and OSM boundaries elsewhere. Record the boundary version, read its declared coordinate reference system, and transform to WGS84 for latitude/longitude containment tests and output. Validate that question options cover their stated scope without overlap; geometric cells provide finer coverage where the name index has no suitable entries. [CAOP data access](https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-tematica/caop)

Start geographic filtering with country boundaries, coast distance, coarse urbanity and available elevation. A roughly 2 km PT grid, coarser elsewhere, is a candidate prior; attach precise OSM/reference coordinates separately.

Keep sourced rules for unusual architecture, granaries, chimneys, paving, plate formats, postcodes and phone prefixes. Record the evidence and exceptions rather than applying unconditional exclusions.

Visible tree/building/water pixel shares are not the same quantity as land-cover area fractions in a geographic cell. Camera direction, occlusion and distance change what is visible. Compare these as learned or weak associations, not direct equalities.

Solar geometry is optional and comes after location candidates. `pvlib` requires latitude, longitude and a time convention; it does not recover a location or heading from the filename alone. The warm-up metadata is stripped, and timestamps may mark an interval sequence rather than the precise shot. Unknown yaw, UTC/local time, device-clock error and mistaken sun detections can undermine the constraint. Use candidate-specific consistency checks only when the observation and time are reliable. [pvlib solar-position API](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.solarposition.get_solarposition.html)

### 4.5 Urban reference gallery

Prepare a manageable gallery of independently sourced urban and landmark imagery with GPS and source identifiers. Prioritise useful coverage over collecting more near-duplicate roadside photos. Test the actual MegaLoc weights and matcher on the target GPU before adopting architecture-only throughput estimates.

Start with the Wikidata landmark photos from section 4.4 (Wikimedia Commons thumbnails, Portugal first), embedded with PE-Core, and with MegaLoc once validated. Their GPS marks the landmark, not the camera. Add Panoramax 360° sequences where they exist (no token needed), and Mapillary only if a token is available.

**Download status (Saturday 18:45, task T06).**
- Wikidata: 1.14 M items with coordinates (`Data/wikidata/`).
- Candidate photos (JPEG only; maps, flags and coats of arms dropped): PT 17,287, ES 131,875, FR 248,344.
- The gallery takes **all of Portugal**, then **30,000 each for Spain and France**, ordered by heritage designation, then sitelinks. That is 500 px thumbnails, about 73 KB each, into `Data/gallery/commons/`.
- Wikimedia requires a contact in the User-Agent; we send the GitHub profile URL. The downloader stays within 2 connections and backs off on throttling. Portugal should finish tonight; Spain/France may run into Sunday.

Measure coverage at 100 m, 1 km and 5 km around external test locations, plus whether nearby images show overlapping scene content. For a method that outputs only gallery-photo GPS, nearest-reference distance gives an optimistic coverage ceiling; geometric refinement and name lookup need separate evaluation.

GeoCLIP and PLONK remain candidate generators until local validation supports finer accuracy. PLONK's authors note retrieval's advantage at very fine resolutions. [PLONK paper](https://arxiv.org/html/2412.06781)

For GeoCLIP, begin with reference-photo coordinates and sensible geographic priors that include off-road locations. Its poor global uniform-gallery result does not prove every dense regional or local refinement grid is invalid. A fine grid can explore an already plausible neighbourhood, but cannot create missing locality evidence. [GeoCLIP gallery analysis](https://arxiv.org/html/2309.16020)

GeoCLIP's stock gallery is 100k coordinates sampled from its Flickr training photos. Reported bounding-box counts of 898 around Portugal and 238 around Lisbon suggest useful concentration around photographed destinations; they do not establish street-level accuracy. Record the gallery version and box definitions, and use country polygons for the actual geographic restriction.

Compare three galleries: the stock gallery restricted to the allowed countries, OSV/reference coordinates, and their merged version with independent landmark coordinates. Deduplicate nearby points and check whether collection density changes geographic weights or ranking. Retain the version that works best in validation rather than always replacing or always augmenting the stock gallery. If PLONK is tested, compare `PLONK_YFCC` (Flickr photos) with `PLONK_OSV_5M` (roadside) on representative landmark and road scenes.

### 4.6 Evaluation with uncertain labels

Keep five distinct evaluation tracks:

| Track | Available reference | What can be reported |
|---|---|---|
| External geotagged data | Supplied GPS, with possible measurement error; Urban category may still be inferred | Coordinate-distance metrics and scores calculated against supplied GPS, with category/source assumptions stated |
| Challenge warm-up | Canonical JSON coordinates, confidence, reported error radii and estimated categories | Baseline distance/score metrics, uncertainty sensitivity, place-option recall and assisted-question results |
| Challenge trial | Independent estimates if available; actual organiser feedback if supplied | Clearly sourced baseline or feedback metrics, plus operational results |
| Organiser feedback, if provided | Whatever distance/category/score fields the organisers actually return | Measured feedback for those fields; computed score only when its required inputs are known |
| Operational rehearsal | Inputs, outputs and event logs | Runtime, memory, valid coordinates, logging, reset isolation, penalties, skips and fallback behaviour |

**External validation and final evaluation.** Set aside validation data for model choice, calibration and fusion weights. Reserve the OSV-5M official test split and an external panorama subset for final comparison. Include Portugal, Spain and France, urban-looking and rural scenes, off-road cases, landmarks and weak-clue cases. If the same test set is used repeatedly to choose models, treat it as validation rather than claiming it remains untouched.

The saved Portuguese Panoramax metadata contains **710 images in 58 collections**, with **377 images in the largest two collections**. These are not 710 independent locations. Sample across collections and geography; split by collection and avoid overlap with training and gallery query images. Source: [saved Panoramax metadata](research_notes/Panorama%20geolocation%20model%20stack/artifacts_datasets/panoramax_PT_360.csv).

**Downloaded sample** (`tools/fetch_panoramax.py`, `Data/panoramax/`, 1.4 GB). Each country's CSV holds the GPS, licence and `split` per picture; whole collections are assigned to `val` or `final`.

| Country | Pictures | Collections | `val` / `final` |
|---|---:|---:|---:|
| PT | 99 | 57 (at most 8 per collection) | 73 / 26 |
| ES | 100 | 100 | 67 / 33 |
| FR | 100 | 100 | 67 / 33 |

- **Portugal's 360° coverage is narrow.** The 709 pictures inside Portugal fall in four 1° tiles: Lisbon, the Oeste coast, Évora and Porto/Minho. Six collections hold 658 of them.
- **Resolutions vary from 4000×2000 to 12288×6144.** Resize to the challenge's 6080×3040 before scoring the pipeline, so OCR and detection see comparable detail.

Use different splits for different tasks. Region generalisation tests need sequence/spatial separation. Place-recognition tests need nearby gallery imagery from different captures: exclude the query and its capture sequence, but do not remove every reference within 1 km and then expect a 100 m image match.

**Canonical warm-up baseline.** Use [Data/warmup_locations.json](Data/warmup_locations.json) for the coordinate baseline, replacing the older location-report pins in validation. The file has 20 records: **19 high-confidence references with reported radii of 5–12 m**, and one low-confidence, unidentified-location reference with a **60,000 m radius**. Use the 19 for primary precise localisation metrics. Keep the coarse record in operational tests and region-level diagnostics, but exclude it from precise distance, street-level hit-rate and primary mean-score comparisons.

Match records by exact panorama filename. Use `lat`, `lon`, `error_radius_m`, `confidence`, `place` and the baseline's estimated `urban` category. Preserve `country`, `method`, `evidence`, `alternatives`, `heading_yaw0_deg` and `used_other_panoramas` as evaluation provenance; do not expose these annotations to the runtime agent. `used_other_panoramas` is descriptive text, so do not convert any nonempty string into a Boolean claim of assistance.

Record the baseline file hash/version and selected records in every evaluation report. Attach `estimated=true`, `is_ground_truth=false`, the reference source and inferred category source to evaluation metadata without changing the input JSON. The supplied error radii are useful estimates of position uncertainty; the resulting ranges are conditional on those estimates rather than formal confidence intervals.

**Coordinate errors and baseline scores.** Report Haversine distance to the baseline point and the challenge-formula score using its category estimate as the primary warm-up comparison. Incorporate each record's error radius explicitly:

```text
d_ref = Haversine(predicted_coordinate, baseline_coordinate), in metres
r = baseline.error_radius_m
d_min = max(0, d_ref - r)
d_max = d_ref + r

nominal score: use d_ref
lower score estimate: use d_max
upper score estimate: use d_min
apply the d < 10 m rule independently to each distance before scoring
```

These score ranges describe sensitivity if the actual camera is within the reported radius. They are not organiser-measured scores. Calculate both Urban/non-Urban scenarios when assessing category uncertainty, keeping the JSON category as the default baseline interpretation.

For a hit threshold such as 100 m or 5 km, report the nominal hit plus whether `d_max <= threshold` (inside throughout the assumed radius), `d_min > threshold` (outside throughout), or the result is boundary-sensitive. Apply the same logic to top-4 candidate coverage. This makes the tight-error references useful for street-level validation without treating a difference of a few metres as conclusive improvement.

**Place and question metrics.** Report whether the reference place is among the options of the first place-level question, using identity/aliases and supporting scene evidence separately from coordinate distance. An answer within 200 m alone does not prove the same place was recognised. Report autonomous results, nominal-oracle results, radius-aware results and human-rehearsal results separately, with question counts and penalties.

Use the same 19 primary references for paired comparisons. Show per-panorama results and, where several images depict the same place, a place-group summary so repeated scenes do not dominate the conclusion. The baseline may be used for evaluation and selecting useful pipeline components; it stays out of training, calibration fitting, retrieval galleries, runtime knowledge and cross-panorama location or clock inference.

OSV alone underrepresents some landmark and shop-name cases. The warm-up baseline directly tests those scenes; add independent external landmark/name examples where practical for broader validation instead of assuming external geotagged data cannot test these components.

**Organiser feedback.** A distance CSV is a possibility in the original plan, not a guaranteed asset. Distance feedback could permit score calculation without revealing GPS, but only if rank, category and applicable penalties are known. Use it for evaluation within the rules; do not infer another panorama's location or assume distance-based localisation probing is permitted.

Measure these on external data and the primary warm-up baseline subset, clearly labelling each reference source:

- Haversine error, median and error distribution, plus fractions within 100 m, 1 km, 5 km and 10 km.
- Top-4 candidate coverage as well as final-answer quality, so fusion is not blamed for a candidate generator that never found the right area.
- Score scenarios using the challenge formulas, separately by known or inferred category. Accuracy within 25 km alone cannot select a street-level urban pipeline.
- Nearest-reference coverage and scene overlap, separated from retrieval ranking quality.
- Complete wall-clock time, initial-result time, refinement time and peak memory.

The score calculator comes first. Verify metres, latitude/longitude order, the strict `d < 10 m` rule, rank factors, event-based penalties and Special One multiplier. Exact maxima and the distance table in section 1 are useful sanity checks.

### 4.7 Acceptance of additional components

Compare the same external validation cases with and without each addition. Include a component when it improves final score scenarios or useful candidate coverage at an acceptable time/memory cost. Inspect failures and variation across locations; a tiny gain on a handful of correlated frames is weak evidence.

Use the JSON baseline for paired warm-up comparisons of autonomous distance/score, place-option recall and assisted results, together with its reported error radii. It is a useful validation baseline; agreement with a VLM is not a substitute for it. Check whether small gains remain meaningful under the radius and category scenarios, and keep external validation for broader coverage and calibration. Run the retained configuration once on the reserved external final subset.

### 4.8 Accuracy acceptance gate

Operational readiness and localisation quality must both pass. The following are **provisional planning targets**, not measured results or predictions. Freeze the targets, primary filenames, estimated category sources, baseline hash, operator policy and time limits before comparing scored configurations. Any later target change must be documented; it must not retrospectively turn a failed run into a pass.

Use a simple working baseline (OCR/VLM, name lookup, one candidate generator and score-aware output) as the comparator. Run paired autonomous and human-assisted comparisons on the same cases under the same time budget. Report autonomous quality even when the intended final system uses human answers. Oracle or simulated-perfect answers cannot satisfy the human-assisted acceptance gate.

For the 19 precise warm-up references, require the retained configuration's realistic human-assisted results to meet both targets:

| Requirement | Target | Calculation |
|---|---|---|
| Urban camera accuracy | At least **50%** robustly within **100 m**; with the current inferred categories, **at least 9 of 17** urban references | For the final selected coordinate, require `d_ref + error_radius_m <= 100 m`; this tests the camera position, not only landmark identity |
| Mean score after interactions and reference uncertainty | At least **30%** of the unpenalised exact maximum, using the conservative score estimate | Score each final list with `d_max`, actual rank factors and per-output penalties; divide by its exact unpenalised maximum, then average over all 19 cases |

For an ordinary panorama, 30% corresponds to **4,815.16 points** out of 16,050.52. Normalise a Special One by its own ×3 maximum. Include every primary case in the denominator: a case with no valid final coordinate list by its deadline contributes zero. Score a valid fallback normally when an optional stage fails or times out. An invalid final output or incomplete interaction/penalty log also fails the operational gate. The conservative score estimate remains conditional on the reported radii and inferred categories, as in section 4.6; also show nominal scores, upper estimates and both category scenarios.

Report per-panorama and place-group summaries, autonomous versus assisted scores, paired differences from the simple baseline, answered/skipped question counts, and complete time. Choose the strongest validated configuration within the resource budget, including the simple baseline if additions do not help. Apply the acceptance rule in section 4.7 to each addition; a gain restricted to repeated views of one place is insufficient evidence of general improvement.

Operators receive the panorama and permitted agent options, without the reference JSON or evaluator annotations. Record whether they already know a warm-up location; familiar-case results do not establish unseen human performance. The independent rehearsal must include unfamiliar external panoramas, Spanish and French coverage, and urban and non-urban cases. Apply the 50% accuracy target using that rehearsal's urban count (round the required hits up), and average normalised scores over all six cases for the 30% target. With supplied external GPS, use uncertainty bounds where source accuracy is available, and label nominal-only results where it is not.

Verify each implemented coordinate branch on independent examples: a reference-camera match with possible viewpoint displacement, a landmark whose object point differs from the camera, a fine cell including off-road positions, and a coarse fallback. Check coordinate roles, representative-point containment, cell bounds and output uncertainty. A successful landmark-name match must not count as a successful camera-position test.

If a target is missed, stop optional additions, inspect the failed locations and select the best validated fallback. Record the miss and remaining limitations rather than claiming accuracy readiness. Keep the reserved external final subset for one final evaluation; repeated tuning on it makes it validation data.

## 5. Timeline and completion gates

Checkpoints determine whether we add components. The first complete baseline may use one working geolocation model while embeddings and classifier preparation continue. All later tasks are lower priority than a usable logged answer.

### Now to the Saturday trial at 19:00

- [x] Start the OSV-5M download, as recorded in the original plan. Verified at 17:10: every file is a complete JPEG with a metadata row (section 4.1). [T01]
- [x] Re-run `tools/fetch_osv5m.sh` after the Spain/France phase finishes: 4,827 of 51,551 Portugal images failed around 16:00 (DNS and TLS errors, most likely the venue network). Done 16:57–17:00 (`Data/osv5m/fetch_retry.log`): test 5,206, Portugal 51,551, Spain/France 50,000, 0 errors. [T02]
- [x] Resolve or assign the organiser questions in section 8, especially log format, feedback availability, category labels and runtime external access. [T08]
- [x] Smoke-test the Python 3.12 environment and chosen model loading on sm_120. Use the locally tested software route and working VLM; avoid making an upgrade or power-profile investigation a prerequisite for the baseline. [T09]
- [x] Implement the score calculator, event/penalty tracker, per-panorama state and JSON logging. [T10, T11]
- [ ] Send a sample JSON log to Discord before 19:00, so the organisers can confirm the format before the trial. [T12]
- [x] Start the name index (section 4.4): save the Wikidata and GeoNames extracts now, so the baseline can resolve names. [T03]
- [x] Run one panorama end to end: views → OCR/VLM → one working candidate generator/name lookup → simple fusion → question/skip handling → coordinates. [T20]
- [x] Start resumable PE-Core embedding preparation as usable training images become available. [T21]
- [x] Select a small, diverse external validation set, with an explicit separate final subset. [T22]
- [x] Freeze a version/hash of `Data/warmup_locations.json`; configure the evaluator for its 19 precise references, reported radii, estimated categories and diagnostic-only coarse record. Keep baseline annotations outside agent inputs. [T23]
- [x] Freeze the accuracy targets and evaluation policy in section 4.8; record a simple baseline for paired comparisons. [T24]
- [x] Implement coordinate-source roles and the output contract in section 3.3, including a usable coarse fallback. [T17]

**Gate A:** a complete coordinate output and reviewable interaction log, including a skipped question and a failed optional stage. Passing this gate does not establish localisation accuracy.

### Saturday 19:00–21:00 trial

- [x] Run the working baseline independently on each trial panorama and record total time. [T26]
- [ ] Have the team submit a sample JSON log for organiser review. [T27]
- [x] Record actual returned feedback, if any. Keep challenge place estimates marked as estimates. [T28]
- [ ] Identify concrete failures: missed text, missing candidate areas, false image matches, ambiguous coordinates or slow stages. [T29]

**Gate B:** usable logs, a functioning human loop and a known operational time budget. Fix these before increasing model count.

### Overnight, in dependency order

The name index and landmark gallery do not depend on the photo bank. Their owner works on them from Saturday afternoon, in parallel with the bank (section 7).

- [x] Build the local name index, zone boundaries and landmark gallery (sections 4.4–4.5). [T31, T32, T33]
- [x] Finish and verify the selected photo bank, metadata and embeddings. [T34, T35]
- [x] Build kNN and train/calibrate the simple mini-PIGEON head on external training/validation data. [T36, T37]
- [x] Compare candidate generation and conservative fusion on external validation cases; test the second geolocation model only if time allows. [T39]
- [x] Run paired autonomous and assisted validation against the warm-up JSON baseline, reporting nominal scores, radius sensitivity, place-option recall and answered/skipped question counts. [T40]
- [x] Validate MegaLoc and geometric matching on separate-capture examples; enable the working path where coverage exists. [T41]
- [x] Implement and check the landmark/cell route: exhaustive options, interior representative points, distance bounds, recovery choices and automatic coordinate generation from clicks. [T42]
- [x] Run the section 4.8 accuracy gate and record whether each target passes; test each implemented coordinate branch. [T43]
- [ ] Add targeted detector crops if they fix observed OCR/perception failures. [T44]
- [ ] Consider SAM 3, segmentation, solar checks, rich grid features and the feature table only after the preceding tasks meet their gates. [T45]
- [x] Rehearse the retained configuration, including unavailable network access, module timeouts and unknown category handling. [T46]

**Gate C:** pass the section 4.8 accuracy targets, coordinate-branch checks and valid logging requirements, alongside measured initial automated processing ≤150 seconds and peak GPU memory ≤14 GB on representative cases. Record complete refinement/human-answer time. Passing the resource limits alone does not pass this gate.

### Sunday before 10:00

- [x] Stop adding features around 08:00, freeze weights/configuration/dependencies and keep a known working fallback. [T53]
- [x] Evaluate the retained version on the reserved external subset once; record assumptions and observed failures. [T54]
- [ ] Rehearse six independent, unfamiliar external panoramas within 60 minutes, with separate logs, no carried-over evidence and actual human answers. Record score/accuracy against supplied GPS, source uncertainty, question penalties and whether the section 4.8 targets hold on the rehearsal. [T55]
- [ ] Confirm output coordinate order, log export and whatever label/feedback format the organisers actually supply. [T56]

**Gate D:** Gate C has passed, and the team completes the unfamiliar six-panorama rehearsal within 60 minutes with valid outputs/logs and measured accuracy meeting the section 4.8 targets under the declared reference assumptions. If reference accuracy is unknown, report the rehearsal check as nominal rather than robust. Keep the strongest validated configuration and document any unmet target; completing six outputs alone is not evidence of accuracy readiness.

## 6. On Sunday

The scoring window is 10:00–13:00, but the team has **60 minutes of solving time** for five panoramas plus the Special One.

- One person operates the agent. A second teammate, the finder, starts locating each panorama with Google Lens and maps as soon as it arrives, so the team can answer zone questions as well as check options. The others check agent-generated options in Street View.
- If the panoramas arrive together, enqueue their automated stages and process them with one GPU worker and fresh state for each. Interactive questions and refinement for the active panorama take priority over later background work; yield between bounded stages so the queue does not block the operator. Tag every request/result with its panorama/run ID. Model weights stay loaded; evidence, conversations, model context and temporary galleries never carry over.
- An example budget is eight minutes per ordinary panorama, fifteen for the Special One and five minutes of buffer. Adjust for the expected weighted score gain of further work.
- Produce an initial answer, then refine where evidence and time justify it. Do not spend the whole budget debugging optional components.
- Answer useful questions only when the team has adequate evidence. Skipping is free and conveys no information.
- Keep the selected coordinate's uncertainty in the log even when the final list repeats it ten times.
- Treat every panorama, including live-presentation panoramas, independently. Keep the frozen external assets available for an offline fallback.

## 7. Team roles if four people

| Owner | First deliverable | Later responsibility |
|---|---|---|
| Pipeline and human loop | Complete baseline, scorer, isolated state, questions with checkable options, and logs | Zone fallback, simulated operator, timers, fallbacks, rehearsal and output export |
| Perception | Working crops, OCR and one VLM with uncertainty-preserving evidence | Targeted detection and measured perception improvements |
| Geography and precise coordinates | Name index (OSM, Wikidata, GeoNames), zone boundaries, candidate coordinate resolution and conservative fusion | Landmark gallery, match verification and geographic checks |
| Pixel geolocation and data | Verified download/partitions, embeddings, kNN and mini-PIGEON | External validation, coverage audit and model comparisons |

Agree on the evidence and candidate JSON formats before integration. Owners can work concurrently on independent tasks; the baseline must remain runnable while additions are developed.

## 8. Questions for the organisers

**Answered on 2026-10-10 (evening); see the Organiser answers in [RULES.md](RULES.md).**
- **Answered:** 1, 2, 3, 4, 6 and 8, plus the time zone in 5. In short:
  - there is no required schema, only an understandable one
  - the Urban label comes after submission
  - runtime fetches are allowed
  - a submission returns a distance
  - filename times are UTC
  - chained zone questions are fine
- **Still open:** 7 (repeated submissions and distance probing), 9 (do the panoramas arrive together?), 10, and whether a timestamp is the shot or the start of a series (the rest of 5).

Resolve these early through the team; do not assume answers from the original plan:

1. What JSON schema is required, including skipped questions, candidate outputs and failed model stages?
2. Are Urban/non-Urban labels supplied for the trial and scoring sets, and what should happen when a label is missing? The current warm-up set has none.
3. May the agent itself fetch Mapillary, OSM or other external data during a run, or must it rely on prepared assets?
4. What feedback do submissions return: distances, scores, categories, a CSV, or only acceptance? True GPS remains undisclosed under the stated rules.
5. Are filename timestamps local time or UTC, and do they represent each shot or an interval sequence start?
6. How are outputs produced before an answered question treated in the final submitted list? Preserve event timestamps and penalty snapshots meanwhile.
7. What limits apply to repeated submissions and attempts to localise through distance feedback? Do not build such a strategy before clarification.
8. Confirm the interaction format for chained, agent-generated geographic questions, including grouped districts and spatial-cell options. The PDF permits geographic-zone questions; show concrete examples of full coverage and recovery options.
9. Do the five panoramas and the Special One arrive together, and may the agent process them back to back with fresh state for each?
10. Confirm the scope of the existing cross-panorama restriction for human answers. Until clarified otherwise, teammates must not use a previous panorama's location, clock inference or recognised scene to guide answers for another; each image is assessed independently.

## 9. Comparison notes and related-document corrections

| Original plan or assumption | V2 decision and reason |
|---|---|
| Nearly tied locations can be spread across output slots | Repeat the maximum-expected-score coordinate; diversity remains useful for internal alternatives and questions |
| Regional prediction leads naturally to an exact spot | Make coordinate resolution explicit; 1 km urban error retains only about 9.1% of maximum points |
| A landmark or geometrically verified image match supplies the camera GPS | Type camera, landmark and area coordinates; use reference-camera anchors or bounded geographic cells, with displacement and source uncertainty recorded |
| Mini-PIGEON grouped with costly additions during review | Keep its simple frozen-embedding classifier as core preparation; assess its additional benefit over kNN |
| Full feature likelihood table is required overnight | Defer it behind the classifier, precise localisation and validation; similarity scores require calibration |
| Every model supplies an independent vote | Account for shared embeddings, reference data and overlapping views; use conservative fusion |
| Always narrow to the best region or four places | Retain alternatives and global fallback candidates; a wrong early decision must remain recoverable |
| Large roadside bank implies precise coverage | Audit geographic and visual coverage, including off-road/landmark scenes; retrieval depends on available references |
| Exact urban matching depends on permitted runtime downloads | Prepare an offline route; online fetches are conditional additions |
| Challenge estimates are too uncertain for useful precise validation | Use the canonical JSON's 19 tight-radius references for baseline error/score metrics, with explicit radius sensitivity; keep the coarse record diagnostic-only |
| Urban category and distance CSV are available inputs | Track missing/inferred categories and confirm actual feedback; calculate both score scenarios when needed |
| 710 Panoramax images form a large independent test set | Account for 58 collections and concentrated coverage; split and sample by capture group |
| One spatial exclusion rule can serve every test | Separate region generalisation tests from VPR tests that need nearby, different-capture references |
| Qwen agrees with PE-Core, so feature labels are validated | Agreement is a consistency check; retain manual audits and independent external validation |
| 25 km accuracy is enough for choosing the geolocation stack | Evaluate candidate recall, distance distributions and challenge-score scenarios at relevant scales |
| All components should be integrated before Sunday | Complete the baseline first; retain optional components only after useful validation and measured resource cost |
| Model timings establish a 1–3 minute complete pipeline | Measure actual loading, preprocessing, VLM work, downloads and refinement; use deadlines and fallbacks |
| Fast processing and valid logs establish competition readiness | Also require declared camera-accuracy and penalty-adjusted score targets, plus an unfamiliar human-assisted rehearsal |
| Answer only when sure | Also check whether the question changes the decision enough to justify its penalty and time |
| Sun plus filename gives a compass heading | Use optional candidate-specific checks; position, timestamp convention, camera yaw and observation reliability matter |
| Four candidate points or selected districts cover every possible location | Use exhaustive geographic partitions, finer spatial cells and explicit recovery choices |
| Perfect simulated answers predict human performance | Report oracle and realistic/rehearsed behaviour separately; skips do not convey missing-candidate information |
| Preserve or replace GeoCLIP's stock gallery unconditionally | Compare restricted stock, reference and deduplicated merged galleries, accounting for geographic density |
| Background panorama processing can occupy the GPU until the whole queue finishes | Prioritise interactive work, bound stages and keep request/result state isolated by run ID |

v2 was adopted on 2026-10-10 and `CLAUDE.md` follows it. `MODEL_DECISIONS.md` still needs these corrections; until then, this plan wins where they disagree:

- Remove the instruction to spread the ten answers ≥100 m apart. Non-maximum suppression can diversify questions/candidate exploration, not the final score-maximising repeated list.
- Correct `MODEL_DECISIONS.md`'s urban score examples: 25 m retains **80%**, and 300 m retains **25%** of maximum. The existing 84% and 12.5% figures use a different decay assumption.
- Distinguish the selected 101,551-image training source pool from the full PT/ES/FR training dataset, and report actual usable counts.
- Replace unconditional product-of-experts fusion, compulsory large-model residency and fine-geocell training with the staged, validated baseline described here.
- Replace unconditional tuning on challenge distance/hand-label estimates with external validation and rule-compliant challenge evaluation.
- Distinguish unofficial challenge pins and inferred Urban labels from externally supplied GPS and official organiser feedback.

These corrections are comparison notes; implementing v2 also requires the measured checks in sections 4 and 5.
