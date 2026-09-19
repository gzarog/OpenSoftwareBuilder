# osb knowledge — incremental and durable knowledge management
#
# Usage:
#   osb knowledge capture   --task-id <id> --role <role> --type <type> --summary "<text>"
#   osb knowledge capture   --task-id <id> --role <role> --none [--reason-none "<text>"]
#   osb knowledge capture   --task-id <id> --from-json knowledge-event.json
#   osb knowledge pending   [--task-id <id>]
#   osb knowledge inspect   --task-id <id>
#   osb knowledge consolidate --task-id <id> [--dry-run]
#   osb knowledge record    <task|component> <name>  [options]
#   osb knowledge status
#
# All commands delegate to the osb binary. This script is a reference wrapper
# kept for environments where the Go binary is not on PATH.

param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('capture', 'pending', 'inspect', 'consolidate', 'record', 'status')]
    [string]$Action,

    [string]$TaskId    = $env:OSB_TASK_ID,
    [string]$Role,
    [string]$Type,
    [string]$Scope,
    [string]$Summary,
    [string]$Reason,
    [string]$Confidence,
    [string]$Supersedes,
    [switch]$None,
    [string]$ReasonNone,
    [string]$FromJson,
    [string[]]$Files,
    [switch]$DryRun,

    # record sub-command
    [string]$RecordKind,
    [string]$RecordName,
    [string[]]$Component,
    [string]$Status,
    [int]$Tier,
    [string]$Decisions,
    [string]$Language,
    [string]$Purpose
)

$ErrorActionPreference = 'Stop'

# Prefer the Go binary when available.
$osbBin = Get-Command 'osb' -ErrorAction SilentlyContinue
if ($osbBin) {
    $osbArgs = @('knowledge', $Action)
    if ($TaskId)     { $osbArgs += @('--task-id', $TaskId) }
    if ($Role)       { $osbArgs += @('--role', $Role) }
    if ($Type)       { $osbArgs += @('--type', $Type) }
    if ($Scope)      { $osbArgs += @('--scope', $Scope) }
    if ($Summary)    { $osbArgs += @('--summary', $Summary) }
    if ($Reason)     { $osbArgs += @('--reason', $Reason) }
    if ($Confidence) { $osbArgs += @('--confidence', $Confidence) }
    if ($Supersedes) { $osbArgs += @('--supersedes', $Supersedes) }
    if ($None)       { $osbArgs += '--none' }
    if ($ReasonNone) { $osbArgs += @('--reason-none', $ReasonNone) }
    if ($FromJson)   { $osbArgs += @('--from-json', $FromJson) }
    if ($DryRun)     { $osbArgs += '--dry-run' }
    foreach ($f in $Files) { $osbArgs += @('--file', $f) }
    if ($RecordKind) { $osbArgs += @($RecordKind, $RecordName) }
    & osb @osbArgs
    exit $LASTEXITCODE
}

# ── Fallback: no Go binary — PowerShell implementation ───────────────────────

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) { Write-Error 'Not in an OSB project.'; exit 1 }
$config = Read-OsbConfig -Root $Root

$knDir      = Join-Path $Root $config.paths.knowledge
$progressDir = Join-Path $Root $config.paths.checkpoints

switch ($Action) {

    'status' {
        $tasksDir = Join-Path $knDir 'tasks'
        $compDir  = Join-Path $knDir 'components'
        $tasks    = (Get-ChildItem $tasksDir -Filter '*.md' -File -EA SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' }).Count
        $comps    = (Get-ChildItem $compDir  -Filter '*.md' -File -EA SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' }).Count
        Write-Output ''
        Write-Output "=== Knowledge Status ==="
        Write-Output "  $tasks task records, $comps component records"
        Write-Output ''
    }

    'capture' {
        if (-not $TaskId) { Write-Error '--task-id is required (or set OSB_TASK_ID)'; exit 1 }
        if (-not $Role)   { Write-Error '--role is required'; exit 1 }

        $validRoles = @('architect','implementer','reviewer','qa')
        if ($Role -notin $validRoles) { Write-Error "Invalid role '$Role'. Must be: $($validRoles -join ', ')"; exit 1 }

        $taskKnDir = Join-Path $progressDir $TaskId 'knowledge'
        New-Item -ItemType Directory -Force -Path $taskKnDir | Out-Null

        if ($None) {
            $ev = [ordered]@{
                id          = "none-$Role"
                timestamp   = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')
                task_id     = $TaskId
                role        = $Role
                none        = $true
                none_reason = $ReasonNone
            }
        } elseif ($FromJson) {
            $ev = Get-Content $FromJson -Raw | ConvertFrom-Json
        } else {
            $validTypes = @('decision','constraint','discovery','gotcha','assumption','assumption-invalidated','review-finding','qa-result','follow-up')
            if ($Type -notin $validTypes) { Write-Error "Invalid type '$Type'. Must be: $($validTypes -join ', ')"; exit 1 }
            if (-not $Summary) { Write-Error '--summary is required'; exit 1 }

            $hash = [System.Security.Cryptography.SHA256]::Create()
            $bytes = [System.Text.Encoding]::UTF8.GetBytes("${Role}:${Type}:$($Summary.Trim())")
            $hashBytes = $hash.ComputeHash($bytes)
            $id = 'event-' + ($hashBytes[0..3] | ForEach-Object { $_.ToString('x2') } | Join-String)

            $ev = [ordered]@{
                id         = $id
                timestamp  = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')
                task_id    = $TaskId
                role       = $Role
                type       = $Type
                summary    = $Summary
            }
            if ($Scope)      { $ev.scope      = $Scope }
            if ($Reason)     { $ev.reason     = $Reason }
            if ($Confidence) { $ev.confidence = $Confidence }
            if ($Supersedes) { $ev.supersedes = $Supersedes }
            if ($Files)      { $ev.source     = @{ files = $Files } }
        }

        $jsonLine = $ev | ConvertTo-Json -Compress
        $rolePath = Join-Path $taskKnDir "$Role.jsonl"
        Add-Content -LiteralPath $rolePath -Value $jsonLine -Encoding UTF8
        Write-Output "  ✓ Captured: $($ev.id)"
    }

    'pending' {
        $ids = @()
        if ($TaskId) {
            $ids = @($TaskId)
        } else {
            if (Test-Path $progressDir -PathType Container) {
                $ids = Get-ChildItem $progressDir -Directory |
                    Where-Object { Test-Path (Join-Path $_.FullName 'knowledge') -PathType Container } |
                    Select-Object -ExpandProperty Name
            }
        }

        if (-not $ids) { Write-Output 'No active task knowledge found.'; exit 0 }

        foreach ($id in $ids) {
            Write-Output ''
            Write-Output "Task: $id"
            Write-Output ''
            foreach ($role in @('architect','implementer','reviewer','qa')) {
                $roleFile = Join-Path $progressDir $id 'knowledge' "$role.jsonl"
                Write-Output "  $([char]::ToUpper($role[0]) + $role.Substring(1))"
                if (Test-Path $roleFile -PathType Leaf) {
                    $lines = Get-Content $roleFile | Where-Object { $_.Trim() -ne '' }
                    $noneFound = $false
                    $count = 0
                    foreach ($line in $lines) {
                        $obj = $line | ConvertFrom-Json
                        if ($obj.none) { $noneFound = $true }
                        else { $count++ }
                    }
                    if ($noneFound) { Write-Output "    no reusable findings" }
                    elseif ($count -eq 0) { Write-Output "    no checkpoint yet" }
                    else { Write-Output "    $count event(s) captured" }
                } else {
                    Write-Output "    no checkpoint yet"
                }
                Write-Output ''
            }
        }
    }

    'inspect' {
        if (-not $TaskId) { Write-Error '--task-id is required'; exit 1 }
        Write-Output ''
        Write-Output "Knowledge — Task: $TaskId"
        foreach ($role in @('architect','implementer','reviewer','qa')) {
            Write-Output ''
            Write-Output "  ── $([char]::ToUpper($role[0]) + $role.Substring(1)) ──"
            $roleFile = Join-Path $progressDir $TaskId 'knowledge' "$role.jsonl"
            if (-not (Test-Path $roleFile -PathType Leaf)) {
                Write-Output "    (no checkpoint yet)"; continue
            }
            foreach ($line in (Get-Content $roleFile | Where-Object { $_.Trim() -ne '' })) {
                $obj = $line | ConvertFrom-Json
                if ($obj.none) {
                    $reason = if ($obj.none_reason) { " ($($obj.none_reason))" } else { '' }
                    Write-Output "    [none]$reason"
                } else {
                    Write-Output "    [$($obj.type)] $($obj.summary)  id=$($obj.id)"
                }
            }
        }
        Write-Output ''
    }

    'consolidate' {
        if (-not $TaskId) { Write-Error '--task-id is required'; exit 1 }
        if ($DryRun) {
            Write-Output "Consolidation dry-run — Task: $TaskId"
            Write-Output "  Use 'osb' binary for full consolidation support."
        } else {
            Write-Error "Consolidation requires the osb binary. Install it with: go install github.com/gzarog/opensoftwarebuilder/cmd/osb@latest"
        }
    }

    'record' {
        # Legacy record action — forwards to osb binary pattern.
        $date     = (Get-Date).ToString('yyyy-MM-dd')
        $tasksDir = Join-Path $knDir 'tasks'
        $compDir  = Join-Path $knDir 'components'
        foreach ($d in @($tasksDir, $compDir)) {
            if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
        }
        Write-Output ''
        Write-Output '=== Knowledge recording ==='
        Write-Output "Date: $date"
        Write-Output "Knowledge dir: $($config.paths.knowledge)"
        Write-Output ''
        Write-Output 'To record a task manually:'
        Write-Output "  1. Copy tasks/_TEMPLATE.md to tasks/${date}-<slug>.md"
        Write-Output '  2. Fill in the sections from captured knowledge events'
        Write-Output "  3. Or use: osb knowledge consolidate --task-id <id>"
        Write-Output ''
        $tc = (Get-ChildItem $tasksDir -Filter '*.md' -File -EA SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' }).Count
        $cc = (Get-ChildItem $compDir  -Filter '*.md' -File -EA SilentlyContinue | Where-Object { $_.Name -ne '_TEMPLATE.md' }).Count
        Write-Output "Existing task records: $tc"
        Write-Output "Existing components:   $cc"
    }
}
