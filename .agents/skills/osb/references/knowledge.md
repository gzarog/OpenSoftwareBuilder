# OSB Incremental Knowledge (Reference)

Knowledge files are the durable source of truth. RagMonk is the index and retrieval layer
over them — never the authoritative store itself.

```text
OSB agents
   │
   ▼
knowledge files
   │
   ▼
RagMonk indexing
   │
   ▼
future OSB retrieval
```

## Supported knowledge types

```text
decision
constraint
discovery
gotcha
assumption
assumption-invalidated
review-finding
qa-result
follow-up
```

## Reporting knowledge (per role, during the task)

Any role may report knowledge at any checkpoint in its `## Knowledge Discovered` section.
Do not require empty knowledge events — if a role has nothing reusable to report, it
simply continues.

Example entry (as reported in a role's markdown output):

```yaml
type: gotcha
summary: Legacy customers may have a null LockState.
component: CustomerService
files:
  - src/CustomerService.cs
```

## Storage layout

```text
.osb/
└── knowledge/
    ├── events/
    │   └── <task-id>.jsonl
    │
    ├── tasks/
    │   └── YYYY-MM-DD-<task>.md
    │
    └── components/
        └── <component>.md
```

## Incremental flow (during a task)

After every meaningful role checkpoint, append the reported knowledge entries to
`.osb/knowledge/events/<task-id>.jsonl`, one JSON object per line:

```json
{"type":"gotcha","role":"implementer","component":"CustomerService","summary":"Legacy LockState may be null","files":["src/CustomerService.cs"]}
```

Then let RagMonk's watcher pick up the change, or trigger an incremental refresh if the
host's RagMonk integration requires an explicit call (see `ragmonk.md`). This is what lets
knowledge discovered by an earlier role in the same task be retrieved by a later role:

```text
Architect      → knowledge → RagMonk
Implementer A  → knowledge → RagMonk
Implementer B  → may retrieve A's discovery
Reviewer       → knowledge → RagMonk
QA             → knowledge → RagMonk
```

## Final consolidation (after clean QA)

1. Read `.osb/knowledge/events/<task-id>.jsonl` in full.
2. Discard transient/noise entries — superseded assumptions, duplicate discoveries,
   anything that only mattered mid-task.
3. Write one immutable task record at
   `.osb/knowledge/tasks/YYYY-MM-DD-<task-slug>.md` (see `templates/knowledge/task.md`).
   Task records describe **what happened** and are never edited after creation.
4. For every component touched, create or update
   `.osb/knowledge/components/<component>.md` (see `templates/knowledge/component.md`).
   Component records describe the **current durable state** of that component — edit them
   in place, don't append history to them.
5. Ensure RagMonk indexes the new/updated files (trigger a refresh if the host's
   integration needs one explicitly).
6. Keep the raw `events/<task-id>.jsonl` file for auditability, or archive it — do not
   delete it silently.

## Rules

- Do not make the RagMonk database the authoritative knowledge source — the files under
  `.osb/knowledge/` are authoritative; RagMonk indexes them.
- Do not skip consolidation for a non-trivial task. A genuinely trivial, single-file,
  no-new-decision task may skip it.
- Component records must stay accurate to current state — remove a "standing gotcha" once
  it no longer applies, rather than leaving stale entries.
