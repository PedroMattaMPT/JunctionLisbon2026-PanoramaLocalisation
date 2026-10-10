# StageRow

One pipeline stage: status as icon + word, its models, real duration and memory; running shows real elapsed seconds against the stage deadline; failures name the fallback that ran.

- **Provide:** `stage` (`name`, `models`, `status` = `queued` | `running` | `done` | `skipped` | `failed` | `timed_out`, `dur`, `deadline`, `gb`, `cpu`, `optional`, `note`, `fallback`), optional `compact`, `pass`.
- Works for any stage name and any model names.
