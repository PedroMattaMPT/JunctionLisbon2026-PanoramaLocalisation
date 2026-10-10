---
name: task
description: Add, update, delete and list tasks in TASKS.md, the team's tracker for the Albatroz panorama localisation challenge, through tools/tasks.py. Use when someone wants to add a task; start, finish, block or drop one; assign it; change its priority, phase or dependencies; or delete it. Also use when they ask what is next, what is blocked, who is on what, or where a phase or gate stands, and after you finish work that matches an open task, to record it with its evidence.
argument-hint: "[what to add, change, delete or list]"
allowed-tools: Bash(python3 tools/tasks.py:*)
---

# Task tracker

`TASKS.md` is the team's task list: one table row per task, grouped by phase, with a summary at the top. `ROADMAP.md` has the phase windows, the gates and the critical path. `PLAN.md` says what each task means, and the checkboxes in its section 5 end with task tags such as `[T10, T11]`.

Change tasks only through `tools/tasks.py`, run from the repo root. It validates every field, never reuses an ID, rewrites the summary, and ticks a PLAN.md checkbox once all its tagged tasks are done. Don't edit task rows or tick PLAN.md boxes by hand.

## Fields

| Field | Values |
|---|---|
| Phase | `A` until the Saturday 19:00 trial · `B` the trial, 19:00–21:00 · `C` overnight · `D` Sunday 08:00–10:00 · `Run` the scoring run and finals · `Backlog` optional components |
| Status | `todo`, `doing`, `blocked`, `done`, `dropped` |
| Pri | `P0` the phase's gate fails without it · `P1` core, should land in this phase · `P2` optional, only after a measured gain (PLAN.md 4.7) |
| Area | `pipeline`, `perception`, `geo`, `pixel` (the PLAN.md section 7 roles), `ui`, `team` |
| Owner | a first name; empty while nobody has picked the task up |
| Needs | IDs that must be done first |
| Notes | the latest useful fact: a blocker, the evidence, a decision |

## Commands

```bash
python3 tools/tasks.py list                      # open tasks by phase
python3 tools/tasks.py list --ready              # todo tasks with nothing left to wait on, P0 first (Backlog skipped)
python3 tools/tasks.py list --status doing,blocked
python3 tools/tasks.py list --owner Ana          # --owner none for unassigned; also --area, --phase, --pri, --all
python3 tools/tasks.py show T12                  # one task, what it needs, what needs it, its PLAN.md lines

python3 tools/tasks.py add "Build the zone boundaries from CAOP" --phase C --pri P1 --area geo --needs T04 --notes "PLAN 4.4"
python3 tools/tasks.py update T12 --status doing --owner Ana
python3 tools/tasks.py update T12 --status done --add-note "sent 18:52; organisers confirmed the format"
python3 tools/tasks.py update T14 T15 --phase B  # several IDs at once; --phase moves the rows
python3 tools/tasks.py update T33 --add-needs T06 --remove-needs T21
python3 tools/tasks.py update T44 --status dropped --add-note "OCR misses came from resolution, not detection"
python3 tools/tasks.py delete T61                # refuses while referenced; --force drops the references
python3 tools/tasks.py check                     # validate only
python3 tools/tasks.py sync                      # after a hand edit or a merge
```

`--add-note` appends a timestamped note, and `--notes` replaces the cell: use it to shorten a cell that has grown. `--needs none` and `--owner none` clear those fields.

## Handling a request

1. **Find the task first.** Use `list --all`, or grep TASKS.md for the subject. If several tasks match, show them and ask which one. If none matches, the request is new work: add it. Never add a duplicate.
2. **Map the request to a command:**
   - "I'm on X" or "Ana takes X": `--status doing --owner <name>`.
   - "X is done": `--status done --add-note "<evidence>"`. Evidence is a file or log path, a measured number or a commit. If the user gave none, ask for it rather than inventing it.
   - "X is stuck on Y": `--status blocked --add-note "<what it waits for>"`, plus `--add-needs` when Y is a task.
   - "We won't do X": `--status dropped --add-note "<reason>"`. Dropping keeps the decision visible; delete only duplicates and mistakes.
   - "What's next?" or "what can I pick up?": `list --ready`, narrowed by `--area` or `--phase` when the person has a role.
   - "Where are we?": the summary table at the top of TASKS.md, plus `list --status doing,blocked`.
3. **Write a new task like this:**
   - Title: imperative, one deliverable, about 15 words at most. Details go in Notes, with the PLAN.md section they come from.
   - Phase: the gate it serves (PLAN.md section 5).
   - Pri: P0 only if that gate fails without it.
   - Optional pipeline components go to `Backlog` at P2 until a measured gain justifies them: YOLOE, SAM 3, EoMT, sun position, grid features, the feature table, gpt-oss-20b.
   - Needs: only real blockers.
4. **Gates.** Phases A–D each have a `Gate X:` task, whose criterion is in PLAN.md section 5. Mark it done only when that criterion is met, with a note on how it was checked.
5. **Report back in a line or two:** the rows the script printed, any PLAN.md checkbox it ticked or unticked, and any warning it gave.

## Keeping the other files in step

- **PLAN.md section 5:** a new checkbox there needs a task and a tag at the end of its line, such as `[T76]`; `check` warns about untagged boxes. If a ticked box's tasks are not done, the script warns instead of unticking it: ask whether the work is done, then mark the task done or untick the box.
- **ROADMAP.md:** edit it only when a phase window, a gate or the critical path changes. Refresh its "Where we stand" section when a gate passes or a phase slips.
- **Hand edits and merge conflicts:** keep one row per task with all nine cells, escape `|` as `\|`, then run `sync`. For a conflict inside the summary block, keep either side: `sync` rewrites it.
- **Git:** don't commit unless the user asks.
