@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar-Profesor.ps1" -Modo Vllm15
set "profesor_result=%errorlevel%"
pause
exit /b %profesor_result%
