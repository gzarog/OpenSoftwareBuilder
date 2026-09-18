# Shared helpers for Open Software Builder CLI.
# Loads and validates osb.yaml configuration.

$ErrorActionPreference = 'Stop'

function Get-OsbRoot {
    $dir = (Get-Location).Path
    while ($dir) {
        if (Test-Path (Join-Path $dir 'osb.yaml') -PathType Leaf) { return $dir }
        if (Test-Path (Join-Path $dir '.osb/osb.yaml') -PathType Leaf) { return $dir }
        $parent = Split-Path $dir -Parent
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

function Read-OsbConfig {
    param([Parameter(Mandatory)][string]$Root)
    $yamlPath = Join-Path $Root 'osb.yaml'
    if (-not (Test-Path $yamlPath -PathType Leaf)) {
        $yamlPath = Join-Path $Root '.osb/osb.yaml'
    }
    if (-not (Test-Path $yamlPath -PathType Leaf)) {
        return $null
    }
    # Simple YAML parser for flat osb.yaml — handles the subset we define
    $config = @{
        version = 1
        paths = @{
            source = @('src')
            generated = @('bin', 'obj', 'node_modules', 'dist', 'build', '.next', 'out', 'coverage')
            checkpoints = '.osb/progress'
            knowledge = '.osb/knowledge'
            state = '.osb/state'
        }
        commands = @{
            build = $null
            test = $null
            fitness = $null
            e2e = $null
            changed = $null
        }
        capabilities = @{
            structural_explorer = $null
            browser_qa = 'optional'
        }
        policy = @{
            require_independent_review = $true
            require_fresh_qa = $true
            sensitive_areas = @('auth', 'payments', 'external-input')
        }
    }
    # Parse YAML lines (flat key: value pairs and arrays)
    $lines = Get-Content -LiteralPath $yamlPath
    $section = $null
    $subsection = $null
    $arrayStarted = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
        if ($line -match '^(\w+):(.*)$') {
            $section = $Matches[1]
            $val = $Matches[2].Trim()
            if ($section -eq 'version' -and $val) { $config.version = [int]$val }
            if ($section -eq 'profile' -and $val) { $config.profile = $val }
            $subsection = $null
            continue
        }
        if ($line -match '^  (\w+):(.*)$') {
            $subsection = $Matches[1]
            $val = $Matches[2].Trim()
            if ($val -and $val -ne 'null' -and $section -and $config.ContainsKey($section)) {
                $config[$section][$subsection] = $val
            }
            continue
        }
        if ($line -match '^\s+- (.+)$') {
            $item = $Matches[1].Trim()
            if ($section -and $subsection -and $config.ContainsKey($section)) {
                $key = "$section.$subsection"
                if (-not $arrayStarted.ContainsKey($key)) {
                    $config[$section][$subsection] = @($item)
                    $arrayStarted[$key] = $true
                } else {
                    $config[$section][$subsection] = @($config[$section][$subsection]) + @($item)
                }
            }
        }
    }
    return $config
}

function Get-OsbSourceDirs {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][hashtable]$Config
    )
    $dirs = @()
    foreach ($d in $Config.paths.source) {
        $full = Join-Path $Root $d
        if (Test-Path $full -PathType Container) { $dirs += $full }
    }
    return $dirs
}

function Get-OsbGeneratedNames {
    param([Parameter(Mandatory)][hashtable]$Config)
    return $Config.paths.generated
}

function ConvertTo-OsbUnixTime {
    param([Parameter(Mandatory)][datetime]$Utc)
    return [double]([DateTimeOffset]$Utc).ToUnixTimeMilliseconds() / 1000.0
}

function Get-OsbScopeLatestMtime {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][hashtable]$Config
    )
    $newest = 0.0
    $pruneNames = Get-OsbGeneratedNames -Config $Config
    foreach ($d in $Config.paths.source) {
        $dir = Join-Path $Root $d
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { continue }
        $files = Get-ChildItem -LiteralPath $dir -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object {
                $normalized = $_.FullName -replace '\\', '/'
                $pruned = $false
                foreach ($p in $pruneNames) {
                    if ($normalized -match "/$([regex]::Escape($p))(/|$)") { $pruned = $true; break }
                }
                -not $pruned
            }
        foreach ($f in $files) {
            $t = ConvertTo-OsbUnixTime -Utc $f.LastWriteTimeUtc
            if ($t -gt $newest) { $newest = $t }
        }
    }
    return $newest
}
