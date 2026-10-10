# Data visualisation

Model outputs are estimates, not calibrated probabilities. Label them so, show ranges where known, and round to two decimals. Colour is never the only channel: every chart pairs it with a label, a glyph, a pattern or position.

| Chart | Component | Rules |
|---|---|---|
| Language vote | `LanguageVote` (on `StackedBar`) | One 100% bar across pt / gl / es / ca / eu / fr; identity by label, the model hue alternates in two steps (`model`, `model-soft`); 2 px gaps; caption "Share of votes, not a probability of country". Absent (not zero) when there is no text. |
| Scene shares | `SceneShares` | One 100% bar in the fixed order sky, building, grass, tree, road, water, ground, masked (`seg-*`); masked is hatched; caption "visible share, not land cover". The order keeps every neighbour pair at least 18 ΔE apart for protan and deutan vision. |
| Compass | `CompassDial` | Image yaw 0 as a line, true north as N, the sun's azimuth as a marker whose distance from the rim encodes elevation, the error as a wedge in `solver`. No sun: no N, the yaw line dashed, "north unknown". |
| Region estimates | `EstimateBars tone="model"` | Top 5 + "other" (other in `ink-3`), range brackets where known, values at right in mono. |
| Candidates | `CandidateRow`, `EstimateBars tone="solver"` | Solver bar with a range bracket, change since last update with ▲/▼, support and contradict counts. Before/after mode draws the old value as a dashed outline. |
| Distance to score | `ScoreCurve` | θ for Urban (solid) and non-Urban (dashed) over a log axis 10 m–100 km, share of 1000 × θ kept (0–100%); marks at 25 m, 100 m, 1 km, 5 km, 10 km; the current uncertainty band in `solver`; the expected score beneath. Label unknown: both curves at full weight and both expected scores. |
| Question value | `GainMeter` | Expected gain as a bar on a 0–30% scale, a `cost` line at 5.26% (×0.95 break-even) and a dashed line at 25% (cue ×0.8); the verdict in words. |
| Heatmap | `MapView heat` | Square cells, one hue (`heat-1`…`heat-5`), `heat-0` transparent so the map shows through. No blur, no rainbow. |
| Confidence | `ConfidenceMeter` | Three cells + value + word; unknown is three dashed cells and the word "unknown". |
| Rank weights | `AnswerSlots` | Ten bars at 1.00 … 0.63 under the coordinate shown once ×10. |

Scoring reference used by the charts: the top slot scores 1000 × θ, each step down × 0.95; Urban θ = 2 / (1 + d/100), non-Urban θ = 2 / (1 + d/10000), d in metres, under 10 m counts as 0; maximum 16,050.52 (48,151.57 for the Special One). An answered question pays off above +5.26% expected gain; a cue above +25%.

| Distance error | Urban keeps | Non-Urban keeps |
|---|---:|---:|
| 25 m | 80% | 99.8% |
| 100 m | 50% | 99.0% |
| 1 km | 9.1% | 90.9% |
| 5 km | 2.0% | 66.7% |
| 10 km | 1.0% | 50.0% |

Charts are interactive in the app: hover a bar, cell or segment for its exact value and source event; every chart has a table view in the case report.
