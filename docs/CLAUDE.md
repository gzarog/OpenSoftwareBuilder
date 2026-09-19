# OSB on Claude Code

## Setup

Copy into your project:

```text
.agents/skills/osb/          (canonical workflow — unmodified)
.claude/skills/osb/SKILL.md  (thin wrapper)
.claude/agents/architect.md
.claude/agents/implementer.md
.claude/agents/reviewer.md
.claude/agents/qa.md
osb.yaml                     (with models.claude-code.* filled in, or left blank to be
                               prompted on first run)
```

## Invocation

```text
/osb <task>
```

Claude Code loads `.claude/skills/osb/SKILL.md`, which points at the canonical
`.agents/skills/osb/SKILL.md` for the actual workflow, then dispatches each role as a
Claude Code subagent using the Agent tool with `subagent_type` set to `architect`,
`implementer`, `reviewer`, or `qa`, and `model` set to the model resolved from
`osb.yaml`.

Every role dispatch must use the model resolved from `models.claude-code.<role>` — there
is no shared or default model across roles:

```text
Architect   dispatch → model = models.claude-code.architect
Implementer dispatch → model = models.claude-code.implementer
Reviewer    dispatch → model = models.claude-code.reviewer
QA          dispatch → model = models.claude-code.qa
```

A role is never dispatched before its own model is resolved. If a configured model turns
out to be unavailable, Claude Code stops and asks the user for a replacement for that
role — it never silently falls back to another model.

## Parallel Implementers

Claude Code defaults to a single Implementer. When the Architect marks two or more units
`Parallel-safe: yes` with disjoint files and no unmet dependency, and splitting genuinely
helps, it dispatches the corresponding Implementer agents together in a single message
with multiple Agent tool calls — up to `osb.yaml` → `execution.max_parallel_implementers`
(default 2). Each Implementer receives only its own unit capsule, never another
Implementer's output or the full architecture.

## RagMonk

Claude Code prefers RagMonk's MCP tools when connected in the session. If no RagMonk MCP
server is configured, it falls back to the RagMonk CLI via Bash. See `docs/RAGMONK.md`.

## Model configuration example

```yaml
models:
  claude-code:
    architect: claude-opus-5
    implementer: claude-sonnet-5
    reviewer: claude-sonnet-5
    qa: claude-sonnet-5
```

Any Claude Code model identifier is valid here — OSB does not maintain its own list.
