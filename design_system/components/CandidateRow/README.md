# CandidateRow

A candidate: rank, name and level, the solver's estimate bar with its range, change since the last update, and support/contradict counts.

- **Provide:** `c` (`id`, `rank`, `name`, `level`, `v`, `lo`, `hi`, `delta`, `sup`, `con`, `other`, `contradictedBy`, `keptNote`, `lookalike`), optional `selected`, `max`, `showDelta`, `ghost`.
- Two lines so it fits a 400 px column. Estimates, not probabilities: round to 0.01.
