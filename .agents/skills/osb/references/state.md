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

```json
{
  "task_id": "OSB-2026-0919-001",
  "goal": "Add optimistic locking to CustomerRepository",
  "phase": "review",
  "architecture_checkpoint": "CP1",
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
    "open": ["F2"],
    "resolved": ["F1"]
  },
  "qa": {
    "status": "pending",
    "failed": []
  },
  "knowledge_watermark": "CP2"
}
```

`phase` is one of: `architecture`, `implementation`, `review`, `repair`, `qa`, `complete`.

`knowledge_watermark` records the last checkpoint whose durable knowledge (if any) has
already been made available for retrieval — see `knowledge.md` §Watermark.

## Checkpoints

Checkpoints are deltas appended to the audit trail and folded into the compact state file.
Save a checkpoint after each meaningful event; never replay the full checkpoint history to
a role.

| Checkpoint | When | Save | Never save |
| --- | --- | --- | --- |
| CP0 task-start | task begins | task id, compact goal, acceptance IDs if known, phase | — |
| CP1 architecture | Architect completes | decisions, interfaces, acceptance criteria, units, affected components, risks, durable architecture knowledge | Architect reasoning/exploration transcript, raw RagMonk output |
| CP2 unit-complete | an Implementer finishes a unit | unit id, changed files, verified AC ids, verification summary, new durable knowledge | — |
| CP3 unit-blocked | an Implementer is blocked | unit id, blocker, invalidated assumption, decision required | — |
| CP4 review | Reviewer reports | clean/findings, finding ids, severity, affected file/AC, durable review knowledge | Reviewer's full reasoning |
| CP5 repair | a repair completes | resolved finding ids, files changed, verification performed | — |
| CP6 qa | QA reports | pass/fail per AC, failed AC details, runtime/test discoveries, durable QA knowledge | full test logs |
| CP7 complete | task finishes | final status, task record path, updated component records | — |

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

CP4:

```json
{"checkpoint": "review", "status": "findings", "findings": [{"id": "F2", "severity": "blocker", "file": "src/CustomerRepository.cs", "ac": "AC3"}]}
```

CP5:

```json
{"checkpoint": "repair", "resolved": ["F2"], "changed": ["src/CustomerRepository.cs", "tests/CustomerRepositoryTests.cs"]}
```

CP6:

```json
{"checkpoint": "qa", "status": "fail", "failed": [{"ac": "AC3", "expected": "legacy row reads successfully", "actual": "500 error"}]}
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
  resolved: [F1, F2]
qa:
  failed: [AC4]
changed_files: [A.cs, B.cs, ATests.cs]
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
2. Determine `phase`.
3. Load only the state fields the next role's handoff needs (never the full checkpoint
   history).
4. Continue from the next role for that phase — do not rerun roles whose phase has
   already passed.

Examples:

```text
phase: review  → do not rerun Architect/Implementer; dispatch Reviewer with current diff
phase: qa      → do not replay review history; dispatch QA directly
```

This is what makes OSB resumable after interruption without replaying prior work or
re-spending tokens on roles that already finished their part.
