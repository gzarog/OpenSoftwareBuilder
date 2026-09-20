# .osb/

Runtime data for OSB task execution, kept separate by durability:

```text
.osb/
├── state/        # ephemeral, mutable, per-task execution state — never indexed by RagMonk
│   └── <task-id>.json
│
└── knowledge/     # durable, selectively consolidated project memory — indexed by RagMonk
    ├── events/      <task-id>.jsonl   (incremental knowledge events during a task)
    ├── tasks/        YYYY-MM-DD-<slug>.md   (immutable, written once after clean QA)
    └── components/   <component>.md   (edited in place, current durable state)
```

See `osb/references/state.md` for the task state schema and checkpoint definitions, and
`osb/references/knowledge.md` for the knowledge format and consolidation rules.

`state/` is safe to leave untracked if a project prefers not to commit ephemeral,
per-session task state — resumability across a single working tree does not require git
tracking. `knowledge/` is the durable project memory OSB and RagMonk rely on across
sessions and should normally be committed.
