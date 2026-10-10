# Design system prompt: panorama geolocation app

**How to use:** paste everything below the line into the design tool, or hand it to a designer. Attach three warm-up panoramas as image references:

- `IMG_20250125_144630_00_319.jpg`: a busy city square, with the photographer visible at the bottom
- `IMG_20260911_125512_00_749.jpg`: a rural bridge with the sun in frame
- `IMG_20260605_092457_00_064.jpg`: a semi-indoor station café

Written 2026-10-10 from `RULES.md`, `PLAN.md` (v2), `MODEL_DECISIONS.md` and the two challenge PDFs. Update the working name and the implementation targets if they change.

---

## The brief

Design a UI/UX design system, and the key screens built with it, for **Aqui**. "Aqui" is a working name: Portuguese for "here", from the challenge tagline "Where in the world could *here* be?". It is a local web app that:

1. takes one 360° panorama photo
2. shows, step by step, what each local AI model sees, what it concludes and how the evidence is combined
3. asks the team multiple-choice questions when an answer is worth its cost
4. pins the final location on a map and exports the coordinates and the interaction log

Animation comes in a later phase. For now I need the static system: tokens, components in every state, and screens, plus motion tokens and a storyboard to build later. Design each state so it can later animate into the next.

## Context

### The challenge

- This is our team's entry for the Albatroz "Panorama Localisation" challenge at the JunctionX Lisbon 2026 hackathon.
- **Goal:** given one panorama, return up to 10 ranked `(lat, lng)` guesses. Mainly Portugal, also Spain and France.
- **Local only:** the agent runs on open-weight models on one laptop with a 16 GB GPU. No cloud APIs.
- **Limited help:** the team can only type text cues or click answers to the agent's own multiple-choice questions, and both cost points.
- **No answer key:** the true locations are never revealed, so the team judges plausibility from the evidence.
- **The organisers' purpose:** to "return the AI-assisted deduction process (could we call it reasoning?)" behind the ranked locations, built by humans and AI together. They are also interested in places that are far apart yet look alike.
- **Why the challenge exists:** the organiser tried to locate a storm photo with AI chatbots. Each reply named a new town with full confidence, apologised when corrected, and never showed why. **Aqui must do the opposite.** Every claim traces back to pixels, uncertainty stays in plain sight, and ruled-out places stay visible with the reason.

### The input

- **The image:** one 360° equirectangular JPG, 6080×3040 (2:1), taken in daylight, at most 5 m above ground, unedited, with a consumer 360° camera.
  - The horizon runs across the middle; the top edge is the zenith and the bottom edge the nadir.
  - The left and right edges join.
- **No metadata:** EXIF, GPS and heading are stripped.
  - The filename `IMG_YYYYMMDD_hhmmss_00_NNN.jpg` is the only side information: date, time (UTC) and a shot counter.
- **Urban label:** each panorama should come labelled Urban or non-Urban, which picks the scoring curve. The warm-up set had no labels, so the app records where the label came from: official, inferred or unknown.
- **Photographer:** the bottom 15–20% shows the photographer's head and hands, the selfie stick's shadow and sometimes friends. The pipeline masks it.
- **Scenes:**
  - City squares, old-town streets, castle walls, a station café, river piers, rural bridges, open fields.
  - Shop signs, other text and landmarks are the strongest clues. Street names are rare.

### Who uses it, and where

| Mode | When | Who | What matters |
|---|---|---|---|
| **Console** | Sunday scoring run: 60 minutes to solve 5 panoramas plus the "Special One" (worth ×3). About 8 minutes each, 15 for the Special One | One operator at the laptop, plus one or two teammates checking the agent's options on other laptops | Speed, keyboard control, every cost visible, timers, nothing hidden |
| **Stage** | The live presentation (one panorama solved live), and the final against the other challenges' winners, in front of the audience | A room watching a 1920×1080 projector | Readable from the back row, one focus at a time, plain-language captions. This is where the animations matter |
| **Case report / replay** | After each panorama and after the event | Organisers, jury, us | The whole deduction: timeline, evidence, questions, costs, final answer, log export |

Stage mode can run as a second window on the projector. It follows the same run while the operator keeps the console on the laptop.

**Sunday flow:**

1. Drop all six panoramas into a queue and mark the Special One.
2. One GPU worker works through the queue in the background, one panorama at a time, each from a clean state. The panorama the operator is working on goes first. A first answer exists within about 1–3 minutes.
3. If a question is worth its cost, the agent asks it and teammates check the options on their laptops.
4. The agent refines the exact spot.
5. Submit, export the log, move to the next panorama.

### The pipeline the UI has to show

- **Evidence:** each stage writes evidence into a file kept for that panorama alone.
- **Who decides:** code combines the evidence. Models never do the probability arithmetic and are never asked for coordinates.
- **Data-driven layout:** the stage list is still changing, and the optional stages may be dropped. The timeline and evidence cards must work for any number of stages and any model names.

| Stage | What runs (all local) | What the UI shows |
|---|---|---|
| Intake | Filename parser | Date, UTC time, shot counter, Urban label and its source, Special One flag |
| Views | py360convert | 8 horizontal views of 45° each, plus sky and ground; the photographer mask |
| Detect (optional) | YOLOE-26-L open-vocabulary detector; SAM 3 checks each box | Boxes for signs, plates, bollards, churches, granaries…; boxes rejected as not really there; full-resolution zoom crops |
| Read | PP-OCRv6 (OCR, on the CPU); three language-ID voters | Raw text with confidence; postcodes, phone prefixes and plates parsed by their format; a language vote across pt / gl / es / ca / eu / fr |
| Describe | Qwen3.5-9B vision-language model (VLM), with Gemma 4 12B as fallback | A closed checklist with `not_visible` on every item (vegetation, architecture, road furniture, terrain, water); landmark guesses |
| Measure (optional) | EoMT-L segmentation; pvlib sun position | Shares of sky, trees, buildings and water; direction of the sea or river; skyline; sun position → compass heading of the image |
| Pixel geolocation | PE-Core embeddings; nearest-neighbour search over ~100k geotagged reference photos; mini-PIGEON (our region classifier); GeoCLIP or PLONK as an extra generator | Nearest reference photos with their GPS, region estimates, a heatmap, sampled points |
| Name lookup | Local index of OSM, Wikidata and GeoNames | Places matching the text read or the landmark guessed, each typed as a camera, landmark or area coordinate |
| Fusion | Code, not a model | Ranked candidates at country → region → town → spot; for each piece of evidence, the candidates it supports or contradicts; ruled-out candidates with the reason |
| Ask | Code picks the question; the VLM writes the wording | A question with up to 4 options and its expected gain against its cost. Zone questions can chain from regions down to small map cells |
| Exact spot (conditional, mostly urban) | MegaLoc retrieval; ALIKED + LightGlue matching | Matching reference photos near the candidates, keypoint matches, inlier counts, an estimated camera position |
| Answer | Code | One coordinate in all 10 slots, its uncertainty, the penalty snapshot, the JSON log |

- **Loops:** the stages from pixel geolocation to exact spot can run again after an answered question.
- **Budget:** 1–3 minutes of compute per panorama, using about 12–14 GB of GPU memory.
- **Outcomes:** stages have deadlines and fallbacks. Any stage can end as done, skipped, failed or timed out, and the run still produces an answer.
- **Correlated evidence:** several sources share one image encoder (PE-Core), so their votes are correlated. Fusion groups them and caps their combined weight, and the UI must show that grouping.

### Rules the UI must build in

- **Allowed input:** only text and multiple-choice clicks go into the agent. Humans never type coordinates or upload anything except the panorama.
- **Cues:**
  - Up to 1000 characters, costing ×0.8.
  - A cue must not name or hint at any place. The organisers' banned example is "the most famous sport here is big-wave surfing", meaning Nazaré.
- **Questions:** written by the agent, at most 4 options. Answering costs ×0.95, right or wrong.
- **Skip is free and must change nothing:**
  - Beliefs stay as they were, and the log records "skipped".
  - A skip is never read as "no" or "none of these".
  - "None of these" exists only when the agent made it one of the options.
  - Questions never say "skip if…".
- **Place names:** if the agent returns a place name instead of coordinates, a human converting it costs ×0.5. The app always produces the coordinates itself, so there is no coordinate entry field.
- **Penalty scope:** a penalty applies to every guess produced after it, for that panorama only. So every output carries the multiplier at the moment it was made.
- **Each panorama is solved on its own:**
  - A new model conversation and empty evidence, with nothing carried over.
  - Using one panorama to locate another is banned. The queue never groups panoramas by date or hints that two were taken on the same day.
- **Logging:** every interaction is logged in JSON with a timestamp.
- **Option links:** links to maps and Street View open on teammates' other devices. Nothing seen there goes back into the agent, except a click on one of the agent's options.

### Scoring the UI must show

- **Formula:**
  - The top slot scores 1000 points × a distance factor θ.
  - Each step down the list multiplies by 0.95, so the rank weights run 1.00, 0.95, 0.90 … 0.63.
  - Urban θ = 2 / (1 + d/100); non-Urban θ = 2 / (1 + d/10000). d is in metres, and under 10 m counts as 0.
- **Totals:** the Special One counts ×3. A panorama scores the sum of its 10 slots. Ties go to the faster team, so time matters.
- **Our default:** repeat the coordinate with the highest expected score in all 10 slots, which the rules allow, even when two candidates are nearly tied. That coordinate isn't always the single most likely spot.
- **Maximum:** 16,050.52 points for 10 exact guesses (48,151.57 for the Special One).

| Distance error | Urban keeps | Non-Urban keeps |
|---|---:|---:|
| 25 m | 80% | 99.8% |
| 100 m | 50% | 99.0% |
| 1 km | 9.1% | 90.9% |
| 5 km | 2.0% | 66.7% |
| 10 km | 1.0% | 50.0% |

- **Expected, not actual:** the true distance is never known, so any score on screen is an **expected score** under the agent's current beliefs and is labelled as an estimate.
- **When to ask:** an answered question pays off only if it raises the expected score by more than 5.26% (1/0.95 − 1). A cue needs 25%. The question card shows the expected gain against that line.
- **Unknown label:** when the Urban label is unknown, show both curves and both expected scores.

### What the answer looks like

- **Slots:** ten slots, each a WGS84 `(lat, lng)`, normally the same coordinate ten times.
- **Each coordinate carries:**
  - its source role: `camera`, `landmark` or `area`
  - its method: `reference_camera`, `geographic_cell` or `coarse_candidate`
  - an uncertainty radius in metres, **or "unknown"**, and where the radius comes from: a geometric bound, a source estimate or an estimated offset
  - the penalty multiplier when it was produced
- **Precision:** extra decimal places don't make a guess precise. A coordinate is always shown with its uncertainty and source.
- **Always submittable:** a current best answer exists from the first fusion onwards, so the operator can submit at any moment.

## Design principles

1. **Show the work.** Every claim links to its evidence: a region of pixels, a crop, the model and its score. Selecting an evidence card highlights its region in the panorama and its area on the map.
2. **Keep observation, inference and estimate apart.** For example: read "4050-253" (observation) → a Portuguese postcode for central Porto (inference) → Porto 0.47 (estimate). Each gets its own visual treatment.
3. **Uncertainty comes first.** Show ranges, radii, `not_visible`, unknowns, contradictions and ruled-out candidates. Confidence moves both ways: contradicting evidence visibly widens the uncertainty.
4. **Three actors.** Models observe, the solver (our fusion code, not a model) decides, and the team answers. Colour and labels make it clear at a glance who did what.
5. **Cost before click.** Every action that costs points shows its multiplier before it is taken, and the running multiplier is always on screen.
6. **One panorama, one sealed case.**
7. **Motion is evidence.** Every animation corresponds to a real event in the log. No decorative loops, no fake progress.
8. **Fast for the operator, readable for the room.** One component set in two densities.

## Visual direction (a starting point; propose better)

- **Mood:** a cartographer's case file crossed with a precise instrument. Calm, exact, slightly editorial. Not a sci-fi HUD, and not a chatbot.
- **Motifs:**
  - hairline graticules
  - a 0–360° bearing ruler under the panorama: camera yaw at first, compass bearings once the sun fixes north
  - leader lines from evidence to pixels
  - stamp-like verdicts ("RULED OUT", "CONFIRMED"), used sparingly
  - a surveyor's mark rather than a generic teardrop for the final pin
- **Colour:**
  - **Base:** quiet. Deep Atlantic ink for dark mode, limestone paper for light mode.
  - **Accents** from the region's materials: azulejo cobalt, Pombaline ochre, roof-tile terracotta, granite grey, cork-oak green.
  - **Map:** a desaturated base, so the data reads first.
  - **What colour encodes:**
    - the three actors: model, solver, team
    - evidence polarity (supports, contradicts, neutral), always paired with an icon
    - confidence: high, medium, low, unknown
    - stage status: queued, running, done, skipped, failed, timed out
    - cost (penalties), kept distinct from neutral information
    - options A–D, used identically on question cards and map zones
    - one sequential palette for heatmaps
  - Stages and models get icons and labels, not colours.
- **Type:**
  - An open-licence UI sans, plus a monospace with tabular figures for coordinates, scores, times and estimates.
  - Optionally, a display face for stage headlines.
  - Every face must render Portuguese, Spanish, French, Catalan, Galician and Basque text, including ç, ã, õ, ñ and l·l.
  - Coordinates to 5 decimals with a true minus sign (−8.61315). Distances in m or km, times as mm:ss.
  - Fonts are self-hosted.
- **Themes:** dark and light. Dark is the default for console and stage, light for the printable case report. Check the stage palette against a washed-out projector.
- **Name:** a simple wordmark and favicon for "Aqui", easy to swap.

## Screens to design

1. **Intake.**
   - Drop one or several JPGs.
   - Accept any 2:1 equirectangular image, and flag sizes other than 6080×3040.
   - Parse the filename. Set the Urban label and its source (official, inferred or unknown), and the Special One flag.
   - On start, show the clean-state check: new conversation, empty evidence, nothing carried over.
   - States: empty, dragging, valid, warning (wrong ratio or unparseable filename), error.
2. **Run console.**
   - **Run bar,** always visible:
     - case ID and Special One badge
     - time used against the panorama's budget, and the 60-minute session clock
     - running multiplier and expected score
     - GPU memory and online/offline status
   - **Main areas:**
     - the panorama: a flat strip with the bearing ruler and overlay layers, switching to an interactive 360° viewer
     - the reasoning: stage timeline and evidence feed
     - the map and the candidates
   - **Model roster:** each local model with its role and memory.
   - **Layout:** propose one. Reading left to right, panorama → reasoning → map is a sensible default.
3. **Question.**
   - A question card with up to four options and Skip. The options also appear on the map as zones or pins in their A–D colours.
   - **Each option has:**
     - a label and a one-line reason
     - its evidence chips
     - a representative point, marked "not a camera position"
     - links to open it in OSM, Google Maps and Street View
   - Copy-all-links (or a QR code for a phone) for teammates.
   - **Zone questions:**
     - The zones in one question never overlap, and together they cover the current scope, so one option is often "anywhere else".
     - Questions can chain: grouped regions → municipality → map cells. The chain ends at a cell whose farthest point is within about 25 m of its representative point (urban) or about 1 km (non-urban).
     - Show a breadcrumb of the parent scopes.
     - A click picks a zone, and the agent computes the coordinate from it.
   - The expected gain against the cost.
   - Keyboard: 1–4 and S.
   - **Show both outcomes:**
     - answered: belief bars before and after, and the multiplier ticks down
     - skipped: nothing changes, and the screen says so
4. **Exact spot.**
   - The query view and a reference photo side by side, with keypoint match lines and the inlier count.
   - Candidate camera positions on the map with uncertainty rings.
   - Accepted and rejected matches.
   - A good image match is not a 10 m camera fix, so show the remaining offset.
5. **Final answer.**
   - The pin and its uncertainty ring.
   - The 10 slots, with rank weights and penalty snapshots. Ten identical rows mustn't look like a bug: show the coordinate once with ×10 and the rank weights, expandable to the full list.
   - If the chosen coordinate differs from the most likely candidate, say why.
   - The expected score on the distance-to-score curve.
   - Copy coordinates, with the lat, lng order stated.
   - Export the JSON log.
   - Submit, with a confirm step.
6. **Case report / replay.**
   - A scrubber over the event log.
   - The evidence × candidate matrix.
   - Questions with their answers and costs.
   - Ruled-out places with their reasons.
   - Look-alikes: far-apart places that share this panorama's evidence, such as Alentejo montado and Extremadura dehesa.
   - Export.
7. **Queue.** Five cases plus the Special One, as sealed cards: waiting, processing, needs answer, done, submitted. Only status crosses between cases.
8. **Stage mode.** Versions of screens 2, 3 and 5 at 1920×1080:
   - an opening card listing the local models
   - one focus at a time, with larger type
   - a plain-language caption bar built from templates, e.g. "Reading signs: a postcode in a format only Portugal uses"
   - the map camera following the evidence
   - a visible replay-speed badge
9. **System states:**
   - a stage failed or timed out, and which fallback ran
   - the VLM returned invalid JSON
   - map tiles offline, falling back to bundled outlines of PT, ES and FR with district borders. It must still look intentional
   - no text found
   - no candidate above the threshold
   - Urban label unknown, with both scoring scenarios side by side

## Components (all states, both densities, both themes)

- **Shell:**
  - run bar and case card
  - timers: time used against budget, a warning at 80%, over budget
  - multiplier chip with its history, and the expected-score readout
  - GPU memory meter, online/offline badge, clean-state badge
  - model roster and shortcut hints
- **Panorama:**
  - flat equirectangular viewer with the bearing ruler and horizon
  - 360° viewer frame, kept in sync with the strip on yaw
  - overlay layers:
    - view sectors
    - photographer-mask hatch
    - detection boxes
    - text boxes with their reading
    - segmentation tint
    - sun marker
    - water-direction arrow
    - skyline trace
  - zoom-crop card and layer toggles
- **Reasoning:**
  - stage row: status, model, duration, memory
  - model chip: name, role, "local · open weights"
  - evidence cards for:
    - text read
    - object found
    - checklist answer, including `not_visible`
    - scene measure
    - sun and compass
    - language vote
    - reference-photo neighbour
    - region estimate
    - name match
    - contradiction
  - a bracket that groups correlated evidence
  - the stage caption bar
- **Beliefs:**
  - candidate row: rank, name, level, estimate bar with range, change since the last update, counts of supporting and contradicting evidence
  - the country → region → town → spot funnel
  - ruled-out row: struck through, with the reason and the deciding evidence
  - the evidence × candidate matrix
- **Map:**
  - candidate pin: ranked, selected, ruled out
  - uncertainty ring. A known radius and an unknown one are drawn differently, and an unknown radius never looks like 0 m
  - heatmap and sampled points
  - reference-photo points, with thumbnails on hover
  - a view cone from a candidate along the measured bearings
  - question zones A–D, each with a label and a representative point
  - final pin, coordinate readout, legend, scale bar
- **Human loop:**
  - question card, option and Skip
  - cue composer: character counter, ×0.8 warning, a check that flags place names and coordinates, confirm step
  - answer receipt showing what changed
- **Output:** 10-slot answer list; coordinate block (monospace, copyable); distance-to-score chart; export buttons; event log viewer.
- **Base:** buttons, inputs, toggles, tabs, tooltips, toasts, dialogs, key caps, badges, empty states, and loading states for real waits.

## Data visualisation

- **Estimates:** model outputs are estimates, not calibrated probabilities. Label them as estimates, show ranges where available, and round sensibly (0.62, not 0.6213).
- **Language vote:** one stacked bar across pt / gl / es / ca / eu / fr.
- **Scene shares:** one 100% bar of sky, building, tree, grass, water, road, ground and masked, captioned "visible share, not land cover".
- **Compass:** a dial with the image's yaw 0, true north, the sun's azimuth and elevation, and the error.
- **Region estimates:** horizontal bars, top 5 plus "other".
- **Distance to score:**
  - θ for Urban and non-Urban over a log distance axis from 10 m to 100 km.
  - Marks at 25 m, 100 m, 1 km, 5 km and 10 km.
  - The current uncertainty band and the resulting expected score.
- **Question value:** expected gain against the 5.26% break-even line.
- **Heatmap:** one sequential hue, transparent at the low end.
- **Colour is never the only channel.** Pair it with an icon, pattern or label.

## Hard problems to solve explicitly

Explain in the design rationale how the system handles each of these:

1. Making Skip feel neutral and free, never like "no".
2. Showing an uncertainty that is unknown, as opposed to small.
3. Showing several correlated sources as one voice.
4. Linking one piece of evidence to its pixels and to the map at the same time.
5. Keeping the flat strip and the 360° viewer in sync.
6. Showing the cost of every action before it happens.
7. Keeping a room engaged through 1–3 minutes of real compute without fake progress.
8. Keeping the map readable with a heatmap, points, zones, rings and pins on it at once.
9. Showing the same coordinate in all ten slots without it looking like a bug.

## Motion (define now, build later)

**Tokens:**

- **Durations:**
  - instant (≤100 ms): hover and press
  - quick (150–200 ms): small state changes
  - standard (250–300 ms): cards and panels
  - deliberate (400–600 ms): estimate bars and rings
  - cinematic (1–2 s): map flights, scaled by how far the zoom changes
- **Easing:** ease-out for entrances, ease-in for exits, a gentle spring only for the final pin.
- **Stagger:** 30–60 ms between list items, at most about 0.5 s in total.
- **Replay:** 1×, 2× or 5×, always with a visible speed badge and real timestamps.
- **Reduced motion:** cross-fades only. Motion never carries information on its own.

**Storyboard,** one beat per event type in the log:

1. **Intake:** the panorama lands as the flat strip, and the filename splits into date, UTC time and shot.
2. **Views:** the eight sectors, sky and ground light up, and the photographer area hatches out.
3. **Detect:** boxes appear. The boxes SAM 3 rejects fade out, struck through.
4. **Read:**
   - Text lifts into evidence cards.
   - Postcodes and phone numbers snap to their country.
   - The language bar fills.
5. **Describe:** checklist items tick in. `not_visible` reads as "can't tell", not as a failure.
6. **Measure:** the segmentation tint sweeps across. The sun is found, and the bearing ruler turns to true north.
7. **Pixel geolocation:** heat appears on the map, reference photos fly to their GPS, and sampled points settle.
8. **Fusion:**
   - Evidence sends weight to the candidate bars.
   - Correlated sources merge into one bracket.
   - A contradiction pulses its two sources.
   - Ruled-out candidates fade to ghosts with their reason.
9. **Narrowing:** the map zooms country → region → town as the estimates concentrate, never tighter than the uncertainty.
10. **Ask:** option zones draw on the map. On an answer the multiplier ticks down. On a skip nothing moves.
11. **Exact spot:**
    - The reference photo slides in beside the query view.
    - Match lines draw, and the inlier count climbs.
    - The ring contracts.
12. **Pinpoint:**
    - The pin lands, and the ring settles at the final radius.
    - The 10 slots fill one by one with their rank weights.
    - The expected score counts up.

Design key frames for beats 3, 8, 10, 11 and 12 now.

## Implementation targets

The system must be buildable by a small team within the weekend.

- **App:** a local web app on the same laptop as the models. React + TypeScript + Tailwind with shadcn/ui-style primitives, fed by a Python backend that streams events over Server-Sent Events or a WebSocket.
- **360° viewer:** Pannellum (already used in our repo) or Photo Sphere Viewer. The flat strip is the equirectangular image with an SVG or canvas overlay.
- **Map:** MapLibre GL JS. Map services were slow or failing from the venue network, so tiles are prefetched, and the bundled outline fallback must look deliberate.
- **Assets:** fonts and icons self-hosted under open licences. No runtime CDNs.
- **Tokens:** CSS custom properties (light and dark) with a Tailwind theme mapping. Component names map 1:1 to code.
- **Sizes:** console at 1440×900 and 2560×1600; stage at 1920×1080. Phones are out of scope.
- **Scope:** prefer a few reusable components over many one-off ones.
- **Log-driven:** everything on screen must be derivable from the event log, so a replay just plays the log again.

Example event:

```json
{"run_id": "r-07", "panorama": "IMG_20260115_143012_00_204.jpg", "t": 41.2,
 "type": "evidence.added", "stage": "read", "actor": "model", "model": "PP-OCRv6-medium",
 "payload": {"text": "4050-253", "kind": "postcode", "country": "PT", "confidence": 0.94,
             "box": {"yaw": 212.5, "pitch": -3.1, "w": 4.2, "h": 1.6}}}
```

Event types:

- `run.started`, `run.finished`
- `stage.started`, `stage.finished`, `stage.skipped`, `stage.failed`, `stage.timed_out`
- `evidence.added`, `candidates.updated`
- `question.asked`, `question.answered`, `question.skipped`
- `cue.sent`
- `output.produced`

## Sample content for the mockups

The data is invented and doesn't need to match the attached images.

**Case A: urban, text-rich, one question answered**

- **File:** `IMG_20260115_143012_00_204.jpg` → 2026-01-15, 14:30:12 UTC, shot 204. Urban (official).
- **Run bar:** 5:40 used of 8:00; session 23:15 of 60:00; GPU 12.6 / 16 GB.
- **Detect:** 17 boxes kept, 3 rejected (e.g. "licence plate" 0.31, which SAM 3 scores 0.02).
- **Read:**
  - "CAFÉ" 0.97
  - "4050-253" 0.94 → a Portuguese postcode; area 4050 is central Porto
  - "22• ••• •••" → a Portuguese landline; prefix 22 is Porto
  - language: pt 0.93, gl 0.04, es 0.02, fr 0.01
- **Describe:**
  - granite masonry ✓
  - blue-and-white azulejo façade ✓
  - wrought-iron balconies ✓
  - river visible ✓
  - calçada portuguesa pavement `not_visible`
  - vegetation `not_visible`
- **Measure:** sky 31%, building 44%, road and pavement 17%, water 5%, tree 3%. Water at a bearing of ~200°. Image yaw 0 → bearing 64° ± 12°.
- **Pixel geolocation:** Porto 0.47, Braga 0.12, Lisboa 0.11, Viana do Castelo 0.06, Galicia (ES) 0.05, other 0.19.
- **Fusion:**
  - Porto · Ribeira 0.52
  - Vila Nova de Gaia · riverside 0.21
  - Porto · Miragaia 0.12
  - Lisboa · Alfama 0.05, contradicted by the postcode
  - other 0.10
  - Ruled out: Galicia (ES), by the Portuguese postcode and spelling.
- **Question** (expected gain +19% against the 5.26% break-even): "Which zone contains the camera?"
  - A · Porto riverfront, Ribeira to Miragaia
  - B · Vila Nova de Gaia riverfront
  - C · rest of Porto district
  - D · none of these (anywhere else in PT, ES or FR)
- **Answered A:** Ribeira 0.69, Miragaia 0.21, Gaia 0.03 (kept in case the answer was wrong), other 0.07. Multiplier ×0.95.
- **Exact spot:** 3 reference photos within 150 m. LightGlue inliers 412 / 118 / 36. Camera at 41.14081, −8.61315 ± 22 m (source GPS plus viewpoint offset).
- **Answer:** 41.14081, −8.61315 ×10 · `reference_camera` · ± 22 m · ×0.95 · expected ≈ 12,500 of 16,050.

**Case B: non-urban, no text, one question skipped**

- **File:** `IMG_20260512_110547_00_318.jpg` → 2026-05-12, 11:05:47 UTC, shot 318. Non-Urban (official).
- **Read:** no text found.
- **Describe:**
  - cork oak ✓ (stripped trunks with a painted digit)
  - holm oak ✓
  - unpaved track ✓
  - whitewashed farmhouse with blue trim in the distance ✓
  - red-brown soil ✓
  - gently rolling terrain
- **Measure:** sky 47%, grass and field 24%, tree 22%, ground 6%, building 1%. Sun found → image yaw 0 → bearing 312° ± 15°.
- **Pixel geolocation:** Évora 0.31, Beja 0.24, Portalegre 0.17, Extremadura (ES) 0.12, Setúbal 0.09, other 0.07.
- **Look-alike:** Alentejo montado and Extremadura dehesa look nearly the same. With no text, Portugal versus Spain stays open.
- **Question** (expected gain +11%): "Which zone contains the camera?"
  - A · Alto Alentejo
  - B · Alentejo Central
  - C · Baixo Alentejo and Alentejo Litoral
  - D · anywhere else in PT, ES or FR
- **Skipped:** nothing changes, and the multiplier stays ×1.00.
- **Answer:** 38.60610, −7.84120 ×10 · `geographic_cell` · ± 4.2 km · ×1.00 · expected ≈ 11,300 of 16,050.

Show one queue card as the Special One (×3).

## Deliverables

1. **Concept:** the wordmark, a short rationale and two or three mood frames.
2. **Foundations,** delivered as CSS custom properties, a Tailwind theme mapping and a JSON token file:
   - colour: light and dark, semantic and data-visualisation palettes, contrast checked
   - type scales for both densities
   - spacing, radii, borders, elevation and layers
   - motion tokens
3. **Components:** everything listed above, with all states, both densities and both themes, plus short usage notes.
4. **Screens,** using cases A and B:
   - Intake
   - Run console mid-run
   - Question, answered and skipped
   - Exact spot
   - Final answer
   - Case report and replay
   - Queue
   - the stage versions of the run, question and final screens
   - the system states
5. **Motion:** the token table and the five key-frame storyboards, with timing notes. No animation code yet.
6. **Accessibility:** WCAG AA contrast, a colour-blindness check of the semantic palette, the keyboard map, reduced motion.

If you can render HTML or React, build the tokens, components and screens as live pages.

## Avoid

- A chat window as the main metaphor. The agent is a reasoning process, not a chat partner.
- Generic AI styling: purple-blue gradients, sparkles, glowing orbs, "magic" wording.
- Confident copy without evidence ("Found it!", "Exact location"). Prefer "best estimate", "± 22 m", "ruled out because…".
- Fake progress bars, spinning globes, particles that aren't data.
- A single over-precise percentage, or an unknown uncertainty drawn as 0 m.
- Styling Skip like "No" or "None of these".
- Anything from another panorama inside a case.
- Embedding Street View or other outside imagery in the app. Options link out instead.
- Albatroz or JunctionX logos and colours. This is our team's entry, not their product.
