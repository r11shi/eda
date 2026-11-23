@echo off
title Food Safety Analytics - servers (keep this window open)
rem Double-click to start everything: PostgreSQL warehouse, Citus, Kafka, Spark, ClickHouse, Grafana and JupyterLab (inside WSL Ubuntu).
rem KEEP THIS WINDOW OPEN while you work or present. Closing it stops all the servers.
rem First time on a new machine instead run:  wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh install   (then "full")
cd /d "%~dp0"
echo Starting everything. This takes about 3 minutes. JupyterLab and Grafana are ready after about 1 minute.
echo.
rem Start everything, then stay in the SAME Linux session: Windows stops what a session started when the session ends,
rem so this window keeps the servers alive until it is closed.
wsl -d Ubuntu -u root --cd "%~dp0" -- bash -c "bash scripts/run_everything_wsl.sh start; echo; echo ==========================================================================; echo ' Everything is running. KEEP THIS WINDOW OPEN.'; echo ' Closing this window stops all the servers.'; echo ==========================================================================; while true; do sleep 3600; done"
