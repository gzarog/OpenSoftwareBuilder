# VS Code adapter

Generates VS Code workspace configuration that integrates with the OSB workflow.

This adapter works alongside any AI agent provider (Copilot, Claude, Codex, etc.) by
providing VS Code tasks, settings, and recommended extensions that support the workflow.

## Generated files

| File | Purpose |
| --- | --- |
| `.vscode/tasks.json` | VS Code tasks for OSB CLI commands |
| `.vscode/settings.json` | Workspace settings (file associations, exclusions) |
| `.vscode/extensions.json` | Recommended extensions |

## VS Code tasks

The adapter generates tasks for every OSB CLI command, accessible from the Command
Palette (Ctrl+Shift+P -> Tasks: Run Task):

- `OSB: Doctor` — validate configuration
- `OSB: Status` — show project state
- `OSB: Changed` — detect recent changes
- `OSB: Gate Review Inspect` — check review gate
- `OSB: Gate Review Approve` — record reviewer approval
- `OSB: Gate Knowledge Inspect` — check knowledge gate
- `OSB: Knowledge Record` — record knowledge

## Notes

- VS Code itself is not an AI agent provider — it's the IDE. This adapter makes OSB
  commands accessible from the VS Code UI regardless of which AI agent is active.
- Browser QA capability depends on the AI agent provider, not VS Code.
- The tasks use PowerShell by default; bash equivalents work on macOS/Linux.
