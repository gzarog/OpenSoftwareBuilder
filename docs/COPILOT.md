# OSB on GitHub Copilot / VS Code

## Setup

Copy into your project:

```text
.agents/skills/osb/              (canonical workflow — unmodified)
.github/copilot-instructions.md
.github/agents/architect.agent.md
.github/agents/implementer.agent.md
.github/agents/reviewer.agent.md
.github/agents/qa.agent.md
osb.yaml                         (with models.copilot.* filled in, or left blank)
```

`copilot-instructions.md` is read automatically by Copilot Chat/agent mode in VS Code. It
tells Copilot to treat `/osb <task>` (or a plain-English request to run the OSB workflow)
as an instruction to load `.agents/skills/osb/SKILL.md` and follow it, dispatching roles
via the `.github/agents/*.agent.md` definitions.

## Invocation

```text
/osb <task>
```

VS Code Copilot does not natively support arbitrary custom slash commands the way Claude
Code does; `copilot-instructions.md` is the compatibility layer that makes the same
`/osb <task>` phrasing work by instructing Copilot what to do when it sees it, without
duplicating the workflow itself.

## RagMonk

Use RagMonk's MCP server if configured in your VS Code MCP settings. Otherwise fall back
to the RagMonk CLI. See `docs/RAGMONK.md`.

## Model binding

`.github/agents/*.agent.md` files do not hardcode a model. Copilot resolves the model for
each role from `osb.yaml` → `models.copilot.<role>` before dispatching that role.
