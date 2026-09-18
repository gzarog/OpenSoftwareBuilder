# Generic adapter

Documentation and templates for integrating any AI agent provider with OSB.

If your provider is not Claude Code, OpenAI Codex, GitHub Copilot, or VS Code, use this
adapter as a starting point.

## Integration checklist

1. **Project instructions** — Create a project-level instruction file that tells the
   agent to read `core/workflow/README.md` as repository policy. Every provider has its
   own file name for this (CLAUDE.md, AGENTS.md, copilot-instructions.md, etc.).

2. **Role dispatch** — Map each of the four neutral roles (`core/roles/*.md`) to your
   provider's agent/subagent/context mechanism. Each dispatch must:
   - Start with a clean context (not inherited conversation).
   - Include the full neutral role definition.
   - Include a self-contained task brief.
   - Return structured evidence.

3. **Capability declaration** — Check `core/workflow/CAPABILITIES.md` and honestly
   declare which capabilities your provider actually has at runtime. Do not claim
   capabilities based on documentation or plugin names alone.

4. **Gate commands** — Ensure the agent can run `osb gate` CLI commands. If your provider
   lacks shell access, gate operations are blocked — report this explicitly.

5. **Checkpoints** — Ensure the agent can read and write Markdown files at the configured
   checkpoint path.

6. **Knowledge** — Ensure the agent can read and write files in the knowledge directory.

## Minimum viable adapter

At minimum, an adapter needs:
- A project instruction file that reads the canonical workflow.
- A way to dispatch the four roles with clean contexts.
- Shell access for build, test, and gate commands.
