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
