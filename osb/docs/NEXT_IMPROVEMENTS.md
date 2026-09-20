# Next Improvements (Phases 0–5)

This is the one-page index for OSB's "next improvements" work: multi-repository
discovery, task-specific impact analysis and test selection, an evidence-aware context
broker, stronger failure recovery, and per-task execution reports. It extends the existing
`osb/` package, schemas, references, and scripts documented in `OSB_V2_CONTRACT.md` — it
does not add a fifth agent, a compiled runtime, a daemon, a secondary knowledge database, a
mandatory UI, or a new provider abstraction, and it does not change the
Architect → Implementer(s) → Reviewer → QA lifecycle or its completion gate
(`references/quality.md`).

Every feature below is **opt-in**: a project with no new `osb.yaml` keys retains exactly
today's behavior (see `templates/osb.yaml`).

| Phase | Feature | Docs | Schema(s) | Script(s) |
| --- | --- | --- | --- | --- |
| 1 | Multi-repository discovery | `MULTI_REPO.md` §Discovery | `schemas/workspace-manifest.schema.json` | `scripts/workspace_discovery.py` |
| 2 | Task-specific impact analysis & test selection | `IMPACT_AND_TEST_SELECTION.md` | `schemas/impact-plan.schema.json` | `scripts/impact_plan.py` |
| 3 | Evidence-aware context broker | `CONTEXT_BROKER.md` | `schemas/context-capsule.schema.json` | `scripts/context_broker.py` |
| 4 | Failure recovery & execution limits | `RECOVERY.md` | `schemas/recovery-event.schema.json` | `scripts/recovery_policy.py` |
| 5 | Execution reports | `EXECUTION_REPORTS.md` | `schemas/execution-report.schema.json` | `scripts/run_report.py` |

## Artifact ownership

```text
Authoritative:      osb.yaml, source repositories, .osb/state/, .osb/knowledge/
Derived/ephemeral:  .osb/cache/, .osb/context/, .osb/runs/
```

- `.osb/cache/` — derived, recomputable artifacts: the confirmed workspace manifest
  (`.osb/cache/workspace-manifest.json`) and per-task impact plans
  (`.osb/cache/impact/<task-id>.json`). Corruption here is recovered by recomputing from
  authoritative inputs (`osb.yaml`, source repositories, task state) — never from guessing.
- `.osb/context/` — derived, per-task, per-role evidence capsules
  (`.osb/context/<task-id>/<role>-<unit>.json`). Never authoritative; never contains
  secrets; safe to delete and regenerate at any time.
- `.osb/runs/` — append-only, per-task recovery events and execution-report records
  (`.osb/runs/<task-id>/{recovery.jsonl,events.jsonl,report.json,report.md}`). Deterministic
  outputs of the task's own state and event log; regenerating a report never re-dispatches a
  role or re-runs a test.
- `.osb/state/` and `.osb/knowledge/` are unchanged in ownership and semantics
  (`references/state.md`, `references/knowledge.md`) — none of the above ever substitutes
  for them, and none of them is indexed by RagMonk.

All of the above are generated inside the root OSB workspace; nothing here requires the
root workspace itself to be a Git repository in multi-repo mode, and nothing here is
written into RagMonk's own database. Add the ephemeral paths above to the workspace's
`.gitignore` only with an explicit, safe merge into a user-owned file — never overwrite an
existing `.gitignore` wholesale.

## Compatibility

Every new `osb.yaml` key documented across the five features above is optional and
namespaced under `workspace.discovery`, `impact`, `context`, `execution`, or `reporting`
(see `templates/osb.yaml`). An existing project with none of these keys present continues
to behave exactly as before: single-repo mode by default, no impact-based test selection,
no context broker, today's retry/resume behavior, and no generated execution report beyond
what `references/state.md`/`quality.md` already require.

## Non-negotiable invariants unchanged by this work

- Final combined-change review and independent, per-AC final QA remain mandatory
  (`references/quality.md`) — no narrow test-selection plan or cached evidence capsule ever
  substitutes for them.
- `ragmonk.required: true` failure semantics are unchanged — no silent fallback to ad hoc
  search (`references/ragmonk.md`).
- Token/context budgets remain starting points, never evidence caps
  (`references/quality.md` §Context expansion triggers).
- OSB never overwrites user-modified files, deletes a worktree/branch it did not create, or
  runs an automatically discovered command without explicit authorization
  (`scripts/safe_exec.py`, `scripts/worktree_guard.py`).
