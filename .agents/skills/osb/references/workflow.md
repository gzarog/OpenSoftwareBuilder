# OSB Workflow (Reference)

This document expands `SKILL.md`'s lifecycle. It is provider-neutral: nothing here depends
on Claude Code, Codex, or Copilot specifics.

The governing principle: **persist execution state frequently, persist durable knowledge
selectively, pass only deltas between roles.** Information moves forward as references +
compact state + deltas — never as full transcripts.

## Overview

```text
Claude Code / Codex / VS Code Copilot
      │
      ▼
    /osb
      │
      ├── resume check (state.md)
      ├── bounded RagMonk retrieval
      │
      ▼
   Architect ── CP1
      │
      ▼
 Implementer(s) ── CP2 / CP3
      │
      ▼
   Reviewer ── CP4
      │
      ▼
 Repair (delta only) ── CP5
      │
      ▼
      QA ── CP6
      │
      ▼
 Knowledge consolidation ── CP7
      │
      ▼
   RagMonk index (only if knowledge changed)
```

## Step 0 — Resume check

Before starting anything, check whether an active task state file exists for this task at
`.osb/state/<task-id>.json` with `phase != complete`. If so, resume per `state.md` §Resume
support instead of restarting from Architect. Do not rerun roles whose phase has already
passed.

## Step 1 — Resolve host

The host is whichever coding assistant is currently executing the skill. Detection is
mechanical (which agent runtime invoked `/osb`), not configuration the user sets in
`osb.yaml`. The host determines:

- how subagents/roles are started (native subagent tool, provider agent config, or a
  single-context role-switch when the host has no subagent primitive),
- which `models.<host>.*` block in `osb.yaml` applies,
- which provider directory (`.claude/`, `.codex/`, `.github/`) holds the thin wrapper
  files for role definitions.

The workflow steps below never change based on host.

## Step 2 — Resolve models

Read `osb.yaml` → `models.<host>.{architect,implementer,reviewer,qa}`. All four are
required. Missing entries trigger the model-resolution prompt in `SKILL.md`. Do not start
the Architect until all four roles have a model.

## Step 3 — Verify RagMonk

Read `osb.yaml` → `ragmonk.enabled` / `ragmonk.required`. See `ragmonk.md` for the exact
behavior per combination, including the stop-the-workflow case when `required: true` and
RagMonk is unreachable.

## Step 4 — Load or create task state

Load `.osb/state/<task-id>.json` (new task: write CP0 per `state.md`). This file is the
single compact source of truth for the rest of the run; do not reconstruct it from
checkpoint history each time.

## Step 5 — Retrieve existing knowledge (bounded)

Query RagMonk (when available) for material relevant to `<task>`, following the
progressive retrieval order and per-role budgets in `ragmonk.md`: previous architectural
decisions touching the same area, component knowledge, related completed tasks, standing
gotchas/constraints, and unresolved follow-ups. Summarize into a short knowledge excerpt —
never dump the whole knowledge base into the Architect's context.

## Step 6 — Architecture (CP1)

Dispatch one Architect with: the user task, repository context it gathers itself, and the
bounded knowledge excerpt from step 5. Required output is in `roles.md` §Architect. On
completion, save CP1 (`state.md`) and advance `knowledge_watermark` if the Architect
reported durable knowledge.

The Architect must produce implementation units concrete enough that an Implementer can
execute one as a standalone unit capsule, without re-deriving architecture decisions.

## Step 7 — Implementation (CP2 / CP3)

```text
Architect
   │
   ├── Implementer A
   └── Implementer B
```

### Implementer fan-out

Default to **one Implementer**. Split into multiple only when the Architect's units are
genuinely independent: file ownership doesn't overlap, interfaces are already fixed,
parallelism is meaningful, and separate contexts provide real value. Do not create
multiple Implementers for tiny adjacent changes. `osb.yaml` →
`execution.max_parallel_implementers` bounds concurrent Implementers (default 2) — raise it
only for a concrete architectural reason.

Dispatch each Implementer with exactly its unit capsule (`handoff.md`), never the full
architecture or other units' outputs. On each unit's completion, save CP2 (or CP3 if
blocked) and advance the knowledge watermark if new knowledge was reported.

## Step 8 — Review (CP4)

```text
Implementer(s)
      │
      ▼
   Reviewer
```

One Reviewer reviews the combined diff from all units in this pass, checked against the
Architect's acceptance criteria, receiving only what `handoff.md` §Reviewer dispatch
specifies. The Reviewer must be a fresh context, independent of any Implementer's session
state. Save CP4 on completion.

## Step 9 — Repair loop (review, CP5)

```text
Reviewer
   │
   ▼ (delta only — handoff.md §Delta-only repair loops)
Implementer
   │
   ▼ (delta only)
Reviewer
```

Route each blocking finding to the Implementer who owns the affected files, as a delta —
never the whole task. Non-blocking findings may be recorded as knowledge
(`review-finding`) without necessarily blocking QA, at the Reviewer's judgment. Repeat
until the Reviewer reports `clean`. Save CP5 after each repair.

## Step 10 — QA (CP6)

```text
Reviewer clean
      │
      ▼
      QA
```

QA runs only after a clean review, receiving only what `handoff.md` §QA dispatch
specifies (never the Architect/Implementer/Reviewer transcripts). QA checks every
acceptance criterion independently — it does not trust prior verification claims, it
re-runs them, with minimal/quiet command output (see §Build/test output below). Save CP6.

## Step 11 — Repair/design loop (QA)

Implementation defect (the design was right, the code has a bug):

```text
QA → Implementer (delta) → Reviewer (delta) → QA
```

Architecture/specification defect (an assumption in the design was wrong):

```text
QA → Architect (delta) → Implementer → Reviewer → QA
```

QA decides which loop applies based on whether the failure traces to an incorrect
implementation of a correct spec, or an incorrect/incomplete spec. Every hop carries only
the failed AC, the affected unit, the relevant files, and the failure evidence — not a
full replay.

## Step 12 — Knowledge consolidation (CP7)

After QA reports pass on every acceptance criterion, consolidate per `knowledge.md`: write
one immutable task record, update touched component records, and let RagMonk index them
only because durable knowledge actually changed (`ragmonk.md` §Refresh policy). Save CP7.

## Step 13 — Complete

Report completion to the user: task summary, changed files, acceptance criteria status,
and the task-record path. If the host exposes usage figures, optionally record proxies for
token efficiency (input/output tokens or prompt/diff/tool-output chars per phase, RagMonk
chars retrieved, Implementers spawned, repair-loop counts) — this is advisory measurement,
never a gate on completion. The workflow instance ends here.

## Build/test output

Use minimal/quiet command output by default (`dotnet test --verbosity minimal`, and the
equivalent low-noise modes for pytest, npm/pnpm, Maven, Gradle, Cargo, Go, etc.).

- On success, retain only: command, exit code, test count, short summary.
- On failure, retain: failing test names, error summary, relevant stack trace lines.

Never forward a full successful build/test log to another role.
