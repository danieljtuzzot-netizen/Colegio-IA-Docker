@echo off
setlocal
cd /d "%~dp0"
docker compose -f compose.ia.yaml stop
if errorlevel 1 goto fallo
docker compose -f VLLM_15B_PC\compose.vllm.15b.yaml stop
if errorlevel 1 goto fallo
echo Servicios detenidos. Se conservan los modelos y las revisiones.
pause
exit /b 0
:fallo
echo No se pudo completar la parada. Conservar la salida anterior.
pause
exit /b 1
