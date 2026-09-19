# OSB Roles (Reference)

OSB v2 has exactly four delivery roles. No role may be split, merged, or renamed by a
provider integration.

---

## Architect

### Responsible for

- understanding the task
- retrieving relevant existing knowledge (via the OSB skill's step 4, or its own targeted
  RagMonk queries)
- inspecting current source where needed
- defining architecture
- defining interfaces/contracts
- defining acceptance criteria
- splitting work into implementation units
- identifying dependencies between units
- identifying which units are parallel-safe
- identifying risks
- recording architectural knowledge

### Must not

- implement production code
- implement tests
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

### Unit 2
Files:
Depends on:
Parallel-safe:
Description:

## Risks

## Knowledge Discovered
```

Implementation units must be specific enough (files, interfaces, acceptance criteria) that
an Implementer can execute one without re-deriving design decisions.

---

## Implementer

### Responsible for

- receiving a clear implementation unit
- retrieving relevant knowledge when needed for its unit
- implementing production code
- implementing tests
- running the relevant build/tests for its scope
- reporting changed files
- reporting verification results
- capturing discoveries, constraints, gotchas, and invalidated assumptions encountered
  while implementing

There may be multiple Implementers active for one task. Parallel Implementers are allowed
only when file ownership does not overlap, interfaces are already defined by the
Architect, and work units do not depend on unfinished work from each other.

### Must not

- redesign the architecture (report a blocker instead if the spec is unworkable)
- touch files outside its assigned unit's file scope
- skip verification of its own unit before reporting Completed

### Required output

```markdown
## Outcome

Completed | Blocked

## Changed Files

## Implementation Summary

## Acceptance Criteria

## Verification

## Knowledge Discovered

## Blockers
```

---

## Reviewer

### Responsible for

- independently reviewing the implementation
- checking acceptance criteria against the diff
- inspecting affected callers and behavior
- identifying regressions
- identifying missing tests
- checking security-sensitive behavior where applicable
- reporting findings
- recording reusable review knowledge

### Must not

- fix production code
- implement missing tests itself
- approve its own findings as resolved without a fresh look at the repair

### Required output

```markdown
## Review Result

Clean | Findings

## Findings

### Finding 1

Severity:
File:
Problem:
Why it matters:
Required repair:
Acceptance criterion affected:

## Knowledge Discovered
```

Blocking findings return to the responsible Implementer. The Reviewer runs again on the
repaired diff. Repeat until Clean.

---

## QA

### Responsible for

- independently validating every acceptance criterion
- running build/test commands itself (not trusting Implementer or Reviewer claims)
- validating runtime behavior where applicable
- testing golden paths
- testing important edge/failure cases
- reporting expected vs. actual behavior
- recording reusable QA knowledge

QA runs only after the Reviewer reports Clean.

### Must not

- fix production code
- approve or resolve review findings

### Required output

```markdown
## QA Result

Pass | Fail

## Acceptance Criteria

### AC1
Expected:
Actual:
Result:

### AC2
Expected:
Actual:
Result:

## Commands / Actions Performed

## Defects

## Knowledge Discovered
```

Implementation defects return to an Implementer. Design/specification problems return to
the Architect. Both loops end by returning to the Reviewer, then back to QA.
