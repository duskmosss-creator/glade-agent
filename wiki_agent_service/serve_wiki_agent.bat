@echo off
cd /d "%~dp0"
title Wiki Agent Server

:MENU
cls
echo ==================================================
echo      WIKI AGENT SERVER - CONFIGURATION MENU
echo ==================================================
echo.
echo Please select the AI Backend Mode:
echo.
echo [1] LEMONADE (Simple Mode)
echo     - Single Model (Qwen3-8B-FLM)
echo     - Runs on Port 8000
echo.
echo [2] LM STUDIO (Hybrid Mode)
echo     - Two Models: 
echo       * Router: Llama-3.2-1B-Instruct
echo       * Smart:  Qwen/Qwen3-8B
echo     - Runs on Port 1234
echo.
echo ==================================================
set /p choice="Enter Selection (1 or 2): "

if "%choice%"=="1" goto SET_LEMONADE
if "%choice%"=="2" goto SET_LMSTUDIO
echo Invalid selection. Please try again.
pause
goto MENU

:SET_LEMONADE
echo.
echo [Config] Switching to LEMONADE (Simple)...
copy /Y wiki_settings_lemonade.json wiki_settings.json
goto START_SERVER

:SET_LMSTUDIO
echo.
echo [Config] Switching to LM STUDIO (Hybrid)...
copy /Y wiki_settings_lmstudio.json wiki_settings.json
goto START_SERVER

:START_SERVER
echo.
echo Starting Wiki Agent Server on Port 8002...
echo --------------------------------------------------
python wiki_server.py
if errorlevel 1 (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo [ERROR] The Server crashed with exit code %errorlevel%
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    echo Press any key to restart the menu...
    pause
    goto MENU
)

pause
