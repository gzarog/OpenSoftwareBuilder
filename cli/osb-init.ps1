# osb init — initialize a project with Open Software Builder
# Creates osb.yaml, .osb/ directory, knowledge templates, and provider adapter stubs.
param(
    [string]$Profile = 'generic',
    [string[]]$Providers = @()
)

$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path

if (Test-Path (Join-Path $Root 'osb.yaml') -PathType Leaf) {
    Write-Warning 'osb.yaml already exists. Use osb doctor to validate.'
    exit 0
}

# Determine OSB install location
$OsbHome = $PSScriptRoot | Split-Path -Parent

# Load profile defaults
$profilePath = Join-Path $OsbHome "profiles/$Profile/profile.yaml"
$profileConfig = $null
if (Test-Path $profilePath -PathType Leaf) {
    Write-Output "Using profile: $Profile"
}

# Create osb.yaml
$yaml = @"
version: 1

# Profile: $Profile
# Customize paths, commands, and policy for your project.

paths:
  source:
    - src
  generated:
    - bin
    - obj
    - node_modules
    - dist
    - build
    - coverage
  checkpoints: .osb/progress
  knowledge: .osb/knowledge
  state: .osb/state

commands:
  build: null
  test: null
  fitness: null
  e2e: null

capabilities:
  structural_explorer: null
  browser_qa: optional

policy:
  require_independent_review: true
  require_fresh_qa: true
  sensitive_areas:
    - auth
    - payments
    - external-input
"@

Set-Content -LiteralPath (Join-Path $Root 'osb.yaml') -Value $yaml -Encoding utf8

# Create .osb directories
$dirs = @('.osb/progress', '.osb/knowledge/tasks', '.osb/knowledge/components', '.osb/state')
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

# Copy knowledge templates
$templateDir = Join-Path $OsbHome 'templates/knowledge'
Copy-Item (Join-Path $templateDir 'task-template.md') (Join-Path $Root '.osb/knowledge/tasks/_TEMPLATE.md')
Copy-Item (Join-Path $templateDir 'component-template.md') (Join-Path $Root '.osb/knowledge/components/_TEMPLATE.md')
Copy-Item (Join-Path $templateDir 'index-template.md') (Join-Path $Root '.osb/knowledge/INDEX.md')

# Copy checkpoint template
Copy-Item (Join-Path $OsbHome 'templates/checkpoints/checkpoint-template.md') (Join-Path $Root '.osb/progress/_TEMPLATE.md')

# Set up provider adapters
$adapterDir = Join-Path $OsbHome 'adapters'
foreach ($provider in $Providers) {
    $adapterPath = Join-Path $adapterDir $provider
    if (-not (Test-Path $adapterPath -PathType Container)) {
        Write-Warning "Unknown provider: $provider (available: claude, codex, copilot, vscode, generic)"
        continue
    }
    $setupScript = Join-Path $adapterPath 'setup.ps1'
    if (Test-Path $setupScript -PathType Leaf) {
        Write-Output "Setting up $provider adapter..."
        & $setupScript -Root $Root -OsbHome $OsbHome
    }
}

# Create .gitignore for .osb state
$gitignore = @"
# OSB state (gate markers, not committed)
state/
"@
Set-Content -LiteralPath (Join-Path $Root '.osb/.gitignore') -Value $gitignore -Encoding utf8

Write-Output ''
Write-Output 'Open Software Builder initialized.'
Write-Output ''
Write-Output 'Next steps:'
Write-Output '  1. Edit osb.yaml — set your source paths and build/test commands'
Write-Output '  2. Run: osb doctor — to validate configuration'
Write-Output '  3. Set up provider adapters with: osb init -Providers claude,codex,copilot,vscode'
