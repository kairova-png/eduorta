@echo off
echo ========================================
echo         College Schedule Server Manager
echo ========================================
echo.

:menu
echo [1] Start Server (Development)
echo [2] Start Server (Production)
echo [3] Stop All Servers
echo [4] Check Server Status
echo [5] Exit
echo.
set /p choice="Select an option (1-5): "

if %choice%==1 goto start_dev
if %choice%==2 goto start_prod
if %choice%==3 goto stop_servers
if %choice%==4 goto check_status
if %choice%==5 goto exit
echo Invalid choice. Please try again.
echo.
goto menu

:start_dev
echo Stopping all existing Flask servers...
wmic process where "name='python.exe' and CommandLine like '%%run.py%%'" delete >nul 2>&1
timeout /t 2 >nul
echo Starting development server...
set FLASK_DEBUG=1
cd /d "%~dp0"
start "College Schedule Server" cmd /c "python run.py & pause"
echo Development server started in new window.
echo Access: http://localhost:5000
echo.
goto menu

:start_prod
echo Stopping all existing Flask servers...
wmic process where "name='python.exe' and CommandLine like '%%run.py%%'" delete >nul 2>&1
timeout /t 2 >nul
echo Starting production server...
set FLASK_ENV=production
cd /d "%~dp0"
start "College Schedule Server" cmd /c "python run.py & pause"
echo Production server started in new window.
echo Access: http://localhost:5000
echo.
goto menu

:stop_servers
echo Stopping all Flask servers...
wmic process where "name='python.exe' and CommandLine like '%%run.py%%'" delete >nul 2>&1
echo All servers stopped.
echo.
goto menu

:check_status
echo Checking server status...
netstat -an | findstr :5000 >nul
if %errorlevel%==0 (
    echo ✓ Server is running on port 5000
    echo Access: http://localhost:5000
) else (
    echo ✗ No server running on port 5000
)
echo.
goto menu

:exit
echo Goodbye!
pause