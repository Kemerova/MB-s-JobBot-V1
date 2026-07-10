@echo off
rem Double-click launcher for the JobBot GUI
cd /d "%~dp0"
.venv\Scripts\python.exe main.py gui
pause
