# Set up VS Code adapter for a project
param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$OsbHome
)

$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Force -Path (Join-Path $Root '.vscode') | Out-Null

# .vscode/tasks.json
$tasks = @"
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "OSB: Doctor",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-doctor.ps1"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Status",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-status.ps1"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Changed",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-changed.ps1"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Gate Review Inspect",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-gate.ps1", "review", "inspect"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Gate Review Approve",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-gate.ps1", "review", "approve"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Gate Knowledge Inspect",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-gate.ps1", "knowledge", "inspect"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "OSB: Knowledge Record",
      "type": "shell",
      "command": "pwsh",
      "args": ["cli/osb-knowledge.ps1", "record"],
      "group": "none",
      "presentation": { "reveal": "always", "panel": "shared" }
    }
  ]
}
"@
Set-Content -LiteralPath (Join-Path $Root '.vscode/tasks.json') -Value $tasks -Encoding utf8

# .vscode/settings.json (merge-safe: only add OSB-specific settings)
$settingsPath = Join-Path $Root '.vscode/settings.json'
$settings = @{}
if (Test-Path $settingsPath -PathType Leaf) {
    try { $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json -AsHashtable } catch {}
}
$settings['files.exclude'] = @{
    '**/.osb/state' = $true
}
$settings['files.associations'] = @{
    'osb.yaml' = 'yaml'
}
$settingsJson = $settings | ConvertTo-Json -Depth 5
Set-Content -LiteralPath $settingsPath -Value $settingsJson -Encoding utf8

# .vscode/extensions.json
$extensions = @"
{
  "recommendations": [
    "redhat.vscode-yaml"
  ]
}
"@
$extPath = Join-Path $Root '.vscode/extensions.json'
if (-not (Test-Path $extPath -PathType Leaf)) {
    Set-Content -LiteralPath $extPath -Value $extensions -Encoding utf8
}

Write-Output '  VS Code adapter configured.'
