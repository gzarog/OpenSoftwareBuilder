# OpenAI Codex adapter

Generates Codex project files that point to the neutral OSB workflow.

## Generated files

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Project instructions — reads neutral workflow, adds Codex mechanics |
| `.codex/skills/osb/SKILL.md` | Workflow entry skill |
| `.codex/skills/knowledge/SKILL.md` | Knowledge management skill |

## Capabilities

| Obligation | Codex support |
| --- | --- |
| Structural explorer | CodeGraph MCP or CLI |
| Self-contained dispatch | Codex collaboration subagent with `fork_turns=none` |
| Independent reviewer | Fresh reviewer subagent |
| Fresh QA | Fresh QA subagent |
| Shell | Codex shell (sandbox + per-command approval) |
| Browser QA | Codex browser/computer capability if available |
| Gate lifecycle | Manual PowerShell commands |
| Checkpoints | File I/O to configured path |
| Knowledge | File I/O via knowledge skill |

## Dispatch conventions

Before each Codex collaboration-agent dispatch, post a commentary update identifying the
agent's task name, selected model, and reasoning effort. Set `model` and
`reasoning_effort` explicitly on the dispatch, and include the same values in the agent's
self-contained brief so its first commentary can repeat them.

Codex workspace sandboxing and per-command approval policy are authoritative. One
provider's permission store never grants another provider authority.
