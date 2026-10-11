# Patterns

Rules that span several components. Each one names the components and options that carry it.

## Skip looks neutral and free, never like "no"

- `Button variant="skip"`: a dashed outline in `line-2`, ink text, the skip icon, a `free` tag in mono and the S key. It is not red, not grey-disabled, not shaped like an option, and sits apart from the options in the card footer.
- The note beside it says exactly what happens: "Changes nothing. Not read as 'no' or 'none of these'." Never write "skip if…".
- "None of these" is a normal `QuestionOption` (`none`) with its own key and colour, never a styled Skip.
- `AnswerReceipt kind="skipped"` renders the same estimate bars with before = after, the multiplier marked "unchanged", and three ticks: beliefs unchanged, logged as skipped, no cost.

## Unknown uncertainty is not small uncertainty

- A known radius is a solid `solver` ring with a light fill, a label ("± 22 m") and its source (geometric bound, source estimate, estimated offset).
- An unknown radius is an open, dashed `ink-1` ring at a fixed generous size with an inner dotted ring and a "?". Text: "± unknown · no bound yet · not zero" (`UncertaintyRing`, `MapView rings[].r = null`).
- A known radius smaller than a pixel at the current zoom keeps a 4 px minimum ring and says "(smaller than a pixel here)".
- `ConfidenceMeter` draws unknown as three dashed empty cells with the word "unknown", never as one cell.

## Correlated sources read as one voice

- Members of a correlated group sit inside one `CorrelationBracket`: a `solver` bracket line, the label ("One voice: PE-Core encoder") and a cap badge ("weight capped at 0.35").
- In `EvidenceMatrix` the grouped rows share a left rule in `solver` and the group name on the first row; the totals row counts the group once.

## Linked selection

- Every evidence item, box, text reading, candidate pin and map area carries the same `data-link` id. Selecting one sets `selected` on each view that shows it.
- `PanoramaStrip` outlines the pixels in `select` with a marker on the bearing ruler; `MapView` outlines the area or pin in `select`; `EvidenceCard` takes a `select` border.
- `LeaderLines` draws a curved line with end dots from the card to the box and to the map area, with a dark halo so it reads across panels.
- With `dimOthers`, everything else dims to `opacity-dim`.

## Strip and 360° viewer share one yaw

- `PanoramaStrip` shows the viewer's field of view as corner brackets labelled "360° view · yaw 212°", and `BearingRuler` shows the same window as a bar.
- `Viewer360` shows yaw, bearing (with its ± error once known) and field of view in its caption, plus "synced with strip", or "not synced — click to re-sync" in `cost`.
- A box selected in either view is outlined in both.

## Cost shows before the click

- `CostTag` (tag icon + ×0.95) sits on every costing `Button` and on every `QuestionOption`; the question footer restates the cost in words.
- `CueComposer` shows ×0.8 in its header with its break-even, blocks place names, hints and coordinates, and confirms with a `Dialog` that restates the cost.
- `MultiplierChip` lists every step in its history. `CoordinateBlock` and `AnswerSlots` carry the multiplier at the moment the output was produced.

## Waits are real

- `StageRow` shows real elapsed seconds against the stage's deadline and names the fallback; `WaitState` names what is running and counts partial results ("4 of 11 checklist items answered so far").
- No spinners, percentages or invented progress anywhere. Replays show `SystemBadge kind="replay"` with the speed and keep real timestamps.

## Map layers stay readable together

- Fixed layer order: base < heat < zones < sampled points < reference photos < rings < pins < final mark < labels.
- Heat is square cells in one hue with a transparent low end; sampled points are 1.6 px dots; reference photos are hollow squares; candidates are filled numbered discs; the final mark is `SurveyMark`.
- Zones use an outline, a hatch at a different angle per letter (A 45°, B −45°, C 0°, D 90°) and the letter key; a catch-all zone uses a sparser, lighter hatch.
- Labels carry a halo in the map's water colour. `MapLegend` lists only the layers on screen and says "key = representative point, not a camera position".
- When a question is open or an item is selected, heat and points dim to `opacity-dim`.

## The same coordinate ten times doesn't look like a bug

- `AnswerSlots` shows the coordinate once with a large "×10", then the ten rank weights as a small bar row (1.00 → 0.63), then the reason in one line. The full ten-row table opens from it.
- `ChoiceNote` says whether the chosen coordinate is the most likely candidate and, when it is not, why the hedge scores higher, with both estimates.
