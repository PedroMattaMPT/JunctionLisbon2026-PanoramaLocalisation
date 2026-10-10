# Hard problems, solved

How the system handles the nine problems the brief names. Each answer points at the component that carries it.

## 1. Skip feels neutral and free, never like "no"

- `Button variant="skip"`: a dashed outline in `line-2`, ink text, the skip icon, a `free` tag in mono and the S key. It is not red, not grey-disabled, not shaped like an option, and sits apart from the options in the card footer.
- The note beside it says exactly what happens: "Changes nothing. Not read as 'no' or 'none of these'." Questions never say "skip if…".
- "None of these" exists only when the agent made it one of the options; it is option D with its own key and colour, and its row says "Exists only because the agent made it an option."
- After a skip, `AnswerReceipt kind="skipped"` renders the same estimate bars with before = after, the multiplier marked "unchanged", and three ticks: beliefs unchanged, logged as skipped, no cost. Motion: nothing moves (Beat 10, frame 4).
- The log records `question.skipped`; the solver never reads it as evidence.

## 2. Unknown uncertainty is not small uncertainty

- A known radius is a solid `solver` ring with a light fill and a label "± 22 m" plus its source (geometric bound, source estimate, estimated offset).
- An unknown radius is an open, dashed `ink-1` ring drawn at a fixed generous size with an inner dotted ring and a "?" — it reads as "we don't know how far", never as a point. Text says "± unknown · no bound yet · not zero" (`UncertaintyRing`, `MapView rings[].r = null`).
- A known radius smaller than a pixel at the current zoom keeps a 4 px minimum ring and says "(smaller than a pixel here)".
- Confidence uses the same rule: `ConfidenceMeter` draws unknown as three dashed empty cells with the word "unknown", never as one cell.

## 3. Correlated sources speak as one voice

- Neighbours (PE-Core kNN), mini-PIGEON regions and any other source on the same encoder sit inside one `CorrelationBracket`: a `solver` bracket line, the label "One voice: PE-Core encoder" and a badge "weight capped at 0.35".
- In `EvidenceMatrix` the grouped rows share a left rule in `solver` and the group name on the first row; the totals row says "correlated rows count once".
- Motion: in Fusion the cards slide together under the bracket before any weight reaches the candidates (Beat 8, frame 2).

## 4. One piece of evidence, linked to its pixels and its map area at once

- Every evidence item, box, text reading, candidate pin and map area carries the same `data-link` id. Selecting one sets `selected` on all three views.
- `PanoramaStrip` outlines the pixels in `select` with a marker on the bearing ruler; `MapView` outlines the area (`area`) or pin in `select`; `EvidenceCard` takes a `select` border.
- `LeaderLines` draws a curved line with end dots from the card to the box and from the card to the map area, with a dark halo so it reads across panels.
- Everything else dims to `opacity-dim` when `dimOthers` is set.

## 5. The flat strip and the 360° viewer stay in sync

- Both views share one yaw. The strip shows the viewer's field of view as corner brackets labelled "360° view · yaw 212°", and the bearing ruler shows the same window as a bar.
- `Viewer360` shows yaw, bearing (once north is known, with its ± error) and field of view in its caption, plus "synced with strip". If the user drags past a threshold without releasing, it says "not synced — click to re-sync" in `cost`.
- Selections are shared: a box selected in either view is outlined in both.

## 6. The cost of every action is visible before it happens

- `CostTag` (tag icon + ×0.95) sits on every costing button and on every option row; the question footer restates "Any answer costs ×0.95 on every guess after it, right or wrong."
- `CueComposer` shows ×0.8 in its header and the +25% break-even, blocks place names, hints and coordinates, and has a confirm step that restates the cost.
- `MultiplierChip` is always in the run bar; its history lists every step with its log time.
- Every output carries the multiplier at the moment it was produced (`CoordinateBlock`, `AnswerSlots` penalty snapshot).

## 7. A room stays engaged through 1–3 minutes of real compute, with no fake progress

- The stage view always shows one real thing happening: the current stage's caption ("Reading signs: …"), its model chip, the log time and replay speed.
- Waits are honest: `StageRow` shows real elapsed seconds against the stage's real deadline and names the fallback; `WaitState` names what is running and counts partial results ("4 of 11 checklist items answered so far").
- Evidence arrives as events (boxes, readings, checklist ticks), each with a short motion beat, so a 20-second describe stage still produces visible steps.
- Replays at 2× and 5× show a speed badge and keep real timestamps.

## 8. The map stays readable with heat, points, zones, rings and pins at once

- Fixed layer order: base < heat < zones < sampled points < reference photos < rings < pins < final mark < labels.
- Heat is square cells in one hue with a transparent low end, so the base shows through; sampled points are 1.6 px dots; reference photos are hollow squares; candidates are filled numbered discs; the final mark is a triangle-in-circle.
- Zones use outline + a hatch at a different angle per letter (A 45°, B −45°, C 0°, D 90°) + the letter key; the catch-all zone uses a sparser, lighter hatch.
- Labels carry a halo in the map's water colour; zone labels are short and the legend explains "key = representative point, not a camera position".
- Focus modes dim everything not linked to the current item; the legend lists only the layers on screen.

## 9. The same coordinate ten times doesn't look like a bug

- `AnswerSlots` shows the coordinate once with a large "×10", then the ten rank weights as a small bar row (1.00 → 0.63), then "Same coordinate in all 10 — our default: the one with the highest expected score".
- The full ten-row table is one click away and shows each slot's rank weight, penalty snapshot and production time.
- `ChoiceNote` says whether the chosen coordinate is the most likely candidate, and when it is not (Case B) explains why the hedge scores higher in expectation, with both expected scores.
