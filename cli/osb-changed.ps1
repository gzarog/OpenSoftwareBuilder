# osb changed [minutes] — detect changes in source directories
# Uses git diff if available, falls back to mtime scan.
param(
    [Parameter(Position = 0)]
    [int]$Minutes = 90
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib/config.ps1')

$Root = Get-OsbRoot
if (-not $Root) { Write-Error 'Not in an OSB project.'; exit 1 }
$config = Read-OsbConfig -Root $Root

$hasGit = Test-Path (Join-Path $Root '.git') -PathType Container

Write-Output ''
Write-Output "=== Changes in last ${Minutes}m ==="
Write-Output ''

if ($hasGit) {
    Write-Output '(using git — content-authoritative)'
    Write-Output ''
    $since = (Get-Date).AddMinutes(-$Minutes).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss')
    Push-Location $Root
    try {
        # Show uncommitted changes in source dirs
        foreach ($d in $config.paths.source) {
            if (Test-Path (Join-Path $Root $d) -PathType Container) {
                $diff = git diff --name-only -- $d 2>$null
                $staged = git diff --cached --name-only -- $d 2>$null
                $untracked = git ls-files --others --exclude-standard -- $d 2>$null
                $all = @($diff) + @($staged) + @($untracked) | Where-Object { $_ } | Sort-Object -Unique
                if ($all.Count -gt 0) {
                    Write-Output "  Uncommitted in ${d}/:"
                    foreach ($f in $all) { Write-Output "    $f" }
                }
            }
        }
        # Show recent commits
        $recentCommits = git log --since="$since" --oneline 2>$null
        if ($recentCommits) {
            Write-Output ''
            Write-Output '  Recent commits:'
            foreach ($c in $recentCommits) { Write-Output "    $c" }
        }
    } finally { Pop-Location }
} else {
    Write-Output '(using mtime scan — timestamps only, not content-authoritative)'
    Write-Output ''
    $cutoff = (Get-Date).AddMinutes(-$Minutes).ToUniversalTime()
    $pruneNames = Get-OsbGeneratedNames -Config $config
    foreach ($d in $config.paths.source) {
        $dir = Join-Path $Root $d
        if (-not (Test-Path $dir -PathType Container)) { continue }
        $files = Get-ChildItem -LiteralPath $dir -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object {
                $normalized = $_.FullName -replace '\\', '/'
                $pruned = $false
                foreach ($p in $pruneNames) {
                    if ($normalized -match "/$([regex]::Escape($p))(/|$)") { $pruned = $true; break }
                }
                (-not $pruned) -and ($_.LastWriteTimeUtc -gt $cutoff)
            } |
            Sort-Object LastWriteTimeUtc -Descending
        if ($files.Count -gt 0) {
            Write-Output "  Changed in ${d}/:"
            foreach ($f in $files) {
                $rel = $f.FullName.Substring($Root.Length + 1) -replace '\\', '/'
                $age = [math]::Round(((Get-Date).ToUniversalTime() - $f.LastWriteTimeUtc).TotalMinutes, 0)
                Write-Output "    $rel  (${age}m ago)"
            }
        }
    }
}

# Check for leftover checkpoints
$cpDir = Join-Path $Root $config.paths.checkpoints
if (Test-Path $cpDir -PathType Container) {
    $checkpoints = Get-ChildItem -LiteralPath $cpDir -Filter '*.md' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '_TEMPLATE.md' }
    if ($checkpoints.Count -gt 0) {
        Write-Output ''
        Write-Output '  Leftover checkpoints:'
        foreach ($cp in $checkpoints) { Write-Output "    $($cp.Name)" }
    }
}
Write-Output ''
