# OSB on OpenAI Codex

## Setup

Copy into your project:

```text
.agents/skills/osb/       (canonical workflow — unmodified)
.codex/agents/architect.toml
.codex/agents/implementer.toml
.codex/agents/reviewer.toml
.codex/agents/qa.toml
osb.yaml                  (with models.codex.* filled in, or left blank to be prompted)
```

Each `.codex/agents/*.toml` file is the smallest possible launcher: it names the agent,
binds a model slot from `osb.yaml`, and points Codex at the canonical role definition in
`.agents/skills/osb/references/roles.md`. It does not duplicate the workflow.

## Invocation

Codex has no native `/osb`-style slash command for arbitrary skills. Trigger the workflow
by asking Codex directly, e.g.:

```text
Run the OSB workflow for: <task>
```

Codex should then read `.agents/skills/osb/SKILL.md`, resolve models for host `codex`
from `osb.yaml`, and drive the Architect → Implementer(s) → Reviewer → QA lifecycle using
the agents in `.codex/agents/`.

If your Codex setup supports custom prompt shortcuts, you can bind a shortcut (e.g.
`osb`) that expands to the line above — this is the "smallest possible compatibility
launcher" the OSB v2 contract calls for; it is not a separate copy of the workflow.

## Model binding

Each `.codex/agents/*.toml` has an empty `model = ""` placeholder. OSB resolves it from
`osb.yaml` → `models.codex.<role>` before dispatch; it is never hardcoded in the TOML
file, so switching models never requires editing the agent definitions.

## RagMonk

Prefer RagMonk's MCP integration if your Codex environment supports MCP servers.
Otherwise use the RagMonk CLI as a fallback. See `docs/RAGMONK.md`.
