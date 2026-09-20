# OSB measurement method (Phase 0)

This defines the metrics used to compare OSB behavior before/after a change (Phase 6
benchmarking depends on these definitions) and the discipline for reporting them: every
number is labelled **measured**, **synthetic**, or **not available** — never presented as
a real improvement unless it was actually measured on a real run.

## Common metrics

| Metric | Definition | Source |
| --- | --- | --- |
| Elapsed time | Wall-clock time from `/osb <task>` invocation to completion report | host session timing |
| Model dispatches | Count of role invocations (Architect + each Implementer + each Reviewer pass + QA) | task state checkpoints |
| Tool calls | Count of tool invocations across all role dispatches, if the host exposes it | host session logs |
| Tokens | Input/output tokens per role dispatch, if the host exposes it | host usage reporting |
| Retrieved characters | Characters returned by RagMonk queries (`ragmonk_explore`/`_search`/etc.) | RagMonk response sizes |
| Repair cycles | Count of review/QA repair loops (`workflow.md` §Repair loop) before completion | task state (`review`/`qa` history) |
| AC verification coverage | `verified ACs / required_ac_ids` at completion | task state `quality.unverified_ac_ids` |
| Regression/failure rate | Fraction of fixture runs where a previously-passing AC failed after a later change | fixture harness results |

## Labelling discipline

- **measured** — an actual number recorded from a real run (a fixture harness execution,
  a live host smoke test, or this repository's own CI). Cite the run (date, commit,
  fixture name).
- **synthetic** — a number derived from a fixture/simulation that does not involve a live
  model dispatch (e.g. counting checkpoints a fixture *would* produce). Useful for
  regression-testing the schema/verifier logic, but never presented as a real efficiency
  claim.
- **not available** — the host doesn't expose the figure (e.g. token counts on a host with
  no usage API), or no run has been performed yet.

Never write "X% faster" or "Y% fewer tokens" without a **measured** entry for both the
baseline and the changed run, on the same fixture and the same patch fingerprint. A
structural/schema check passing is not evidence a run actually behaved a given way — see
`osb/references/quality.md` §Non-negotiable principles.

## Where this is used

- Phase 0: this document + the fixtures under `osb/tests/fixtures/tasks/` establish the
  baseline measurement method before any workflow-policy change.
- Phase 6 (`osb/scripts/benchmark_report.py`): produces a before/after report using these
  same definitions and labels, run against identical fixture task revisions.
