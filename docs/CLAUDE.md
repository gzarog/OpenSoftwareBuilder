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

## Parallel Implementers

When the Architect marks two or more units `Parallel-safe: yes` with disjoint files and
no unmet dependency, Claude Code dispatches the corresponding Implementer agents together
in a single message with multiple Agent tool calls, per its own guidance on parallel,
independent tool calls.

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
