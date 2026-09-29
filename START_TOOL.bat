@echo off
title DashLeague Broadcast Tool [FORGE NODE]
cd /d "%~dp0"

:: 1. Check for Virtual Environment
if not exist venv (
    echo [!] Virtual Environment not found. Creating...
    py -3.11 -m venv venv
    call .\venv\Scripts\activate
    echo [!] Installing Requirements...
    pip install -r requirements.txt
)

:: 2. Activate and Run
echo [OK] Environment Active.
echo [OK] Launching DashLeague Tool...
.\venv\Scripts\python.exe dashleague_cast_tool.py

if %ERRORLEVEL% NEQ 0 (
    echo [!] Tool crashed with Exit Code: %ERRORLEVEL%
    pause
)