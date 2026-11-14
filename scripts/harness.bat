@echo off
REM Run cert scenarios.
REM Usage: harness.bat
REM        harness.bat --jsonl %TEMP%\ach-trajectories.jsonl
REM        harness.bat run horizons\discovery\scenarios\h1_cloud_seats.json
setlocal
call "%~dp0_common.bat"
if "%~1"=="" (
  "%PYTHON%" -m ach.harness.cli run-all
) else if /I "%~1"=="run" (
  "%PYTHON%" -m ach.harness.cli run %2 %3 %4 %5 %6 %7 %8 %9
) else (
  "%PYTHON%" -m ach.harness.cli run-all %*
)
endlocal
