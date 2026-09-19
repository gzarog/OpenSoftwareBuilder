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

Each `.codex/agents/*.toml` file is a small, self-contained launcher: it names the agent,
sets its native `sandbox_mode`, and inlines that role's contract (allowed/prohibited
actions and required output schema) directly into `developer_instructions`, derived from
the canonical `.agents/skills/osb/references/roles.md`. The agent does not read
`SKILL.md` or the shared reference files itself at dispatch time — it starts with no
memory of any prior conversation and needs no extra file reads to know its job. It never
hardcodes a model — see "Model binding" below.

## Invocation

The canonical skill at `.agents/skills/osb/SKILL.md` carries Agent Skills frontmatter
(`name: osb`), so Codex can discover and invoke it directly:

```text
$osb <task>
```

If `$osb` isn't discovered automatically, fall back to explicit skill discovery:

```text
/skills
```

then select `osb` from the list.

Either path has Codex read `.agents/skills/osb/SKILL.md`, resolve models for host `codex`
from `osb.yaml`, and drive the Architect → Implementer(s) → Reviewer → QA lifecycle using
the agents in `.codex/agents/` — each running under its own `sandbox_mode`
(`architect`/`reviewer`/`qa`: `read-only`; `implementer`: `workspace-write`).

Plain-English invocation (e.g. "Run the OSB workflow for: `<task>`") remains available as
a fallback, but `$osb <task>` is the primary, documented mechanism.

## Model binding

`.codex/agents/*.toml` files never set a `model` field. The OSB coordinator resolves each
role's model from `osb.yaml` independently before dispatch — there is no shared or
default model across roles:

```text
Architect   dispatch → model = models.codex.architect
Implementer dispatch → model = models.codex.implementer
Reviewer    dispatch → model = models.codex.reviewer
QA          dispatch → model = models.codex.qa
```

A role is never dispatched before its own model is resolved. If a required model is
missing or a configured model is unavailable, Codex stops and asks the user for that role
only, rather than falling back to a Codex default.

## RagMonk

Prefer RagMonk's MCP integration if your Codex environment supports MCP servers.
Otherwise use the RagMonk CLI as a fallback. See `docs/RAGMONK.md`.
