# Implementation

Built to be picked up by a small team in a weekend: React + TypeScript + Tailwind with shadcn/ui-style primitives, fed by a Python backend streaming events (SSE or WebSocket). Everything on screen derives from the event log, so a replay is the same render driven by older log state.

## Tokens

- `tokens.json` is the single source (colour in three themes, type, spacing, radius, shadow, border, z-index, duration, easing, opacity, size). The page compiles it to `tokens.css`: `:root, [data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="stage"]`, one class per type style (`.console-body`, `.stage-caption`, `.inference`…) and the `@font-face` rules.
- Tailwind: `code/aqui.tailwind.preset.js` maps every utility to the same variables — `bg-surface-2`, `text-ink-2`, `text-solver`, `border-line-2`, `rounded-2`, `p-3`, `shadow-focus`, `duration-quick`, `ease-enter`, `z-dialog`, and font sizes named after the type styles (`text-console-body`). Themes switch by setting `data-theme` on any ancestor; no rebuild.
- Density: set `data-density="stage"` (or wrap in `Density value="stage"`) and components switch to the `stage-*` type styles and doubled spacing and lines.

```js
// tailwind.config.js
module.exports = { presets: [require('./aqui.tailwind.preset.js')], content: ['./src/**/*.{ts,tsx}'] };
```

## Fonts

Self-hosted variable WOFF2 files in `fonts/` (subset to Latin, Latin-1, Latin Extended-A/B and punctuation, maths and arrows ranges): Atkinson Hyperlegible Next (roman and italic, 200–800), Atkinson Hyperlegible Mono (200–800), Newsreader (roman and italic, 200–800, optical size 6–72). Licences (SIL OFL 1.1) are in `licences/`. No runtime CDN.

## Components ↔ code

Component names map 1:1 to code. The bundle exposes them on `window.Aqui`; in the app, import the same names from `src/components`. Props are documented in `components/index.d.ts`.

| Event type | Drives |
|---|---|
| `run.started` / `run.finished` | `RunBar`, `CleanStateCheck`, `CaseCard` status |
| `stage.started` / `.finished` / `.skipped` / `.failed` / `.timed_out` | `StageRow`, `StageTimeline`, `WaitState`, `CaptionBar`, `Toast` |
| `evidence.added` | `EvidenceCard`, `PanoramaStrip` layers, `ZoomCrop`, `LanguageVote`, `SceneShares`, `CompassDial`, `MapView` heat/refs/samples, `EvidenceMatrix` |
| `candidates.updated` | `CandidateList`, `Funnel`, `RuledOutRow`, `MapView` pins and rings, `ScoreReadout` |
| `question.asked` / `.answered` / `.skipped` | `QuestionCard`, `MapView` zones, `GainMeter`, `AnswerReceipt`, `MultiplierChip` |
| `cue.sent` | `CueComposer`, `MultiplierChip` |
| `output.produced` | `CoordinateBlock`, `AnswerSlots`, `ChoiceNote`, `ScoreCurve`, `SurveyMark`, `ExportBar` |

Every event carries `run_id`, `panorama`, `t` (seconds since `run.started`), `type`, `stage`, `actor` (`model` | `solver` | `team`), `model` and a `payload`. Boxes are angular (`yaw`, `pitch`, `w`, `h` in degrees) so the same payload places a box on the strip, in the 360° viewer and in a crop. The `EventLog` component renders the raw JSON of any row.

## Panorama and 360° viewer

- The strip is the equirectangular JPG in an `<svg>` with overlay layers in image-yaw degrees: x = yaw / 360 × width, y = (90 − pitch) / 180 × height. Yaw 0 is the left edge; the bearing ruler maps bearing = yaw + the sun fix offset once it exists.
- The 360° viewer is Pannellum (already in the repo) or Photo Sphere Viewer. Keep one `yaw` in state; the strip draws the viewer's field of view, and the viewer's `yawchange` writes back.

## Map

MapLibre GL JS with prefetched tiles. Style the base with the `map-*` tokens (read them from computed styles at load and on theme change): water `map-water`, land `map-land`, other countries `map-land-out`, admin-1 lines `map-border`, national lines `map-border-country`, labels `map-label` with a halo. Data layers: heat as a grid of fill squares using `heat-1`…`heat-5`; zones as fill + line + a hatch pattern per option; rings as circles in metres (`circle-radius` from a zoom expression) — unknown radius uses a dashed line at a fixed pixel size. When tiles fail, switch to the bundled GeoJSON of PT, ES and FR with admin-1 borders (the outline mode in `MapView`).

## Placeholder imagery

The previews draw a procedural urban riverfront and a rural montado as equirectangular strips and rectilinear views, plus schematic Porto streets. They are illustration stand-ins; replace them with the real panorama and tiles. Their colours are not tokens on purpose.
