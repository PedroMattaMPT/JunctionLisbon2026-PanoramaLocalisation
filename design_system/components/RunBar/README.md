# RunBar

The always-visible run bar: case and Special One badge, Urban label and source, this-panorama timer, session clock, multiplier, expected score, GPU memory and worker status.

- **Provide:** `c` (the case record: `label`, `urban`, `urbanSource`, `special`, `run` {`used`, `budget`, `session`, `sessionBudget`, `gpu`, `gpuMax`, `multiplier`, `expected`, `split`}, `multiplierHistory`), optional `online`, `tilesOffline`, `replay` (speed).
- With the Urban label unknown it shows both expected scores. Sticky at `z-runbar`.
