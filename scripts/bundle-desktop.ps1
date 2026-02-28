# 一键打包桌面安装程序（前端 + Python 后端 + Java 11）
# 在项目根目录执行: .\scripts\bundle-desktop.ps1
# 依赖: Python（含项目依赖）、Node.js、Rust、PyInstaller（脚本内可自动安装）

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $ProjectRoot "pyproject.toml"))) {
    Write-Error "Run from project root or ensure pyproject.toml exists: $ProjectRoot"
    exit 1
}

Push-Location $ProjectRoot
try {
    Write-Host "========== 1/3 构建 Python bridge ==========" -ForegroundColor Cyan
    & "$ProjectRoot\desktop\scripts\build-bridge.ps1"
    if ($LASTEXITCODE -ne 0) { throw "build-bridge.ps1 failed" }

    Write-Host "`n========== 2/3 下载 JDK 11 ==========" -ForegroundColor Cyan
    & "$ProjectRoot\desktop\scripts\download-jdk11.ps1"
    if ($LASTEXITCODE -ne 0) { throw "download-jdk11.ps1 failed" }

    Write-Host "`n========== 3/3 构建 Tauri 安装包 ==========" -ForegroundColor Cyan
    Set-Location (Join-Path $ProjectRoot "desktop")
    npm run tauri build
    if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }

    Write-Host "`n========== 打包完成 ==========" -ForegroundColor Green
    $NsisDir = Join-Path $ProjectRoot "desktop\src-tauri\target\release\bundle\nsis"
    $MsiDir  = Join-Path $ProjectRoot "desktop\src-tauri\target\release\bundle\msi"
    if (Test-Path $NsisDir) {
        Get-ChildItem $NsisDir -Filter "*.exe" | ForEach-Object { Write-Host "  NSIS: $($_.FullName)" }
    }
    if (Test-Path $MsiDir) {
        Get-ChildItem $MsiDir -Recurse -Filter "*.msi" | ForEach-Object { Write-Host "  MSI:  $($_.FullName)" }
    }
} catch {
    Write-Error $_
    exit 1
} finally {
    Pop-Location
}
