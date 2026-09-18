# Set up OpenAI Codex adapter for a project
param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$OsbHome
)

$ErrorActionPreference = 'Stop'

# Create directories
New-Item -ItemType Directory -Force -Path (Join-Path $Root '.codex/skills/osb') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root '.codex/skills/knowledge') | Out-Null

# AGENTS.md
$agentsMd = @"
# Project -- Codex adapter

Read [the canonical workflow](core/workflow/README.md) in full once per fresh context
before non-trivial work. It is repository policy. This adapter supplies Codex mechanics
only.

Use the neutral roles in ``core/roles/``; dispatch Codex collaboration subagents with
``fork_turns=none`` and include the full neutral role plus a self-contained task brief;
inherited conversation is not a handoff. Use CodeGraph MCP/CLI for structural exploration
and an actually available Codex browser/computer capability for UI QA. Gate scripts are
run manually from the repository root.

Before each Codex collaboration-agent dispatch, post a commentary update identifying the
agent's task name, selected model, and reasoning effort. Set ``model`` and
``reasoning_effort`` explicitly on the dispatch.

Codex workspace sandboxing and per-command approval policy are authoritative. One
provider's permission store never grants another provider authority. Check that a mapped
capability is present before claiming it was used.

Gate commands (from repository root in PowerShell):
  Inspect review:    pwsh cli/osb-gate.ps1 review inspect
  Approve review:    pwsh cli/osb-gate.ps1 review approve
  Skip review:       pwsh cli/osb-gate.ps1 review skip '<reason>'
  Inspect knowledge: pwsh cli/osb-gate.ps1 knowledge inspect
  Skip knowledge:    pwsh cli/osb-gate.ps1 knowledge skip '<reason>'
"@
Set-Content -LiteralPath (Join-Path $Root 'AGENTS.md') -Value $agentsMd -Encoding utf8

# Skills
$osbSkill = @"
---
name: osb
description: Open Software Builder workflow entry
---

Read [the canonical workflow](../../core/workflow/README.md) in full. Follow its triage,
pipeline, handoff, and evidence rules. Use the configured commands from osb.yaml.
"@
Set-Content -LiteralPath (Join-Path $Root '.codex/skills/osb/SKILL.md') -Value $osbSkill -Encoding utf8

$knowledgeSkill = @"
---
name: knowledge
description: Durable project knowledge management
---

Read [KNOWLEDGE.md](../../core/knowledge/KNOWLEDGE.md). Query and record per its rules.
Use the knowledge directory configured in osb.yaml.
"@
Set-Content -LiteralPath (Join-Path $Root '.codex/skills/knowledge/SKILL.md') -Value $knowledgeSkill -Encoding utf8

Write-Output '  Codex adapter configured.'
