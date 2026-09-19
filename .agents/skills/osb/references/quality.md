# OSB Quality Guardrails (Reference)

Token budgets, compact handoffs, delta repair loops, and bounded RagMonk retrieval
(`workflow.md`, `handoff.md`, `ragmonk.md`) are **starting points for cheap cases, not
evidence caps**. This file is the canonical source of the invariants that keep those
optimizations from silently trading away correctness. It does not restore a custom agent
runtime, duplicate the workflow itself, or remove the incremental checkpoints — it
constrains how they may be used.

## Non-negotiable principles

1. Quality is a gate; token budgets are starting points, not evidence caps.
2. No full transcripts by default. Expand only the information needed to resolve a named
   uncertainty.
3. Every mandatory requirement and acceptance criterion must survive handoff compaction.
4. After any code-changing repair, prior final-review and QA approvals are stale.
5. Complete only with a clean, final combined-change review and independent QA evidence
   for every AC against the final revision.
6. Inconclusive evidence is not success. Return `blocked`/`needs-evidence` rather than
   inventing confidence or silently dropping a check.
7. Explicit per-role models, independent Reviewer/QA, and `ragmonk.required` failure
   semantics are preserved — nothing here weakens them.

## Context expansion triggers

An agent **must** request more context (`needs-evidence`, see `handoff.md` §Agent-to-
coordinator expansion request) if one or more of these apply:

- RagMonk indicates truncated evidence, returns no relevant evidence for a required
  question, or a result hits its initial limit while an important dependency is still
  unresolved.
- A required interface, behavior, existing decision, data migration, caller, security
  assumption, or acceptance criterion is ambiguous or absent from the current capsule.
- A change may affect other components, shared contracts, authorization, money/data
  integrity, migrations, concurrency, or externally observable behavior beyond the
  capsule's initial file list.
- Review cannot establish whether a changed symbol's callers, tests, or adjacent behavior
  remain correct.
- QA cannot execute a required test or reliably observe the expected behavior.
- An unexpected change appears in the final diff, test output, or working tree.

Do **not** expand solely because more data exists. A context request must name the
unresolved question and the smallest next source likely to answer it (see `ragmonk.md`
§Adaptive retrieval for the escalation shape). The coordinator supplies only the
requested, relevant evidence — never a transcript dump — and the same role continues. If
the context is unobtainable, the task is `blocked` with the unresolved question, never
silently resolved.

## Final combined-change review gate

An initial (or repeat) Reviewer pass over one finding's repair is an **intermediate**
check only — it establishes that one finding is fixed, nothing more. It is never
sufficient by itself to reach QA or completion.

Before QA runs, and before completion, a **final combined-change review** is mandatory:
one Reviewer pass over the complete change — every unit, every repair, every changed file
— checked against every acceptance criterion, since the task's recorded base revision.
This does not mean reading the entire repository or the whole diff in one prompt: start
from `git diff --stat <base>`, enumerate changed files, inspect relevant patches in
manageable chunks, and expand to related files/symbols only when impact warrants it (see
`workflow.md` §Final combined-change review).

The final review's result is tied to an exact revision fingerprint (see §Fingerprinting
below), recorded in task state as `review.scope: final-combined-change` with
`review.reviewed_revision`. A finding that is still open never disappears from state just
because the latest Reviewer pass returned a short `clean` on a narrower scope.

## Final-revision QA gate

QA still receives only acceptance criteria, verification targets, affected areas, and
commands — never transcripts. In addition:

1. QA starts only after the final combined-change review is clean for the current patch
   fingerprint.
2. QA independently assesses **every** AC on the final code, including ACs that
   previously passed — a repair elsewhere may have broken one.
3. Each AC verdict carries minimal evidence: a command/test/observable result (or an
   explicit manual-check reference) plus the tested revision. Successful logs stay
   summarized; failures keep enough diagnostics to reproduce the problem.
4. `not-run`, `blocked`, `inconclusive`, or `environment-unavailable` is **never** `pass`.
   Ask for context, resolve the environment, or report a blocker — never report an
   unexecuted check as passing.
5. A repair after QA marks the affected (and potentially affected) verdicts stale;
   completion requires re-establishing both the final review and QA against the new
   fingerprint.

## Staleness

Any code, test, or config change after a final review or QA verdict invalidates that
verdict for the changed scope. At minimum, re-run an affected-scope review, then a fresh
final combined-change review, for the new fingerprint — and re-run QA for any AC the
change could affect. This applies equally after an explicit repair and after an external
working-tree modification discovered on resume (`state.md` §Resume support).

## Fingerprinting

A revision fingerprint identifies the exact effective patch a review or QA verdict
applies to. It must change when **tracked or uncommitted** implementation content
changes — a `HEAD` commit SHA alone is not sufficient, since agents may edit the working
tree without committing. Compute it as a reproducible hash/summary of the task's changed
tracked files plus any relevant untracked files, recorded at:

- CP0 — the task's base revision, before any implementation.
- Before final review — the current patch fingerprint.
- Before completion — recomputed and compared against the fingerprint the final review
  and QA verdicts were recorded against.

On resume, recompute the current fingerprint before trusting any persisted review/QA
approval (`state.md` §Resume support). If it doesn't match, re-enter the required
verification stage rather than resuming at completion.

## Completion gate

`/osb` completes a task only when **all** of the following hold simultaneously:

- The final combined-change review is clean for the current patch fingerprint.
- Every required acceptance criterion has an independent QA `pass` verdict for that same
  fingerprint — no AC is `not-run`, `blocked`, or `inconclusive`.
- There are no open blocking findings and no open evidence gaps
  (`state.md` → `quality.unresolved_context_requests`).
- Durable knowledge has been consolidated (`knowledge.md`).

This gate protects the token-saving optimizations elsewhere in OSB — it is deliberately
the one place completion cannot be inferred from a narrow, cheap check.
