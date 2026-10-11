# Accessibility

Targets: WCAG 2.2 AA in all three themes, a colour-blind-safe semantic palette, full keyboard operation, and reduced motion. All figures below are computed from `tokens.json`, not eyeballed.

## Contrast

Text needs 4.5:1; control edges, focus rings, icons and other meaningful marks need 3:1. Each row is the lowest ratio of that foreground across the grounds its usage note names.

| Foreground | Lowest ratio across these grounds | Dark | Light | Stage |
|---|---|---:|---:|---:|
| `ink-1` | `surface-0`, `surface-1`, `surface-2`, `surface-3` | 12.1 | 13.8 | 11.1 |
| `ink-2` | `surface-0`, `surface-1`, `surface-2`, `surface-3` | 8.2 | 8.3 | 8.9 |
| `ink-3` | `surface-0`, `surface-1`, `surface-2`, `surface-3` | 5.9 | 5.5 | 7.1 |
| `model` | `surface-1`, `surface-2`, `surface-3`, `model-soft` | 5.1 | 8.4 | 5.1 |
| `solver` | `surface-1`, `surface-2`, `surface-3`, `solver-soft` | 9.3 | 7.8 | 8.5 |
| `team` | `surface-1`, `surface-2`, `surface-3`, `team-soft` | 7.9 | 4.8 | 7.6 |
| `cost` | `surface-1`, `surface-2`, `surface-3`, `cost-soft` | 6.1 | 4.6 | 5.3 |
| `support` | `surface-1`, `surface-2`, `surface-3`, `support-soft` | 9.0 | 4.7 | 8.4 |
| `contra` | `surface-1`, `surface-2`, `surface-3`, `contra-soft` | 4.7 | 9.3 | 4.6 |
| `opt-a` | `surface-1`, `surface-2`, `surface-3`, `opt-a-soft` | 8.0 | 8.2 | 7.1 |
| `opt-b` | `surface-1`, `surface-2`, `surface-3`, `opt-b-soft` | 4.9 | 4.7 | 5.2 |
| `opt-c` | `surface-1`, `surface-2`, `surface-3`, `opt-c-soft` | 8.2 | 7.2 | 7.6 |
| `opt-d` | `surface-1`, `surface-2`, `surface-3`, `opt-d-soft` | 4.9 | 5.2 | 5.2 |
| `on-model` | `model` | 6.9 | 9.8 | 8.7 |
| `on-solver` | `solver` | 12.5 | 9.1 | 14.3 |
| `on-team` | `team` | 10.6 | 5.7 | 12.8 |
| `on-cost` | `cost` | 8.2 | 5.4 | 8.9 |
| `on-contra` | `contra` | 6.3 | 10.9 | 7.8 |
| `on-opt-a` | `opt-a` | 10.8 | 9.6 | 12.0 |
| `on-opt-b` | `opt-b` | 6.6 | 5.5 | 8.7 |
| `on-opt-c` | `opt-c` | 11.0 | 8.4 | 12.8 |
| `on-opt-d` | `opt-d` | 6.6 | 6.1 | 8.8 |
| `line-2` (control edges, 3:1) | `surface-1`, `surface-2` | 3.3 | 3.6 | 4.4 |
| `focus` (ring, 3:1) | `surface-0`, `surface-1`, `surface-2`, `surface-3` | 12.1 | 7.8 | 11.1 |
| `map-label` | `map-land`, `map-water` | 6.3 | 5.2 | 8.5 |
| `map-border-country` (3:1) | `map-land`, `map-water` | 3.1 | 3.3 | 4.4 |

- Every pair passes in every theme. The tightest are `contra` on dark surfaces (4.6–4.7) and `opt-b`/`opt-d` (4.7–5.2); they are never used below 12 px.
- Labels on the panorama are white on a 70% black plate (`on-photo` on `photo-halo`), which holds 4.5:1 over any photo.
- Disabled labels (`ink-disabled`) are exempt and never carry information.

## Colour-blindness

Separation is measured as OKLab ΔE ×100 under protanopia and deuteranopia (Machado 2009, severity 1.0); 8 is the target, 6 the floor when a second channel (glyph, letter, hatch, label) is always present. The normal-vision floor is 15.

| Set | Pairs checked | Dark: worst CVD ΔE (pair) · normal ΔE | Light | Stage |
|---|---|---|---|---|
| Actors, cost, polarity | all 15 pairs | 8.6 (team / support) · 14.7 | 9.1 (solver / cost) · 15.7 | 9.0 (solver / support) · 15.3 |
| Options A–D | all 6 pairs | 10.9 (opt-b / opt-c) · 19.9 | 7.0 (opt-a / opt-d) · 15.9 | 6.9 (opt-a / opt-d) · 16.7 |
| Scene classes | adjacent in the bar | 18.0 (seg-water / seg-ground) · 22.8 | 18.3 (seg-water / seg-ground) · 22.7 | 19.0 (seg-water / seg-ground) · 23.3 |

- Actors, cost and polarity clear 8.6 everywhere. The one pair just under the normal-vision floor (solver vs cost in dark, 14.7) never sits side by side as fills, and cost always carries its × figure and tag icon.
- Options A–D clear the floor in light and stage (7.0, 6.9) and always show their letter and a hatch at their own angle, so hue is the third channel, not the first.
- Supports and contradicts are verdigris and port, not green and red, and always carry ▲ or ▼. Stage failure uses the same port with a × or ⧖ icon and the words "Failed" or "Timed out".
- Confidence is a lightness ramp plus a cell count plus a word.

## Keyboard

- One focus ring everywhere (`focus-ring`: 2 px surface gap + 2 px `focus`, at least 7.8:1).
- `Tabs`, `Segmented` and option lists move with the arrow keys, Home and End.
- `Dialog`, `Modal` and the Details sheet trap focus, close with Esc and return focus to where it was.
- `QuestionCard` and `FocusQuestion` are radio groups: 1–4 answer, S skips. Every key appears as a `KeyCap` beside its action, and no shortcut fires while a text field has focus.
- Interactive marks on the strip, matrix and map take focus like buttons.
- Focus order follows reading order within each component; the order across components is the app's to set.

## Screen readers

Charts carry an `aria-label` with their values; `StageRow` and `WaitState` use `aria-live="polite"` and announce real times; `CaptionBar`, `Thinking`, `FocusQuestion` and `WorkerBanner` are polite live regions; the map has a text equivalent in `CandidateList`; the question card is a radio group.

## Reduced motion

With `prefers-reduced-motion: reduce`, every animation becomes a 180 ms cross-fade (`dur-quick`), counts jump to their final value, map flights cut and ambient loops play once. Motion never carries information on its own.

## Projector check

The stage theme was tuned for a washed-out 1920×1080 projector: a deeper ground (`surface-0` #010f1e), wider lightness steps between surfaces (0.06–0.07 OKLCH L), brighter accents, doubled line weights (`border-rule`), and no text under 20 px. Check the room once with `ModelRoster` at stage density: if the model list reads from the back row, everything else will.
