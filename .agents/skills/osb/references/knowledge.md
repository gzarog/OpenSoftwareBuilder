# OSB Incremental Knowledge (Reference)

Knowledge files are the durable source of truth. RagMonk is the index and retrieval layer
over them — never the authoritative store itself. **Durable knowledge is separate from
execution state** (`state.md`) — task phase, unit status, open findings, failed ACs, and
checkpoints belong in `.osb/state/`, not here.

```text
OSB agents
   │
   ▼
knowledge files (.osb/knowledge/)
   │
   ▼
RagMonk indexing (only when durable knowledge changed)
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

Events like "Reviewer started", "U1 completed", "tests passed", or "QA started" are
execution state, not knowledge — they belong in `.osb/state/<task-id>.json`, never in a
knowledge event.

## Reporting knowledge (per role, during the task)

Any role may report knowledge at any checkpoint in its `knowledge` field (Implementer,
Reviewer, QA — see `roles.md`) or `Knowledge Discovered` section (Architect). Do not
require empty knowledge events — if a role has nothing reusable to report, it simply
continues with an empty list.

Example entry:

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

After a checkpoint that contains new durable knowledge, append the reported entries to
`.osb/knowledge/events/<task-id>.jsonl`, one JSON object per line:

```json
{"type":"gotcha","role":"implementer","component":"CustomerService","summary":"Legacy LockState may be null","files":["src/CustomerService.cs"]}
```

A checkpoint that contains **no** durable knowledge does not append anything and does not
trigger a RagMonk refresh — see `ragmonk.md` §Refresh policy.

## Watermark

`state.md`'s task state carries `knowledge_watermark`: the last checkpoint whose durable
knowledge has already been made retrievable. Use it to avoid re-retrieving or re-injecting
the same knowledge into every subsequent role:

```text
Architect creates knowledge   → CP1 watermark
Implementer creates a gotcha  → CP2 watermark
Reviewer may retrieve knowledge created after CP1/CP2 only if relevant — not the full
knowledge base, and not knowledge it would already have received via its dispatch brief.
```

Advance the watermark whenever a checkpoint appends durable knowledge; leave it unchanged
otherwise.

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
5. Ensure RagMonk indexes the new/updated files (see `ragmonk.md` §Refresh policy).
6. Keep the raw `events/<task-id>.jsonl` file for auditability, or archive it — do not
   delete it silently.

## Rules

- Do not make the RagMonk database the authoritative knowledge source — the files under
  `.osb/knowledge/` are authoritative; RagMonk indexes them.
- Do not skip consolidation for a non-trivial task. A genuinely trivial, single-file,
  no-new-decision task may skip it.
- Component records must stay accurate to current state — remove a "standing gotcha" once
  it no longer applies, rather than leaving stale entries.
- Never index or treat `.osb/state/` as knowledge.
