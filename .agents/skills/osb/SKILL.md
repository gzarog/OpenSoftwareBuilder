---
name: osb
description: Run the OpenSoftwareBuilder Architect → Implement → Review → QA workflow with RagMonk-backed project memory.
argument-hint: <task>
---

# OSB Skill

OpenSoftwareBuilder (OSB) is a provider-neutral **Architect → Implement → Review → QA**
workflow with RagMonk-backed project memory. This file is the canonical, provider-neutral
source of truth for the `/osb` workflow. Provider-specific files (`.claude/`, `.codex/`,
`.github/`) are thin wrappers that bind models and launch mechanics onto this workflow —
they must never redefine it.

OSB is not an agent runtime. It defines workflow policy, roles, handoff contracts, model
selection rules, RagMonk usage, and knowledge capture. The host coding assistant (Claude
Code, Codex, or GitHub Copilot) provides everything else: execution, code navigation,
build/test running, and subagent orchestration.

## Invocation

```text
/osb <task>
```

`<task>` is a free-text description of the work to deliver. This is the canonical
invocation name; the exact syntax a host exposes it under can differ (e.g. Codex invokes
it as `$osb <task>`) — see the host-specific doc under `docs/` for the exact form.

## Roles

Exactly four roles exist. See `references/roles.md` for full detail.

- **Architect** — understands the task, retrieves knowledge, designs, splits work into
  implementation units, never edits production code.
- **Implementer** — implements one unit (code + tests), verifies it, reports knowledge.
  There may be several Implementers running in parallel on independent units.
- **Reviewer** — independently reviews the diff against acceptance criteria, never fixes
  production code.
- **QA** — independently validates every acceptance criterion against running
  build/tests/behavior, never fixes production code.

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

Full detail for each step is in `references/workflow.md`.

### 1. Resolve host

Detect which host is running the workflow: `claude-code`, `codex`, or `copilot`. The host
affects only how subagents are started, how models are assigned, and where host-specific
agent definitions live. The workflow itself never changes by host.

### 2. Resolve models

Read `osb.yaml` for the active host's role→model mapping (`architect`, `implementer`,
`reviewer`, `qa`). If any required role has no model configured, **stop and ask the user**
before execution starts — see "Model Resolution" below. Never invent a default model.

### 3. Verify RagMonk

When `ragmonk.enabled` and `ragmonk.required` are both true: verify RagMonk is reachable
(MCP preferred, CLI fallback) and that the current repository is registered/indexed. If
required access is unavailable, **stop the workflow** and explain exactly what needs to be
fixed. Do not silently fall back to ad hoc repository search. See `references/ragmonk.md`.

### 4. Retrieve relevant knowledge

Before architecture, query RagMonk for prior decisions, component knowledge, related
completed tasks, standing gotchas, constraints, and unresolved follow-ups relevant to
`<task>`. Keep retrieval bounded and relevant — never dump the whole knowledge base into
the Architect's context.

### 5. Run Architect

Dispatch the Architect with: the user task, current repository context, and the retrieved
knowledge excerpts. Require the output format in `references/roles.md` §Architect,
including implementation units with `Files`, `Depends on`, `Parallel-safe`, and
`Description`.

### 6. Run Implementer(s)

For each implementation unit, dispatch an Implementer with its exact scope (see
`references/handoff.md`). Units flagged `Parallel-safe: yes` with disjoint files and no
unmet dependency may run concurrently; anything else runs sequentially. Every Implementer
returns the format in `references/roles.md` §Implementer.

### 7. Run Reviewer

After all units for this pass are implemented, dispatch one Reviewer over the combined
diff. The Reviewer must be logically independent from implementation (do not reuse an
Implementer's context as the Reviewer). Required output in `references/roles.md`
§Reviewer.

### 8. Repair loop

If the Reviewer reports blocking findings, return them to the responsible Implementer(s),
then re-run the Reviewer. Repeat until review is clean.

### 9. Run QA

Only after a clean review, dispatch QA to validate every acceptance criterion from the
architecture stage. Required output in `references/roles.md` §QA.

### 10. Repair/design loop

- An **implementation defect** goes back to an Implementer, then Reviewer, then QA.
- A **design/specification problem** goes back to the Architect, then Implementer(s), then
  Reviewer, then QA.

Repeat until QA passes.

### 11. Consolidate knowledge

After clean QA, consolidate the task's incremental knowledge events into one immutable
task record and updated component records, per `references/knowledge.md`.

### 12. Complete

The task is complete when: QA passed, review is clean, knowledge has been consolidated,
and RagMonk has been given the chance to index the result.

## Model resolution

Model selection is always explicit — OSB must never silently choose a model for a role
that has none configured.

**Invariant:** every role dispatch, on every host, must use the model resolved from
`models.<host>.<role>` in `osb.yaml`. There is no host-wide or workflow-wide default model
— each of the four dispatches is bound independently:

```text
Architect   dispatch → model = models.<host>.architect
Implementer dispatch → model = models.<host>.implementer
Reviewer    dispatch → model = models.<host>.reviewer
QA          dispatch → model = models.<host>.qa
```

A role must never be dispatched before its own model is resolved, even if other roles'
models are already known. If a role's configured model turns out to be unavailable at
dispatch time, stop and ask the user for a replacement for that role only — never
silently substitute another role's model or a host default.

```text
/osb <task>
      │
      ▼
detect active host
      │
      ▼
read osb.yaml
      │
      ▼
are all required role models defined?
      │
   ┌──┴───┐
  yes     no
   │      │
continue  ask user
```

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

Rules:

1. Ask only for the roles that are actually missing a model.
2. Allow one model answer to apply to all roles.
3. Allow a different model per role.
4. Persist the answer into `osb.yaml` when the host allows writing project files.
5. Never hardcode a "best model" ranking inside OSB.
6. Never replace a user-configured model automatically.
7. If a configured model turns out to be unavailable at run time, ask the user for a
   replacement — do not silently substitute one.

## Handoff contract

Every role transition uses the same conceptual result shape (adapted per role, see
`references/handoff.md`):

```markdown
## Outcome

Completed | Blocked | Findings | Pass | Fail

## Changes

## Acceptance Criteria

## Verification

## Knowledge Discovered

## Blockers
```

## Incremental knowledge

Any role may report reusable knowledge at any checkpoint (type: `decision`, `constraint`,
`discovery`, `gotcha`, `assumption`, `assumption-invalidated`, `review-finding`,
`qa-result`, `follow-up`). Do not require empty knowledge events — if there is nothing
reusable to report, continue silently. See `references/knowledge.md` for storage and
consolidation.

## Completion criteria

`/osb` is done for a task when all of the following hold:

- Every acceptance criterion has a QA verdict of Pass.
- The Reviewer's most recent pass is Clean.
- Knowledge discovered during the task has been consolidated into a task record and any
  touched component records.
- RagMonk has been given the opportunity to index the new knowledge.

## Reference material

- `references/workflow.md` — full lifecycle detail and control flow.
- `references/roles.md` — full responsibilities, prohibitions, and output formats per role.
- `references/handoff.md` — the common handoff contract in detail.
- `references/knowledge.md` — incremental knowledge format, storage, and consolidation.
- `references/ragmonk.md` — RagMonk verification, retrieval, and failure behavior.
