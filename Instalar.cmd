@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --no-deps -e "."
if errorlevel 1 goto error
echo.
echo Entorno Python listo. Revisa docs\TAREAS_MANUALES.md para Ollama y el motor Excel.
pause
exit /b 0
:error
echo No se completo la instalacion. Comproba Python 3.11 o superior.
pause
exit /b 1
