# Benchmarking (P1-F, Phase 6)

Optimizations elsewhere in OSB (compact handoffs, bounded retrieval, deterministic-first
classification) are worth keeping only if they hold up against measurement — this phase
adds the reporting, not new optimizations of its own.

## Run-metrics records

An optional, advisory record per run (`osb/schemas/run-metrics.schema.json`) — **never**
RagMonk-indexed knowledge, and never part of `.osb/state/` (`state.md` keeps only
execution-control fields). A missing figure (e.g. a host with no token-usage API) is
recorded as the literal string `"unavailable"`, never `0` — a `0` claims "measured zero,"
which is a different, false statement.

```json
{
  "fixture_id": "single-file-bug",
  "run_label": "baseline",
  "task_revision": "fp-8a3c1e",
  "metrics": {
    "elapsed_seconds": 145,
    "model_dispatches": 4,
    "tool_calls": 22,
    "input_tokens": "unavailable",
    "output_tokens": "unavailable",
    "repair_cycles": 0,
    "implementers_spawned": 1
  },
  "quality": {
    "ac_coverage": 1.0,
    "regressions_found": 0,
    "unresolved_blockers": 0,
    "repeatable": true
  }
}
```

## Producing a run-metrics record

Run one of the Phase 0 fixtures (`osb/tests/fixtures/tasks/*.json`) either as a live
`/osb` invocation on a real host (a **measured** run — cite host, date, commit) or as a
fixture-harness simulation that exercises `verify_task.py`/`classify_task.py` without a
live model (a **synthetic** run — see `osb/docs/METRICS.md` for the labelling
discipline). Record whichever metrics are actually available; never estimate a number and
present it as measured.

## Comparing two runs

```sh
python osb/scripts/benchmark_report.py baseline-run.json changed-run.json
```

`osb/scripts/benchmark_report.py`:

- refuses to compare runs from different fixtures or different `task_revision`s — a
  comparison is only meaningful against the identical task and patch fingerprint;
- reports a delta for every metric present in both runs, leaving a metric `"unavailable"`
  in the report the moment either run recorded it as unavailable (never substituting 0 or
  interpolating);
- checks `quality.ac_coverage` (lower is a regression), `quality.regressions_found` /
  `quality.unresolved_blockers` (higher is a regression), and `quality.repeatable`
  (`true` → `false` is a regression); **any** quality regression rejects the comparison
  (`verdict: REJECTED: ...`) regardless of how favorable the efficiency deltas look. A
  reduced token/tool-call count is never itself sufficient justification for a workflow
  change that also reduced AC coverage or increased blockers.

## Context capsule reuse

A revision-keyed capsule (the bounded knowledge/code excerpt already assembled for a given
`(repository_id, source_path, source_revision)` — see
`osb/references/knowledge.md` §Provenance and freshness) may be reused across roles or
across a repair loop's re-dispatch **only** while that exact source identity is unchanged.
This is the same dedup rule Phase 5 uses for knowledge events — Phase 6 doesn't add a new
cache, it reuses this identity to avoid repeated full-file reads or repeated retrieval of
identical chunks. **QA verdicts are never cached** this way: `quality.md` §Final-revision
QA gate requires every AC to be independently checked on the final revision every time; a
capsule-reuse rule for retrieved *context* must never be read as a shortcut for the
mandatory QA re-run itself.

## Relationship to per-task execution reports

`osb/schemas/run-metrics.schema.json` (this document) is for **before/after fixture**
comparisons and requires a `fixture_id` — it is not the right shape for reporting an
ordinary user task. `osb/docs/EXECUTION_REPORTS.md` (Next Improvements Phase 5) covers
that case with its own `osb/schemas/execution-report.schema.json`, with only an optional
linkage back to a benchmark fixture. Both share the same measurement labels and discipline
(`osb/docs/METRICS.md`).

## Tuning classification-based behavior

Only tune `task_profile`-based initial retrieval/parallelism (`workflow.md` §Task
classification) when a benchmark actually shows a benefit on a fixture, with quality held
constant. Escalation (`quality.md` §Context expansion triggers) is never tuned away —
evidence gaps and security/regression risk always widen scope regardless of what a
benchmark showed on an easier case.
