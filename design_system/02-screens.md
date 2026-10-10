# Screens and layout

Three modes share one component set. Every screen is a composition of components fed by one case record (which mirrors the event log); the showcase pages are under Screens, Stage and Motion.

## Console (operator, 1440×900; scales to 2560×1600)

Read left to right: **panorama → reasoning → map**.

| Region | Size at 1440 | Contents |
|---|---|---|
| Run bar | full width × 52 | `RunBar`: wordmark, case and Special One badge, Urban label and its source, this-panorama timer, session clock, `MultiplierChip`, `ScoreReadout`, `GpuMeter`, worker status |
| Panorama column | 584 | `PanoramaStrip` (2:1, bearing ruler, overlays), `LayerToggles`, `Viewer360` synced on yaw, `ZoomCrop` of the selected box, `CompassDial` |
| Reasoning column | 432, on `surface-0` | `Tabs` (Stages · Evidence · Matrix · Log), the running `StageRow`, the evidence feed (`EvidenceCard`, `CorrelationBracket`) |
| Map column | 424 | `MapView` (focus follows the selection), `MapLegend`, `CandidateList` with ruled-out rows |
| Shortcut bar | full width × 28 | `ShortcutBar` for the current mode |

At 2560×1600 the columns grow to 1040 / 760 / 760 and the strip shows labels for every box (`labelMode="all"`). The question replaces the reasoning column; exact spot and final answer take the panorama and reasoning columns.

## Screens

| Screen | Case | What it proves |
|---|---|---|
| Intake | all six files | Any 2:1 accepted, other sizes flagged, unparsed names explained, Urban label + source and Special One per file, clean-state check, model roster, Start |
| Queue | six cards | Sealed cards: only status crosses (waiting, processing, question waiting, answer ready, submitted); the Special One counts ×3; no dates, no thumbnails |
| Run console | A, 05:40 | One evidence item linked to pixels and map; exact spot running against its deadline; the correlated group bracketed |
| Question | A, 03:28 | Options as cards and as zones; gain +19% against 5.26%; cost on every answer; free Skip; D off-map shown in the inset |
| Question outcomes | A answered, B skipped | Answered: multiplier ticks, bars move, chosen zone thickens. Skipped: nothing moves, and it says so |
| Exact spot | A | Query vs reference with matches, inlier counts, accepted and rejected references, the remaining offset |
| Final answer | A | Surveyor's mark and ring, coordinate block, ×10 slots, score curve, export and submit |
| Case report | A (light) | Replay scrubber + log, evidence × candidate matrix, questions and costs, ruled out, look-alikes, export |
| System states | A/B | Failed and timed-out stages with fallbacks, invalid JSON, tiles offline, no text, no candidate above threshold, Urban label unknown |

## Stage (projector, 1920×1080, `theme="stage"`, `Density value="stage"`)

- A second window on the projector follows the same run while the operator keeps the console.
- Top bar (88): wordmark, case, Urban, timer, multiplier, replay badge. Caption bar (120) at the bottom: Newsreader headline + one sentence + model chip + log time.
- One focus at a time in the remaining 872 px: the crop being read, the question with its map, or the final mark with its score.
- The map camera follows the evidence: country → region → town → spot, never tighter than the current uncertainty.
- Opening card lists every local model and what it does, plus the solver and the team.

## Case report (`theme="light"`, printable)

A4/Letter friendly at 1440 wide: Newsreader title, coordinate block and expected score in the header, then replay, matrix, questions, ruled out and look-alikes. Look-alikes are computed per case from that case's own evidence; cases never inform each other.

## Keyboard map

| Key | Console | Question open |
|---|---|---|
| J / K | next / previous evidence | next / previous option |
| 1–4 | — | answer A–D (costs ×0.95) |
| S | — | skip (free) |
| O | — | copy all option links |
| L | toggle layer panel | — |
| V | swap strip and 360° view focus | — |
| M | map follows the selection | — |
| C | open the cue composer | — |
| Space | play / pause replay | — |
| ⇧⏎ | submit (asks to confirm) | — |
| 1–6 (queue) | open case | — |
| Esc | close popover or dialog | — |

Every action with a key shows its `KeyCap`. Focus order follows reading order: run bar → panorama → reasoning → map.
