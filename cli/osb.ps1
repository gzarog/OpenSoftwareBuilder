# osb — Open Software Builder CLI entry point
# Usage: pwsh osb.ps1 <command> [args]
param(
    [Parameter(Position = 0)]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments)]
    [string[]]$Args
)

$ErrorActionPreference = 'Stop'
$scriptDir = $PSScriptRoot

if (-not $Command) {
    Write-Output @"

  Open Software Builder
  An auditable, provider-neutral multi-agent software-delivery workflow.

  Usage: osb <command> [args]

  Commands:
    init                          Initialize a project with OSB
    doctor                        Validate configuration and health
    status                        Show project state (gates, checkpoints, knowledge)
    changed [minutes]             Detect recent source changes (default: 90m)
    validate <spec|checkpoint>    Validate an artifact against its schema
    gate <review|knowledge>       Manage quality gates
      inspect                     Show gate state
      approve                     Record reviewer approval (review gate only)
      skip "<reason>"             Record an auditable skip
    knowledge record              Interactive knowledge recording helper

  Provider adapters:
    Claude Code       CLAUDE.md + .claude/agents/ + .claude/skills/
    OpenAI Codex      AGENTS.md + .codex/skills/
    GitHub Copilot    .github/copilot-instructions.md + .github/agents/
    VS Code           .vscode/settings.json + .vscode/tasks.json

"@
    exit 0
}

$scriptMap = @{
    'init'     = 'osb-init.ps1'
    'doctor'   = 'osb-doctor.ps1'
    'status'   = 'osb-status.ps1'
    'changed'  = 'osb-changed.ps1'
    'validate' = 'osb-validate.ps1'
    'gate'     = 'osb-gate.ps1'
    'knowledge'= 'osb-knowledge.ps1'
}

$script = $scriptMap[$Command]
if (-not $script) {
    Write-Error "Unknown command: $Command. Run 'osb' for usage."
    exit 1
}

$scriptPath = Join-Path $scriptDir $script
& $scriptPath @Args
