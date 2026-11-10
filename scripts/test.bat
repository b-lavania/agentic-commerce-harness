@echo off
REM Run the full pytest suite (or pass through args).
REM Usage: test.bat
REM        test.bat tests\test_scenarios.py -q
setlocal
call "%~dp0_common.bat"
if "%~1"=="" (
  "%PYTHON%" -m pytest -q
) else (
  "%PYTHON%" -m pytest %*
)
endlocal
