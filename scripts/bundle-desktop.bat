@echo off
REM 一键打包桌面安装程序，在项目根执行: scripts\bundle-desktop.bat
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bundle-desktop.ps1"
exit /b %ERRORLEVEL%
