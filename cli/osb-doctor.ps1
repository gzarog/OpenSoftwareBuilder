# osb doctor — validate project configuration and health
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) {
    Write-Error 'Not in an OSB project (no osb.yaml found). Run: osb init'
    exit 1
}

$config = Read-OsbConfig -Root $Root
$issues = @()
$ok = @()

# Check version
if ($config.version -ne 1) {
    $issues += "osb.yaml version is $($config.version), expected 1"
} else {
    $ok += 'osb.yaml version: 1'
}

# Check source directories exist
foreach ($d in $config.paths.source) {
    $full = Join-Path $Root $d
    if (Test-Path $full -PathType Container) {
        $ok += "Source directory exists: $d"
    } else {
        $issues += "Source directory missing: $d"
    }
}

# Check checkpoint directory
$cpDir = Join-Path $Root $config.paths.checkpoints
if (Test-Path $cpDir -PathType Container) {
    $ok += "Checkpoint directory exists: $($config.paths.checkpoints)"
} else {
    $issues += "Checkpoint directory missing: $($config.paths.checkpoints)"
}

# Check knowledge directory
$knDir = Join-Path $Root $config.paths.knowledge
if (Test-Path $knDir -PathType Container) {
    $ok += "Knowledge directory exists: $($config.paths.knowledge)"
    # Check templates
    if (Test-Path (Join-Path $knDir 'tasks/_TEMPLATE.md') -PathType Leaf) {
        $ok += 'Task template present'
    } else {
        $issues += 'Task template missing: run osb init to create it'
    }
    if (Test-Path (Join-Path $knDir 'components/_TEMPLATE.md') -PathType Leaf) {
        $ok += 'Component template present'
    } else {
        $issues += 'Component template missing: run osb init to create it'
    }
    if (Test-Path (Join-Path $knDir 'INDEX.md') -PathType Leaf) {
        $ok += 'Knowledge index present'
    } else {
        $issues += 'Knowledge index missing'
    }
} else {
    $issues += "Knowledge directory missing: $($config.paths.knowledge)"
}

# Check commands
$cmdNames = @('build', 'test')
foreach ($cmd in $cmdNames) {
    if ($config.commands[$cmd]) {
        $ok += "Command configured: $cmd = $($config.commands[$cmd])"
    } else {
        $issues += "Command not configured: $cmd (set in osb.yaml)"
    }
}

# Check VCS
$hasGit = Test-Path (Join-Path $Root '.git') -PathType Container
if ($hasGit) {
    $ok += 'Git repository detected (content-authoritative change detection)'
} else {
    $issues += 'No git repository (change detection will use mtime — less reliable)'
}

# Check provider adapters
$providers = @('claude', 'codex', 'copilot', 'vscode')
$foundProviders = @()
foreach ($p in $providers) {
    switch ($p) {
        'claude' {
            if (Test-Path (Join-Path $Root 'CLAUDE.md') -PathType Leaf) { $foundProviders += $p }
        }
        'codex' {
            if (Test-Path (Join-Path $Root 'AGENTS.md') -PathType Leaf) { $foundProviders += $p }
        }
        'copilot' {
            if (Test-Path (Join-Path $Root '.github/copilot-instructions.md') -PathType Leaf) { $foundProviders += $p }
        }
        'vscode' {
            if (Test-Path (Join-Path $Root '.vscode/settings.json') -PathType Leaf) { $foundProviders += $p }
        }
    }
}
if ($foundProviders.Count -gt 0) {
    $ok += "Provider adapters found: $($foundProviders -join ', ')"
} else {
    $issues += 'No provider adapters configured (run: osb init -Providers claude,codex,copilot,vscode)'
}

# Check for leftover checkpoints
$cpDir = Join-Path $Root $config.paths.checkpoints
if (Test-Path $cpDir -PathType Container) {
    $checkpoints = Get-ChildItem -LiteralPath $cpDir -Filter '*.md' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '_TEMPLATE.md' }
    if ($checkpoints.Count -gt 0) {
        $issues += "Leftover checkpoints found ($($checkpoints.Count)): resume or clean up"
        foreach ($cp in $checkpoints) {
            $issues += "  - $($cp.Name)"
        }
    }
}

# Report
Write-Output ''
Write-Output '=== Open Software Builder: doctor ==='
Write-Output ''
if ($ok.Count -gt 0) {
    foreach ($item in $ok) { Write-Output "  [OK] $item" }
}
if ($issues.Count -gt 0) {
    Write-Output ''
    foreach ($item in $issues) { Write-Output "  [!!] $item" }
    Write-Output ''
    Write-Output "Found $($issues.Count) issue(s)."
    exit 1
} else {
    Write-Output ''
    Write-Output 'All checks passed.'
}
