@echo off
echo Starting SMS Agent...
echo (Press Ctrl+C at any time to quit)
cd /d "%~dp0\.."
python src\main.py
pause
