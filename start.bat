@echo off
cd /d "%~dp0"
if not exist .venv python -m venv .venv
if errorlevel 1 goto fail
if not exist .venv\.rp-installed (
  .venv\Scripts\python -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  echo installed>.venv\.rp-installed
)
.venv\Scripts\python -m rp_creator %*
pause
exit /b
:fail
echo Instale Python 3.11 ou superior com Add Python to PATH.
pause
exit /b 1
