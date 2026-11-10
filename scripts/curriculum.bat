@echo off
REM H1 → H2 curriculum driver (no Counter).
REM Usage: curriculum.bat
REM        curriculum.bat --h1 horizons\discovery\scenarios\h1_virtual_bundle.json
REM        curriculum.bat --out %TEMP%\handoff.json
setlocal
call "%~dp0_common.bat"
"%PYTHON%" -m ach.driver.curriculum %*
endlocal
