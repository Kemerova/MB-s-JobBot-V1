@echo off
REM JobBot - AI-Powered Job Hunting Assistant
REM Double-click this file to start JobBot

title JobBot - AI Job Hunter
echo.
echo ========================================
echo   JobBot - AI Job Hunting Assistant
echo ========================================
echo.

cd /d "%~dp0"

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo Starting JobBot...
python main.py

REM After completion, start dashboard server
echo.
echo Starting dashboard server...
python dashboard_server.py

echo.
echo Press any key to exit...
pause >nul