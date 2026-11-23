@echo off
title Food Safety Analytics - every part, one after another
rem Runs every part of the project in order in this terminal (A, B, C, F, the analytics table, G, H, I), showing each command
rem in green and its real output. Each part's output is also saved to docs\run_logs\part_<X>.log.  About 9 minutes.
rem Start_Project.cmd must be running first.  Add D (Citus) and E (real-time) too: change "all" to "full" below (about 16 minutes).
cd /d "%~dp0"
wsl -d Ubuntu -u root --cd "%~dp0" -- bash scripts/part.sh all
echo.
echo Done. Press any key to close.
pause >nul
