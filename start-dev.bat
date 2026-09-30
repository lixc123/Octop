@echo off
setlocal EnableExtensions

rem Octop local development launcher.
rem Optional overrides before running:
rem   set OCTOP_DEV_HOST=127.0.0.1
rem   set OCTOP_BACKEND_PORT=8088
rem   set OCTOP_FRONTEND_PORT=5173

set "OCTOP_DEV_ROOT=%~dp0"
if not defined OCTOP_DEV_HOST set "OCTOP_DEV_HOST=127.0.0.1"
if not defined OCTOP_BACKEND_PORT set "OCTOP_BACKEND_PORT=8088"
if not defined OCTOP_FRONTEND_PORT set "OCTOP_FRONTEND_PORT=5173"

if not exist "%OCTOP_DEV_ROOT%dashboard\package.json" (
    echo [octop] ERROR: dashboard\package.json was not found.
    exit /b 1
)

set "OCTOP_DEV_PYTHON="
if exist "%OCTOP_DEV_ROOT%.venv\Scripts\python.exe" set "OCTOP_DEV_PYTHON=%OCTOP_DEV_ROOT%.venv\Scripts\python.exe"
if not defined OCTOP_DEV_PYTHON if exist "%USERPROFILE%\.octop\venv\Scripts\python.exe" set "OCTOP_DEV_PYTHON=%USERPROFILE%\.octop\venv\Scripts\python.exe"
if not defined OCTOP_DEV_PYTHON for /f "delims=" %%P in ('where python 2^>nul') do if not defined OCTOP_DEV_PYTHON set "OCTOP_DEV_PYTHON=%%P"

if not defined OCTOP_DEV_PYTHON (
    echo [octop] ERROR: Python 3.12 was not found. Create .venv or install Python first.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [octop] ERROR: npm was not found. Install Node.js before starting the dashboard.
    exit /b 1
)

if /i "%~1"=="--check" goto :check
if /i "%~1"=="backend" goto :backend
if /i "%~1"=="frontend" goto :frontend

call :port_pid %OCTOP_BACKEND_PORT%
if defined OCTOP_PORT_PID (
    echo [octop] Backend already listening on http://%OCTOP_DEV_HOST%:%OCTOP_BACKEND_PORT% ^(PID %OCTOP_PORT_PID%^) - reusing it.
) else (
    echo [octop] Starting backend on http://%OCTOP_DEV_HOST%:%OCTOP_BACKEND_PORT% ...
    start "Octop Backend" "%ComSpec%" /k call "%~f0" backend
    call :wait_for_port %OCTOP_BACKEND_PORT% 20
    if errorlevel 1 echo [octop] WARNING: backend did not listen within 20 seconds. Check the backend window for the error.
)

call :port_pid %OCTOP_FRONTEND_PORT%
if defined OCTOP_PORT_PID (
    echo [octop] Dashboard already listening on http://%OCTOP_DEV_HOST%:%OCTOP_FRONTEND_PORT% ^(PID %OCTOP_PORT_PID%^) - reusing it.
) else (
    echo [octop] Starting dashboard on http://%OCTOP_DEV_HOST%:%OCTOP_FRONTEND_PORT% ...
    start "Octop Dashboard" "%ComSpec%" /k call "%~f0" frontend
    call :wait_for_port %OCTOP_FRONTEND_PORT% 20
    if errorlevel 1 echo [octop] WARNING: dashboard did not listen within 20 seconds. Check the dashboard window for the error.
)

echo.
echo [octop] Backend:  http://%OCTOP_DEV_HOST%:%OCTOP_BACKEND_PORT%
echo [octop] Dashboard: http://%OCTOP_DEV_HOST%:%OCTOP_FRONTEND_PORT%
echo [octop] Existing listeners are reused; close the service windows to stop new processes.
exit /b 0

:check
echo [octop] Configuration check passed.
echo [octop] Python: %OCTOP_DEV_PYTHON%
echo [octop] Backend port: %OCTOP_BACKEND_PORT%
echo [octop] Frontend port: %OCTOP_FRONTEND_PORT%
exit /b 0

:backend
title Octop Backend
cd /d "%OCTOP_DEV_ROOT%"
set "PYTHONPATH=%OCTOP_DEV_ROOT%src;%PYTHONPATH%"
echo [octop] Python: %OCTOP_DEV_PYTHON%
echo [octop] Press Ctrl+C in this window to stop the backend.
echo.
"%OCTOP_DEV_PYTHON%" -m octop.cli.main run --host "%OCTOP_DEV_HOST%" --port %OCTOP_BACKEND_PORT% --log-level info
set "OCTOP_EXIT_CODE=%ERRORLEVEL%"
echo.
echo [octop] Backend stopped with exit code %OCTOP_EXIT_CODE%.
pause
exit /b %OCTOP_EXIT_CODE%

:frontend
title Octop Dashboard
cd /d "%OCTOP_DEV_ROOT%dashboard"
if not exist "node_modules\.bin\vite.cmd" (
    echo [octop] dashboard dependencies are missing; running npm ci ...
    call npm ci
    if errorlevel 1 (
        echo [octop] ERROR: npm ci failed.
        pause
        exit /b 1
    )
)
set "VITE_API_PORT=%OCTOP_BACKEND_PORT%"
set "VITE_DEV_PORT=%OCTOP_FRONTEND_PORT%"
echo [octop] API proxy: http://127.0.0.1:%OCTOP_BACKEND_PORT%
echo [octop] Press Ctrl+C in this window to stop the dashboard.
echo.
call npm run dev -- --host %OCTOP_DEV_HOST% --strictPort
set "OCTOP_EXIT_CODE=%ERRORLEVEL%"
echo.
echo [octop] Dashboard stopped with exit code %OCTOP_EXIT_CODE%.
pause
exit /b %OCTOP_EXIT_CODE%

:port_pid
set "OCTOP_PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do if not defined OCTOP_PORT_PID set "OCTOP_PORT_PID=%%P"
exit /b 0

:wait_for_port
set /a OCTOP_WAIT_REMAINING=%~2
:wait_for_port_loop
call :port_pid %~1
if defined OCTOP_PORT_PID exit /b 0
if %OCTOP_WAIT_REMAINING% LEQ 0 exit /b 1
timeout /t 1 /nobreak >nul
set /a OCTOP_WAIT_REMAINING-=1
goto wait_for_port_loop
