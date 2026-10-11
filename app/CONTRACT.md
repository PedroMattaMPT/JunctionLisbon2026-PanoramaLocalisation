# Event and HTTP contract

`panoloc/runlog.py` is authoritative. **Existing** below means the current Python writer or candidate schema already defines the field. **Proposed** means the frontend reads it and fixtures/mock exercise it; the production pipeline and HTTP service must adopt or negotiate it.

## Existing event envelope

One JSON object per line in `events.jsonl`, or an object containing an `events` array in `log.json`:

```ts
interface RunEvent {
  run_id: string;
  panorama: string;
  seq: number;
  t: number;                  // actual monotonic seconds since run start
  ts: string;                 // UTC
  type: string;
  stage: string | null;
  actor: 'agent' | 'model' | 'team';
  model: string | null;
  payload: Record<string, unknown>;
}
```

Events are sorted by `seq`; repeated IDs are ignored. Imported logs must contain one run and one panorama. Unknown types, stages, model IDs and evidence kinds remain in the Log tab. `agent` renders as Solver, with the code attribution. Language models are never accepted as the source of candidates or output coordinates.

The pure bridge is `src/reducer.ts`: `reduce(events)` and `reduceEvent(previous, event)`. Replay uses a prefix of the same event stream. Presentation selection, yaw, layers and replay speed never alter the solver's state.

## Existing payloads

| Event | Fields read |
| --- | --- |
| `run.started` | `panorama`, `special_one`, `category: {value: 'urban' \| 'non-urban' \| null, source: 'official' \| 'inferred' \| 'unknown'}`, `versions` |
| `stage.started` | `optional`, `deadline_s` (nullable) |
| `stage.finished` | `elapsed_s`, `over_deadline` |
| `stage.failed` / `stage.timed_out` | `optional`, `elapsed_s`, `message`, `error` on failure |
| `stage.skipped` | `reason` |
| `evidence.added` | `evidence_id`, `kind`, kind-specific fields |
| `candidates.updated` | `candidates`, with `candidate_id`, `lat`, `lng`, `role`, `source`, `label`, `weight`, nullable `accuracy_m` / `extent_m`, `country`, `group`, `evidence`, `details` |
| `question.asked` | `question_id`, `kind`, `text`, up to four `options: {id, label, detail?, support?}`; optional `agent_probabilities: {option_id: probability}` overrides displayed option support |
| `question.answered` | `question_id`, `option_id`, `label`, `penalty` |
| `question.skipped` | `question_id` only |
| `cue.sent` | `text`, `chars`, `penalty` |
| `conversion.applied` | `place`, `coordinate`, `note`, `penalty`; rendered in replay, never offered as an action |
| `output.produced` | `output_id`, `coordinates: {rank, lat, lng}[]`, `output_method`, `sources`, `source_role`, nullable `position_uncertainty_m`, `uncertainty_source`, `category`, `special_one`, `penalty`, `note` |
| `run.finished` | `duration_s`, `final_output`, `questions`, `penalty` |
| `run.reopened` | `output_id`, `reason: 'answer_review'`, unchanged `penalty`; clears the finished flag while retaining all outputs and receipts |

`penalty` is the existing snapshot `{answered_questions, cues, conversions, multiplier}`. The displayed multiplier changes only when one arrives from the backend. Each output retains its own snapshot. A skipped question changes no weight, candidate or multiplier, and yields no evidence.

The current organiser clarification in `RULES.md` reveals the official Urban label only after submission. Live intake defaults to an unknown category; operator-selected categories default to `inferred`. Production should retain this distinction. Submission feedback transport and any returned distance/category metadata are not part of the current app API; no challenge answer key or true coordinate is read.

Candidate `role` is `camera`, `landmark` or `area`. Their labels respectively say camera position, landmark point and representative area point. Candidate rings use the available `accuracy_m` plus `extent_m`; if both are null, the radius is unknown. Output rings use `position_uncertainty_m`, independently of the candidate. A null radius is never treated as zero. A numeric zero is retained when explicitly logged.

Support is non-negative fusion weight divided by the sum of weights, to two decimals. It is labelled support, not presented as a calibrated location likelihood. A zero total gives unknown support. Missing intervals are not invented. Score estimates use the existing `rt.theta`, logged radius as a distance proxy, rank weights and the output's penalty snapshot. This is an estimate, not validation against a true location; an unknown Urban label shows both scenarios and a null radius produces no numeric score.

## Evidence payloads: existing subsets and proposed additions

The live scene stage also emits `stage.progress`: `{message, completed, total, view?, box?}`. Counts are measured completed views (`0 <= completed <= total`), with `total > 0`; absent counts remain unknown. The reducer attaches progress to the running stage without creating an observation or changing its status. `box` uses the same angular convention as evidence boxes. Older logs need no progress events.

`vlm_checklist` retains `answers`, `seen`, `counts`, the inspected view's `box`, and `features: {key, label, value, description, countries, regions, strength}[]`. `inference` is a short public explanation derived from validated checklist answers and the clue catalogue. `vlm_summary` carries the combined hints and a similar explanation. A view-level box frames the inspected perspective; it is not a localized object detection. These events stream per completed view, and cached runs restore the saved observations with fresh IDs.

The real sample currently contains postcode/text, checklist, landmark hypothesis and views observations. Evidence payloads are open dictionaries in the existing writer; the richer fields below form the proposed UI contract. Every subset renders without invented boxes, votes, counts or match lines.

| Kind / stage | Fields | Status |
| --- | --- | --- |
| `views` / views | `count`, `sky`, `ground`, `photographer_masked` | Proposed; the mock uses this observation to reveal sectors and the retained mask |
| `object` / detect | `label`, `score`, angular `box`, `sam_score`, `kept` | Proposed |
| `text`, `postcode`, `phone`, `road_number` / read | `text` verbatim, `confidence`, `box`, `country`, `parsed`, `crop_url` | Text/postcode/confidence/box/country have existing sample examples; parsed/crops/other kinds proposed |
| `language` / read | `votes: {pt, gl, es, ca, eu, fr}` or `{id, v}[]` | Proposed; values are logged shares |
| `checklist` / describe | `item`, `answer: 'yes' \| 'no' \| 'not_visible'`, optional `box`, `answered`, `total` | Item/answer existing; box and partial counts proposed |
| `landmark_hypothesis` / describe | `name`, `not_visible` | Existing sample; coordinate-free inference |
| `scene_shares` / measure | `shares` in order sky/building/grass/tree/road/water/ground, `masked`, `mask_url`, optional `mask_palette` | Proposed; visible image share, not land cover |
| `sun` / measure | `azimuth`, `elevation`, `yaw`, `bearing_of_yaw0`, `err_deg` | Proposed; true bearings appear only after a logged conversion |
| `neighbour` / geo | `photo_url`, `lat`, `lng`, `similarity`, `source`, `group: 'pe-core'` | Proposed; prepared reference-camera GPS, labelled looks similar |
| `region` / geo | `regions: {name, v, lo?, hi?}[]`, `cells: {lat, lng, size_m, v}[]` | Proposed; incomplete numeric rows are kept in the log but not drawn |
| `geo_sample` / geo | `points: {lat, lng}[]` | Proposed; only actual sampled points are drawn |
| `name_match` / names | `query`, `matches: {label, lat, lng, role, source}[]` | Proposed; landmark/area points, not camera positions |
| `landmark_photo` / names | `photo_url`, `lat`, `lng`, `source`, `role: 'landmark'` | Proposed; prepared Commons reference |
| `match` / spot | `reference: {id, photo_url, lat, lng, source}`, `matches`, `inliers`, `threshold`, `accepted`, `reason`, `query_yaw`, optional `query_fov`, `keypoints_url` | Proposed; `accepted === true` is required for the confirmed match stamp |
| `contradiction` / fuse | `between: string[]` evidence IDs, `note` | Proposed |

An angular box is `{yaw, pitch, w, h}` in degrees, centred at yaw/pitch. Image yaw zero is the JPEG's left edge. Logs from the real pipeline, whose `run.started` carries `versions.pipeline`, use the `panoloc/views.py` convention instead: yaw zero is the image centre, as in Pannellum. The reducer adds 180° to their evidence boxes (T76). Strip centre: `x = yaw / 360 * width`, `y = (90 - pitch) / 180 * height`. Width/height use their angular scale. Yaw wraps at the seam. Missing or invalid boxes yield no pixel overlay and “position not logged”.

The photographer mask is a retained fraction of image height at the bottom, not a discarded crop. It is drawn only when `photographer_masked` arrives. A `stage.finished` views event may alternatively provide proposed `views` and `photographer_masked` fields.

### Proposed mask encoding

Serve a strip-resolution 2:1 PNG, no larger than 4096×2048. A non-interlaced indexed PNG (1/2/4/8-bit palette indices) or an 8-bit grayscale PNG holds **class indices**, not display colours. The frontend inflates and reverses PNG filters, preserving indices even if palette entries share colours. It maps them to the current `seg-*` tokens.

Default indices: 0 sky, 1 building, 2 grass, 3 tree, 4 road, 5 water, 6 ground, 7 masked. Unmapped indices, including 255, are transparent. If the model uses another class order, send `mask_palette`, e.g. `{"0":"sky","10":"building","255":"masked"}`. This is a proposed field requiring pipeline agreement. Already colourised PNG/SVG assets are also supported; the procedural fixture SVG is an invented illustration. PNG chunk handling follows the [W3C PNG specification](https://www.w3.org/TR/PNG-Chunks.html).

### Proposed match geometry

Inline `keypoints` or the JSON at `keypoints_url` contains pairs of normalized image points:

```json
[{"query":[0.31,0.46],"reference":[0.33,0.49],"inlier":true}]
```

`query` refers to the rectilinear query view, `reference` to the reference image. Both axes range from 0 to 1. The frontend samples the already decoded panorama at `query_yaw`, using the logged `query_fov` and a 500×320 frame. The pipeline must send the exact query FOV; when it is missing, query geometry is unavailable and no match lines are invented. A different matcher projection or aspect ratio needs an agreed query crop extension. Counts come from `inliers` / `matches`, never from the number of display lines. Rejected matches remain visible with their logged reason.

### Proposed linking and fusion fields

Evidence may additionally carry `observation`, `inference`, `polarity: {candidate_id: -1 | 0 | 1}`, `group`, and `group_cap`. Groups keep correlated sources under one bracket. A numeric cap is shown only if logged.

Candidates may carry `name`, `level: 'country' | 'region' | 'town' | 'spot'`, `lo`, `hi`, `supports`, and `contradicts`. These evidence ID lists drive selection, the matrix and candidate reference filtering. Reference evidence can carry `candidate_id` / `candidate_ids` or a matching source for explicit ownership. The frontend never invents reference associations or reuses another case's images.

`candidates.updated.ruled_out` is proposed: `{name, level, reason, by}[]`. Ruled-out entries remain in the record. Stage payloads may include proposed `fallback`, which is the only basis for naming a fallback model in a deadline row.

### Proposed question fields

`question.asked`: `gain`, `break_even`, `scope: string[]`, `worded_by`. Gain and break-even are fractions (0.12 means a 12% expected gain). Missing gain is labelled unknown. The standard answer cost is ×0.95; break-even is `1 / 0.95 - 1` when omitted.

Options: `reason`, `evidence: string[]`, `point: [lat, lng]`, `zone` as a GeoJSON Polygon geometry, `none`, `links`. GeoJSON geometry coordinates retain the GeoJSON `[lng, lat]` order; only `point` uses latitude first. Current zone drawing supports the outer ring of a Polygon; polygon holes and MultiPolygon zones need an extension before use. A geometry-free question draws no invented zone. A none-of-these option exists only if the agent supplied it. Skips carry no selection.

## Proposed HTTP interface

All paths are local, preferably same-origin behind `/api`. Every write must reach the backend and its log. Responses may acknowledge acceptance but cannot change UI penalties optimistically. Errors are JSON `{"error":"plain reason"}` with an appropriate 4xx/5xx status.

| Method / path | Request and response |
| --- | --- |
| `POST /api/runs` | Multipart `file` unchanged JPEG, `category` (`urban`, `non-urban`, empty for unknown), `category_source`, `special_one` (`true` / `false`); returns `{run_id}` |
| `GET /api/runs/{run_id}/events` | SSE `id: seq`, `data: <one envelope>`, blank line; honours `Last-Event-ID`; optional `?after=seq` for an initial subscription after importing a current log |
| `POST /api/runs/{run_id}/questions/{question_id}/answer` | `{option_id}`; backend validates open question and option, then logs `question.answered` |
| `POST /api/runs/{run_id}/questions/{question_id}/skip` | `{}`; logs only the question ID, with no evidence or penalty |
| `POST /api/runs/{run_id}/cues` | `{text}`; validates before logging, maximum 1000 characters, rejects place names, hints and coordinates |
| `GET /api/runs` | `[{run_id, status, special_one}]` or `{runs:[...]}`; status-only inventory |
| `GET /api/runs/{run_id}/log.json` | Existing `Run.export()` document, including all events and summaries |
| `GET /api/files/{path}` | Prepared crops, masks, keypoint JSON and references; local paths constrained by the backend |
| `GET /api/status` | `{worker, gpu:{used_gb:null|number,total_gb:number}, models:[...], tile_source:null|string, csrf_token:string, mock?:boolean}` |
| `POST /api/runs/{run_id}/skip-remaining` | `{}`; live server: skips the open question and every later one of that run (free, neutral), each logged as `operator.auto_skip` `{question_id, reason: 'skip_remaining' \| 'timeout', waited_s, timeout_s}` before the pipeline's `question.skipped`; returns `{accepted, open_question}` |
| `POST /api/runs/{run_id}/review` | `{output_id}`; live server: explicitly reopen the latest finished answer and queue a model-directed review; returns `{accepted:true}` with 202. Stale, active and exhausted requests are rejected. Same local write token and Origin validation as other writes. |
| `GET /api/tiles/{layer}/{z}/{x}/{y}` | Live server: one cached base-map tile (`streets`, `satellite`); 404/503/504 JSON when unavailable, 403 for other sites' pages |
| `POST /api/tiles/prefetch` | `{run_id, question_id, layer}`; warms the tile cache behind one open question's options (at most 48 tiles, zoom ≤ 16) |
| `GET /api/streetview/nearest?lat={lat}&lng={lng}` | Display-only lookup: `{pictures, unavailable}`; at most eight panoramas within 1 km with coordinate, distance, date, heading, credit, licence, source page and a local image-proxy URL. Only coordinates go upstream; no run ID, upload or evidence is accepted |
| `GET /api/streetview/image/{provider}/{id}/{sd\|hd}` | Cached public JPEG from previously resolved metadata; approved hosts and redirects only. 503 when disabled/unavailable and 403 for other sites' pages; an image-host outage leaves other hosts and the catalog usable |

The live server adds `tile_layers: {id, name, url, max_zoom, attribution, attribution_url}[]`, `current`, `current_panorama`, `queue`, `current_question: {question_id, text, kind, waiting_s, timeout_in_s} | null`, `question_timeout_s` and `answer_review: {enabled, max_requests}`; its `/api/runs` rows add `panorama`, `question`, `skip_remaining`, optional `can_review` and a queue `position`. Model-roster entries use `{id, name, role, state, gb}`. Unknown GPU residency and memory remain unknown. `tile_source` is a local z/x/y raster URL or PMTiles URL; vector extracts must use the agreed source-layer schema.

Review keeps one panorama's original Run, monotonically increasing sequence/IDs, question constraints and penalty counters. The controller logs short `answer_review` decisions plus `review_finished` or `review_failed` evidence. It permits one self-check, two human questions and three decisions per request, and three requests per run. Self-checks replace the existing VLM clue group through name-index lookup; repeat reasoning is never independent confirmation. Reopen is explicit, and imported replay cannot call it. SSE must reconnect with the last seen `seq` after a review request because the completed stream has already ended. A new `run.finished` closes each review.

### Additional proposed endpoints used by this app

| Method / path | Purpose |
| --- | --- |
| `POST /api/runs/{run_id}/priority` | `{}`; move a queued sealed case to the front, without pre-empting the active worker; optional audit event `run.prioritised` |
| `POST /api/runs/{run_id}/submit` | `{output_id}`; validate that the reviewed output is current, then acknowledge submission; proposed `run.submitted` event contains `output_id`, `coordinates`, `penalty` |

Submission transport to the organisers is **not implemented**. The mock logs an acknowledgement using `Run._emit` and then finishes the run. Production owners should expose a public audit method or equivalent hook; private `_emit` use is confined to the development mock.

The mock gets its authoritative events from `Run(on_event=...)`. The SSE adapter resumes by sequence, sends keep-alive comments while idle, and sends optional `event: end` when the run finishes. The client closes on `end`; reconnects otherwise replay missed envelopes, which are safely deduplicated.

### Local write protection

The app reads `csrf_token` from `/api/status` and sends `X-Aqui-Token` on POSTs. This is a proposed addition to the brief's API. The mock binds loopback only, validates Host and Origin, constrains file access and limits upload/request size. A production localhost API should implement an equivalent token and origin check, not open arbitrary writes through CORS.

The mock cue validator rejects a limited development gazetteer, selected place hints and coordinate patterns. It is **not a complete challenge-rule validator**. Production needs the local name index and a semantic hint check before enabling real cues. Browser checks remain operator assistance; backend validation decides. Server JPEG checks in the mock read frame dimensions; production must fully decode and validate the image as the browser does.

## Integration sequence

1. Implement the existing envelope stream and upload endpoint using a clean `Run` per panorama.
2. Adopt status/write-token endpoints, question and cue validation, and one-worker queue semantics.
3. Emit proposed observations as each model becomes available; sparse events already render without placeholder numbers.
4. Serve only prepared reference assets; link them by evidence/candidate IDs and state their coordinate role.
5. Verify projection/mask conventions, local tile extracts, cue rules and submission transport with the pipeline team before completing T50.
