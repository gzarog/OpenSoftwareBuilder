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
