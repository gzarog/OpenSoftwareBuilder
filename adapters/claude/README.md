# Claude Code adapter

Generates Claude Code project files that point to the neutral OSB workflow.

## Generated files

| File | Purpose |
| --- | --- |
| `CLAUDE.md` | Project instructions — reads neutral workflow, adds Claude mechanics |
| `.claude/agents/architect.md` | Agent wrapper — reads neutral architect role |
| `.claude/agents/implementer.md` | Agent wrapper — reads neutral implementer role |
| `.claude/agents/reviewer.md` | Agent wrapper — reads neutral reviewer role |
| `.claude/agents/qa-tester.md` | Agent wrapper — reads neutral QA role |
| `.claude/skills/osb/SKILL.md` | Workflow entry skill |
| `.claude/skills/knowledge/SKILL.md` | Knowledge management skill |
| `.claude/hooks/review-gate.ps1` | Stop hook — blocks on unapproved source changes |
| `.claude/hooks/knowledge-gate.ps1` | Stop hook — blocks on missing knowledge update |

## Full Mode — Intelligence Rules

When the project is configured in **Full OSB mode** (`mode: full`), every Claude Code
agent operating in this project **must** follow these rules without exception:

> **Do not independently scan the repository to discover historical project context.
> Use the OSB-provided RagMonk context package.**

Specifically:
- **Before any architectural decision, implementation task, review, or QA pass** — call
  `osb context build "<task description>" --role <role>` to obtain the bounded evidence
  package. Do not substitute a manual file search.
- **Do not** use file-search tools, `grep`, `read`, or directory walks to reconstruct
  project history, past decisions, component ownership, or task status from raw files.
  That information must come through RagMonk.
- **If RagMonk is unavailable** (`osb intelligence status` shows errors), hard-stop and
  report the error. There is no silent fallback to direct filesystem scanning in full mode.
- **Source code** (implementation files, tests) may still be read directly for the purpose
  of understanding or modifying the code. The prohibition is on using the filesystem as a
  substitute for the intelligence index for *historical* and *contextual* project knowledge.

Check `osb intelligence status` before starting any multi-step task. If the intelligence
gate is not `PASS`, run `osb intelligence doctor` and resolve the issues before proceeding.

## Capabilities

| Obligation | Claude Code support |
| --- | --- |
| Structural explorer | CodeGraph MCP or CLI, codegraph_explore |
| Self-contained dispatch | Claude Agent with clean context |
| Independent reviewer | Fresh reviewer agent |
| Fresh QA | Fresh QA agent with browser capability |
| Shell | Full shell access (Bash + PowerShell) |
| Browser QA | Built-in browser pane |
| Gate lifecycle | Stop hooks + manual commands |
| Checkpoints | File I/O to configured path |
| Knowledge | File I/O via knowledge skill |
