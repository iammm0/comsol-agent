# 构建 Python bridge 可执行文件，供 Tauri 安装包内嵌（externalBin）。
# 在项目根目录执行: .\desktop\scripts\build-bridge.ps1
# 或在 desktop 目录执行: ..\..\desktop\scripts\build-bridge.ps1（需先 cd 到项目根再调 pyinstaller）

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $DesktopRoot
$BinariesDir = Join-Path $DesktopRoot "src-tauri\binaries"

# 目标三元组（与 Rust 一致，Tauri externalBin 要求）
$TargetTriple = (rustc --print host-tuple 2>$null)
if (-not $TargetTriple) { $TargetTriple = "x86_64-pc-windows-msvc" }
$BridgeName = "comsol-agent-bridge-$TargetTriple.exe"

$DistExe = Join-Path $ProjectRoot "dist\comsol-agent-bridge.exe"
$DestExe = Join-Path $BinariesDir $BridgeName

Write-Host "Building Python bridge with PyInstaller..."
Push-Location $ProjectRoot
try {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) { throw "python or py not found" }
    $pyExe = $py.Source
    cmd /c "`"$pyExe`" -m pip install pyinstaller --quiet"
    cmd /c "`"$pyExe`" -m PyInstaller desktop/scripts/bridge.spec --noconfirm"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller exited with code $LASTEXITCODE" }
    if (-not (Test-Path $DistExe)) {
        throw "PyInstaller did not produce: $DistExe"
    }
    New-Item -ItemType Directory -Path $BinariesDir -Force | Out-Null
    Copy-Item -Path $DistExe -Destination $DestExe -Force
    Write-Host "Bridge built: $DestExe"
} finally {
    Pop-Location
}
