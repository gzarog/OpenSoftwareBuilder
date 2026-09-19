# OSB Handoff Contract (Reference)

Information moves forward as **references + compact state + deltas** — never as full
transcripts. A downstream role never receives an upstream role's reasoning, narrative, or
self-approval; it receives only the structured result it needs to do its own job
independently.

## Common result shape

Architect returns a design document (see `roles.md` §Architect). Implementer, Reviewer,
and QA return the compact schemas in `roles.md` — no free-form narrative report.

| Role | Outcome values | Shape |
| --- | --- | --- |
| Architect | (produces a spec, not an outcome) | Markdown sections: `Goal` / `Implementation Units` / etc. |
| Implementer | done \| blocked | Compact YAML: `status`, `changed`, `verify`, `knowledge` |
| Reviewer | clean \| findings | Compact YAML: `status`, `findings[]`, `knowledge` |
| QA | pass \| fail | Compact YAML: `status`, `ac{}` or `failed[]` |

Prose is used only when needed for ambiguity or a blocker that a structured field cannot
express cleanly.

## Implementer dispatch: unit capsules

Never send an Implementer the full original task transcript, the full Architect narrative,
unrelated acceptance criteria, all prior RagMonk evidence, or other Implementers' outputs.
Send exactly the **unit capsule** for its assigned unit:

```yaml
unit: U1
goal: Add optimistic locking to CustomerRepository

files:
  - src/CustomerRepository.cs
  - tests/CustomerRepositoryTests.cs

acceptance:
  - AC1
  - AC2
  - AC3

constraints:
  - public API unchanged
  - use existing RowVersion field

knowledge:
  - legacy RowVersion may be null

verify:
  - targeted CustomerRepository tests
```

`knowledge` here is the bounded set of durable knowledge entries (from `knowledge.md`)
relevant to this unit — never the whole knowledge base.

## Reviewer dispatch

Reviewer receives only:

```text
relevant acceptance criteria
changed file list
git diff / patch
targeted RagMonk impact data, if needed
```

Reviewer must **not** receive: Implementer reasoning, Implementer narrative, Implementer
self-approval, or the full Architect transcript. This protects independence as much as it
saves tokens — the Reviewer must reach its own conclusion from the diff and the acceptance
criteria, not from being told the Implementer already checked it.

## QA dispatch

QA receives only:

```text
acceptance criteria
verification targets
changed areas
required runtime/test commands
```

QA does not normally receive: Architect transcript, Implementer transcript, Reviewer
transcript, or RagMonk history. The Reviewer passes only `status: clean` (plus its
knowledge entries) to the coordinator; the coordinator then dispatches QA from the compact
task state (`state.md`), not from the Reviewer's output.

## Delta-only repair loops

A review or QA failure never replays the whole task, the whole architecture, all previous
findings, or all previous test output. Only the relevant delta moves.

### Review failure

Reviewer returns one finding:

```text
F2 | blocker | CustomerRepository.cs:74 | AC3
Legacy null RowVersion causes exception.
Required: handle null + add regression test.
```

The Implementer receives only: the unit reference, finding `F2`, the affected file, the
affected AC, and the required repair. After repair, the Reviewer receives only: finding
`F2` and the new patch/diff — not the whole task again.

### QA failure

QA returns one failed AC:

```text
AC3
expected: legacy row loads
actual: 500
```

The repair handoff includes only: the failed AC, the affected implementation unit, the
relevant files, and the failure evidence. The loop then runs
`Implementer/Architect → Reviewer → QA` with delta context only at each step.

## Dispatch brief checklist

Every role dispatch (subagent call, provider agent invocation, or context handoff) must
include only:

- the specific unit of work this role is responsible for right now,
- relevant acceptance criteria (not all of them, unless all are relevant),
- file scope, when applicable (Implementer, Reviewer),
- dependencies already resolved (interfaces, contracts, prior unit outputs),
- bounded, relevant knowledge excerpts — never the whole knowledge base,
- what verification is required before reporting done/clean/pass.

It must **not** include the full original user task statement verbatim, upstream roles'
full transcripts, or checkpoint history beyond what the receiving role's own fields need.

## Return contract

A role's response is not accepted as final until it matches its required schema in
`roles.md`. If a role returns an incomplete or malformed result, ask it to resubmit in the
correct format rather than guessing at missing fields.

## Knowledge reporting

Every role's output includes a `knowledge` field (Implementer/Reviewer/QA) or a
`Knowledge Discovered` section (Architect). It is optional — if the role found nothing
reusable, it is empty/omitted. See `knowledge.md` for the entry format and watermarking.

## Blockers

A `blocked` Implementer, or a QA `fail` routed to the Architect, must state precisely what
is blocking and what decision or information is needed to unblock — never just "stuck."
