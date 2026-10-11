# Implementation

React 18 + TypeScript + Tailwind 3. Every design option is a CSS variable compiled from `tokens.json`, and every component reads only those variables.

## Tokens

- `tokens.json` is the single source (colour in three themes, type, spacing, radius, shadow, border, z-index, duration, easing, opacity, size). It compiles to `tokens.css`: `:root, [data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="stage"]`, one class per type style (`.console-body`, `.stage-caption`, `.inference`…) and the `@font-face` rules. The app generates it with `app/scripts/build-tokens.mjs`.
- Tailwind: `code/aqui.tailwind.preset.js` maps every utility to the same variables — `bg-surface-2`, `text-ink-2`, `text-solver`, `border-line-2`, `rounded-2`, `p-3`, `shadow-focus`, `duration-quick`, `ease-enter`, `z-dialog`, and font sizes named after the type styles (`text-console-body`). Themes switch by setting `data-theme` on any ancestor; no rebuild.
- Density: set `data-density="stage"` (or wrap in `Density value="stage"`) and components switch to the `stage-*` type styles and doubled spacing and lines.

```js
// tailwind.config.js
module.exports = { presets: [require('./aqui.tailwind.preset.js')], content: ['./src/**/*.{ts,tsx}'] };
```

## Fonts

Self-hosted variable WOFF2 files in `fonts/` (subset to Latin, Latin-1, Latin Extended-A/B and punctuation, maths and arrows ranges): Atkinson Hyperlegible Next (roman and italic, 200–800), Atkinson Hyperlegible Mono (200–800), Newsreader (roman and italic, 200–800, optical size 6–72). Licences (SIL OFL 1.1) are in `licences/`. No runtime CDN.

## Components ↔ code

Component names map 1:1 to code in `components/src/`, grouped by module: `base` (buttons, tabs, dialogs, states), `shell` (run bar, timers, cases, models), `panorama`, `reasoning` (stages, evidence), `beliefs` (candidates, matrix), `charts`, `map`, `human` (questions, cues), `output` (coordinate, slots, log, replay, export) and `extra` (filename, drop zone, match, leader lines).

- **In a Vite app:** alias the folder (`'@ds': 'design_system/components/src'`), import by module (`import { Button } from '@ds/base'`), set `window.React` before the first import (`app/src/react-global.ts`), and import `components/bundle.css` after `tokens.css`.
- **In a static page:** load `components/bundle.js` and use `window.Aqui`.
- Props are in each component's README and in `components/index.d.ts`.
- `screens.tsx` and `docs.tsx` still hold the old showcase pages and the brand-book frame for the bundle. They are not part of the system and nothing in the app imports them.

## Panorama overlays

Overlays on `PanoramaStrip`, `Viewer360` and `ZoomCrop` take angular boxes (`yaw`, `pitch`, `w`, `h` in degrees), so one box places itself in all three. On the strip, x = yaw / 360 × width and y = (90 − pitch) / 180 × height, with yaw 0 at the left edge. `BearingRuler` maps bearing = yaw + the north offset once one is known.

## Map styling

Style the base with the `map-*` tokens (read them from computed styles at load and on theme change): water `map-water`, land `map-land`, other countries `map-land-out`, admin-1 lines `map-border`, national lines `map-border-country`, labels `map-label` with a halo. Data layers: heat as a grid of fill squares in `heat-1`…`heat-5`; zones as fill + line + a hatch pattern per option; rings as circles in metres, with an unknown radius as a dashed line at a fixed pixel size. Without tiles, `MapView` falls back to its bundled outlines of PT, ES and FR with admin-1 borders.

## Placeholder imagery

The previews draw a procedural urban riverfront and a rural montado as equirectangular strips and rectilinear views, plus schematic Porto streets (`components/src/scene.ts`). They are illustration stand-ins, and their colours are deliberately not tokens.
