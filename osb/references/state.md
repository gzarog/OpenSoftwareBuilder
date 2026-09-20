# OSB Execution State (Reference)

Execution state is the compact, mutable, resumable record of an in-progress task. It is
distinct from durable knowledge (`knowledge.md`) and is never itself treated as
authoritative project memory.

```text
.osb/
├── state/
│   └── <task-id>.json        # this file
│
└── knowledge/                # durable, see knowledge.md
    ├── events/
    ├── tasks/
    └── components/
```

## Rules

- Task state is mutable, compact, execution-oriented, and resumable.
- Task state is not durable knowledge and is not indexed by RagMonk.
- Write `.osb/state/<task-id>.json` after every checkpoint (§Checkpoints below).
- The state file holds **current compact truth**, not a transcript. Checkpoints are an
  audit trail; agents consume the state file, never the whole checkpoint history.
- Never forward the state file's checkpoint history to a role — forward only the fields
  that role's handoff needs (see `handoff.md`).

## Task state schema

The machine-checkable contract is `osb/schemas/task-state.schema.json`
(`osb/scripts/verify_task.py` validates every task state file against it before trusting
it — see `quality.md` §Completion gate). This section is the human-readable walkthrough of
the same shape:

```json
{
  "task_id": "OSB-2026-0919-001",
  "goal": "Add optimistic locking to CustomerRepository",
  "phase": "review",
  "architecture_checkpoint": "CP1",
  "task_profile": "feature",
  "task_profile_rationale": "single-repo change touching one component, no cross-service contract",
  "risk_flags": [],
  "acceptance": {
    "AC1": "existing public API remains unchanged",
    "AC2": "concurrent update conflict returns expected domain error",
    "AC3": "legacy rows with null RowVersion remain readable"
  },
  "units": {
    "U1": {
      "status": "complete",
      "files": ["src/CustomerRepository.cs", "tests/CustomerRepositoryTests.cs"],
      "checkpoint": "CP2"
    }
  },
  "review": {
    "status": "findings",
    "scope": "delta",
    "open": ["F2"],
    "resolved": ["F1"]
  },
  "qa": {
    "status": "pending",
    "failed": []
  },
  "knowledge_watermark": "CP2",
  "quality": {
    "unresolved_context_requests": [],
    "required_ac_ids": ["AC1", "AC2", "AC3"],
    "task_base_revision": "<commit>",
    "current_patch_fingerprint": "<fingerprint>",
    "final_review_fingerprint": null,
    "final_qa_fingerprint": null,
    "unverified_ac_ids": []
  }
}
```

`phase` is one of: `architecture`, `implementation`, `review`, `repair`, `qa`, `complete`.

`task_profile` / `task_profile_rationale` / `risk_flags` record the coordinator's
deterministic-first classification (`workflow.md` §Task classification) — they select
initial context/execution strategy only and never weaken the AC set, the mandatory final
review, or independent QA. `null` until the coordinator classifies the task.

`knowledge_watermark` records the last checkpoint whose durable knowledge (if any) has
already been made available for retrieval — see `knowledge.md` §Watermark.

`quality` tracks the invariants in `quality.md` and is the only part of state that gates
completion:

- `unresolved_context_requests` — open `needs-evidence` requests (`handoff.md` §Agent-to-
  coordinator expansion request); completion requires this to be empty.
- `required_ac_ids` — the stable AC set the task must satisfy (`handoff.md` §AC coverage
  map).
- `task_base_revision` — the revision recorded at CP0, before any implementation.
- `current_patch_fingerprint` — recomputed before each final review and before completion
  (`quality.md` §Fingerprinting); must cover uncommitted/untracked implementation content,
  not just `HEAD`.
- `final_review_fingerprint` / `final_qa_fingerprint` — the fingerprint the last clean
  final combined-change review / passing QA run applied to. `null` until first set.
  Completion requires both to equal `current_patch_fingerprint`.
- `unverified_ac_ids` — required ACs without a current `pass` verdict on
  `final_qa_fingerprint`; must be empty at completion.

## Checkpoints

Checkpoints are deltas appended to the audit trail and folded into the compact state file.
Save a checkpoint after each meaningful event; never replay the full checkpoint history to
a role.

| Checkpoint | When | Save | Never save |
| --- | --- | --- | --- |
| CP0 task-start | task begins | task id, compact goal, acceptance IDs if known, phase, `task_base_revision`, initial `current_patch_fingerprint` | — |
| CP1 architecture | Architect completes | decisions, interfaces, acceptance criteria, units, affected components, risks, durable architecture knowledge | Architect reasoning/exploration transcript, raw RagMonk output |
| CP2 unit-complete | an Implementer finishes a unit | unit id, changed files, verified AC ids, verification summary, new durable knowledge, any new evidence gaps | — |
| CP3 unit-blocked | an Implementer is blocked | unit id, blocker, invalidated assumption, decision required | — |
| CP4 review | Reviewer reports | `scope` (delta or final-combined-change), clean/findings, finding ids, severity, affected file/AC, `reviewed_revision` when scope is final, durable review knowledge, open evidence gaps | Reviewer's full reasoning |
| CP5 repair | a repair completes | resolved finding ids, files changed, verification performed, updated `current_patch_fingerprint`, invalidation of `final_review_fingerprint`/`final_qa_fingerprint` | — |
| CP6 qa | QA reports | pass/fail per AC, failed/unverified AC details, runtime/test discoveries, durable QA knowledge, `final_qa_fingerprint` | full test logs |
| CP7 complete | task finishes | final status, task record path, updated component records — only once fingerprints match and `unverified_ac_ids`/`unresolved_context_requests` are empty | — |

### Examples

CP0:

```json
{"checkpoint": "task-start", "task_id": "OSB-2026-0919-001", "goal": "Add optimistic locking to CustomerRepository", "phase": "architecture"}
```

CP1:

```json
{"checkpoint": "architecture", "decisions": ["Use existing RowVersion field"], "acceptance": ["AC1", "AC2", "AC3"], "units": ["U1"], "components": ["CustomerRepository"]}
```

CP2:

```json
{"checkpoint": "unit-complete", "unit": "U1", "changed": ["src/CustomerRepository.cs", "tests/CustomerRepositoryTests.cs"], "verified": ["AC1", "AC2"], "verification": "targeted tests passed"}
```

CP3:

```json
{"checkpoint": "unit-blocked", "unit": "U1", "blocker": "Legacy schema allows null RowVersion", "decision_required": "Define null-version migration behavior"}
```

CP4 (delta):

```json
{"checkpoint": "review", "scope": "delta", "status": "findings", "findings": [{"id": "F2", "severity": "blocker", "file": "src/CustomerRepository.cs", "ac": "AC3"}]}
```

CP4 (final combined-change, after the delta is resolved):

```json
{"checkpoint": "review", "scope": "final-combined-change", "status": "clean", "reviewed_revision": "fp-8a3c1e"}
```

CP5:

```json
{"checkpoint": "repair", "resolved": ["F2"], "changed": ["src/CustomerRepository.cs", "tests/CustomerRepositoryTests.cs"], "current_patch_fingerprint": "fp-8a3c1e", "invalidated": ["final_review_fingerprint", "final_qa_fingerprint"]}
```

CP6:

```json
{"checkpoint": "qa", "status": "fail", "final_qa_fingerprint": "fp-8a3c1e", "failed": [{"ac": "AC3", "expected": "legacy row reads successfully", "actual": "500 error"}]}
```

CP7:

```json
{"checkpoint": "complete", "status": "complete", "task_record": ".osb/knowledge/tasks/2026-09-19-customer-locking.md", "components": [".osb/knowledge/components/customer-repository.md"]}
```

## Checkpoint compaction

Long tasks accumulate many checkpoints (e.g. CP1, CP2, CP3, CP4, CP5, CP6 review, CP6 QA
fail, CP5 repair, CP6 QA pass). Do not replay all of them to future agents. After each
checkpoint, fold it into the compact state file so the file always reflects current truth:

```yaml
phase: qa
architecture:
  ref: CP1
units:
  U1: complete
  U2: complete
review:
  status: clean
  scope: final-combined-change
  resolved: [F1, F2]
qa:
  failed: [AC4]
changed_files: [A.cs, B.cs, ATests.cs]
quality:
  current_patch_fingerprint: fp-8a3c1e
  final_review_fingerprint: fp-8a3c1e
  final_qa_fingerprint: null
  unverified_ac_ids: [AC4]
```

Rule: **checkpoints are an audit trail; the state file is current compact truth.** Agents
consume the state file, not the checkpoint history.

## Resume support

On `/osb <task>` start, check for existing active task state before starting a new task:

```text
if .osb/state/<task-id>.json exists and phase != complete:
    resume from state.phase
else:
    start a new task at CP0
```

Resume logic:

1. Read the state file.
2. Recompute `current_patch_fingerprint` and compare it against `final_review_fingerprint`
   and `final_qa_fingerprint` (`quality.md` §Fingerprinting). A mismatch means the working
   tree changed since those verdicts were recorded — they are stale.
3. Determine `phase`. If fingerprints matched in step 2, continue from the next role for
   that phase — do not rerun roles whose phase has already passed. If they didn't match,
   re-enter at the final combined-change review (or earlier, if the mismatch also affects
   an in-progress unit) rather than resuming later phases or completion.
4. Load only the state fields the next role's handoff needs (never the full checkpoint
   history).

Examples:

```text
phase: review, fingerprints match    → do not rerun Architect/Implementer; dispatch Reviewer with current diff
phase: qa, fingerprints match        → do not replay review history; dispatch QA directly
phase: complete, fingerprints differ → do not trust the stored completion; re-run final review, then QA
```

This is what makes OSB resumable after interruption without replaying prior work or
re-spending tokens on roles that already finished their part — while never reusing a
review/QA approval for code that has since changed.
