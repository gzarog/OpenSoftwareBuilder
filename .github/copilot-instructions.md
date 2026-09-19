# OpenSoftwareBuilder (OSB) — Copilot Instructions

This repository ships **OpenSoftwareBuilder v2**, a provider-neutral
Architect → Implement → Review → QA workflow with RagMonk-backed project memory.

When a user asks you (Copilot) to run `/osb <task>`, or asks to "run OSB" / "use the OSB
workflow" for a task, do the following:

1. Read the canonical, provider-neutral workflow at `.agents/skills/osb/SKILL.md` and its
   `references/*.md` files. That is the single source of truth for the lifecycle, the
   four roles (Architect, Implementer, Reviewer, QA), the handoff contract, model
   resolution, RagMonk usage, and knowledge capture. Follow it exactly — do not
   reinterpret or shortcut it.
2. Use the host identity `copilot` when resolving `osb.yaml` → `models.copilot.*`. If any
   of `architect`, `implementer`, `reviewer`, `qa` is missing a model, stop and ask the
   user per `SKILL.md` §"Model resolution" before doing any work.
3. Launch each role using the corresponding definition in `.github/agents/`
   (`architect.agent.md`, `implementer.agent.md`, `reviewer.agent.md`, `qa.agent.md`).
   Each dispatch must be a self-contained brief per
   `.agents/skills/osb/references/handoff.md` — the role has no memory of this
   conversation.
4. Use RagMonk via its MCP tools when configured in this environment; fall back to the
   RagMonk CLI only if MCP is unavailable. Follow
   `.agents/skills/osb/references/ragmonk.md`, including stopping the workflow when
   `osb.yaml` sets `ragmonk.required: true` and RagMonk is unreachable.
5. Persist any newly-resolved model configuration back into `osb.yaml` when asked to.
6. Consolidate knowledge into `.osb/knowledge/` per
   `.agents/skills/osb/references/knowledge.md` once QA passes.

Provider-specific files in this repository (`.github/agents/*.agent.md`, `.claude/`,
`.codex/`) are thin wrappers only. They must never contain workflow policy of their own —
that always lives in `.agents/skills/osb/`.

For general repository work not related to `/osb`, no special instructions apply beyond
normal good practice for this codebase.
