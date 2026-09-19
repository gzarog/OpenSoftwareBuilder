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

The canonical skill at `.agents/skills/osb/SKILL.md` carries Agent Skills frontmatter
(`name: osb`), so hosts that support Agent Skills — including VS Code Copilot — can
discover and invoke it natively as `/osb`. `copilot-instructions.md` is read
automatically by Copilot Chat/agent mode and carries general OSB integration rules (host
identity, per-role model binding, RagMonk access, knowledge consolidation) — it is not
what creates the `/osb` slash command itself.

## Invocation

```text
/osb <task>
```

This is the primary invocation, resolved through Copilot's Agent Skills mechanism against
the canonical skill. Copilot then dispatches roles via the `.github/agents/*.agent.md`
definitions, per `copilot-instructions.md`.

## RagMonk

Use RagMonk's MCP server if configured in your VS Code MCP settings. Otherwise fall back
to the RagMonk CLI. See `docs/RAGMONK.md`.

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
