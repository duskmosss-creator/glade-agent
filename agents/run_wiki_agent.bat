@echo off
echo Starting Wiki Agent...
echo (Press Ctrl+C at any time to quit)
cd /d "%~dp0\.."
python src\wiki_agent.py
pause
