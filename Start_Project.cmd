@echo off
title Food Safety Analytics - servers (keep this window open)
rem Double-click to start everything: PostgreSQL warehouse, Citus, Kafka, Spark, ClickHouse, Grafana and JupyterLab (inside WSL Ubuntu).
rem KEEP THIS WINDOW OPEN while you work or present. Closing it stops all the servers.
rem First time on a new machine instead run:  wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh install   (then "full")
cd /d "%~dp0"
echo Starting everything. This takes about 3 minutes. JupyterLab and Grafana are ready after about 1 minute.
echo.
wsl -d Ubuntu -u root --cd "%~dp0" -- bash scripts/run_everything_wsl.sh start
echo.
echo ==========================================================================
echo  Everything is running. KEEP THIS WINDOW OPEN.
echo  Closing this window (or pressing Ctrl+C) stops all the servers.
echo ==========================================================================
rem Windows shuts the Linux side down when no WSL command is running; this keeps it alive until the window is closed.
wsl -d Ubuntu -u root -- bash -c "while true; do sleep 3600; done"
