# OSB Impact Analysis & Test Selection (Reference)

Task-specific impact analysis scopes *initial* review/test attention to what a change
plausibly affects — it never replaces RagMonk as the code-intelligence engine, and it
never narrows the mandatory final combined-change review or final QA on every required
acceptance criterion (`quality.md`). See `osb/docs/IMPACT_AND_TEST_SELECTION.md` for the
schema and worked examples.

## Division of responsibility

- **RagMonk** (`ragmonk.md`) remains the only code-intelligence/search engine OSB calls:
  exact-symbol lookup, callers/callees, lexical search, bounded explore, and impact
  queries. Nothing in this phase builds a second index.
- **`osb/scripts/impact_plan.py`** is deterministic parsing/normalization only: a minimal
  C# `<ProjectReference>` graph (metadata inspection, not a model) used to find confirmed
  in-repo dependents and candidate intermediate test projects, plus the merge/fingerprint/
  validation logic that combines those with whatever confirmed/possible impacts and
  unknowns a role's own RagMonk queries already established.

## When to build an impact plan

After task classification and pre-architecture retrieval (`workflow.md` §Step 5/6), once
the coordinator has a task-specific seed set — changed/likely-changed files or symbols,
contract names, and the confirmed workspace graph (`osb/docs/MULTI_REPO.md` §Discovery,
when used). Recompute the plan whenever the seed set, changed files, or workspace manifest
fingerprint changes materially — a stale impact plan is never presented as current.

## Query policy (RagMonk)

Follow the same progressive order as every other role (`ragmonk.md` §Progressive
retrieval policy): exact symbol → lexical → targeted impact/graph → bounded explore → full
file read only if necessary. Use `ragmonk_impact`/`ragmonk_callers`/`ragmonk_callees` for
cross-file blast radius beyond what the deterministic C# reference graph covers (other
languages, runtime/reflection-based consumers, shared contract callers). Record whatever
those queries establish as `confirmed_impacts[]` (with an explicit source/evidence
reference) or `possible_impacts[]` (with a `reason` and, where relevant, a `question`) —
never silently promote a `possible` result to `confirmed`.

## Confirmed vs. possible impacts

| | Confirmed | Possible |
| --- | --- | --- |
| Meaning | A specific caller, implementation, or project reference that concretely depends on the changed code | An indirect, ambiguous, or dynamically-resolved consumer |
| Source | Direct evidence: file + reference, exact caller/callee edge, resolvable project reference | A hint: matching name, shared contract with unknown consumers, dynamic dispatch |
| Effect on dispatch/test selection | Included in the affected-repository set, unit scope, and initial test targets | Never silently promoted; surfaces as a `needs-evidence` question when the ambiguity matters to an AC |

Absence of a graph result is never treated as proof of no impact — an unresolved dynamic
consumer, missing index, or graph-depth/traversal limit is recorded under `unknowns[]`
(with the specific question) and `truncated: true`, which is a cue to escalate
(`quality.md` §Context expansion triggers), not a green light.

## Test selection

`test_plan[]` entries are always `stage: intermediate` — they exist for fast feedback
during implementation, never as a substitute for the Reviewer's final combined-change
review or QA's independent verification of every required AC on the final revision
(`quality.md` §Final-revision QA gate). Selection precedence:

1. A user-approved or project-configured test command (`command_source:
   project-configured`) — the strongest signal, and the only kind that should be executed
   without further confirmation.
2. A safely discovered test project/file name (`command_source: discovered-suggestion`,
   `status: proposed`) — a *suggestion* only. Never execute a newly discovered command
   without explicit host/user authorization (`osb/scripts/safe_exec.py`
   `run_bounded(..., authorized=True)` is the enforcement point).

Record both executed and **not-executed** suggested tests (`status`) in task
state/reporting so a report can never imply blanket test coverage that didn't actually
run (`osb/docs/EXECUTION_REPORTS.md`).

## Interaction with the completion gate

Nothing here changes `quality.md` §Completion gate. Impact-scoped intermediate tests speed
up the repair loop; they never substitute for:

- the mandatory final combined-change review over every unit and repair since the task's
  base revision, and
- QA independently verifying **every** required acceptance criterion on the final
  revision, including ones an impact-scoped intermediate test already passed.

A missing configured test environment or an unresolved impact question remains
`blocked`/`needs-evidence`, never a silent pass.
