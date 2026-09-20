#!/usr/bin/env pwsh
<#
.SYNOPSIS
  OSB one-time registration / doctor / upgrade launcher for Windows PowerShell.

.DESCRIPTION
  Resolves its own location and hands off to the cross-platform Python implementation at
  osb/scripts/install.py — this script contains no workflow policy itself and starts no
  background process. Requires Python 3.11+ on PATH (as `python` or `python3`).
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "osb/install.ps1: python3 (3.11+) was not found on PATH"
    exit 1
}

& $python.Source (Join-Path $ScriptDir "scripts/install.py") @Args
exit $LASTEXITCODE
