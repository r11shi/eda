#!/usr/bin/env bash
# One command for the whole project inside WSL Ubuntu (all three warehouses + Grafana).
#
# From Windows (PowerShell or cmd), in the project folder:
#     wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh install   # once: Java, Citus, Python packages, Kafka/ClickHouse/Grafana (~15 min)
#     wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh full      # rebuild everything from the raw data and run all parts (~20 min)
#     wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh start     # after a reboot: start all servers + replay the stream (~2 min)
#     wsl -d Ubuntu -u root -- bash scripts/run_everything_wsl.sh stop      # stop Kafka, Spark, ClickHouse, Grafana
# or double-click Start_Project.cmd in the project folder (= "start").
#
# The project is copied to /root/eda (Linux disk, much faster than /mnt/e) and run there.
# Results are copied back to this folder's results/ after "full".
# Keep the window open while presenting: closing it lets WSL shut the servers down.
set -euo pipefail
MODE="${1:-start}"
SRC="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"   # the Windows project folder, e.g. /mnt/e/web/EDA
[ -f "$SRC/run_all.py" ] && [ -d "$SRC/etl" ] || { echo "Not the project folder: $SRC (run this script from the project's scripts/ folder)"; exit 1; }
P=/root/eda                                         # working copy on the Linux disk
VENV=/root/venv
PGVER="$(ls /usr/lib/postgresql | sort -V | tail -1)"
export PATH="$VENV/bin:$PATH"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

sync_code() {
  say "Copying the project from $SRC to $P"
  mkdir -p "$P"
  rsync -a --delete --exclude .git --exclude runtime --exclude data/curated --exclude .claude "$SRC/" "$P/"
  find "$P" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.sql' -o -name '*.yml' \) -exec sed -i 's/\r$//' {} +
  chmod +x "$P"/scripts/*.sh
}

start_postgres() {
  say "PostgreSQL $PGVER: main warehouse (5432) and Citus coordinator + 2 workers (5440-5442)"
  pg_ctlcluster "$PGVER" main start 2>/dev/null || true
  cd "$P" && bash scripts/setup_postgres.sh >/dev/null
  bash scripts/setup_citus_cluster.sh | tail -6
}

start_stream() {
  say "Real-time stack: ClickHouse -> Kafka -> Spark Structured Streaming -> Grafana"
  cd "$P"
  pkill -f spark_stream.py 2>/dev/null && sleep 3 || true    # one streaming job only (start_realtime_stack.sh launches a new one)
  bash scripts/start_realtime_stack.sh
  sleep 20
  for t in inspection_events invalid_events window_agg daily_event_time_agg; do   # clean replay: empty the ClickHouse tables (ClickHouse is up now)
    curl -s http://127.0.0.1:8123/ --data-binary "TRUNCATE TABLE IF EXISTS food.$t" >/dev/null; done
  say "Replaying Oct-Dec 2025 inspections into Kafka (80 events/s, one malformed test event every 150)"
  mkdir -p docs/console_logs
  { echo "\$ python streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150"
    python streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate "${START_RATE:-150}" --bad-every 150; } | tee docs/console_logs/stream_producer.log | tail -2
  sleep 20
  ch() { echo ":) $1"; curl -s http://127.0.0.1:8123/ --data-binary "$1 FORMAT PrettyCompactMonoBlock"; echo; }
  { echo "\$ clickhouse client   (ClickHouse, real-time warehouse)"
    ch "SELECT count() AS valid_events, min(event_date) AS first_day, max(event_date) AS last_day FROM food.inspection_events"
    ch "SELECT reason, count() AS events FROM food.invalid_events GROUP BY reason ORDER BY events DESC"
    ch "SELECT result_group, count() AS inspections FROM food.inspection_events GROUP BY result_group ORDER BY inspections DESC"
  } > docs/console_logs/stream_clickhouse.log
  rsync -a docs/console_logs/stream_*.log "$SRC/docs/console_logs/" 2>/dev/null || true
  python streaming/measure_streaming.py | tail -16
}

dashboards() {
  say "Grafana (real-time dashboard) and JupyterLab (notebooks)"
  cd "$P"
  python streaming/grafana/build_dashboard.py
  pkill -f "bin/grafana server" 2>/dev/null || true; sleep 2
  bash scripts/start_grafana.sh >/dev/null
  PY="$VENV/bin/python" bash scripts/start_notebooks.sh
}

stop_stream() {
  say "Stopping Spark, Kafka, ClickHouse and Grafana"
  pkill -f spark_stream.py 2>/dev/null || true
  [ -x "$P/runtime/tools/kafka_2.13-3.9.0/bin/kafka-server-stop.sh" ] && "$P/runtime/tools/kafka_2.13-3.9.0/bin/kafka-server-stop.sh" 2>/dev/null || true
  pkill -f "clickhouse server" 2>/dev/null || true
  pkill -f "bin/grafana server" 2>/dev/null || true
  pkill -f "jupyter-lab|jupyter lab" 2>/dev/null || true
}

banner() {
  cat <<TXT

  ===================================================================================
   Everything is running. Open in your Windows browser:
     Guide (read this)         README.html  (double-click it in the project folder)
     Dashboard (all parts)     dashboard/food_safety_dashboard.html  (double-click)
     Real-time dashboard (E)   http://localhost:3000/d/food-safety-rt
     Notebooks (A, G, H, I)    http://localhost:8888/lab/tree/notebooks
   SQL clients (pgAdmin / DBeaver):
     warehouse   localhost:5432  db foodsafety        user foodsafety  password foodsafety
     Citus       localhost:5440  db foodsafety_citus  user postgres    (no password)
     ClickHouse  http://localhost:8123/play  (user default, no password)
   Keep this window open while presenting. Ctrl+C here stops nothing; run "stop" to stop.
  ===================================================================================
TXT
}

case "$MODE" in
  install)
    sync_code
    say "apt packages: PostgreSQL $PGVER, Java 21, Citus build tools"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq postgresql openjdk-21-jre-headless postgresql-server-dev-all build-essential git rsync curl \
      libcurl4-openssl-dev liblz4-dev libzstd-dev libssl-dev libkrb5-dev libselinux1-dev libxslt1-dev libpam0g-dev \
      libreadline-dev libicu-dev autoconf flex bison python3-venv >/dev/null
    PGVER="$(ls /usr/lib/postgresql | sort -V | tail -1)"
    if [ ! -f "/usr/lib/postgresql/$PGVER/lib/citus.so" ]; then
      CITUS_TAG=v14.3.0; [ "$PGVER" -le 17 ] && CITUS_TAG=v13.2.0
      say "Building Citus $CITUS_TAG for PostgreSQL $PGVER from source"
      rm -rf /root/citus && git -c advice.detachedHead=false clone -q --depth 1 --branch "$CITUS_TAG" https://github.com/citusdata/citus.git /root/citus
      (cd /root/citus && ./configure PG_CONFIG="/usr/lib/postgresql/$PGVER/bin/pg_config" >/dev/null && make -j"$(nproc)" >/dev/null && make install >/dev/null)
    fi
    say "Python packages"
    [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$P/requirements.txt" clickhouse-connect kafka-python-ng
    [ -x "$P/runtime/venv-spark/bin/python" ] || { python3 -m venv "$P/runtime/venv-spark"; "$P/runtime/venv-spark/bin/pip" install -q pyspark==4.0.1 clickhouse-connect pandas pyarrow; }
    say "Kafka, ClickHouse, Grafana (checksums verified)"
    bash "$P/scripts/install_tools.sh" | tail -3
    say "Installed. Next: run_everything_wsl.sh full" ;;
  full)
    sync_code
    start_postgres
    say "Parts A-C, F-I: batch warehouse, OLAP, dashboard, models (run_all.py, ~9 min)"
    cd "$P" && python run_all.py
    say "Part D: distribution-key analysis, single-node baseline, then the Citus benchmark (~5 min)"
    python etl/distributed_baseline.py | tail -3
    python etl/distributed_citus.py | tail -28
    start_stream
    dashboards
    say "Copying results/ back to $SRC/results"
    rsync -a "$P/results/" "$SRC/results/"
    banner ;;
  start)
    [ -d "$P/runtime/tools" ] || { echo "Run 'install' and 'full' first."; exit 1; }
    sync_code
    start_postgres
    dashboards          # notebooks + Grafana first, so they can be opened while the stream starts
    start_stream
    banner ;;
  dashboards)      # only copy the code again and restart Grafana + the notebook server
    sync_code
    dashboards
    banner ;;
  replay)          # live demo: empty ClickHouse, then send the Oct-Dec 2025 inspections again (slowly, so Grafana fills up while you watch)
    cd "$P"
    for t in inspection_events invalid_events window_agg daily_event_time_agg; do
      curl -s http://127.0.0.1:8123/ --data-binary "TRUNCATE TABLE IF EXISTS food.$t" >/dev/null; done
    say "Replaying 3,647 inspections at ${RATE:-25} events/s. Watch http://localhost:3000/d/food-safety-rt"
    python streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate "${RATE:-25}" --bad-every 150 ;;
  stop)
    stop_stream ;;
  *)
    echo "usage: run_everything_wsl.sh install|full|start|dashboards|replay|stop"; exit 1 ;;
esac
