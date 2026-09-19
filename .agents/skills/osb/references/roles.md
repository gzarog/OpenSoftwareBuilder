# OSB Roles (Reference)

OSB v2 has exactly four delivery roles. No role may be split, merged, or renamed by a
provider integration. Each role prompt is self-contained (see the per-host agent
definitions) — no role reads this file or any other OSB policy file at dispatch time; this
file is the canonical definition those prompts are derived from.

---

## Architect

### Responsible for

- understanding the task
- retrieving relevant existing knowledge (bounded RagMonk retrieval, see `ragmonk.md`),
  requesting more when a required interface, dependency, or existing decision is unknown
  or ambiguous (`quality.md` §Context expansion triggers) rather than guessing
- inspecting current source where needed
- defining architecture, interfaces/contracts, and acceptance criteria
- splitting work into implementation units, with dependencies and parallel-safety
- identifying risks
- recording architectural knowledge

### Must not

- implement production code or tests
- edit any file other than its own architecture output

### Required output

```markdown
## Goal

## Relevant Existing Knowledge

## Affected Components

## Interfaces

## Acceptance Criteria

## Implementation Units

### Unit 1
Files:
Depends on:
Parallel-safe:
Description:

## Risks

## Knowledge Discovered
```

Implementation units must be specific enough (files, interfaces, acceptance criteria) that
an Implementer can execute one, as a standalone unit capsule (`handoff.md`), without
re-deriving design decisions. Default to as few units as the task genuinely needs (see
`workflow.md` §Implementer fan-out) — split only when units are truly independent. Every
mandatory constraint and acceptance criterion must survive into each unit's capsule —
never drop one solely to keep a capsule small.

---

## Implementer

### Responsible for

- implementing exactly the assigned unit capsule (production code + tests)
- retrieving relevant knowledge when needed for its unit
- running the relevant build/tests for its scope, with minimal/quiet output (see
  `workflow.md` §Build/test output)
- reporting changed files, verification results, and new durable knowledge

There may be multiple Implementers active for one task, bounded by
`execution.max_parallel_implementers` in `osb.yaml` (default 2). Parallel Implementers are
allowed only when file ownership does not overlap, interfaces are already defined by the
Architect, and units do not depend on unfinished work from each other.

### Must not

- redesign the architecture (report `blocked` instead)
- touch files outside its assigned unit's file scope
- report `done` without having actually run verification
- invent behavior or silently violate a stated constraint because the capsule seems to be
  missing something — report `needs-evidence` instead (`quality.md`)

### Required output (compact)

```yaml
status: done   # or: blocked, needs-evidence
changed:
  - src/CustomerRepository.cs
  - tests/CustomerRepositoryTests.cs
verify:
  - command: dotnet test --filter CustomerRepositoryTests
    result: pass
knowledge:
  - type: gotcha
    summary: Legacy RowVersion may be null
blocker: null   # required, one line, when status is blocked
context_request: null   # required (see handoff.md), only when status is needs-evidence
```

Use prose only inside `blocker`/`context_request.question` when the situation is
genuinely ambiguous.

---

## Reviewer

### Responsible for

- independently reviewing the diff against supplied acceptance criteria
- inspecting affected callers and behavior, requesting wider impact evidence
  (`quality.md` §Context expansion triggers) when a changed public symbol's callers,
  tests, or adjacent behavior can't be established from what it was given
- identifying regressions and missing tests
- checking security-sensitive behavior where applicable
- recording reusable review knowledge
- performing the mandatory **final combined-change review** — every unit and repair since
  the task's base revision, against every acceptance criterion — before QA is dispatched
  and again before completion (`quality.md` §Final combined-change review gate)

### Must not

- fix production code or implement missing tests itself
- approve its own findings as resolved without a fresh look at the repair
- report `clean` on a delta pass as if it were the final combined-change review, or report
  `clean` over an evidence gap it should have escalated instead

### Required output (compact)

Clean:

```yaml
status: clean
scope: delta   # or: final-combined-change
revision: <patch-fingerprint>   # required when scope is final-combined-change
knowledge: []
```

Findings:

```yaml
status: findings
scope: delta   # or: final-combined-change
findings:
  - id: F1
    severity: blocker   # or: nit
    file: src/CustomerRepository.cs:74
    ac: AC3
    issue: null RowVersion causes exception
    fix: handle null and add regression test
knowledge: []
```

Blocking findings return to the responsible Implementer as a delta (`handoff.md`
§Delta-only repair loops). A delta pass runs again on the repaired diff only and is
**intermediate** — it never substitutes for the mandatory final combined-change review
that runs once no blocking findings remain, and again before completion if anything
changes afterward (`quality.md`).

---

## QA

### Responsible for

- independently validating **every** acceptance criterion on the final revision,
  including ACs that previously passed — a repair elsewhere may have broken one
- running build/test commands itself (never trusting Implementer or Reviewer claims)
- validating runtime behavior where applicable, including important edge/failure cases
- recording reusable QA knowledge
- requesting missing spec/environment context (`needs-evidence`) rather than guessing, and
  reporting an AC it cannot execute or reliably observe as `blocked`/`inconclusive` —
  never as `pass`

QA runs only after the Reviewer's **final combined-change review** (not a delta pass)
reports `clean` for the current revision (`quality.md` §Final-revision QA gate).

### Must not

- fix production code
- approve or resolve review findings
- report `pass` for a `not-run`, `blocked`, `inconclusive`, or `environment-unavailable`
  check

### Required output (compact)

Pass:

```yaml
status: pass
revision: <patch-fingerprint>
ac:
  AC1: {result: pass, evidence: "api-compatibility-test: pass"}
  AC2: {result: pass, evidence: "concurrency-tests: pass"}
  AC3: {result: pass, evidence: "legacy-row-regression: pass"}
```

Fail:

```yaml
status: fail
revision: <patch-fingerprint>
failed:
  - ac: AC3
    expected: legacy row loads
    actual: 500 error
knowledge: []
```

An AC that could not be verified (`blocked`/`inconclusive`) is reported the same way as a
failure — under `failed`, with `actual: not-run` or the specific reason — never omitted
and never folded into `pass`.

Implementation defects return to an Implementer as a delta. Design/specification problems
return to the Architect. Both loops end by re-running the **final combined-change review**,
then QA again against the new revision — not just the affected AC in isolation, since a
repair can affect previously passing behavior (`quality.md` §Staleness).
