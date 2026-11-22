@echo off
rem Double-click to start every warehouse (PostgreSQL, Citus, Kafka/Spark/ClickHouse) and Grafana inside WSL Ubuntu.
rem Then open http://localhost:3000 . Keep this window open while presenting.
rem First time on a new machine instead run:  wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh install   (then "full")
cd /d "%~dp0"
wsl -d Ubuntu -u root --cd "%~dp0" -- bash scripts/run_everything_wsl.sh start
echo.
echo Servers are running. Press any key to close this window (this lets WSL stop them).
pause >nul
