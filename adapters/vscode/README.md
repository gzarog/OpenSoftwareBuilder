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

## Full Mode — Intelligence Rules

When the project is configured in **Full OSB mode** (`mode: full`), any AI agent active
in this VS Code workspace **must** follow these rules without exception:

> **Do not independently scan the repository to discover historical project context.
> Use the OSB-provided RagMonk context package.**

The VS Code adapter generates a task `OSB: Context Build` that runs
`osb context build "<query>" --role <role>` from the integrated terminal. Agents should
use this task (or run the command directly) rather than browsing `.osb/knowledge/` or
other files to reconstruct project history.

If RagMonk is unavailable (`OSB: Intelligence Status` task shows errors), report the
error and stop. There is no silent fallback to direct filesystem scanning in full mode.

## Notes

- VS Code itself is not an AI agent provider — it's the IDE. This adapter makes OSB
  commands accessible from the VS Code UI regardless of which AI agent is active.
- Browser QA capability depends on the AI agent provider, not VS Code.
- The tasks use PowerShell by default; bash equivalents work on macOS/Linux.
