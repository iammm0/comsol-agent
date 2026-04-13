#requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$BridgeDebug
)

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$DesktopDir = Join-Path $ProjectRoot "desktop"
$CurrentPid = $PID
$ProcessNames = @(
    "cmd.exe",
    "cargo.exe",
    "mph-agent-desktop.exe",
    "node.exe",
    "py.exe",
    "python.exe",
    "rustc.exe"
)

function Test-ContainsIgnoreCase {
    param(
        [string]$Text,
        [string]$Needle
    )

    if ([string]::IsNullOrWhiteSpace($Text) -or [string]::IsNullOrWhiteSpace($Needle)) {
        return $false
    }

    return $Text.IndexOf($Needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Get-RepoDevProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $CurrentPid -and
            $ProcessNames -contains ([string]$_.Name).ToLowerInvariant()
        } |
        Where-Object {
            $cmd = [string]$_.CommandLine
            $exe = [string]$_.ExecutablePath
            (Test-ContainsIgnoreCase $cmd $ProjectRoot) -or
            (Test-ContainsIgnoreCase $exe $ProjectRoot)
        } |
        Sort-Object ProcessId -Unique
}

if (-not (Test-Path -LiteralPath (Join-Path $DesktopDir "package.json"))) {
    throw "desktop/package.json not found. Run this script from the repository root."
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd not found. Install Node.js first."
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo not found. Install Rust first."
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  mph-agent dev restart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Root: $ProjectRoot"
Write-Host ""

$procs = @(Get-RepoDevProcesses)
if ($procs.Count -gt 0) {
    Write-Host "[1/2] Stopping existing repo-scoped dev processes..." -ForegroundColor Yellow
    foreach ($proc in $procs) {
        $cmd = ([string]$proc.CommandLine).Trim()
        if ($cmd.Length -gt 120) {
            $cmd = $cmd.Substring(0, 120) + "..."
        }
        Write-Host ("  - stop {0} (PID {1}) {2}" -f $proc.Name, $proc.ProcessId, $cmd)
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "[1/2] No existing repo-scoped dev processes found." -ForegroundColor Yellow
}

$env:PYTHONIOENCODING = "utf-8"
$env:MPH_AGENT_ROOT = $ProjectRoot

if ($BridgeDebug) {
    $env:MPH_AGENT_BRIDGE_DEBUG = "1"
    Write-Host "Bridge debug enabled: MPH_AGENT_BRIDGE_DEBUG=1" -ForegroundColor Green
} elseif ($env:MPH_AGENT_BRIDGE_DEBUG) {
    Write-Host "Bridge debug already enabled in current shell." -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/2] Starting desktop dev app..." -ForegroundColor Yellow
Write-Host "Command: npm run tauri dev"
Write-Host "Working directory: $DesktopDir"
Write-Host ""

Push-Location $DesktopDir
try {
    & npm.cmd run tauri dev
} finally {
    Pop-Location
}
