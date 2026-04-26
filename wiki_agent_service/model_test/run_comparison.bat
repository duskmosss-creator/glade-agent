@echo off
SETLOCAL EnableDelayedExpansion
TITLE Wiki Agent Model Benchmark

echo ========================================================
echo        WIKI AGENT: RESEARCH MODEL BENCHMARK
echo ========================================================
echo.
echo Target Area: Cincinnati to West Virginia (Cryptids)
echo.

:: LOG DIRECTORY
SET LOG_DIR=logs
if not exist %LOG_DIR% mkdir %LOG_DIR%
SET TIMESTAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
SET TIMESTAMP=%TIMESTAMP: =0%
SET LOG_FILE=%LOG_DIR%\benchmark_%TIMESTAMP%.log

echo Logging all output to %LOG_FILE%
echo. > %LOG_FILE%

:: TEST 1: LLAMA
echo [STEP 1] TESTING LLAMA 3.2 3B
echo Make sure 'llama-3.2-3b-instruct' is loaded in LM Studio at port 1234.
echo Press any key when ready to start Llama bench...
pause > nul

echo Running Llama iterations...
echo Running Llama iterations...
python benchmark_models.py --model llama-3.2-3b-instruct --count 1 --searches 80 --cycles 8 --query "Investigate history of Mothman sightings in Point Pleasant (1966-1967). Focus on eyewitness accounts (Scarberry/Mallette), journalist Mary Hyre, Chief Cornstalk curse, and economic impact (Tourism/Festival)." >> %LOG_FILE% 2>&1
type %LOG_FILE% | findstr "Finished"

echo.
echo [COOLDOWN] Waiting 20 seconds between models...
timeout /t 20 /nobreak > nul

:: TEST 2: GRANITE
echo.
echo [STEP 2] TESTING GRANITE 4.0 H TINY
echo !!! PLEASE UNLOAD LLAMA AND LOAD 'ibm/granite-4-h-tiny' IN LM STUDIO !!!
echo Press any key when Granite is ready...
pause > nul

echo Running Granite iterations...
echo Running Granite iterations...
echo Running Granite iterations...
python benchmark_models.py --model ibm/granite-4-h-tiny --count 1 --searches 80 --cycles 8 --query "Investigate history of Mothman sightings in Point Pleasant (1966-1967). Focus on eyewitness accounts (Scarberry/Mallette), journalist Mary Hyre, Chief Cornstalk curse, and economic impact (Tourism/Festival)." >> %LOG_FILE% 2>&1
type %LOG_FILE% | findstr "Finished"

echo.
echo ========================================================
echo             BENCHMARK COMPLETE
echo ========================================================
echo Detailed logs for each model are in:
echo   - bench_llama-3_2-3b-instruct.log
echo   - bench_ibm_granite-4-h-tiny.log
echo.
pause
