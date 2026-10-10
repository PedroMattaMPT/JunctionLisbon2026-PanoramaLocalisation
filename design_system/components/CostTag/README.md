# CostTag

The multiplier an action will apply, shown before it is taken: tag icon + ×0.95 in `cost` on `cost-soft`.

- **Provide:** `multiplier` (0.95 answer, 0.8 cue, 0.5 human place-name conversion), optional `label`.
- Sits inside `Button`, on every `QuestionOption`, in the `CueComposer` header and in confirm dialogs. Tooltip: "Costs ×0.95 on every guess after this".
- Never use `cost` colour for anything that does not spend points or time.
