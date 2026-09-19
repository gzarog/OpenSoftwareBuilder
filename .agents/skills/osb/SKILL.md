---
name: osb
description: Run Architect → Implement → Review → QA with RagMonk-backed project memory.
argument-hint: <task>
---

# OSB

OpenSoftwareBuilder (OSB) is a provider-neutral **Architect → Implement → Review → QA**
workflow with RagMonk-backed project memory. This file is the canonical, provider-neutral
coordinator for `/osb`. Provider-specific files (`.claude/`, `.codex/`, `.github/`) bind
models and launch mechanics onto this workflow — they must never redefine it. Role agents
are self-contained and do not read this file or its references at dispatch time.

## Lifecycle

```text
0.  Resume check — resume from .osb/state/<task-id>.json if an active task exists.
1.  Resolve host.
2.  Resolve required role models from osb.yaml; never invent a missing model.
3.  Verify required RagMonk access.
4.  Load or create compact task state.
5.  Retrieve bounded, relevant knowledge before architecture.
6.  Dispatch Architect. Checkpoint CP1.
7.  Dispatch the minimum necessary Implementer(s), each with a unit capsule. Checkpoint CP2/CP3.
8.  Dispatch an independent Reviewer over the combined diff. Checkpoint CP4.
9.  Repair blocking findings using delta handoffs, then re-review. Checkpoint CP5.
10. Dispatch an independent QA once review is clean. Checkpoint CP6.
11. Repair failed acceptance criteria using delta handoffs (Implementer or Architect as needed), then re-review, then re-QA.
12. Consolidate durable knowledge; refresh RagMonk only if knowledge changed. Checkpoint CP7.
13. Report completion.
```

## Rules

- Never invent a missing model — stop and ask (see §Model resolution).
- Never forward full role transcripts between roles — pass only role-specific context
  (`references/handoff.md`).
- Retrieve knowledge and code context progressively and within budget
  (`references/ragmonk.md`).
- Persist execution state after every meaningful checkpoint (`references/state.md`).
- Persist durable knowledge only when new reusable knowledge exists; refresh RagMonk only
  then (`references/knowledge.md`).
- Default to one Implementer; split fan-out only when units are truly independent
  (`references/workflow.md` §Implementer fan-out).
- Keep successful build/test output to a short summary; never forward full logs.

## Model resolution

Every role dispatch, on every host, uses the model resolved from `models.<host>.<role>` in
`osb.yaml` — there is no host-wide or workflow-wide default. A role must never be
dispatched before its own model is resolved. If a role's configured model turns out to be
unavailable at dispatch time, stop and ask the user for a replacement for that role only.

When a role model is missing, ask:

```text
OSB does not have model configuration for <host>.

Which model should be used for:

Architect:
Implementer:
Reviewer:
QA:

You may also specify one model for all roles.
```

Persist the answer into `osb.yaml` when the host allows writing project files. Never
hardcode a "best model" ranking or replace a user-configured model automatically.

## Completion criteria

`/osb` is done for a task when: every acceptance criterion has a QA verdict of pass, the
Reviewer's most recent pass is clean, knowledge discovered during the task has been
consolidated, and RagMonk has been given the opportunity to index the result.

## Reference material

- `references/workflow.md` — full lifecycle detail, checkpoints, and control flow.
- `references/roles.md` — responsibilities, prohibitions, and output schemas per role.
- `references/handoff.md` — unit capsules, dispatch briefs, and delta-only repair loops.
- `references/knowledge.md` — incremental knowledge format, storage, watermark, and consolidation.
- `references/ragmonk.md` — RagMonk verification, retrieval budgets, and refresh policy.
- `references/state.md` — execution state schema, checkpoints, compaction, and resume.
