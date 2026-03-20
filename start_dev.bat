@echo off
echo Starting Flask in DEVELOPMENT mode with auto-reload...
echo.

cd /d "C:\Users\tkulz\Downloads\college_schedule_backup_20251212\college_schedule"

rem Kill existing Flask processes
wmic process where "name='python.exe' and CommandLine like '%%run.py%%'" delete 2>nul

rem Set development environment variables
set FLASK_APP=run.py
set FLASK_ENV=development
set FLASK_DEBUG=1
set PYTHONPATH=%cd%

echo Environment:
echo FLASK_ENV=%FLASK_ENV%
echo FLASK_DEBUG=%FLASK_DEBUG%
echo FLASK_APP=%FLASK_APP%
echo.

echo Starting Flask server with auto-reload...
python run.py

pause