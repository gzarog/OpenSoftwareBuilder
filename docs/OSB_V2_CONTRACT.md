# OSB v2 Contract

This is the provider-neutral specification for OpenSoftwareBuilder v2. It can be fully
understood without referring to Go code, PowerShell commands, provider abstractions,
toolchains, profiles, or executors — none of those exist in v2. The full detail lives in
`.agents/skills/osb/`; this document is the frozen summary of what that skill guarantees.

## Roles

Exactly four: **Architect**, **Implementer** (one or more), **Reviewer**, **QA**. Full
responsibilities, prohibitions, and output formats:
`.agents/skills/osb/references/roles.md`.

## Lifecycle

```text
/osb <task>

0.  Resume check (compact task state)
1.  Resolve host
2.  Resolve models
3.  Verify RagMonk
4.  Load or create compact task state
5.  Retrieve relevant knowledge (bounded, progressive)
6.  Run Architect                          — checkpoint
7.  Run Implementer(s), min necessary fan-out — checkpoint
8.  Run Reviewer                           — checkpoint
9.  Repair loop if needed (delta only)     — checkpoint
10. Run QA                                 — checkpoint
11. Repair/design loop if needed (delta only)
12. Consolidate knowledge                  — checkpoint
13. Complete
```

Execution state is persisted after every checkpoint so an interrupted task can resume
from its current phase instead of restarting. Information moves forward between roles as
references + compact state + deltas, never as full transcripts. Full detail:
`.agents/skills/osb/references/workflow.md` and `.agents/skills/osb/references/state.md`.

## Model resolution

Model selection is always explicit, per role, per host. OSB never invents a default
model for a role that has none configured — it stops and asks the user. Configuration
lives in `osb.yaml` → `models.<host>.{architect,implementer,reviewer,qa}`. Full detail:
`.agents/skills/osb/SKILL.md` §"Model resolution".

## RagMonk responsibilities

OSB delegates all historical/project knowledge retrieval and code-intelligence queries to
RagMonk (MCP preferred, CLI fallback). OSB does not implement its own code-analysis or
repository-search engine. When `osb.yaml` sets `ragmonk.required: true` and RagMonk is
unreachable or the repository isn't indexed, OSB stops before the Architect is dispatched
rather than silently falling back to ad hoc search. Full detail:
`.agents/skills/osb/references/ragmonk.md`.

## Handoff format

The Architect returns a design document; Implementer, Reviewer, and QA return compact
YAML results (`status`, changed files/findings/AC verdicts, `knowledge`) instead of
free-form narrative reports. An Implementer receives a **unit capsule** (its unit, files,
acceptance criteria, constraints, bounded knowledge) rather than the full task and
architecture. A review or QA failure sends only the affected finding/AC as a delta back to
an Implementer or Architect — never a replay of the whole task. Full detail, including the
per-role schemas: `.agents/skills/osb/references/handoff.md` and
`.agents/skills/osb/references/roles.md`.

## Incremental knowledge format

Any role may report knowledge of type `decision`, `constraint`, `discovery`, `gotcha`,
`assumption`, `assumption-invalidated`, `review-finding`, `qa-result`, or `follow-up` at
any checkpoint. Entries are appended as JSONL to `.osb/knowledge/events/<task-id>.jsonl`
during the task, then consolidated after clean QA into an immutable task record
(`.osb/knowledge/tasks/`) and updated component records (`.osb/knowledge/components/`).
Knowledge files are authoritative; RagMonk indexes them. Full detail:
`.agents/skills/osb/references/knowledge.md`.

## Execution state

Task progress is persisted as compact, mutable JSON at `.osb/state/<task-id>.json` —
current phase, unit status, open findings, failed acceptance criteria, and a knowledge
watermark. It is separate from durable knowledge, is not indexed by RagMonk, and lets an
interrupted task resume from its current phase instead of restarting. Full detail:
`.agents/skills/osb/references/state.md`.

## Completion criteria

A task is complete when every acceptance criterion has a QA verdict of Pass, the
Reviewer's most recent pass is Clean, knowledge has been consolidated, and RagMonk has
been given the opportunity to index the result.

## What OSB v2 deliberately does not have

- its own AI runtime, provider abstraction, or executor framework
- its own build-system, toolchain, or OS abstraction
- its own code-analysis engine or repository search engine (RagMonk + host tools instead)
- its own daemon or workflow state machine
- language/project profiles (conventions live in the project, not in OSB)
- a hardcoded "best model" ranking

Everything in that list is provided by the host coding assistant (Claude Code, Codex, or
GitHub Copilot) or by RagMonk.
