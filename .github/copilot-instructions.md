# OSB

For `/osb <task>` (or "run OSB" / "use the OSB workflow"), use
`.agents/skills/osb/SKILL.md` as the single source of truth for the lifecycle, the four
roles, handoffs, model resolution, RagMonk usage, execution state, and knowledge capture.
Follow it exactly — do not reinterpret, shortcut, or duplicate its policy here.

Host: `copilot`. Resolve each role's model from `osb.yaml` →
`models.copilot.{architect,implementer,reviewer,qa}`; stop and ask the user per
`SKILL.md` §"Model resolution" if any is missing. Never dispatch a role before its own
model is resolved.

Launch each role from `.github/agents/` (`architect.agent.md`, `implementer.agent.md`,
`reviewer.agent.md`, `qa.agent.md`) with a compact, self-contained dispatch brief per
`.agents/skills/osb/references/handoff.md` — the role has no memory of this conversation
and does not read OSB policy files itself.

Use RagMonk MCP tools when available, CLI as fallback, per
`.agents/skills/osb/references/ragmonk.md`.

`.github/agents/*.agent.md`, `.claude/`, and `.codex/` are thin wrappers only — they never
contain workflow policy of their own.

For general repository work not related to `/osb`, no special instructions apply.
