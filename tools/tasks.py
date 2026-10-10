#!/usr/bin/env python3
"""Add, update, delete and list the tasks in TASKS.md. The /task skill drives it; anyone can run it.

TASKS.md is the only store: one Markdown table row per task, under level-2 phase headings written
"## <key> · <title>" (keys A, B, C, D, Run, Backlog). A write edits task rows in place and leaves every
other line alone, rewrites the summary between <!-- summary:start --> and <!-- summary:end -->, and
ticks each PLAN.md checkbox whose line ends with task tags such as "[T10, T11]" once all of them are
done. A box is unticked only when one of its tasks is reopened by the same command; a ticked box
whose tasks are not done is reported, never silently cleared. New IDs come from the
<!-- next-id: N --> counter, so a deleted ID is never reused.

Usage (from anywhere; paths resolve from the repo root). Standard library only.
  python3 tools/tasks.py list [--phase A] [--status todo,doing] [--area geo] [--owner Ana|none]
                              [--pri P0] [--ready] [--all]
  python3 tools/tasks.py show T12
  python3 tools/tasks.py add "Build the zone boundaries" --phase C [--pri P1] [--area geo]
                             [--owner Ana] [--needs T04,T05] [--status todo] [--notes "..."]
  python3 tools/tasks.py update T12 [T13 ...] [--status done] [--owner Ana|none] [--pri P0] [--area geo]
                                [--phase C] [--title "..."] [--needs T03,T04|none] [--add-needs T05]
                                [--remove-needs T03] [--notes "..." | --add-note "..."]
  python3 tools/tasks.py delete T12 [--force]   refuses while tasks or PLAN.md reference it, unless --force
  python3 tools/tasks.py check                  validate TASKS.md and the PLAN.md tags; exit 1 on errors
  python3 tools/tasks.py sync                   validate, then rewrite rows, summary and PLAN.md checkboxes

`list` hides done and dropped tasks unless --all or --status asks for them. `--ready` keeps the
todo tasks whose Needs are all done or dropped, P0 first, and skips the Backlog phase unless
--phase names it. `--add-note` appends a timestamped note; `--notes` replaces the whole cell.
"""
import argparse
import datetime
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATUSES = ("todo", "doing", "blocked", "done", "dropped")
OPEN = ("todo", "doing", "blocked")
SETTLED = ("done", "dropped")  # a Need in one of these no longer holds anything up
PRIORITIES = ("P0", "P1", "P2")
AREAS = ("pipeline", "perception", "geo", "pixel", "ui", "team")
FIELDS = ("id", "status", "pri", "area", "title", "owner", "needs", "updated", "notes")
HEADER = "| ID | Status | Pri | Area | Task | Owner | Needs | Updated | Notes |"
SEPARATOR = "|---|---|---|---|---|---|---|---|---|"
SUMMARY_START, SUMMARY_END = "<!-- summary:start -->", "<!-- summary:end -->"
NONE_WORDS = ("", "none", "-", "—")

PHASE_RE = re.compile(r"^## (\S+) · (.+?)\s*$")
ROW_RE = re.compile(r"^\|\s*([Tt]\d+)\s*\|")
CELL_RE = re.compile(r"(?<!\\)\|")
ID_RE = re.compile(r"^T\d+$")
NEXT_ID_RE = re.compile(r"^<!-- next-id: (\d+) -->$")
CHECKBOX_RE = re.compile(r"^\s*[-*] \[[ xX]\] ")
TAG_RE = re.compile(r"^(\s*[-*] \[)([ xX])(\].*\[)(T\d+(?:\s*,\s*T\d+)*)(\]\s*)$")


def stamp():
    now = datetime.datetime.now()
    return f"{('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[now.weekday()]} {now:%H:%M}"


def normalize_id(token):
    m = re.fullmatch(r"[Tt]?(\d+)", token.strip())
    return f"T{int(m.group(1)):02d}" if m else token.strip()


def split_ids(text):
    text = (text or "").strip()
    if text.lower() in NONE_WORDS:
        return []
    return [normalize_id(t) for t in re.split(r"[,\s]+", text) if t]


def clean(value):
    return " ".join(str(value).split()).replace("|", "\\|")


def split_cells(line):
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.strip().replace("\\|", "|") for cell in CELL_RE.split(body)]


def render_row(t):
    cells = (t["id"], t["status"], t["pri"], t["area"], t["title"], t["owner"],
             ", ".join(t["needs"]), t["updated"], t["notes"])
    return "| " + " | ".join(clean(c) for c in cells) + " |"


def atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class Doc:
    """TASKS.md as a list of lines, re-parsed into phases and tasks after every structural edit."""

    def __init__(self, path):
        self.path = path
        if not path.exists():
            sys.exit(f"{path} not found")
        self.lines = path.read_text(encoding="utf-8").splitlines()
        self.parse()

    def parse(self):
        self.phases, self.tasks, self.errors = [], {}, []
        self.next_id = self.next_id_line = None
        phase = None
        for i, line in enumerate(self.lines):
            m = PHASE_RE.match(line)
            if m:
                phase = {"key": m.group(1), "title": m.group(2), "line": i}
                self.phases.append(phase)
                continue
            if line.startswith("## "):
                phase = None
                continue
            m = NEXT_ID_RE.match(line.strip())
            if m:
                self.next_id, self.next_id_line = int(m.group(1)), i
                continue
            m = ROW_RE.match(line)
            if not m:
                continue
            where = f"{self.path.name}:{i + 1}"
            if phase is None:
                self.errors.append(f"{where}: {m.group(1)} is outside a phase section")
                continue
            cells = split_cells(line)
            if len(cells) != len(FIELDS):
                self.errors.append(f"{where}: {m.group(1)} has {len(cells)} cells, expected {len(FIELDS)}")
                continue
            task = dict(zip(FIELDS, cells))
            task.update(id=normalize_id(task["id"]), needs=split_ids(task["needs"]), phase=phase["key"], line=i)
            if task["id"] in self.tasks:
                self.errors.append(f"{where}: duplicate ID {task['id']}")
                continue
            self.tasks[task["id"]] = task

    def phase(self, key):
        for p in self.phases:
            if p["key"].lower() == key.strip().lower():
                return p
        sys.exit(f"unknown phase {key!r}; phases: {', '.join(p['key'] for p in self.phases)}")

    def get(self, tid):
        tid = normalize_id(tid)
        if tid not in self.tasks:
            sys.exit(f"no task {tid}")
        return self.tasks[tid]

    def section(self, key):
        start = self.phase(key)["line"]
        end = next((i for i in range(start + 1, len(self.lines)) if self.lines[i].startswith("## ")), len(self.lines))
        return start, end

    def insert_row(self, key, row):
        start, end = self.section(key)
        header = next((i for i in range(start + 1, end) if self.lines[i].startswith("| ID |")), None)
        if header is None:  # first task of this phase: open a table at the end of its section
            at = end
            while at - 1 > start and not self.lines[at - 1].strip():
                at -= 1
            self.lines[at:at] = ["", HEADER, SEPARATOR, row]
        else:
            at = header
            while at + 1 < end and self.lines[at + 1].startswith("|"):
                at += 1
            self.lines.insert(at + 1, row)
        self.parse()

    def remove_row(self, tid):
        del self.lines[self.tasks[tid]["line"]]
        self.parse()

    def replace_row(self, t):
        self.lines[t["line"]] = render_row(t)

    def allocate_id(self):
        n = max([self.next_id or 1] + [int(i[1:]) + 1 for i in self.tasks if ID_RE.match(i)])
        counter = f"<!-- next-id: {n + 1} -->"
        if self.next_id_line is not None:
            self.lines[self.next_id_line] = counter
        else:
            at = self.lines.index(SUMMARY_END) + 1 if SUMMARY_END in self.lines else 1
            self.lines.insert(at, counter)
        self.parse()
        return f"T{n:02d}"

    def waiting(self, t):
        return [n for n in t["needs"] if n in self.tasks and self.tasks[n]["status"] not in SETTLED]

    def summary(self, last_change):
        rows = ["| Phase | Done | Doing | Blocked | To do | Dropped | Gate |",
                "|---|---:|---:|---:|---:|---:|---|"]
        total = Counter()
        for p in self.phases:
            ts = [t for t in self.tasks.values() if t["phase"] == p["key"]]
            c = Counter(t["status"] for t in ts)
            total.update(c)
            gate = ", ".join(f"{t['id']} {'passed' if t['status'] == 'done' else 'open'}"
                             for t in ts if t["title"].lower().startswith("gate "))
            rows.append(f"| {p['key']} · {p['title']} | {c['done']} / {len(ts) - c['dropped']} | {c['doing']} "
                        f"| {c['blocked']} | {c['todo']} | {c['dropped']} | {gate} |")
        rows.append(f"| **All** | {total['done']} / {sum(total.values()) - total['dropped']} | {total['doing']} "
                    f"| {total['blocked']} | {total['todo']} | {total['dropped']} | |")
        return [SUMMARY_START, *rows, "", last_change, SUMMARY_END]

    def summary_span(self):
        if SUMMARY_START not in self.lines:
            return None
        start = self.lines.index(SUMMARY_START)
        if SUMMARY_END not in self.lines[start:]:
            return None
        return start, self.lines.index(SUMMARY_END, start)

    def write_summary(self, last_change=None):
        span = self.summary_span()
        if span is None:
            return
        start, end = span
        if last_change is None:
            last_change = next((l for l in self.lines[start:end] if l.startswith("Last change")), "Last change: none yet.")
        self.lines[start:end + 1] = self.summary(last_change)
        self.parse()

    def save(self):
        atomic_write(self.path, "\n".join(self.lines) + "\n")


def find_cycle(tasks):
    state = {}

    def visit(tid, path):
        state[tid] = "open"
        path.append(tid)
        for n in tasks[tid]["needs"]:
            if n not in tasks:
                continue
            if state.get(n) == "open":
                return path[path.index(n):] + [n]
            if n not in state:
                cycle = visit(n, path)
                if cycle:
                    return cycle
        state[tid] = "closed"
        path.pop()
        return None

    for tid in tasks:
        if tid not in state:
            cycle = visit(tid, [])
            if cycle:
                return cycle
    return None


def validate(doc):
    errors, warnings = list(doc.errors), []
    for t in doc.tasks.values():
        tid = t["id"]
        if not ID_RE.match(tid):
            errors.append(f"{tid}: IDs look like T12")
        if t["status"] not in STATUSES:
            errors.append(f"{tid}: status {t['status']!r} is not one of {', '.join(STATUSES)}")
        if t["pri"] not in PRIORITIES:
            errors.append(f"{tid}: priority {t['pri']!r} is not one of {', '.join(PRIORITIES)}")
        if not t["title"]:
            errors.append(f"{tid}: empty task title")
        for n in t["needs"]:
            if n == tid:
                errors.append(f"{tid}: needs itself")
            elif n not in doc.tasks:
                errors.append(f"{tid}: needs unknown task {n!r}")
        if t["area"] and t["area"] not in AREAS:
            warnings.append(f"{tid}: area {t['area']!r} is not one of {', '.join(AREAS)}")
        if t["status"] in ("blocked", "dropped") and not t["notes"]:
            warnings.append(f"{tid}: {t['status']} without a note saying why")
        if t["status"] == "done" and not t["notes"]:
            warnings.append(f"{tid}: done without a note saying what proves it")
        waiting = doc.waiting(t)
        if t["status"] in ("doing", "done") and waiting:
            warnings.append(f"{tid}: {t['status']} while {', '.join(waiting)} is not done")
    cycle = find_cycle(doc.tasks)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))
    if doc.next_id is None:
        warnings.append(f"{doc.path.name} has no <!-- next-id: N --> line; add will use the highest ID + 1")
    elif any(ID_RE.match(i) and int(i[1:]) >= doc.next_id for i in doc.tasks):
        errors.append(f"next-id {doc.next_id} is not above every existing ID")
    if doc.summary_span() is None:
        warnings.append(f"{doc.path.name} has no {SUMMARY_START} ... {SUMMARY_END} block")
    if not doc.phases:
        errors.append(f"{doc.path.name} has no phase headings like '## A · Before the trial'")
    return errors, warnings


def read_plan(plan):
    text = plan.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    return text.split(nl), nl


def plan_sync(plan, tasks, write, reopened=()):
    """Tick tagged PLAN.md checkboxes whose tasks are all done.

    Returns (changes, warnings, errors). A box is unticked only for a task in `reopened`; otherwise a
    ticked box with unfinished tasks becomes a warning, so a hand tick is never thrown away.
    """
    if not plan.exists():
        return [], [], []
    lines, nl = read_plan(plan)
    changes, warnings, errors = [], [], []
    section5 = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section5 = line.startswith("## 5.")
        m = TAG_RE.match(line)
        if not m:
            if section5 and CHECKBOX_RE.match(line):
                warnings.append(f"{plan.name}:{i + 1}: section 5 checkbox has no task tag")
            continue
        ids = [x.strip() for x in m.group(4).split(",")]
        unknown = [x for x in ids if x not in tasks]
        if unknown:
            errors.append(f"{plan.name}:{i + 1}: tags unknown task {', '.join(unknown)}")
            continue
        ticked = m.group(2) in "xX"
        done = all(tasks[x]["status"] == "done" for x in ids)
        if done and not ticked:
            mark = "x"
        elif ticked and not done and any(x in reopened for x in ids):
            mark = " "
        else:
            if ticked and not done:
                open_ids = ", ".join(f"{x} {tasks[x]['status']}" for x in ids if tasks[x]["status"] != "done")
                warnings.append(f"{plan.name}:{i + 1}: ticked, but {open_ids}: mark the task done or untick the box")
            continue
        lines[i] = m.group(1) + mark + m.group(3) + m.group(4) + m.group(5)
        changes.append((i + 1, mark, ids))
    if changes and write:
        atomic_write(plan, nl.join(lines))
    return changes, warnings, errors


def plan_refs(plan, tid):
    if not plan.exists():
        return []
    lines, _ = read_plan(plan)
    refs = []
    for i, line in enumerate(lines):
        m = TAG_RE.match(line)
        if m and tid in [x.strip() for x in m.group(4).split(",")]:
            refs.append(i + 1)
    return refs


def plan_untag(plan, tid):
    lines, nl = read_plan(plan)
    changed = []
    for i, line in enumerate(lines):
        m = TAG_RE.match(line)
        if not m:
            continue
        ids = [x.strip() for x in m.group(4).split(",")]
        if tid not in ids:
            continue
        ids.remove(tid)
        if ids:
            lines[i] = m.group(1) + m.group(2) + m.group(3) + ", ".join(ids) + m.group(5)
        else:
            lines[i] = (m.group(1) + m.group(2) + m.group(3)[:-1]).rstrip()
        changed.append(i + 1)
    if changed:
        atomic_write(plan, nl.join(lines))
    return changed


def brief(doc, t, with_phase=False):
    line = f"{t['id']:<4} {t['status']:<7} {t['pri']}  {t['area'] or '-':<10} {t['title']}"
    if t["owner"]:
        line += f"  @{t['owner']}"
    waiting = doc.waiting(t)
    if waiting and t["status"] not in SETTLED:
        line += f"  [waits on {', '.join(waiting)}]"
    return f"[{t['phase']}] {line}" if with_phase else line


def finish(doc, plan, what, ids, reopened=()):
    """Validate, rewrite the summary, save TASKS.md, sync PLAN.md, report what changed."""
    errors, warnings = validate(doc)
    if errors:
        sys.exit("not saved:\n  " + "\n  ".join(errors))
    doc.write_summary(f"Last change: {stamp()}, {what}.")
    doc.save()
    changes, plan_warnings, plan_errors = plan_sync(plan, doc.tasks, write=True, reopened=reopened)
    for tid in ids:
        if tid in doc.tasks:
            print(brief(doc, doc.tasks[tid], with_phase=True))
    for line_no, mark, tags in changes:
        print(f"{plan.name}:{line_no}: {'ticked' if mark == 'x' else 'unticked'} [{', '.join(tags)}]")
    for w in warnings:
        if w.split(":")[0] in ids:
            print("warning: " + w)
    for w in plan_errors + [w for w in plan_warnings if "ticked, but" in w]:
        print("warning: " + w)


def check_ids_exist(doc, ids, tid=None):
    for n in ids:
        if n == tid:
            sys.exit(f"{tid} cannot need itself")
        if n not in doc.tasks:
            sys.exit(f"no task {n}")


def cmd_list(doc, args, plan):
    if args.status:
        statuses = {s.strip() for s in args.status.split(",")}
        bad = statuses - set(STATUSES)
        if bad:
            sys.exit(f"unknown status {', '.join(sorted(bad))}; statuses: {', '.join(STATUSES)}")
    else:
        statuses = set(STATUSES) if args.all else set(OPEN)
    if args.phase:
        doc.phase(args.phase)
    owner = args.owner.strip().lower() if args.owner is not None else None
    shown = 0
    for p in doc.phases:
        if args.phase and p["key"].lower() != args.phase.strip().lower():
            continue
        if args.ready and not args.phase and p["key"].lower() == "backlog":
            continue  # optional work is never "next" unless asked for by phase
        rows = []
        for t in doc.tasks.values():
            if t["phase"] != p["key"] or t["status"] not in statuses:
                continue
            if args.area and t["area"] != args.area:
                continue
            if owner is not None and t["owner"].lower() != ("" if owner in NONE_WORDS else owner):
                continue
            if args.pri and t["pri"] != args.pri.upper():
                continue
            if args.ready and (t["status"] != "todo" or doc.waiting(t)):
                continue
            rows.append(t)
        if args.ready:
            rows.sort(key=lambda t: t["pri"])
        if rows:
            print(f"{p['key']} · {p['title']}")
            for t in rows:
                print("  " + brief(doc, t))
            shown += len(rows)
    if not shown:
        print("no matching tasks")


def cmd_show(doc, args, plan):
    t = doc.get(args.id)
    p = doc.phase(t["phase"])
    print(f"{t['id']}  {t['title']}")
    print(f"  phase      {p['key']} · {p['title']}")
    for field in ("status", "pri", "area", "owner", "updated", "notes"):
        print(f"  {field:<10} {t[field] or '-'}")
    needs = ", ".join(f"{n} ({doc.tasks[n]['status']})" for n in t["needs"] if n in doc.tasks)
    print(f"  needs      {needs or '-'}")
    print(f"  needed by  {', '.join(o['id'] for o in doc.tasks.values() if t['id'] in o['needs']) or '-'}")
    print(f"  PLAN.md    {', '.join(f'line {n}' for n in plan_refs(plan, t['id'])) or '-'}")


def cmd_add(doc, args, plan):
    phase = doc.phase(args.phase)
    task = {"id": "", "status": args.status or "todo", "pri": args.pri or "P1", "area": args.area or "",
            "title": args.title.strip(), "owner": "" if (args.owner or "").lower() in NONE_WORDS else args.owner,
            "needs": split_ids(args.needs), "updated": stamp(), "notes": args.notes or ""}
    if not task["title"]:
        sys.exit("the task needs a title")
    check_ids_exist(doc, task["needs"])
    task["id"] = doc.allocate_id()
    doc.insert_row(phase["key"], render_row(task))
    finish(doc, plan, f"{task['id']} added", [task["id"]])


def cmd_update(doc, args, plan):
    ids = [doc.get(i)["id"] for i in args.ids]
    target = doc.phase(args.phase)["key"] if args.phase else None
    changed, reopened = [], []
    for tid in ids:
        t = dict(doc.tasks[tid], needs=list(doc.tasks[tid]["needs"]))
        before = dict(t, needs=list(t["needs"]))
        if args.status:
            t["status"] = args.status
        if args.pri:
            t["pri"] = args.pri
        if args.area is not None:
            t["area"] = args.area.strip()
        if args.owner is not None:
            t["owner"] = "" if args.owner.strip().lower() in NONE_WORDS else args.owner.strip()
        if args.title:
            t["title"] = args.title.strip()
        if args.needs is not None:
            t["needs"] = split_ids(args.needs)
        t["needs"] += [n for n in split_ids(args.add_needs) if n not in t["needs"]]
        t["needs"] = [n for n in t["needs"] if n not in split_ids(args.remove_needs)]
        if args.notes is not None:
            t["notes"] = args.notes.strip()
        if args.add_note:
            note = f"{stamp()}: {args.add_note.strip()}"
            t["notes"] = f"{t['notes']} · {note}" if t["notes"] else note
        moved = target is not None and target != t["phase"]
        if not moved and all(t[f] == before[f] for f in FIELDS):
            continue
        check_ids_exist(doc, t["needs"], tid)
        t["updated"] = stamp()
        if before["status"] == "done" and t["status"] != "done":
            reopened.append(tid)
        if moved:
            doc.remove_row(tid)
            doc.insert_row(target, render_row(t))
        else:
            doc.replace_row(t)
            doc.parse()
        changed.append(tid)
    if not changed:
        print("nothing to change")
        return
    what = f"{', '.join(changed)} {args.status}" if args.status else f"{', '.join(changed)} updated"
    finish(doc, plan, what, changed, reopened)


def cmd_delete(doc, args, plan):
    t = doc.get(args.id)
    tid = t["id"]
    dependents = [o["id"] for o in doc.tasks.values() if tid in o["needs"]]
    refs = plan_refs(plan, tid)
    if (dependents or refs) and not args.force:
        sys.exit(f"{tid} is still referenced (needed by: {', '.join(dependents) or '-'}; "
                 f"{plan.name} lines: {', '.join(map(str, refs)) or '-'}). Change those first, "
                 f"or pass --force to drop the references. To record a decision, prefer --status dropped.")
    doc.remove_row(tid)
    for d in dependents:
        o = doc.tasks[d]
        o["needs"].remove(tid)
        o["updated"] = stamp()
        doc.replace_row(o)
    doc.parse()
    untagged = plan_untag(plan, tid) if refs else []
    finish(doc, plan, f"{tid} deleted", dependents)
    print(f"deleted {tid}: {t['title']}")
    for line_no in untagged:
        print(f"{plan.name}:{line_no}: removed the {tid} tag")


def drift(doc, plan):
    """What `sync` would rewrite: (row lines, summary out of date, PLAN.md changes and messages)."""
    rows = [t["id"] for t in doc.tasks.values() if doc.lines[t["line"]] != render_row(t)]
    span = doc.summary_span()
    stale = False
    if span:
        start, end = span
        last = next((l for l in doc.lines[start:end] if l.startswith("Last change")), "Last change: none yet.")
        stale = doc.lines[start:end + 1] != doc.summary(last)
    return rows, stale, plan_sync(plan, doc.tasks, write=False)


def cmd_check(doc, args, plan):
    errors, warnings = validate(doc)
    rows, stale, (changes, plan_warnings, plan_errors) = drift(doc, plan)
    errors += plan_errors
    warnings += plan_warnings
    if rows:
        warnings.append(f"rows not in canonical form (sync rewrites them): {', '.join(rows)}")
    if stale:
        warnings.append("summary is out of date (sync rewrites it)")
    for line_no, mark, tags in changes:
        warnings.append(f"{plan.name}:{line_no}: should be ticked for [{', '.join(tags)}] (sync ticks it)")
    for e in errors:
        print("error: " + e)
    for w in warnings:
        print("warning: " + w)
    n = len(doc.tasks)
    print(f"{n} tasks in {len(doc.phases)} phases: {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


def cmd_sync(doc, args, plan):
    errors, warnings = validate(doc)
    if errors:
        sys.exit("not saved:\n  " + "\n  ".join(errors))
    rows, _, _ = drift(doc, plan)
    for tid in rows:
        doc.replace_row(doc.tasks[tid])
    doc.parse()
    doc.write_summary()
    doc.save()
    changes, plan_warnings, plan_errors = plan_sync(plan, doc.tasks, write=True)
    for line_no, mark, tags in changes:
        print(f"{plan.name}:{line_no}: {'ticked' if mark == 'x' else 'unticked'} [{', '.join(tags)}]")
    for w in warnings + plan_errors + plan_warnings:
        print("warning: " + w)
    print(f"synced {len(doc.tasks)} tasks ({len(rows)} rows rewritten, {len(changes)} PLAN.md checkboxes changed)")


def main():
    ap = argparse.ArgumentParser(prog="tasks.py", description=__doc__.split("\n\n")[0],
                                 epilog="Full usage: the header of tools/tasks.py, or the /task skill.")
    ap.add_argument("--tasks", type=Path, default=ROOT / "TASKS.md", help="tracker file (default: TASKS.md)")
    ap.add_argument("--plan", type=Path, default=ROOT / "PLAN.md", help="plan whose checkboxes follow it")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="open tasks by phase")
    p.add_argument("--phase")
    p.add_argument("--status", help="comma-separated, e.g. doing,blocked")
    p.add_argument("--area")
    p.add_argument("--owner", help="a name, or 'none' for unassigned")
    p.add_argument("--pri", type=str.upper, choices=PRIORITIES)
    p.add_argument("--ready", action="store_true", help="todo tasks with nothing left to wait on")
    p.add_argument("--all", action="store_true", help="include done and dropped")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="one task in full, with what it needs and what needs it")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("add", help="add a task to a phase")
    p.add_argument("title")
    p.add_argument("--phase", required=True)
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--pri", type=str.upper, choices=PRIORITIES, help="default P1")
    p.add_argument("--area")
    p.add_argument("--owner")
    p.add_argument("--needs", help="comma-separated IDs")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("update", help="change one or more tasks")
    p.add_argument("ids", nargs="+")
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--pri", type=str.upper, choices=PRIORITIES)
    p.add_argument("--area")
    p.add_argument("--owner", help="a name, or 'none' to unassign")
    p.add_argument("--title")
    p.add_argument("--phase", help="move to another phase")
    p.add_argument("--needs", help="replace: comma-separated IDs, or 'none'")
    p.add_argument("--add-needs")
    p.add_argument("--remove-needs")
    notes = p.add_mutually_exclusive_group()
    notes.add_argument("--notes", help="replace the notes")
    notes.add_argument("--add-note", help="append a timestamped note")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="remove a task (prefer --status dropped to record a decision)")
    p.add_argument("id")
    p.add_argument("--force", action="store_true", help="also drop it from other tasks' Needs and PLAN.md tags")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("check", help="validate only")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("sync", help="validate, then rewrite rows, summary and PLAN.md checkboxes")
    p.set_defaults(func=cmd_sync)

    args = ap.parse_args()
    args.func(Doc(args.tasks), args, args.plan)


if __name__ == "__main__":
    main()
