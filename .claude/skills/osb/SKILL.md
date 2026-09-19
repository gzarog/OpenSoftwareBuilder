---
name: osb
description: Run the OpenSoftwareBuilder Architect → Implement → Review → QA workflow for a task. Use when the user types /osb <task> or asks to run the OSB workflow.
---

# /osb (Claude Code)

This is a thin Claude Code wrapper. The workflow itself lives in the canonical,
provider-neutral skill at `.agents/skills/osb/SKILL.md` — read that file (and its
`references/*.md`) first and follow it exactly. This file only adds Claude-Code-specific
mechanics: how to resolve models and launch each role as a Claude Code subagent.

## Host identity

For model resolution (`osb.yaml` → `models.<host>.*`) and RagMonk access, the host is
`claude-code`.

## Resolving models

Read `osb.yaml` at the repository root. If `models.claude-code.architect`,
`.implementer`, `.reviewer`, or `.qa` is missing, ask the user using the prompt format in
the canonical `SKILL.md` §"Model resolution" before dispatching anything. If the user
approves persisting the answer, write it back into `osb.yaml`'s `models.claude-code`
block, preserving all other content.

## Launching roles

Each of the four roles is a Claude Code subagent defined in `.claude/agents/`:

| Role | Agent definition |
| --- | --- |
| Architect | `.claude/agents/architect.md` |
| Implementer | `.claude/agents/implementer.md` |
| Reviewer | `.claude/agents/reviewer.md` |
| QA | `.claude/agents/qa.md` |

Dispatch a role with the Agent tool, `subagent_type` set to the role's name
(`architect`, `implementer`, `reviewer`, or `qa`), and `model` set to the model resolved
for that role in `osb.yaml`. Pass the role's dispatch brief (per
`.agents/skills/osb/references/handoff.md`) as the agent prompt — it must be
self-contained, since the subagent starts with no memory of this conversation.

For parallel-safe implementation units, dispatch the corresponding Implementer agents in
a single message with multiple Agent tool calls, per the canonical workflow's
parallel-safety rules. Otherwise dispatch sequentially, one unit at a time.

## RagMonk access

Use RagMonk's MCP tools when available in this session (search the tool list / use
ToolSearch for `ragmonk`). Fall back to the RagMonk CLI via Bash only if MCP access is
unavailable. Follow `.agents/skills/osb/references/ragmonk.md` for verification and
failure behavior — including stopping the workflow when `ragmonk.required: true` and
RagMonk is unreachable.

## Everything else

Lifecycle steps, role responsibilities and output formats, the handoff contract, and
knowledge capture/consolidation are defined once in `.agents/skills/osb/` — do not
duplicate or reinterpret them here.
