@echo off
rem LIVE DEMO of Part E. Run Start_Project.cmd first, open http://localhost:3000/d/food-safety-rt, then double-click this.
rem It empties ClickHouse and replays the Oct-Dec 2025 inspections through Kafka and Spark (about 2.5 minutes).
cd /d "%~dp0"
wsl -d Ubuntu -u root --cd "%~dp0" -- bash scripts/run_everything_wsl.sh replay
echo.
echo Replay finished. Press any key to close.
pause >nul
