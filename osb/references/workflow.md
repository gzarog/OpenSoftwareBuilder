# OSB Workflow (Reference)

This document expands `SKILL.md`'s lifecycle. It is provider-neutral: nothing here depends
on Claude Code, Codex, or Copilot specifics.

The governing principle: **persist execution state frequently, persist durable knowledge
selectively, pass only deltas between roles.** Information moves forward as references +
compact state + deltas — never as full transcripts. That principle is bounded by
`quality.md`: token budgets are starting points, not evidence caps, and completion
requires a clean final combined-change review plus independent QA evidence for every AC
on the final revision.

## Overview

```text
Claude Code / Codex / VS Code Copilot
      │
      ▼
    /osb
      │
      ├── resume check (state.md)
      ├── bounded, escalatable RagMonk retrieval
      │
      ▼
   Architect ── CP1
      │
      ▼
 Implementer(s) ── CP2 / CP3
      │
      ▼
   Reviewer (intermediate, delta scope) ── CP4
      │
      ▼
 Repair (delta only) ── CP5
      │
      ▼
   Reviewer (MANDATORY final combined-change review) ── CP4 (final scope)
      │
      ▼
      QA (every AC, final revision) ── CP6
      │
      ▼
 repair? ── yes → back to repair, then re-run final review + QA
      │ no
      ▼
 Knowledge consolidation ── CP7
      │
      ▼
   RagMonk index (only if knowledge changed)
```

## Step 0 — Resume check

Before starting anything, check whether an active task state file exists for this task at
`.osb/state/<task-id>.json` with `phase != complete`. If so, resume per `state.md` §Resume
support instead of restarting from Architect — but first recompute the current patch
fingerprint and compare it against any persisted `review`/`qa` fingerprints
(`quality.md` §Fingerprinting). `osb/scripts/verify_task.py fingerprint <repo-root>
<task_base_revision>` computes this deterministically when a host wants to shell out
rather than recompute it inline. If they differ (e.g. the working tree changed outside this
run), the persisted review/QA verdicts are stale: re-enter at step 9 or 10 rather than
resuming at completion. Do not rerun roles whose phase has already passed and whose
verdicts are still fresh.

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
never dump the whole knowledge base into the Architect's context. These are initial
defaults, not ceilings — escalate per `ragmonk.md` §Adaptive retrieval when a
`quality.md` §Context expansion trigger applies.

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
architecture or other units' outputs. If an Implementer reports `needs-evidence`, supply
only the requested evidence and let it continue (`quality.md` §Context expansion
triggers) — do not treat that as a failure. On each unit's completion, save CP2 (or CP3 if
blocked) and advance the knowledge watermark if new knowledge was reported.

## Step 8 — Review, intermediate/delta scope (CP4)

```text
Implementer(s)
      │
      ▼
   Reviewer (scope: delta if this is a repair recheck, else the initial combined diff)
```

One Reviewer reviews the diff from all units in this pass, checked against the relevant
acceptance criteria, receiving only what `handoff.md` §Reviewer dispatch specifies. The
Reviewer must be a fresh context, independent of any Implementer's session state. This
pass — even the first one, before any finding exists — is **not** a substitute for the
mandatory final combined-change review in step 10; it establishes only that this pass's
scope is clean. Save CP4 on completion.

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
until the Reviewer reports `clean` on this delta scope. Save CP5 after each repair. Once
clean, proceed to step 10 — do not skip straight to QA.

## Step 10 — Final combined-change review (mandatory, CP4 final scope)

```text
no open blocking findings
      │
      ▼
   Reviewer — scope: final-combined-change
```

Once the delta scope is clean, dispatch the Reviewer once more over the **complete**
change since the task's base revision: all units, all repairs, every changed file, checked
against every acceptance criterion and significant regression/security surface. Start from
`git diff --stat <base>`, enumerate changed files, inspect relevant patches in manageable
chunks, and expand to related files/symbols only when impact warrants it — this is not a
whole-repository read or a single giant diff prompt (`quality.md` §Final combined-change
review gate). Compute the current patch fingerprint (`quality.md` §Fingerprinting,
`state.md`) and record it as `review.reviewed_revision` alongside `review.scope:
final-combined-change`. If this pass finds a blocking issue, return to step 9 for that
delta, then re-run this step against the new fingerprint. Save CP4 (final scope) on a
clean result.

## Step 11 — QA, every AC on the final revision (CP6)

```text
final combined-change review clean
      │
      ▼
      QA
```

QA runs only after the **final combined-change review** — not a delta pass — reports
`clean` for the current fingerprint, receiving only what `handoff.md` §QA dispatch
specifies (never the Architect/Implementer/Reviewer transcripts). QA independently checks
**every** acceptance criterion, including ones that previously passed, with minimal/quiet
command output (see §Build/test output below) — it does not trust prior verification
claims, it re-runs them. `not-run`/`blocked`/`inconclusive` is never reported as `pass`
(`quality.md` §Final-revision QA gate). Save CP6, including the QA fingerprint and any
unverified AC IDs.

## Step 12 — Repair/design loop (QA)

Implementation defect (the design was right, the code has a bug):

```text
QA → Implementer (delta) → step 10 (final review) → step 11 (QA)
```

Architecture/specification defect (an assumption in the design was wrong):

```text
QA → Architect (delta) → Implementer → step 10 (final review) → step 11 (QA)
```

QA decides which loop applies based on whether the failure traces to an incorrect
implementation of a correct spec, or an incorrect/incomplete spec. Every repair hop
carries only the failed AC, the affected unit, the relevant files, and the failure
evidence — not a full replay. The loop never closes on a delta re-review or a re-check of
only the one failed AC: any repair invalidates the prior final review and QA verdicts
(`quality.md` §Staleness), so both step 10 and step 11 run again, in full, against the new
fingerprint before the loop can close.

## Step 13 — Knowledge consolidation (CP7)

After QA reports pass on every required acceptance criterion against the final revision,
consolidate per `knowledge.md`: write one immutable task record, update touched component
records, and let RagMonk index them only because durable knowledge actually changed
(`ragmonk.md` §Refresh policy). Save CP7.

## Step 14 — Complete

Before reporting completion, confirm the completion gate in `quality.md` §Completion gate
— run `osb/scripts/verify_task.py check .osb/state/<task-id>.json --repo-root . --evidence
<qa-result>` (or the equivalent inline check) and do not report completion unless it
reports the gate holds: final review and QA fingerprints match the current patch
fingerprint, no open blocking findings or evidence gaps, every required AC independently
`pass`, knowledge consolidated. Then report to the user: task summary, changed files, acceptance criteria status, and the
task-record path. If the host exposes usage figures, optionally record proxies for token
efficiency (input/output tokens or prompt/diff/tool-output chars per phase, RagMonk chars
retrieved, Implementers spawned, repair-loop counts) — this is advisory measurement, never
a gate on completion. The workflow instance ends here.

## Build/test output

Use minimal/quiet command output by default (`dotnet test --verbosity minimal`, and the
equivalent low-noise modes for pytest, npm/pnpm, Maven, Gradle, Cargo, Go, etc.).

- On success, retain only: command, exit code, test count, short summary.
- On failure, retain: failing test names, error summary, relevant stack trace lines.

Never forward a full successful build/test log to another role.
