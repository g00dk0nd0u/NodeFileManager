@echo off
setlocal
cd /d "%~dp0.."

echo NodeFileManager launcher
echo Repository: "%CD%"
echo Stop the source application with Ctrl+C.

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.14 -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.14"
)
if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
  )
)
if not defined PYTHON_CMD (
  where python3 >nul 2>nul
  if not errorlevel 1 (
    python3 -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
  )
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)
if not defined PYTHON_CMD (
  echo ERROR: Compatible Python 3 was not found. Python 3.14 is preferred.
  echo Install an approved Python, then run this file again. No admin rights are otherwise needed.
  pause
  exit /b 1
)

echo Using: %PYTHON_CMD%
%PYTHON_CMD% -m backend.launcher
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
