# osb status — show project state: gates, checkpoints, recent knowledge
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) { Write-Error 'Not in an OSB project.'; exit 1 }
$config = Read-OsbConfig -Root $Root

Write-Output ''
Write-Output '=== Open Software Builder: status ==='
Write-Output ''

# Gate state
$stateDir = Join-Path $Root $config.paths.state
$reviewMarker = Join-Path $stateDir 'review-approved'
$reviewSkip = Join-Path $stateDir 'review-skip'
$knowledgeSkip = Join-Path $stateDir 'knowledge-skip'

$codeT = Get-OsbScopeLatestMtime -Root $Root -Config $config

Write-Output '--- Gates ---'
if ($codeT -eq 0) {
    Write-Output '  No source files found in configured paths.'
} else {
    # Review gate
    $reviewState = 'NEEDS REVIEW'
    if (Test-Path $reviewMarker -PathType Leaf) {
        $approvedAt = 0.0
        if ([double]::TryParse((Get-Content -LiteralPath $reviewMarker -Raw), [ref]$approvedAt) -and $codeT -le $approvedAt) {
            $reviewState = 'APPROVED'
        }
    }
    if ($reviewState -ne 'APPROVED' -and (Test-Path $reviewSkip -PathType Leaf)) {
        $lines = Get-Content -LiteralPath $reviewSkip
        if ($lines.Count -ge 1) {
            $skippedAt = 0.0
            if ([double]::TryParse($lines[0], [ref]$skippedAt) -and $codeT -le $skippedAt) {
                $reason = if ($lines.Count -ge 2) { $lines[1] } else { '(no reason)' }
                $reviewState = "SKIPPED: $reason"
            }
        }
    }
    Write-Output "  Review gate: $reviewState"

    # Knowledge gate
    $knowledgeState = 'NEEDS UPDATE'
    $knDir = Join-Path $Root $config.paths.knowledge
    $knowledgeT = 0.0
    $tasksDir = Join-Path $knDir 'tasks'
    if (Test-Path $tasksDir -PathType Container) {
        foreach ($f in Get-ChildItem -LiteralPath $tasksDir -Filter '*.md' -File -ErrorAction SilentlyContinue) {
            $t = ConvertTo-OsbUnixTime -Utc $f.LastWriteTimeUtc
            if ($t -gt $knowledgeT) { $knowledgeT = $t }
        }
    }
    $indexPath = Join-Path $knDir 'INDEX.md'
    if (Test-Path $indexPath -PathType Leaf) {
        $t = ConvertTo-OsbUnixTime -Utc (Get-Item -LiteralPath $indexPath).LastWriteTimeUtc
        if ($t -gt $knowledgeT) { $knowledgeT = $t }
    }
    if ($codeT -le $knowledgeT) { $knowledgeState = 'UP TO DATE' }
    if ($knowledgeState -ne 'UP TO DATE' -and (Test-Path $knowledgeSkip -PathType Leaf)) {
        $lines = Get-Content -LiteralPath $knowledgeSkip
        if ($lines.Count -ge 1) {
            $skippedAt = 0.0
            if ([double]::TryParse($lines[0], [ref]$skippedAt) -and $codeT -le $skippedAt) {
                $reason = if ($lines.Count -ge 2) { $lines[1] } else { '(no reason)' }
                $knowledgeState = "SKIPPED: $reason"
            }
        }
    }
    Write-Output "  Knowledge gate: $knowledgeState"
}

# Checkpoints
Write-Output ''
Write-Output '--- Active checkpoints ---'
$cpDir = Join-Path $Root $config.paths.checkpoints
if (Test-Path $cpDir -PathType Container) {
    $checkpoints = Get-ChildItem -LiteralPath $cpDir -Filter '*.md' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '_TEMPLATE.md' } |
        Sort-Object LastWriteTimeUtc -Descending
    if ($checkpoints.Count -eq 0) {
        Write-Output '  (none)'
    } else {
        foreach ($cp in $checkpoints) {
            $age = [math]::Round(((Get-Date).ToUniversalTime() - $cp.LastWriteTimeUtc).TotalHours, 1)
            Write-Output "  $($cp.Name)  (${age}h ago)"
        }
    }
} else {
    Write-Output '  (checkpoint directory not found)'
}

# Recent knowledge
Write-Output ''
Write-Output '--- Recent knowledge ---'
$indexPath = Join-Path $Root "$($config.paths.knowledge)/INDEX.md"
if (Test-Path $indexPath -PathType Leaf) {
    $indexLines = Get-Content -LiteralPath $indexPath |
        Where-Object { $_ -match '^\|.*\|$' -and $_ -notmatch '^\| ---' -and $_ -notmatch '^\| Date' } |
        Select-Object -First 5
    if ($indexLines.Count -eq 0) {
        Write-Output '  (no records)'
    } else {
        foreach ($line in $indexLines) { Write-Output "  $line" }
    }
} else {
    Write-Output '  (no knowledge index)'
}
Write-Output ''
