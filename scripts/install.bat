@echo off
REM Create .venv (if missing) and install the package editable with dev deps.
REM Usage: install.bat
setlocal
call "%~dp0_common.bat"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Creating .venv ...
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    python -m venv "%ROOT%\.venv"
  ) else (
    python3 -m venv "%ROOT%\.venv"
  )
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
)

echo Installing agentic-commerce-harness (editable + dev) ...
"%PYTHON%" -m pip install -U pip
"%PYTHON%" -m pip install -e ".[dev]"
echo Done. PYTHON=%PYTHON%
endlocal
