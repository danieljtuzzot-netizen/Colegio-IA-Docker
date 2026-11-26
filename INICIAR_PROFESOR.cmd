@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar-Profesor.ps1" -Modo Base
set "profesor_result=%errorlevel%"
pause
exit /b %profesor_result%
