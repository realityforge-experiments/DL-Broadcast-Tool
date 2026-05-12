@echo off
title DashLeague Broadcast Tool
echo Checking Dependencies...
pip install -r requirements.txt
echo.
echo Launching...
python dashleague_cast_tool.py
pause