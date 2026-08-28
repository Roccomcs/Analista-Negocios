@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Falta instalar el entorno. Ejecuta Instalar.cmd primero.
  pause
  exit /b 1
)
start "Cadmo Analista" ".venv\Scripts\pythonw.exe" -m analista.gui
