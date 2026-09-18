# GitHub Copilot adapter

Generates GitHub Copilot project files that point to the neutral OSB workflow.

GitHub Copilot supports custom instructions via `.github/copilot-instructions.md` and
agent-mode extensions (Copilot Agents in VS Code, Copilot Workspace). This adapter
generates the instruction file and optional agent definitions.

## Generated files

| File | Purpose |
| --- | --- |
| `.github/copilot-instructions.md` | Copilot custom instructions — reads neutral workflow |
| `.github/agents/architect.md` | Copilot agent mode — architect role |
| `.github/agents/implementer.md` | Copilot agent mode — implementer role |
| `.github/agents/reviewer.md` | Copilot agent mode — reviewer role |
| `.github/agents/qa-tester.md` | Copilot agent mode — QA role |

## Full Mode — Intelligence Rules

When the project is configured in **Full OSB mode** (`mode: full`), every Copilot agent
operating in this project **must** follow these rules without exception:

> **Do not independently scan the repository to discover historical project context.
> Use the OSB-provided RagMonk context package.**

Specifically:
- **Before any architectural decision, implementation task, review, or QA pass** — run
  `osb context build "<task description>" --role <role>` from the integrated terminal to
  obtain the bounded evidence package. Do not substitute a manual file search or Copilot's
  own semantic search for this purpose.
- **Do not** use `@workspace` search, inline code suggestions, or Copilot Chat to
  reconstruct project history, past decisions, component ownership, or task status from
  raw files. That information must come through RagMonk.
- **If RagMonk is unavailable** (`osb intelligence status` shows errors), hard-stop and
  report the error. There is no silent fallback to direct filesystem scanning in full mode.
- **Source code** (implementation files, tests) may still be read directly for the purpose
  of understanding or modifying the code. The prohibition is on using Copilot's context or
  filesystem access as a substitute for the intelligence index for *historical* and
  *contextual* project knowledge.

Run `osb intelligence status` before starting any multi-step task.

## Capabilities

| Obligation | Copilot support |
| --- | --- |
| Structural explorer | VS Code language services, Copilot code navigation |
| Self-contained dispatch | Copilot agent mode (@workspace mentions) |
| Independent reviewer | Copilot code review (PR review, inline suggestions) |
| Fresh QA | Manual or Copilot-assisted test execution |
| Shell | VS Code integrated terminal |
| Browser QA | Manual browser testing (Copilot has no browser control) |
| Gate lifecycle | Manual CLI commands from integrated terminal |
| Checkpoints | File I/O to configured path |
| Knowledge | File I/O |

## Notes

- Copilot does not currently support Stop hooks or automatic gate enforcement. Gate
  commands must be run manually from the integrated terminal.
- Copilot agent mode is available in VS Code and GitHub.com. The agents defined here
  work in VS Code's Copilot Chat with `@workspace` and agent references.
- Browser QA is a **gap** — Copilot cannot drive a browser. Report it explicitly rather
  than skipping it.
