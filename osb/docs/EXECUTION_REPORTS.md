# Per-task execution reports (Next Improvements, Phase 5)

A concise, honest, user-facing report of one actual `/osb` run — distinct from
`osb/docs/BENCHMARKING.md`'s before/after **fixture** comparisons, which require a
`fixture_id` and exist for comparing workflow variants, not for reporting an ordinary
task. `osb/scripts/run_report.py` never re-dispatches a role, re-runs a test, or
re-indexes RagMonk — it is deterministic rendering from validated task state
(`osb/schemas/task-state.schema.json`) plus concise event records.

## Configuration

```yaml
reporting:
  enabled: true
  write_json: true
  write_markdown: true
```

Omitting the `reporting` block keeps today's behavior (a plain end-of-run summary per
`osb/references/workflow.md` §Step 15, no persisted report files).

## Capturing events

```sh
python osb/scripts/run_report.py record <task-id> event.json --workspace-root .
```

Append one concise record per checkpoint/role-dispatch boundary to
`.osb/runs/<task-id>/events.jsonl` — timestamp, role, unit/repo ids, fingerprints, outcome,
tool-call/retrieved-char/repair counts, and token counts **only if the host exposes them**.
Never write raw logs or full agent messages here (`osb/references/workflow.md` §Build/test
output already requires summarized output; this is the same discipline applied to the
report's own event log).

## Rendering a report

```sh
python osb/scripts/run_report.py render state.json request.json --workspace-root .
```

`request.json` supplies the optional context `render()` needs beyond `state.json` and the
event log: `host`, `models`, `started_at`/`ended_at`, `workspace_manifest_fingerprint`,
`preserved_worktree_paths`, `resume_instruction`, `partial_scan_or_impact_unknowns`,
`integration_checks_run`, `missing_test_evidence`, `metric_sources`, `evidence_refs`.
Writes a schema-validated (`osb/schemas/execution-report.schema.json`) `report.json` and a
readable `report.md` to `.osb/runs/<task-id>/`, on successful completion **or** when
execution stops blocked/failed — a report is never withheld just because the run didn't
finish cleanly.

## Report sections

1. **Task/status** — task id, host/models where known, elapsed time (measured or
   `unavailable`), `final_status` (`complete`/`blocked`/`failed`/`interrupted`, derived
   from `state.phase`/`state.recovery.status`, never invented), report-generation
   timestamp.
2. **Scope/delivery** — affected repositories, workspace manifest fingerprint, changed
   file counts, units and their status, final patch/workspace fingerprints.
   `local_changes_only` stays `true` unless the coordinator explicitly confirms changes
   were pushed/merged — this never implies a cross-repository atomic commit
   (`osb/docs/MULTI_REPO.md` §Verification, failure, and delivery).
3. **Quality** — required/verified/unverified AC ids, review status/scope/fingerprint, QA
   status/fingerprint, integration checks actually run, and missing test evidence stated
   explicitly. `verified_ac_ids` is `required_ac_ids - unverified_ac_ids` from state —
   a report can only ever show as verified what the completion gate itself would accept
   (`osb/references/quality.md` §Completion gate); it never infers coverage beyond that.
4. **Efficiency** — elapsed time, role dispatches, tool calls, tokens, RagMonk retrieved
   characters, context-broker cache hits/misses, context expansions, repair attempts, and
   repeated-failure blocks. Every metric is summed from `events.jsonl`; a metric no event
   ever reported is `"unavailable"`, never `0` (`osb/docs/METRICS.md` §Labelling
   discipline).
5. **Recovery/follow-up** — unresolved blockers (from `quality.unresolved_context_requests`
   and `recovery.last_blocker`), partial-scan/impact unknowns, preserved OSB worktree/
   branch paths, and an actionable resume instruction — never phrased so as to imply a
   blocked run is complete.
6. **Provenance** — evidence references and `metric_sources` labelled `measured` /
   `synthetic` / `unavailable` per `osb/docs/METRICS.md`.

## Example (illustrative only)

```text
OSB T123 — BLOCKED
Repositories: contracts, payments
Units: 2 complete, 1 blocked
Review: findings (scope: delta)
QA: 1/2 required AC(s) verified — unverified: AC2
Missing test evidence: payments integration environment unavailable
Elapsed: 812.0
Tokens: in=unavailable out=unavailable
Blockers: AC2 attempted twice; payments integration environment unavailable
Safe resume: /osb <same task> after the integration environment is configured
Report generated: 2026-09-20T00:00:00Z
```

## Idempotency and correctness

`render()` is a pure function of `state` + `events` (plus the caller-supplied context
above) — re-rendering the same snapshot produces the same meaningful fields, aside from
`report_generated_at` unless the caller pins it. An interrupted/incomplete event file still
yields a report; it is simply built from whatever events exist, and a `final_status` other
than `complete` makes that visible rather than hidden. A generated report is never treated
as RagMonk-indexable knowledge (`osb/references/knowledge.md` §Rules) and never changes
task acceptance status — only `osb/scripts/verify_task.py`'s completion gate does that.
