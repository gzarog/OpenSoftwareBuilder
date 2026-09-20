# Impact analysis & test selection (Next Improvements, Phase 2)

Opt-in, per-task scoping that speeds up the intermediate feedback loop without weakening
the mandatory final combined-change review or final QA (`osb/references/quality.md`). See
`osb/references/impact.md` for the RagMonk query policy this builds on.

## Configuration

```yaml
impact:
  enabled: true
  max_depth: 3
  include_tests: true
```

Omitting the `impact` block (the default) means no impact plan is built — task scoping
falls back to today's behavior. `max_depth`/`include_tests` are advisory to the coordinator
when scoping RagMonk queries; the deterministic C# reference-graph analysis below is not
itself depth-limited by this key (it uses `impact_plan.py`'s own bounded traversal).

## Building a plan

```sh
python osb/scripts/impact_plan.py build request.json --workspace-root . [--out PATH]
python osb/scripts/impact_plan.py validate .osb/cache/impact/<task-id>.json
```

`request.json` supplies the task id, the (typically manifest-derived) repository list, the
changed/seed files per repository, and — optionally — whatever confirmed/possible impacts
and unknowns the coordinator's own RagMonk queries already established
(`external_confirmed_impacts`, `external_possible_impacts`, `external_unknowns`,
`external_truncated`):

```json
{
  "task_id": "OSB-2026-0919-001",
  "repositories": [
    {"id": "contracts", "path": "shared-contracts"},
    {"id": "payments", "path": "services/payments-api"}
  ],
  "changed_files": {
    "contracts": ["src/IPaymentContract.cs"]
  },
  "workspace_manifest_fingerprint": "wmf-...",
  "ac_to_repository_map": {"AC2": ["contracts", "payments"]}
}
```

`build` writes a schema-validated (`osb/schemas/impact-plan.schema.json`) record to
`.osb/cache/impact/<task-id>.json` and refuses to write anything that fails validation.

## What the deterministic C# analysis contributes

For each changed file, `impact_plan.py` finds its owning `.csproj` (nearest ancestor
project file, or the file itself if it already is one) and walks the in-repository
`<ProjectReference>` graph backwards to find every project that transitively depends on
it. Each such dependent becomes a `confirmed_impacts[]` entry (`kind: project-reference`,
or `test-dependent` when the dependent looks like a test project by name/location), and
every test-like dependent becomes an `intermediate`-stage `test_plan[]` suggestion.

A changed file with no discoverable owning project becomes an `unknowns[]` entry rather
than being silently skipped. Hitting the internal traversal bound (very large dependency
fan-out) sets `truncated: true` — a cue for the coordinator to escalate via
`needs-evidence` (`osb/references/quality.md` §Context expansion triggers), never proof
that no further impact exists.

## Executing test_plan entries

Every `test_plan` entry starts `command_source: discovered-suggestion`,
`status: proposed` — nothing in `impact_plan.py` runs a command. A coordinator authorizes
and executes a specific entry (e.g. via `osb/scripts/safe_exec.py`'s `run_bounded(...,
authorized=True)`) only after confirming the command against project convention, then
updates the entry's `status` to `executed` or `not-executed` for the run's report
(`osb/docs/EXECUTION_REPORTS.md`) — a report can never claim blanket coverage from
suggestions that were never actually run.

## Relationship to final review and QA

Nothing here changes `osb/references/quality.md` §Completion gate. Intermediate,
impact-scoped tests exist for fast feedback during implementation; the Reviewer's final
combined-change review and QA's independent verification of **every** required acceptance
criterion on the final revision still run in full, regardless of what an impact-scoped
test already covered.
