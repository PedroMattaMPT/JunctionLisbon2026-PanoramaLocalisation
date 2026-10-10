# CueComposer

A free-text cue to the agent: character counter, ×0.8 before sending, a check that blocks place names, hints and coordinates, then a confirm step.

- **Provide:** optional `text`, `confirm`, `max` (1000), `sent`.
- The check flags gazetteer names, known hint phrases (big-wave surfing → Nazaré) and coordinate patterns. Sending stays disabled while anything is flagged.
