# OSB v2 Contract

This is the provider-neutral specification for OpenSoftwareBuilder v2. It can be fully
understood without referring to Go code, PowerShell commands, provider abstractions,
toolchains, profiles, or executors — none of those exist in v2. The full detail lives in
`osb/`; this document is the frozen summary of what that skill guarantees.

## Roles

Exactly four: **Architect**, **Implementer** (one or more), **Reviewer**, **QA**. Full
responsibilities, prohibitions, and output formats:
`osb/references/roles.md`.

## Lifecycle

```text
/osb <task>

0.  Resume check (compact task state; revalidate fingerprint before trusting it)
1.  Resolve host
2.  Resolve models
3.  Verify RagMonk
4.  Load or create compact task state
5.  Retrieve relevant knowledge (bounded, progressive, escalatable — see quality gate)
6.  Run Architect                            — checkpoint
7.  Run Implementer(s), min necessary fan-out — checkpoint
8.  Run Reviewer (intermediate, delta scope)  — checkpoint
9.  Repair loop if needed (delta only)        — checkpoint
10. MANDATORY final combined-change review    — checkpoint
11. Run QA on every AC, final revision        — checkpoint
12. Repair loop if needed; any repair re-runs steps 10 and 11 in full
13. Consolidate knowledge                     — checkpoint
14. Complete, only once the quality gate holds
```

Execution state is persisted after every checkpoint so an interrupted task can resume
from its current phase instead of restarting. Information moves forward between roles as
references + compact state + deltas, never as full transcripts — bounded by the quality
gate below, which is deliberately the one place completion cannot be inferred from a
narrow, cheap check. Full detail: `osb/references/workflow.md` and
`osb/references/state.md`.

## Model resolution

Model selection is always explicit, per role, per host. OSB never invents a default
model for a role that has none configured — it stops and asks the user. Configuration
lives in `osb.yaml` → `models.<host>.{architect,implementer,reviewer,qa}`. Full detail:
`osb/SKILL.md` §"Model resolution".

## RagMonk responsibilities

OSB delegates all historical/project knowledge retrieval and code-intelligence queries to
RagMonk (MCP preferred, CLI fallback). OSB does not implement its own code-analysis or
repository-search engine. When `osb.yaml` sets `ragmonk.required: true` and RagMonk is
unreachable or the repository isn't indexed, OSB stops before the Architect is dispatched
rather than silently falling back to ad hoc search. Full detail:
`osb/references/ragmonk.md`.

## Handoff format

The Architect returns a design document; Implementer, Reviewer, and QA return compact
YAML results (`status`, changed files/findings/AC verdicts, `knowledge`) instead of
free-form narrative reports. An Implementer receives a **unit capsule** (its unit, files,
acceptance criteria with their exact requirement text, constraints, interfaces, bounded
knowledge) rather than the full task and architecture — compaction may omit irrelevant
detail but must never drop a mandatory requirement. A review or QA failure sends only the
affected finding/AC as a delta back to an Implementer or Architect — never a replay of the
whole task, though the loop only closes on the full final review and QA passes, not the
delta recheck alone. Any role may report `needs-evidence` with a named question instead of
guessing over a gap. Full detail, including the per-role schemas:
`osb/references/handoff.md` and `osb/references/roles.md`.

## Quality gate

Token budgets, compact handoffs, and delta repair loops are starting points for the cheap
case, not evidence caps. A delta review pass (after one repair) is always intermediate — a
**mandatory final combined-change review**, covering every unit and repair since the
task's base revision against every acceptance criterion, must be clean before QA runs and
again before completion. QA then independently verifies **every** AC — including ones that
previously passed — on that same revision; `not-run`/`blocked`/`inconclusive` is never
reported as `pass`. Both verdicts are tied to a patch fingerprint that covers uncommitted
implementation content, not just a commit SHA; any later code/test/config change, whether
from an explicit repair or discovered on resume, invalidates them and requires re-running
the final review and QA. Full detail: `osb/references/quality.md`.

## Incremental knowledge format

Any role may report knowledge of type `decision`, `constraint`, `discovery`, `gotcha`,
`assumption`, `assumption-invalidated`, `review-finding`, `qa-result`, or `follow-up` at
any checkpoint. Entries are appended as JSONL to `.osb/knowledge/events/<task-id>.jsonl`
during the task, then consolidated after clean QA into an immutable task record
(`.osb/knowledge/tasks/`) and updated component records (`.osb/knowledge/components/`).
Knowledge files are authoritative; RagMonk indexes them. Full detail:
`osb/references/knowledge.md`.

## Execution state

Task progress is persisted as compact, mutable JSON at `.osb/state/<task-id>.json` —
current phase, unit status, open findings, failed acceptance criteria, and a knowledge
watermark. It is separate from durable knowledge, is not indexed by RagMonk, and lets an
interrupted task resume from its current phase instead of restarting. Full detail:
`osb/references/state.md`.

## Completion criteria

A task is complete when: the final combined-change review is Clean for the current patch
fingerprint; every required acceptance criterion has an independent QA verdict of Pass on
that same fingerprint; there are no open blocking findings or open evidence gaps;
knowledge has been consolidated; and RagMonk has been given the opportunity to index the
result. See `osb/references/quality.md` §Completion gate.

## What OSB v2 deliberately does not have

- its own AI runtime, provider abstraction, or executor framework
- its own build-system, toolchain, or OS abstraction
- its own code-analysis engine or repository search engine (RagMonk + host tools instead)
- its own daemon or workflow state machine
- language/project profiles (conventions live in the project, not in OSB)
- a hardcoded "best model" ranking

Everything in that list is provided by the host coding assistant (Claude Code, Codex, or
GitHub Copilot) or by RagMonk.
