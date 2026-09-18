# osb knowledge record — helper for recording a knowledge entry
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('record')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) { Write-Error 'Not in an OSB project.'; exit 1 }
$config = Read-OsbConfig -Root $Root

$knDir = Join-Path $Root $config.paths.knowledge
$tasksDir = Join-Path $knDir 'tasks'
$componentsDir = Join-Path $knDir 'components'

# Ensure directories exist
foreach ($d in @($tasksDir, $componentsDir)) {
    if (-not (Test-Path $d -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
}

$date = (Get-Date).ToString('yyyy-MM-dd')
Write-Output ''
Write-Output '=== Knowledge recording ==='
Write-Output ''
Write-Output "Date: $date"
Write-Output "Knowledge dir: $($config.paths.knowledge)"
Write-Output ''

# Check template exists
$templatePath = Join-Path $tasksDir '_TEMPLATE.md'
if (-not (Test-Path $templatePath -PathType Leaf)) {
    $OsbHome = $PSScriptRoot | Split-Path -Parent
    $srcTemplate = Join-Path $OsbHome 'templates/knowledge/task-template.md'
    if (Test-Path $srcTemplate -PathType Leaf) {
        Copy-Item $srcTemplate $templatePath
        Write-Output 'Created task template.'
    } else {
        Write-Warning 'Task template not found. Create one manually.'
    }
}

$componentTemplate = Join-Path $componentsDir '_TEMPLATE.md'
if (-not (Test-Path $componentTemplate -PathType Leaf)) {
    $OsbHome = $PSScriptRoot | Split-Path -Parent
    $srcTemplate = Join-Path $OsbHome 'templates/knowledge/component-template.md'
    if (Test-Path $srcTemplate -PathType Leaf) {
        Copy-Item $srcTemplate $componentTemplate
        Write-Output 'Created component template.'
    }
}

# Check index exists
$indexPath = Join-Path $knDir 'INDEX.md'
if (-not (Test-Path $indexPath -PathType Leaf)) {
    $OsbHome = $PSScriptRoot | Split-Path -Parent
    $srcIndex = Join-Path $OsbHome 'templates/knowledge/index-template.md'
    if (Test-Path $srcIndex -PathType Leaf) {
        Copy-Item $srcIndex $indexPath
        Write-Output 'Created knowledge index.'
    }
}

Write-Output ''
Write-Output 'To record a task:'
Write-Output "  1. Copy $($config.paths.knowledge)/tasks/_TEMPLATE.md to"
Write-Output "     $($config.paths.knowledge)/tasks/${date}-<slug>.md"
Write-Output '  2. Fill in the template from architecture, implementation, review, and QA evidence'
Write-Output "  3. Add a row to $($config.paths.knowledge)/INDEX.md (newest first)"
Write-Output '  4. Update each touched component record in place'
Write-Output ''
Write-Output "Existing task records: $(( Get-ChildItem $tasksDir -Filter '*.md' -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' } ).Count)"
Write-Output "Existing components:   $(( Get-ChildItem $componentsDir -Filter '*.md' -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' } ).Count)"
