# OSB Roles (Reference)

OSB v2 has exactly four delivery roles. No role may be split, merged, or renamed by a
provider integration. Each role prompt is self-contained (see the per-host agent
definitions) — no role reads this file or any other OSB policy file at dispatch time; this
file is the canonical definition those prompts are derived from.

---

## Architect

### Responsible for

- understanding the task
- retrieving relevant existing knowledge (bounded RagMonk retrieval, see `ragmonk.md`)
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
`workflow.md` §Implementer fan-out) — split only when units are truly independent.

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

### Required output (compact)

```yaml
status: done   # or: blocked
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
```

Use prose only inside `blocker` when the situation is genuinely ambiguous.

---

## Reviewer

### Responsible for

- independently reviewing the diff against supplied acceptance criteria
- inspecting affected callers and behavior
- identifying regressions and missing tests
- checking security-sensitive behavior where applicable
- recording reusable review knowledge

### Must not

- fix production code or implement missing tests itself
- approve its own findings as resolved without a fresh look at the repair

### Required output (compact)

Clean:

```yaml
status: clean
knowledge: []
```

Findings:

```yaml
status: findings
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
§Delta-only repair loops). The Reviewer runs again on the repaired diff only. Repeat until
`clean`.

---

## QA

### Responsible for

- independently validating every acceptance criterion
- running build/test commands itself (never trusting Implementer or Reviewer claims)
- validating runtime behavior where applicable, including important edge/failure cases
- recording reusable QA knowledge

QA runs only after the Reviewer reports `clean`.

### Must not

- fix production code
- approve or resolve review findings

### Required output (compact)

Pass:

```yaml
status: pass
ac:
  AC1: pass
  AC2: pass
  AC3: pass
```

Fail:

```yaml
status: fail
failed:
  - ac: AC3
    expected: legacy row loads
    actual: 500 error
knowledge: []
```

Implementation defects return to an Implementer as a delta. Design/specification problems
return to the Architect. Both loops end by returning to the Reviewer, then back to QA.
