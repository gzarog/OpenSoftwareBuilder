# osb gate <review|knowledge> <inspect|approve|skip "reason">
# Cross-platform gate management for Open Software Builder.
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('review', 'knowledge')]
    [string]$Gate,

    [Parameter(Position = 1, Mandatory)]
    [ValidateSet('inspect', 'approve', 'skip')]
    [string]$Action,

    [Parameter(Position = 2)]
    [string]$Reason
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) { Write-Error 'Not in an OSB project.'; exit 1 }
$config = Read-OsbConfig -Root $Root

$stateDir = Join-Path $Root $config.paths.state
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$codeT = Get-OsbScopeLatestMtime -Root $Root -Config $config

if ($Gate -eq 'review') {
    $marker = Join-Path $stateDir 'review-approved'
    $skipMarker = Join-Path $stateDir 'review-skip'

    switch ($Action) {
        'approve' {
            Set-Content -LiteralPath $marker -Value ([string]$codeT)
            Write-Output 'Review approval recorded.'
        }
        'skip' {
            if ([string]::IsNullOrWhiteSpace($Reason)) {
                Write-Error 'Usage: osb gate review skip "<reason>"'
                exit 1
            }
            Set-Content -LiteralPath $skipMarker -Value @([string]$codeT, $Reason)
            Write-Output "Review skip recorded: $Reason"
        }
        'inspect' {
            if ($codeT -eq 0) {
                Write-Output 'No source files in configured paths.'
                exit 0
            }
            $state = 'NEEDS REVIEW'
            if (Test-Path $marker -PathType Leaf) {
                $approvedAt = 0.0
                if ([double]::TryParse((Get-Content -LiteralPath $marker -Raw), [ref]$approvedAt) -and $codeT -le $approvedAt) {
                    $state = 'APPROVED'
                }
            }
            if ($state -ne 'APPROVED' -and (Test-Path $skipMarker -PathType Leaf)) {
                $lines = Get-Content -LiteralPath $skipMarker
                if ($lines.Count -ge 1) {
                    $skippedAt = 0.0
                    if ([double]::TryParse($lines[0], [ref]$skippedAt) -and $codeT -le $skippedAt) {
                        $reason = if ($lines.Count -ge 2) { $lines[1] } else { '(no reason)' }
                        $state = "SKIPPED: $reason"
                    }
                }
            }
            Write-Output "Review gate: $state"
        }
    }
}

if ($Gate -eq 'knowledge') {
    $skipMarker = Join-Path $stateDir 'knowledge-skip'

    switch ($Action) {
        'approve' {
            Write-Error 'Knowledge gate has no approve action. Record knowledge via the knowledge directory, or use: osb gate knowledge skip "<reason>"'
            exit 1
        }
        'skip' {
            if ([string]::IsNullOrWhiteSpace($Reason)) {
                Write-Error 'Usage: osb gate knowledge skip "<reason>"'
                exit 1
            }
            Set-Content -LiteralPath $skipMarker -Value @([string]$codeT, $Reason)
            Write-Output "Knowledge skip recorded: $Reason"
        }
        'inspect' {
            if ($codeT -eq 0) {
                Write-Output 'No source files in configured paths.'
                exit 0
            }
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

            $state = 'NEEDS UPDATE'
            if ($codeT -le $knowledgeT) { $state = 'UP TO DATE' }
            if ($state -ne 'UP TO DATE' -and (Test-Path $skipMarker -PathType Leaf)) {
                $lines = Get-Content -LiteralPath $skipMarker
                if ($lines.Count -ge 1) {
                    $skippedAt = 0.0
                    if ([double]::TryParse($lines[0], [ref]$skippedAt) -and $codeT -le $skippedAt) {
                        $reason = if ($lines.Count -ge 2) { $lines[1] } else { '(no reason)' }
                        $state = "SKIPPED: $reason"
                    }
                }
            }
            Write-Output "Knowledge gate: $state"
        }
    }
}
