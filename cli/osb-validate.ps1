# osb validate <spec|checkpoint> <file> — validate artifact against schema
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('spec', 'checkpoint')]
    [string]$Type,

    [Parameter(Position = 1, Mandatory)]
    [string]$File
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $File -PathType Leaf)) {
    Write-Error "File not found: $File"
    exit 1
}

$content = Get-Content -LiteralPath $File -Raw
$issues = @()

if ($Type -eq 'spec') {
    # Validate architecture spec: must have the five required sections
    $requiredSections = @('Interfaces', 'Acceptance criteria', 'Milestones', 'Tradeoffs', 'Risks')
    foreach ($s in $requiredSections) {
        if ($content -notmatch "(?m)^\*\*$s\*\*|^##\s+$s|^###\s+$s") {
            $issues += "Missing required section: $s"
        }
    }
    # Check for unit metadata
    $requiredMeta = @('Files:', 'Depends on:', 'Parallel-safe:', 'Risk tier:')
    $hasUnits = $content -match '(?m)^Files:'
    if ($hasUnits) {
        foreach ($m in $requiredMeta) {
            if ($content -notmatch [regex]::Escape($m)) {
                $issues += "Missing unit metadata: $m"
            }
        }
    }
    # Check risk tier values
    if ($content -match 'Risk tier:\s*(\w+)') {
        $tier = $Matches[1]
        if ($tier -notin @('mechanical', 'standard', 'sensitive')) {
            $issues += "Invalid risk tier: $tier (must be mechanical, standard, or sensitive)"
        }
    }
}

if ($Type -eq 'checkpoint') {
    # Validate checkpoint: must have key sections
    $requiredSections = @('Done and verified', 'Remaining')
    foreach ($s in $requiredSections) {
        if ($content -notmatch "(?mi)^\#{1,3}\s+$s") {
            $issues += "Missing section: $s"
        }
    }
    # Must have tier and role
    if ($content -notmatch '(?mi)\*\*Tier:\*\*') { $issues += 'Missing Tier field' }
    if ($content -notmatch '(?mi)\*\*Role:\*\*') { $issues += 'Missing Role field' }
    if ($content -notmatch '(?mi)\*\*Milestone:\*\*') { $issues += 'Missing Milestone field' }
}

if ($issues.Count -gt 0) {
    Write-Output "Validation failed for: $File"
    foreach ($i in $issues) { Write-Output "  [!!] $i" }
    exit 1
} else {
    Write-Output "Validation passed: $File"
}
