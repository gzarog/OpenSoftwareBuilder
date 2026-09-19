# OSB Workflow (Reference)

This document expands `SKILL.md`'s twelve-step lifecycle. It is provider-neutral: nothing
here depends on Claude Code, Codex, or Copilot specifics.

## Overview

```text
Claude Code / Codex / VS Code Copilot
      │
      ▼
    /osb
      │
      ▼
   OSB Skill
      │
      ├── RagMonk retrieval
      │
      ▼
   Architect
      │
      ▼
 Implementer(s)
      │
      ▼
   Reviewer
      │
      ▼
      QA
      │
      ▼
 Knowledge consolidation
      │
      ▼
   RagMonk index
```

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
the Architect until all four roles have a model (or the host's default model is explicitly
accepted by the user as the answer for a role).

## Step 3 — Verify RagMonk

Read `osb.yaml` → `ragmonk.enabled` / `ragmonk.required`.

- If `enabled: false`: skip RagMonk entirely; knowledge retrieval in step 4 is skipped and
  the Architect proceeds with only repository context.
- If `enabled: true, required: false`: attempt verification; on failure, warn and continue
  without RagMonk-backed retrieval.
- If `enabled: true, required: true`: attempt verification; on failure, **stop the
  workflow** before any role is dispatched and explain the exact remediation (see
  `ragmonk.md`).

## Step 4 — Retrieve existing knowledge

Query RagMonk (when available) for material relevant to `<task>`:

- previous architectural decisions touching the same area,
- component knowledge for components the task is likely to touch,
- related completed tasks,
- standing gotchas and constraints,
- unresolved follow-ups,
- similar implementation history.

Bound the query (relevance + a result cap) rather than retrieving everything. Summarize
findings into a short knowledge excerpt block to pass to the Architect.

## Step 5 — Architecture

Dispatch one Architect. Inputs: the user task, current repository context the Architect
gathers itself (native code navigation, repository search, RagMonk symbol/caller/impact
queries), and the knowledge excerpt from step 4. Required output format is in `roles.md`.

The Architect must produce implementation units clear enough that an Implementer can
execute one independently, without re-deriving architecture decisions.

## Step 6 — Implementation

```text
Architect
   │
   ├── Implementer A
   ├── Implementer B
   └── Implementer C
```

Dispatch one Implementer per unit. Units run in parallel only when **all** of:

- file ownership does not overlap with any other in-flight unit,
- the interfaces/contracts the unit needs are already fixed by the architecture (not still
  being decided by another in-flight unit),
- the unit does not depend on unfinished work from another in-flight unit.

Otherwise run units sequentially in dependency order. Each Implementer receives the
handoff described in `handoff.md` and returns the format in `roles.md`.

## Step 7 — Review

```text
Implementer(s)
      │
      ▼
   Reviewer
```

One Reviewer reviews the combined diff from all units in this pass, checked against the
Architect's acceptance criteria. The Reviewer must be a fresh context, independent of any
Implementer's session state.

## Step 8 — Repair loop (review)

```text
Reviewer
   │
   ▼
Implementer
   │
   ▼
Reviewer
```

Route each blocking finding to the Implementer who owns the affected files. Non-blocking
findings may be recorded as knowledge (`review-finding`) without necessarily blocking QA,
at the Reviewer's judgment. Repeat until the Reviewer reports Clean.

## Step 9 — QA

```text
Reviewer Clean
      │
      ▼
      QA
```

QA runs only after a clean review. QA checks every acceptance criterion from the
architecture stage independently — it does not trust the Implementer's or Reviewer's
verification claims, it re-runs them.

## Step 10 — Repair/design loop (QA)

Implementation defect (the design was right, the code has a bug):

```text
QA → Implementer → Reviewer → QA
```

Architecture/specification defect (an assumption in the design was wrong):

```text
QA → Architect → Implementer → Reviewer → QA
```

QA decides which loop applies based on whether the failure traces to an incorrect
implementation of a correct spec, or an incorrect/incomplete spec.

## Step 11 — Knowledge consolidation

After QA reports Pass on every acceptance criterion:

1. Read the incremental knowledge events recorded during this task.
2. Discard transient/noise entries (superseded assumptions, duplicate discoveries).
3. Write one immutable task record.
4. Update the component records for every touched component.
5. Trigger or allow RagMonk indexing of the new/updated files.
6. Keep (or archive) the raw event stream for auditability.

See `knowledge.md` for exact formats and paths.

## Step 12 — Complete

Report completion to the user: task summary, changed files, acceptance criteria status,
and the task-record path. The workflow instance ends here.
