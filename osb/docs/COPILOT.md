# OSB on GitHub Copilot / VS Code

## Setup

Copy the `osb/` package into your workspace, then register Copilot:

```sh
bash ./osb/install.sh init --host copilot
```

This generates:

```text
.agents/skills/osb/SKILL.md        (verbatim reproduction of osb/SKILL.md, for native discovery)
.github/copilot-instructions.md    (generated from osb/hosts/copilot/copilot-instructions.md.tmpl)
.github/agents/architect.agent.md  (generated from osb/agents/architect.md)
.github/agents/implementer.agent.md
.github/agents/reviewer.agent.md
.github/agents/qa.agent.md
```

`.agents/skills/osb/SKILL.md` carries Agent Skills frontmatter (`name: osb`), so hosts
that support Agent Skills — including VS Code Copilot — can discover and invoke it
natively as `/osb`. `copilot-instructions.md` is read automatically by Copilot Chat/agent
mode and carries general OSB integration rules (host identity, per-role model binding,
RagMonk access, knowledge consolidation) — it is not what creates the `/osb` slash command
itself.

## Invocation

```text
/osb <task>
```

This is the primary invocation, resolved through Copilot's Agent Skills mechanism against
the generated native skill copy. Copilot then dispatches roles via the
`.github/agents/*.agent.md` definitions, per `copilot-instructions.md`. Confirm this
invocation against your installed Copilot/VS Code version — see
`osb/docs/HOST_COMPATIBILITY.md` — before relying on it.

## RagMonk

Use RagMonk's MCP server if configured in your VS Code MCP settings. Otherwise fall back
to the RagMonk CLI. See `osb/docs/RAGMONK.md`.

## Model binding

`.github/agents/*.agent.md` files do not hardcode a model. Each role dispatch is bound to
its own resolved model, independently — there is no shared or default model across roles:

```text
Architect   dispatch → model = models.copilot.architect
Implementer dispatch → model = models.copilot.implementer
Reviewer    dispatch → model = models.copilot.reviewer
QA          dispatch → model = models.copilot.qa
```

A role is never dispatched before its own model is resolved. If a configured model is
unavailable, Copilot stops and asks the user for a replacement for that role only.
