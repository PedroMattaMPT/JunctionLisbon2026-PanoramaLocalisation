# Aqui design system

The design options and components of Aqui, the operator console in `app/`. Design options are the choices a page makes through tokens: theme, density, colour role, type style, spacing, shape, line and motion. Components are the React pieces built on them. The system's own components live in the bundle, one folder each under `components/` with its README and preview. The app's compositions are in [App components](02-app-components.md). Screens, flows, the keyboard map and the event wiring belong to the app: see `app/README.md` and `app/CONTRACT.md`. Aqui is a working name; the wordmark is one SVG and swaps cleanly.

The look exists to be the opposite of a chatbot that names a new town with full confidence and never says why. Every claim traces back to pixels, uncertainty stays in view, and ruled-out places stay on screen with the reason.

| File | Contents |
|---|---|
| This README | Design rules, copy, colour, type, space, icons, imagery |
| [Patterns](01-patterns.md) | Rules that span several components (Skip, unknown radius, linked selection, map layers…) |
| [App components](02-app-components.md) | The app's components built from the system |
| [Motion](03-motion.md) | Motion tokens and what each component's motion means |
| [Data visualisation](04-data-visualisation.md) | Chart components and their rules |
| [Accessibility](05-accessibility.md) | Contrast, colour-blindness, keyboard and screen-reader behaviour per component |
| [Implementation](06-implementation.md) | Tokens, Tailwind preset, fonts, how to import the components |

## Design options

| Option | Values | Set with |
|---|---|---|
| Theme | `dark` (console default), `light` (report, print), `stage` (projector) | `data-theme` on any ancestor, or `Density theme` |
| Density | `console` (body 13/18), `stage` (body 24/32, nothing under 20 px, doubled spacing and lines) | `data-density`, or `Density value` |
| Colour role | see Colour below | `color` tokens |
| Type style | `console-*`, `stage-*`, `narrative-*`, `inference` | classes or `useT()` |
| Space, shape, line | `space-*`, `radius-*`, `line-*`, `border-rule`, `shadow-*`, `focus-ring` | tokens |
| Layering | `z-*` | tokens |
| Motion | `dur-*`, `ease-*` | tokens ([Motion](03-motion.md)) |
| Emphasis | `opacity-dim`, `opacity-ghost` | tokens |

Every value is in `tokens.json`; nothing outside it is a design option.

## Design rules

1. **Show the work.** Every claim links to its evidence: a region of pixels, a crop, the model and its score. Selecting an `EvidenceCard` outlines its pixels in `PanoramaStrip` and its area on `MapView` in `select`, joined by `LeaderLines`.
2. **Keep observation, inference and estimate apart.** Observation: a bracketed box on `model-soft` with the reading in `console-data` ("4050-253"). Inference: an `inference` line in Newsreader italic after the ∴ icon ("a Portuguese postcode; area 4050 is central Porto"). Estimate: `console-data` in `solver` after the ≈ icon, with its range ("Porto 0.47"). Never merge two registers in one line.
3. **Uncertainty comes first.** Show ranges, radii, `not_visible`, unknowns, contradictions and ruled-out places. An unknown radius is drawn as an open dashed ring with "?", never as a dot. Confidence moves both ways: contradicting evidence visibly widens a range.
4. **Three actors.** Models observe (`model`, eye icon), the solver decides (`solver`, balance icon, "code, not a model"), the team answers (`team`, person icon). Every chip, log row and stage names its actor in words as well as colour.
5. **Cost before click.** Every action that costs points carries a `CostTag` before it is taken (×0.95 answer, ×0.8 cue), and the running multiplier stays visible (`MultiplierChip`).
6. **Cases stay sealed.** `CaseCard` and `QueueCard` show status only: no images, no dates, no shared evidence.
7. **Motion is evidence.** Every animation follows a real state change. No spinners and no fake progress; the one ambient loop is `Thinking`, and only while a stage really runs.
8. **One component set, two densities.** The same components serve the operator and the room; wrap a subtree in `Density value="stage"` for the projector.

## Copy

Write like a careful surveyor's field notes: plain, exact, unhurried. Sentence case everywhere; the only capitals in the system are the verdict stamps (`stamp`). No exclamation marks, no "magic", no "AI found". Components talk about the agent in the third person ("the solver decided", "worded by Qwen3.5-9B") and address the team as "you" only in confirmations.

| Say | Never say |
|---|---|
| Best estimate · ± 22 m | Found it! · Exact location |
| Ruled out because Portuguese postcode format and Portuguese spelling | Not Spain |
| Estimate, not a calibrated probability · Porto 0.47 | 47% chance it's Porto |
| Can't tell (`not_visible`) | Failed to detect |
| Skip · free · changes nothing | Skip if unsure · No |
| Describe timed out after 45 s. Fallback ran: Gemma 4 12B. | Something went wrong |
| Representative point, not a camera position | Location |

- Numbers: coordinates to 5 decimals with a true minus, latitude first, always with the order stated ("Latitude, longitude · WGS84"); distances in m under 1 km, then km with one decimal; times as mm:ss; estimates to 2 decimals (0.62, never 0.6213); multipliers as ×0.95.
- Expected scores are always labelled "estimate" and prefixed with ≈. Show the maximum beside them ("≈ 12,500 of 16,050").
- Languages are lowercase codes: pt, gl, es, ca, eu, fr. Place names keep their own spelling (Évora, Castilla y León, Vila Nova de Gaia).
- `CaptionBar` text is one plain sentence: "Reading signs: a postcode in a format only Portugal uses".
- Errors explain what happened and what ran instead. They never apologise.

## Colour

The base is quiet: deep Atlantic ink in dark (`surface-0` to `surface-3`), limestone paper in light. Colour is spent only on meaning, and every meaning is paired with an icon or a word.

| Role | Tokens | Material | Means |
|---|---|---|---|
| Model | `model`, `model-soft`, `on-model` | azulejo cobalt | something a local model observed |
| Solver | `solver`, `solver-soft`, `on-solver` | Pombaline ochre | what our fusion code estimated or decided; the final mark |
| Team | `team`, `team-soft`, `on-team` | jacaranda | what a human did (answer, cue, submit) — never Skip |
| Cost | `cost`, `cost-soft`, `on-cost` | roof-tile terracotta | any point multiplier, and the time budget past 80% |
| Supports | `support`, `support-soft` | verdigris | evidence raises a candidate (▲) |
| Contradicts | `contra`, `contra-soft`, `on-contra` | port | evidence lowers a candidate (▼); a stage failed or timed out |
| Neutral | `neutral` (= `ink-3`) | granite | evidence that says nothing either way (●) |
| Options A–D | `opt-a`…`opt-d` (+ `-soft`, `on-`) | — | identity only, never meaning; always with the letter and a hatch angle |
| Confidence | `conf-high`, `conf-med`, `conf-low`, `conf-unknown` | ink ramp | three cells + a word; unknown is dashed, never "low" |
| Stage status | `status-queued` … `status-timeout` | aliases | icon + word: ○ queued, ● running, ✓ done, hop skipped, × failed, ⧖ timed out |
| Heat | `heat-0`…`heat-5` | cobalt | one sequential hue, transparent at the low end |
| Scene classes | `seg-sky` … `seg-masked` | natural | segmentation tint and the visible-share bar, in that order |
| Map base | `map-water`, `map-land`, `map-land-out`, `map-border`, `map-border-country`, `map-graticule`, `map-label` | desaturated | so data reads first |

- Body text is `ink-1` on any surface; secondary `ink-2`; captions and units `ink-3`. All three hold 4.5:1 on `surface-0` to `surface-3` in every theme.
- Role colours are text-safe on `surface-1` to `surface-3` and on their own `-soft`. Text on a solid role fill uses `on-<role>`, never white.
- Cork-oak green, the brief's fifth material, is option B (`opt-b`). Jacaranda replaces it as the team colour because green beside verdigris and ochre fails colour-blind separation.
- Option colours are chosen to sit between the role hues and at matched weight, so no option looks preferred. Polarity chips inside a question card keep their glyphs.
- `select` (white in dark) is the linked-selection outline and leader line. `focus` is the keyboard ring (see Lines and focus).
- Three themes: **Dark** (console default), **Light** (case report, print), **Stage** (projector: deeper ground, larger steps between surfaces, brighter accents). Force a subtree with `Density theme="stage"` or `data-theme`.

| Token | Dark | Light | Stage |
|---|---|---|---|
| `surface-1` | `#0d1d2a` | `#f5f3ef` | `#0b2031` |
| `ink-1` | `#ecf1f5` | `#0f1f2f` | `#f9fcfe` |
| `model` | `#5ba0fa` | `#114278` | `#71b1ff` |
| `solver` | `#f4d16d` | `#5d4201` | `#ffda74` |
| `team` | `#cebafe` | `#7453ae` | `#dacbff` |
| `cost` | `#fc9252` | `#aa4d0a` | `#fd974e` |
| `support` | `#8be1cb` | `#0c736a` | `#81f2c1` |
| `contra` | `#d27ba6` | `#730a48` | `#ee82b8` |

## Type

Three faces, three voices. All are open-licence (SIL OFL), self-hosted from `fonts/`, and cover Portuguese, Spanish, French, Catalan, Galician and Basque (ç ã õ ñ l·l; the precomposed ŀ falls back to the system face).

- **Atkinson Hyperlegible Next** (`--font-sans`) — the interface. Built so I, l and 1, and O and 0 never collide; this app reads signs, so that matters.
- **Atkinson Hyperlegible Mono** (`--font-mono`) — every reading, coordinate, score, time and estimate. Use it for numbers and verbatim OCR text only, not for labels.
- **Newsreader** (`--font-serif`) — the narrator: stage headlines (`narrative-headline`), titles (`narrative-title`), large display lines such as the stage roster (`narrative-display`) and inference lines (`inference`, italic). It never carries a number.

Pick styles by density through the type helper (`useT()` in the bundle): console uses `console-*` (body 13/18), stage uses `stage-*` (body 24/32, nothing under 20 px). Arrows and triangles are drawn as icons, not glyphs.

## Space, shape and lines

- 4 px base: `space-half` 2 px gaps between marks; `space-2`–`space-4` inside console components; stage doubles the step (`space-4`–`space-8`).
- Corners say what kind of thing it is: `radius-0` for imagery and maps, `radius-1` for chips and keys, `radius-2` for controls and cards, `radius-3` only for sealed case cards, dialogs and toasts, `radius-pill` for toggles and the replay badge.
- Borders, not shadows, separate things at rest: `line-1` hairlines, `line-2` for control edges (3:1). `shadow-float` and `shadow-dialog` only for what floats.
- Stage doubles every hairline (`border-rule`) so it survives a projector.
- **Focus**: `focus-ring` everywhere — a 2 px gap in `surface-1`, then 2 px solid `focus` (12:1 dark, 7.8:1 light).

## Iconography

A custom set drawn for Aqui on a 16 px grid: 1.5 px stroke, square caps, mitred joins, `currentColor`. Filled shapes are reserved for polarity (▲ supports, ▼ contradicts, ● neutral) so they survive print and colour-blindness. No emoji. An icon never carries meaning alone — pair it with a word. The set lives in the `Icon` component and as SVG files under Icons (drawn in `#0f1f2f`, ink-1 light; recolour when inlined). Logos: the wordmark for light and dark grounds and the favicon mark.

## Imagery and the map

- The panorama is the hero. Overlays draw a dark halo under every stroke (`photo-halo`) and put labels on dark plates (`on-photo`), so they read on any photo.
- At console density, label only the selected box and text readings (`labelMode`); at stage density, label the one focus.
- The map base is desaturated; layers stack base < heat < zones < points < rings < pins < labels. When a question is open or an item is selected, heat and points dim to `opacity-dim`.
- Water names are Newsreader italic, places are sans — classic cartographic convention.
- The final pin is a surveyor's trig mark (`SurveyMark`), not a teardrop.
- The panoramas and street maps in the previews are procedural stand-ins drawn in muted illustration colours; in the app they are the real JPG and MapLibre tiles (or bundled PT/ES/FR outlines when offline).

## Using the components

Components are React 18 function components. Import them by name from `components/src` (the app aliases it as `@ds`), or load `components/bundle.js` and `components/bundle.css` after `tokens.css` and use `window.Aqui`. Each takes plain props, so the same render works live and in a replay. `Aqui.Samples` holds two sample cases that feed the previews only. Props are in each component's README and in `components/index.d.ts`.
