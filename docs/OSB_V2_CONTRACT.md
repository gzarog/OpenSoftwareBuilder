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

1. Resolve host
2. Resolve models
3. Verify RagMonk
4. Retrieve relevant knowledge
5. Run Architect
6. Run Implementer(s)
7. Run Reviewer
8. Repair loop if needed
9. Run QA
10. Repair/design loop if needed
11. Consolidate knowledge
12. Complete
```

Full detail: `.agents/skills/osb/references/workflow.md`.

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

Every role transition uses one conceptual result shape:

```markdown
## Outcome

Completed | Blocked | Findings | Pass | Fail

## Changes

## Acceptance Criteria

## Verification

## Knowledge Discovered

## Blockers
```

Full detail, including the per-role specialization of this shape:
`.agents/skills/osb/references/handoff.md`.

## Incremental knowledge format

Any role may report knowledge of type `decision`, `constraint`, `discovery`, `gotcha`,
`assumption`, `assumption-invalidated`, `review-finding`, `qa-result`, or `follow-up` at
any checkpoint. Entries are appended as JSONL to `.osb/knowledge/events/<task-id>.jsonl`
during the task, then consolidated after clean QA into an immutable task record
(`.osb/knowledge/tasks/`) and updated component records (`.osb/knowledge/components/`).
Knowledge files are authoritative; RagMonk indexes them. Full detail:
`.agents/skills/osb/references/knowledge.md`.

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
