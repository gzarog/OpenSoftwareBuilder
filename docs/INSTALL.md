# Installing OSB in a project

OSB v2 has no compiled runtime to install. A project adopts OSB by copying a small set of
files into its own repository.

## 1. Copy the canonical skill

```text
project/
└── .agents/skills/osb/     ← copy from this repo, unmodified
```

This directory is the single source of truth for the workflow. Never edit it per-project
— if a project needs different behavior, that belongs in `osb.yaml` or project-specific
knowledge, not in a fork of the skill.

## 2. Add provider-specific role definitions for the hosts you use

Copy whichever of these apply:

```text
.claude/skills/osb/SKILL.md
.claude/agents/{architect,implementer,reviewer,qa}.md

.codex/agents/{architect,implementer,reviewer,qa}.toml

.github/copilot-instructions.md
.github/agents/{architect,implementer,reviewer,qa}.agent.md
```

See `docs/CLAUDE.md`, `docs/CODEX.md`, and `docs/COPILOT.md` for host-specific notes.

## 3. Add `osb.yaml`

Copy `templates/osb.yaml` to the project root and fill in a model for every role, for
every host you use:

```yaml
models:
  claude-code:
    architect: <model id>
    implementer: <model id>
    reviewer: <model id>
    qa: <model id>
```

If you leave a role blank, `/osb` will ask for it the first time it's needed and can
persist your answer back into this file.

## 4. Set up `.osb/`

```text
.osb/
├── state/          ephemeral, per-task execution state — see templates/state/task.json
└── knowledge/
    ├── events/
    ├── tasks/
    └── components/
```

These directories are created automatically the first time `/osb` checkpoints or records
knowledge, but you can create them up front. Commit `.osb/knowledge/` to version control
— it's durable project memory, not scratch state. `.osb/state/` is safe to leave
untracked (or gitignore) if you don't want to commit ephemeral per-task progress; it isn't
required for resumability within a single working tree.

## 5. Set up RagMonk

See `docs/RAGMONK.md`. If you don't want to require RagMonk, set `ragmonk.required:
false` in `osb.yaml` (OSB will still use it opportunistically when reachable).

## 6. Run it

```text
/osb <task>
```

The exact invocation mechanics differ slightly per host — see the host-specific doc.
