# Set up Claude Code adapter for a project
param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$OsbHome
)

$ErrorActionPreference = 'Stop'

# Create directories
$dirs = @('.claude/agents', '.claude/skills/osb', '.claude/skills/knowledge', '.claude/hooks', '.claude/hooks/lib')
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

# CLAUDE.md
$claudeMd = @"
# Project — Claude adapter

Read [the canonical workflow](core/workflow/README.md) in full once per fresh context
before non-trivial work. It is repository policy. This adapter supplies Claude mechanics
only.

Use ``.claude/agents/<role>.md``; each reads its neutral role in ``core/roles/`` before
action. Use available CodeGraph tools for structural exploration and Claude browser
capability for UI QA. Existing ``.claude/hooks/`` and checkpoint paths remain
authoritative.

Use the canonical tiering, handoff, evidence, checkpoint, independence, verification,
and knowledge rules. The skills at ``.claude/skills/`` are short entrypoints to the same
policy.
"@
Set-Content -LiteralPath (Join-Path $Root 'CLAUDE.md') -Value $claudeMd -Encoding utf8

# Agent wrappers
$agents = @{
    'architect' = @{
        model = 'opus'
        role = 'Architect'
        body = 'Read the neutral [architect role](../../core/roles/architect.md) and the [workflow policy](../../core/workflow/README.md) before action. Design only; never implement. Use structural exploration first.'
    }
    'implementer' = @{
        model = 'opus'
        role = 'Implementer'
        body = 'Read the neutral [implementer role](../../core/roles/implementer.md) and the [workflow policy](../../core/workflow/README.md) before action. Checkpoint early. Build and test owned scope.'
    }
    'reviewer' = @{
        model = 'opus'
        role = 'Reviewer'
        body = 'Read the neutral [reviewer role](../../core/roles/reviewer.md) and the [workflow policy](../../core/workflow/README.md) before action. Review and report only; never fix. Only approve the review gate with no blocking findings.'
    }
    'qa-tester' = @{
        model = 'opus'
        role = 'QA Tester'
        body = 'Read the neutral [QA role](../../core/roles/qa-tester.md) and the [workflow policy](../../core/workflow/README.md) before action. Verify and report only; never fix or approve review. Use browser for UI flows.'
    }
}

foreach ($name in $agents.Keys) {
    $a = $agents[$name]
    $content = @"
---
model: $($a.model)
role: $($a.role)
---

$($a.body)
"@
    Set-Content -LiteralPath (Join-Path $Root ".claude/agents/$name.md") -Value $content -Encoding utf8
}

# Skills
$osbSkill = @"
---
name: osb
description: Open Software Builder workflow entry
---

Read [the canonical workflow](../../core/workflow/README.md) in full. Follow its triage,
pipeline, handoff, and evidence rules. Use the configured commands from osb.yaml.
"@
Set-Content -LiteralPath (Join-Path $Root '.claude/skills/osb/SKILL.md') -Value $osbSkill -Encoding utf8

$knowledgeSkill = @"
---
name: knowledge
description: Durable project knowledge management
---

Read [KNOWLEDGE.md](../../core/knowledge/KNOWLEDGE.md). Query and record per its rules.
Use the knowledge directory configured in osb.yaml.
"@
Set-Content -LiteralPath (Join-Path $Root '.claude/skills/knowledge/SKILL.md') -Value $knowledgeSkill -Encoding utf8

# Copy gate hooks from CLI lib
$cliDir = Join-Path $OsbHome 'cli'
$gateSource = Join-Path $cliDir 'lib/config.ps1'
if (Test-Path $gateSource -PathType Leaf) {
    Copy-Item $gateSource (Join-Path $Root '.claude/hooks/lib/pipeline-scope.ps1')
}

Write-Output '  Claude Code adapter configured.'
