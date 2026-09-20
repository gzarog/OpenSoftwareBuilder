# OSB on Claude Code

## Setup

Copy the `osb/` package into your workspace, then register Claude Code:

```sh
bash ./osb/install.sh init --host claude
```

This generates:

```text
.claude/skills/osb/SKILL.md   (thin wrapper, generated from osb/hosts/claude/skill.md.tmpl)
.claude/agents/architect.md   (generated from osb/agents/architect.md)
.claude/agents/implementer.md (generated from osb/agents/implementer.md)
.claude/agents/reviewer.md    (generated from osb/agents/reviewer.md)
.claude/agents/qa.md          (generated from osb/agents/qa.md)
```

and creates root `osb.yaml` (fill in `models.claude-code.*`, or leave blank to be prompted
on first run) plus `.osb/state/` and `.osb/knowledge/` if they don't already exist.

Do not hand-edit the generated files above — re-run `bash ./osb/install.sh upgrade` after
changing `osb/agents/*.md` or `osb/hosts/claude/*` to regenerate them, or `doctor` to
detect that they've drifted from the source.

## Invocation

```text
/osb <task>
```

Claude Code loads `.claude/skills/osb/SKILL.md`, which points at the canonical
`osb/SKILL.md` for the actual workflow, then dispatches each role as a Claude Code
subagent using the Agent tool with `subagent_type` set to `architect`, `implementer`,
`reviewer`, or `qa`, and `model` set to the model resolved from `osb.yaml`.

Every role dispatch must use the model resolved from `models.claude-code.<role>` — there
is no shared or default model across roles:

```text
Architect   dispatch → model = models.claude-code.architect
Implementer dispatch → model = models.claude-code.implementer
Reviewer    dispatch → model = models.claude-code.reviewer
QA          dispatch → model = models.claude-code.qa
```

A role is never dispatched before its own model is resolved. If a configured model turns
out to be unavailable, Claude Code stops and asks the user for a replacement for that
role — it never silently falls back to another model.

## Parallel Implementers

Claude Code defaults to a single Implementer. When the Architect marks two or more units
`Parallel-safe: yes` with disjoint files and no unmet dependency, and splitting genuinely
helps, it dispatches the corresponding Implementer agents together in a single message
with multiple Agent tool calls — up to `osb.yaml` → `execution.max_parallel_implementers`
(default 2). Each Implementer receives only its own unit capsule, never another
Implementer's output or the full architecture.

## RagMonk

Claude Code prefers RagMonk's MCP tools when connected in the session. If no RagMonk MCP
server is configured, it falls back to the RagMonk CLI via Bash. See `osb/docs/RAGMONK.md`.

## Model configuration example

```yaml
models:
  claude-code:
    architect: claude-opus-5
    implementer: claude-sonnet-5
    reviewer: claude-sonnet-5
    qa: claude-sonnet-5
```

Any Claude Code model identifier is valid here — OSB does not maintain its own list.
