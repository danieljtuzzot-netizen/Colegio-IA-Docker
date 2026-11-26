@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VERIFICAR_ARCHIVOS.ps1"
set "verify_result=%errorlevel%"
pause
exit /b %verify_result%
