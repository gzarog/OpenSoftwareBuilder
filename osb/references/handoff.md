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
| Implementer | done \| blocked \| needs-evidence | Compact YAML: `status`, `changed`, `verify`, `knowledge` |
| Reviewer | clean \| findings \| needs-evidence | Compact YAML: `status`, `scope`, `revision`, `findings[]`, `knowledge` |
| QA | pass \| fail \| needs-evidence | Compact YAML: `status`, `revision`, `ac{}` or `failed[]` |

Prose is used only when needed for ambiguity or a blocker that a structured field cannot
express cleanly. `needs-evidence` (see §Agent-to-coordinator expansion request below) is
available to every role — it is not a failure, it is a request to keep going with the
missing piece supplied.

## Implementer dispatch: unit capsules

Never send an Implementer the full original task transcript, the full Architect narrative,
unrelated acceptance criteria, all prior RagMonk evidence, or other Implementers' outputs.
A capsule stays compact, but it must carry every **normative** detail the unit needs —
**never drop a mandatory requirement, constraint, or interface solely to fit a token
target.** Carry an exact, scoped quote or a file/reference when paraphrase could change
meaning. Send exactly the **unit capsule** for its assigned unit:

```yaml
unit: U1
goal: Add optimistic locking to CustomerRepository

files:
  - src/CustomerRepository.cs
  - tests/CustomerRepositoryTests.cs

acceptance:
  AC2: concurrent updates return the expected domain error

constraints:
  - preserve the existing public API
  - legacy null RowVersion values must remain readable

interfaces:
  - CustomerRepository.Update(expectedVersion, ...)

knowledge_refs:
  - .osb/knowledge/components/customer-repository.md#legacy-rows

verify:
  - targeted CustomerRepository tests
```

`acceptance` maps each relevant AC-ID to its exact requirement text, not just the ID —
compaction may omit *irrelevant* ACs, never truncate a relevant one's meaning.
`knowledge_refs` points at the bounded, relevant durable knowledge (from `knowledge.md`)
this unit needs — never the whole knowledge base; inline a `knowledge` excerpt instead of
a reference when the source is short. The coordinator remains responsible for full AC
coverage across the complete task — see §AC coverage map below.

## Reviewer dispatch

Two distinct review passes exist, and the dispatch differs:

- **Delta pass** (intermediate — after one repair): the finding, the affected file, the
  affected AC, and the new patch/diff for that finding only.
- **Final combined-change review** (mandatory before QA and before completion — see
  `quality.md` §Final combined-change review gate): the full set of acceptance criteria,
  the complete changed-file list since the task's base revision, and the combined
  diff/patch (inspected in chunks, not as one giant prompt), plus targeted RagMonk impact
  data if needed.

Either way, Reviewer must **not** receive: Implementer reasoning, Implementer narrative,
Implementer self-approval, or the full Architect transcript. This protects independence as
much as it saves tokens — the Reviewer must reach its own conclusion from the diff and the
acceptance criteria, not from being told the Implementer already checked it. A delta pass
returning `clean` establishes only that its one finding is fixed — it is never, by itself,
sufficient to dispatch QA or to complete the task.

## QA dispatch

QA receives only:

```text
acceptance criteria (all of them, on the final combined-change review)
verification targets
changed areas
required runtime/test commands
the current patch fingerprint (quality.md §Fingerprinting)
```

QA does not normally receive: Architect transcript, Implementer transcript, Reviewer
transcript, or RagMonk history. QA is dispatched only once the final combined-change
review — not a delta pass — reports `clean` for the current fingerprint. The coordinator
dispatches QA from the compact task state (`state.md`), not from the Reviewer's raw
output.

## Delta-only repair loops

A review or QA failure never replays the whole task, the whole architecture, all previous
findings, or all previous test output. Only the relevant delta moves — but a delta repair
never substitutes for the mandatory final combined-change review and final QA that follow
it (`quality.md`).

### Review failure

Reviewer returns one finding:

```text
F2 | blocker | CustomerRepository.cs:74 | AC3
Legacy null RowVersion causes exception.
Required: handle null + add regression test.
```

The Implementer receives only: the unit reference, finding `F2`, the affected file, the
affected AC, and the required repair. After repair, the Reviewer receives only: finding
`F2` and the new patch/diff — this delta pass is intermediate; the final combined-change
review still runs once no blocking findings remain.

### QA failure

QA returns one failed AC:

```text
AC3
expected: legacy row loads
actual: 500
```

The repair handoff includes only: the failed AC, the affected implementation unit, the
relevant files, and the failure evidence. The loop then runs
`Implementer/Architect → Reviewer (final combined-change) → QA (final revision)` with
delta context only at each repair step — but the review and QA that close the loop are
always the full, final-revision passes, never a delta shortcut.

## Agent-to-coordinator expansion request

Any role may report `status: needs-evidence` instead of guessing when a `quality.md`
§Context expansion trigger applies:

```yaml
status: needs-evidence
context_request:
  question: Does Update have callers outside CustomerService?
  reason: Public contract changed; initial impact result hit its limit.
  request: ragmonk_callers CustomerRepository.Update with wider scoped limit
  ac: AC2
```

The coordinator supplies only the requested, relevant evidence (or authorizes the named
tool call); the same role then continues from where it left off. If the context is
unobtainable, the task becomes `blocked` with the unresolved question. Never let
`needs-evidence` silently become `done`, `clean`, or `pass` — and never respond to it with
the whole task transcript.

## AC coverage map

The coordinator keeps a stable `AC-ID → requirement text → affected unit(s) →
verification target(s)` map in task state (`state.md`). If the Architect changes a
requirement or interface mid-task, update every affected capsule and invalidate the
work/checks it impacts before resuming that unit, review, or QA.

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

A `blocked` Implementer, a `needs-evidence` role whose context request came back
unanswerable, or a QA `fail` routed to the Architect, must state precisely what is
blocking and what decision or information is needed to unblock — never just "stuck."
`not-run`, `inconclusive`, or `environment-unavailable` results are never reported as
`done`, `clean`, or `pass` — see `quality.md` §Final-revision QA gate.
