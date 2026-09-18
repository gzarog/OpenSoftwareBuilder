# Set up GitHub Copilot adapter for a project
param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$OsbHome
)

$ErrorActionPreference = 'Stop'

# Create directories
New-Item -ItemType Directory -Force -Path (Join-Path $Root '.github/agents') | Out-Null

# .github/copilot-instructions.md
$instructions = @"
# Project instructions for GitHub Copilot

This project uses Open Software Builder, an auditable multi-agent software-delivery
workflow. Read ``core/workflow/README.md`` for the canonical policy.

## Workflow rules

- Classify work as Tier 1 (trivial), Tier 2 (mechanical), or Tier 3 (design needed)
  before starting.
- Tier 2+: implement then independently review. Auth, data, money, settlement, and
  external input always require review.
- Tier 3: architecture -> implementation -> independent review -> fresh QA -> knowledge.
- Use structural exploration (language services, find references) before grep for code
  understanding.
- Checkpoint progress at ``.osb/progress/`` for any non-trivial work.
- Record knowledge at ``.osb/knowledge/`` after completed tasks.

## Gate commands (run from integrated terminal)

``````
pwsh cli/osb-gate.ps1 review inspect
pwsh cli/osb-gate.ps1 review approve
pwsh cli/osb-gate.ps1 review skip '<reason>'
pwsh cli/osb-gate.ps1 knowledge inspect
pwsh cli/osb-gate.ps1 knowledge skip '<reason>'
``````

## Roles

Agent definitions for Copilot Chat are in ``.github/agents/``. Each reads its neutral
role from ``core/roles/`` and the workflow policy.

## Build/test commands

See ``osb.yaml`` for configured project commands.
"@
Set-Content -LiteralPath (Join-Path $Root '.github/copilot-instructions.md') -Value $instructions -Encoding utf8

# Agent definitions for Copilot Chat
$agents = @{
    'architect' = @"
---
name: architect
description: Design modules, interfaces, and data flow before code is written
---

Read the neutral [architect role](../../core/roles/architect.md) and the
[workflow policy](../../core/workflow/README.md) before action.

Design only; never implement. Use VS Code language services (Go to Definition, Find All
References) for structural exploration. Return exact interfaces, acceptance criteria,
milestones, tradeoffs, and risks using the five-section spec format.
"@
    'implementer' = @"
---
name: implementer
description: Implement a well-specified feature against a given design
---

Read the neutral [implementer role](../../core/roles/implementer.md) and the
[workflow policy](../../core/workflow/README.md) before action.

Implement only from complete, unambiguous briefs. Checkpoint at ``.osb/progress/`` early
and after every milestone. Build and test owned scope using the commands in osb.yaml.
"@
    'reviewer' = @"
---
name: reviewer
description: Review code changes for correctness, security, and conventions
---

Read the neutral [reviewer role](../../core/roles/reviewer.md) and the
[workflow policy](../../core/workflow/README.md) before action.

Review and report only; never fix. Each finding gives file/location, problem, severity,
and repair. Only with no blocking findings, approve the review gate from the terminal.
"@
    'qa-tester' = @"
---
name: qa-tester
description: Verify acceptance criteria through builds, tests, and browser flows
---

Read the neutral [QA role](../../core/roles/qa-tester.md) and the
[workflow policy](../../core/workflow/README.md) before action.

Verify and report only; never fix or approve review. Run build, test, and fitness
commands from osb.yaml. For UI work, note that browser QA requires manual verification
-- report the gap explicitly.
"@
}

foreach ($name in $agents.Keys) {
    Set-Content -LiteralPath (Join-Path $Root ".github/agents/$name.md") -Value $agents[$name] -Encoding utf8
}

Write-Output '  Copilot adapter configured.'
