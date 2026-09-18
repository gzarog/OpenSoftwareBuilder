# OpenAI Codex adapter

Generates Codex project files that point to the neutral OSB workflow.

## Generated files

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Project instructions — reads neutral workflow, adds Codex mechanics |
| `.codex/skills/osb/SKILL.md` | Workflow entry skill |
| `.codex/skills/knowledge/SKILL.md` | Knowledge management skill |

## Full Mode — Intelligence Rules

When the project is configured in **Full OSB mode** (`mode: full`), every Codex agent
operating in this project **must** follow these rules without exception:

> **Do not independently scan the repository to discover historical project context.
> Use the OSB-provided RagMonk context package.**

Specifically:
- **Before any architectural decision, implementation task, review, or QA pass** — run
  `osb context build "<task description>" --role <role>` to obtain the bounded evidence
  package. Do not substitute a manual file search.
- **Do not** use file-search, grep, or directory walks to reconstruct project history, past
  decisions, component ownership, or task status from raw files. That information must come
  through RagMonk.
- **If RagMonk is unavailable** (`osb intelligence status` shows errors), hard-stop and
  report the error. There is no silent fallback to direct filesystem scanning in full mode.
- **Source code** (implementation files, tests) may still be read directly for the purpose
  of understanding or modifying the code. The prohibition is on using the filesystem as a
  substitute for the intelligence index for *historical* and *contextual* project knowledge.

Check `osb intelligence status` before starting any multi-step task.

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
