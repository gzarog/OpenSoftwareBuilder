# OSB on OpenAI Codex

## Setup

Copy the `osb/` package into your workspace, then register Codex:

```sh
bash ./osb/install.sh init --host codex
```

This generates:

```text
.agents/skills/osb/SKILL.md   (verbatim reproduction of osb/SKILL.md, for native discovery)
.codex/agents/architect.toml  (generated from osb/agents/architect.md + osb/hosts/codex/agent.toml.tmpl)
.codex/agents/implementer.toml
.codex/agents/reviewer.toml
.codex/agents/qa.toml
```

Each `.codex/agents/*.toml` file is a small, self-contained launcher: it names the agent,
sets its native `sandbox_mode`, and inlines that role's contract (allowed/prohibited
actions and required output schema) directly into `developer_instructions`, derived from
the canonical `osb/agents/<role>.md`. The agent does not read `SKILL.md` or the shared
reference files itself at dispatch time — it starts with no memory of any prior
conversation and needs no extra file reads to know its job. It never hardcodes a model —
see "Model binding" below.

## Invocation

`.agents/skills/osb/SKILL.md` is a generated, verbatim copy of `osb/SKILL.md` and carries
Agent Skills frontmatter (`name: osb`), so Codex can discover and invoke it directly:

```text
$osb <task>
```

If `$osb` isn't discovered automatically, fall back to explicit skill discovery:

```text
/skills
```

then select `osb` from the list. Do not advertise `/osb` on Codex unless your Codex
version has actually been smoke-tested to support it (see
`osb/docs/HOST_COMPATIBILITY.md`); `$osb` is the verified spelling.

Either path has Codex read `osb/SKILL.md` (via its generated copy), resolve models for
host `codex` from `osb.yaml`, and drive the Architect → Implementer(s) → Reviewer → QA
lifecycle using the agents in `.codex/agents/` — each running under its own
`sandbox_mode` (`architect`/`reviewer`/`qa`: `read-only`; `implementer`:
`workspace-write`).

Plain-English invocation (e.g. "Run the OSB workflow for: `<task>`") remains available as
a fallback.

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
Otherwise use the RagMonk CLI as a fallback. See `osb/docs/RAGMONK.md`.
