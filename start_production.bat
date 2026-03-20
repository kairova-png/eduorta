@echo off
echo ========================================
echo  APEC College Schedule - Production Mode
echo ========================================
echo.

REM Set production environment
set FLASK_ENV=production
set LOG_LEVEL=INFO

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)

echo.
echo Installing/upgrading requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo Creating necessary directories...
if not exist "instance" mkdir instance
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports

echo.
echo Initializing database (if needed)...
python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all(); print('Database ready.')"

echo.
echo ========================================
echo  Starting College Schedule in Production Mode
echo ========================================
echo  Application will run on: http://127.0.0.1:5000
echo  Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start with Gunicorn for production (if available) or fall back to Python
python -m pip show gunicorn >nul 2>&1
if errorlevel 1 (
    echo Using Flask development server (install gunicorn for better performance^)
    python run.py
) else (
    echo Using Gunicorn production server
    gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 120 --access-logfile logs/access.log --error-logfile logs/error.log "run:app"
)

pause