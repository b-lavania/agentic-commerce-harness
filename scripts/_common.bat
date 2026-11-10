@echo off
REM Shared setup for agentic-commerce-harness launch scripts.
REM Call with: call "%~dp0_common.bat"
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"

if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
  where python >nul 2>&1 && set "PYTHON=python" || set "PYTHON=python3"
)
