---
name: osb
description: Run Architect → Implement → Review → QA with RagMonk-backed project memory.
argument-hint: <task>
---

# OSB

OpenSoftwareBuilder (OSB) is a provider-neutral **Architect → Implement → Review → QA**
workflow with RagMonk-backed project memory. This file is the canonical coordinator for
`/osb`. Provider-specific files (`.claude/`, `.codex/`, `.github/`) bind models and launch
mechanics onto this workflow — never redefine it. Role agents are self-contained and do
not read this file or its references at dispatch time.

## Lifecycle

```text
0.  Resume check (.osb/state/<task-id>.json).
1.  Resolve host.
2.  Resolve required role models from osb.yaml; never invent a missing model.
3.  Verify required RagMonk access.
4.  Load or create compact task state.
5.  Retrieve bounded, relevant knowledge before architecture.
6.  Dispatch Architect. CP1.
7.  Dispatch minimum necessary Implementer(s), each with a unit capsule. CP2/CP3.
8.  Independent Reviewer over the combined diff (intermediate pass). CP4.
9.  Repair blocking findings via delta handoffs, then re-review (still intermediate). CP5.
10. No open blocking findings → mandatory final combined-change review. CP4 (final scope).
11. Independent QA once final review is clean; verify every AC on the final revision. CP6.
12. Repair failed ACs via delta handoffs; any repair restarts step 10 and 11.
13. Consolidate durable knowledge; refresh RagMonk only if knowledge changed. CP7.
14. Report completion — only once the completion gate holds (`references/quality.md`).
```

## Rules

- Never invent a missing model — stop and ask (see §Model resolution).
- Never forward full role transcripts between roles — pass only role-specific context
  (`references/handoff.md`).
- Retrieve knowledge/code context progressively and within budget, escalating on a named,
  specific gap (`references/ragmonk.md`).
- Persist execution state after every checkpoint; persist durable knowledge only when new
  reusable knowledge exists, and refresh RagMonk only then (`references/state.md`,
  `references/knowledge.md`).
- Default to one Implementer; split fan-out only when units are truly independent
  (`references/workflow.md` §Implementer fan-out). Keep successful build/test output to a
  short summary — never forward full logs.
- Quality overrides the initial context budget: request focused additional evidence when
  needed; never assume truncated/missing evidence means a check passed. After any repair,
  prior final-review and QA approvals are stale — require a fresh final combined-change
  review and independent QA against the final revision before completion
  (`references/quality.md`).

## Model resolution

Every role dispatch, on every host, uses the model resolved from `models.<host>.<role>` in
`osb.yaml` — there is no host-wide or workflow-wide default. A role must never be
dispatched before its own model is resolved. If a role's configured model turns out to be
unavailable at dispatch time, stop and ask the user for a replacement for that role only.

When a role model is missing, ask which model to use for each missing role (one answer may
apply to all). Persist the answer into `osb.yaml` when the host allows writing project
files. Never hardcode a "best model" ranking or replace a user-configured model
automatically.

## Completion criteria

See `references/quality.md` §Completion gate for the full, binding checklist. In short:
final combined-change review clean, every required AC independently `pass` on that same
revision, no open blocking findings or evidence gaps, and knowledge consolidated.

## Reference material

- `references/workflow.md` — full lifecycle detail, checkpoints, and control flow.
- `references/roles.md` — responsibilities, prohibitions, and output schemas per role.
- `references/handoff.md` — unit capsules, dispatch briefs, and delta-only repair loops.
- `references/knowledge.md` — incremental knowledge format, storage, watermark, and consolidation.
- `references/ragmonk.md` — RagMonk verification, retrieval budgets, and refresh policy.
- `references/state.md` — execution state schema, checkpoints, compaction, and resume.
- `references/quality.md` — context-expansion triggers, evidence rules, final review/QA
  gates, and staleness/fingerprint rules.
