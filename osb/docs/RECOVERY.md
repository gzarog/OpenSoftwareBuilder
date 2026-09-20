# Failure recovery & execution limits (Next Improvements, Phase 4)

Bounded retries and resume support that never weaken the completion gate
(`osb/references/quality.md`). `osb/scripts/recovery_policy.py` is deterministic
bookkeeping only — it never dispatches a role, never fixes anything, and never turns a
`blocked`/`needs-evidence` result into a pass.

## Configuration

```yaml
execution:
  max_repair_attempts_per_finding: 3
  max_identical_failure_repeats: 2
  max_context_expansions_per_question: 5
```

These are the documented safe defaults; omitting them keeps exactly this behavior. Retry
counters are keyed by **task + role + finding/AC/question + source fingerprint** — never a
global attempt counter, so resolving one failure is never blocked by an unrelated one
hitting its own budget.

## Failure classification

| Situation | Handling |
| --- | --- |
| Recoverable implementation failure — same finding/AC, meaningfully changed patch | Another targeted repair, within `max_repair_attempts_per_finding` |
| Repeated identical failure — same normalized failure signature **and** unchanged implementation fingerprint | Stop blind retries at `max_identical_failure_repeats`; route a concise blocker to the Architect/coordinator |
| Architecture/contract mismatch | Route to Architect for a delta decision; a changed AC/interface invalidates affected capsules and prior verification |
| Missing evidence / RagMonk unavailable / test environment unavailable / unresolved dependency / worktree conflict | `blocked`/`needs-evidence` — never success, never a silent switch to an unapproved alternative |
| Interruption/crash | Resume from persisted phase and verified fingerprints; completed unaffected units stay saved, but approvals on changed combined content go stale |

```sh
python osb/scripts/recovery_policy.py evaluate request.json --workspace-root . [--record]
python osb/scripts/recovery_policy.py record event.json --workspace-root .
python osb/scripts/recovery_policy.py status <task-id> --workspace-root .
```

`evaluate` reads `.osb/runs/<task-id>/recovery.jsonl` and returns one of:

- `retry` — within both budgets; another targeted attempt is authorized.
- `stop-identical-failure` — the same failure signature recurred against the same,
  unchanged implementation fingerprint; route a blocker instead of retrying again.
- `attempts-exhausted` — the per-finding repair-attempt budget is spent.
- `expand-context` / `question-unresolved` — the context-expansion equivalent for a named
  unanswered question (`osb/references/quality.md` §Context expansion triggers): reaching
  the limit reports the question unresolved with the next required source/action, and
  never truncates a mandatory requirement or bypasses QA.

`--record` (or the separate `record` subcommand) appends the schema-validated event
(`osb/schemas/recovery-event.schema.json`) to the append-only log. `status` is read-only —
it never becomes a competing orchestrator.

## Re-authorization

A `root_cause_id` scopes the repair-attempt budget. Passing a **new** `root_cause_id` for
the same finding is a coordinator's explicit acknowledgment that a genuinely new root
cause (or source revision) has been established — it starts a fresh attempt series rather
than being permanently blocked by an earlier, unrelated exhaustion. This is never inferred
automatically from a changed implementation fingerprint alone; the coordinator decides and
states the new root cause.

## Task-state extension

`osb/schemas/task-state.schema.json`'s `phase` enum gains `blocked` — a task can now
express "not complete, not silently abandoned" without claiming completion. An optional
`recovery` object (`status`, `blocked_role`, `last_blocker`, `events_file`, per-target
`attempts` counters) summarizes the event log for a coordinator/report without storing
full logs or transcripts in state. `osb/scripts/verify_task.py check_completion()` rejects
a state whose `phase` or `recovery.status` is `blocked` — a blocked run is never reported
as complete regardless of what its review/QA fingerprints say.

## Resume and worktrees

Resume reuses the existing machinery rather than duplicating it:

- `osb/references/state.md` §Resume support and `osb/references/quality.md`
  §Fingerprinting still govern recomputing the current patch fingerprint and comparing it
  against persisted review/QA fingerprints before trusting any prior approval.
- `osb/scripts/worktree_guard.py list_osb_worktrees()` gives a read-only inventory of every
  OSB-created worktree so a resumed task can reconcile in-flight units against what
  actually exists on disk — recovery never force-resets, cleans, or deletes a worktree or
  branch automatically; an unresolved conflict is described as a safe manual action, not
  performed automatically.
- Unaffected, already-`complete` unit checkpoints are reused; only affected planning/
  implementation is rerun. Any repair (from any cause) still re-enters the mandatory final
  combined-change review and full QA before completion, per `quality.md` §Staleness — this
  phase enforces retry *limits*, it never shortens what a passing verdict requires.
