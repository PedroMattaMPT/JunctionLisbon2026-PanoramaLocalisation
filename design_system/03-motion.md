# Motion

Every animation follows a real state change in the component's props, so a replay animates exactly like the live run. Design each state so it can animate into the next.

## Tokens

| Token | Value | Use |
|---|---|---|
| `dur-instant` | 90 ms | hover and press |
| `dur-quick` | 180 ms | small state changes, status icon swaps, reduced-motion cross-fades |
| `dur-standard` | 280 ms | cards and panels entering or leaving |
| `dur-deliberate` | 520 ms | estimate bars, uncertainty rings, multiplier tick |
| `dur-cinematic` | 1400 ms | map flights at one zoom step; scale 1000–2000 ms by zoom levels crossed |
| `dur-stagger` | 40 ms | between list items (30–60 ms) |
| `dur-stagger-cap` | 480 ms | the total stagger never exceeds this |
| `ease-enter` | cubic-bezier(0.16, 1, 0.3, 1) | entrances |
| `ease-exit` | cubic-bezier(0.7, 0, 0.84, 0) | exits, ghosting |
| `ease-move` | cubic-bezier(0.65, 0, 0.35, 1) | in-place change: bars, rings, flights, ruler turning |
| `ease-spring` | linear(…) gentle overshoot | `SurveyMark` only |

At replay speeds of 2× or 5× the waits between changes shrink; the durations above do not.

**Reduced motion:** every animation becomes a `dur-quick` cross-fade, counts jump to their final value, map flights cut, and the ambient loops play once. Motion never carries information on its own: every moving thing also changes a number, a word or a mark.

## Component motion

| Component | Change | Motion |
|---|---|---|
| `PanoramaStrip` boxes | boxes arrive | corner brackets scale 0.92 → 1 and fade in, `dur-quick`, `ease-enter`, staggered `dur-stagger` up to `dur-stagger-cap`; labels follow once the box settles |
| `PanoramaStrip` boxes | a box is rejected | dashed and struck (`dur-quick`), then fades to `opacity-ghost` (`dur-standard`, `ease-exit`); it stays visible |
| `EvidenceCard` | a card arrives | lifts into the feed, `dur-standard`, `ease-enter` |
| `PolarityChip`, `EstimateBars` | weight reaches a candidate | ▲ / ▼ chips tick in sequence while bars grow, `dur-deliberate`, `ease-move` |
| `CorrelationBracket` | members are grouped | cards slide together under the bracket; the cap badge comes last |
| `EvidenceCard kind="contradiction"` | a contradiction is found | its two sources outline twice (2 × `dur-quick`, no loop) and the affected range visibly widens |
| `RuledOutRow` | a candidate is ruled out | strikes, then ghosts with its reason; it never leaves the list |
| `MapView` | the estimate narrows | the camera flies country → region → town, `dur-cinematic`, never tighter than the current uncertainty |
| `MapView` zones | a question opens | outlines draw A → D (`dur-standard` each, staggered), the hatch fades in after, heat dims |
| `QuestionCard`, `GainMeter` | a question opens | the card rises; the gain bar fills once |
| `QuestionCard` | answered | the chosen zone thickens, the others dim, and `MultiplierChip` ticks ×1.00 → ×0.95 in place, `dur-deliberate` |
| `QuestionCard` | skipped | collapses to a dashed `AnswerReceipt`; nothing else moves |
| `MatchView` | a reference is compared | the reference slides in from the right (`dur-standard`); matches draw in batches, rejected ones dashed then fading; the inlier count counts up to its known number (`dur-deliberate`) |
| `UncertaintyRing` | the bound tightens | the ring contracts to the new radius (`dur-deliberate`, `ease-move`) and stops at the remaining offset |
| `SurveyMark` | the output lands | drops 12 px with `ease-spring`, the only spring; the ring settles and its label fades in |
| `AnswerSlots` | the output lands | the ten weight bars fill left to right, `dur-stagger` apart |
| `ScoreReadout size="xl"` | the output lands | counts 0 → the estimate over `dur-cinematic`, labelled "estimate" throughout |
| Case pill | a case needs an answer | its ? glyph pulses once (scale 1.25) |
| `Thinking`, scan overlay | a stage is running | ambient loop for as long as the stage runs, beside its real elapsed time |
