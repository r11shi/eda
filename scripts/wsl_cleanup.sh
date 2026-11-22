#!/usr/bin/env bash
# Removes everything the WSL (Ubuntu) set-up of this project installed.
# Run inside WSL as root:   wsl -d Ubuntu -- bash /mnt/e/web/EDA/scripts/wsl_cleanup.sh
# Leaves the stock Ubuntu PostgreSQL 18 'main' cluster in place (only the project database and role are dropped).
set -u
echo "Stopping the real-time stack (Spark, Kafka, ClickHouse, Grafana)..."
pkill -f spark_stream.py      2>/dev/null
pkill -f kafka.Kafka          2>/dev/null
pkill -f "clickhouse server"  2>/dev/null
pkill -f "grafana server"     2>/dev/null
sleep 3

echo "Dropping the Citus clusters (coord, worker1, worker2)..."
for c in coord worker1 worker2; do pg_dropcluster --stop 18 "$c" 2>/dev/null; done

echo "Dropping the project database and role from the main cluster..."
su postgres -c "psql -q -c 'DROP DATABASE IF EXISTS foodsafety'"      2>/dev/null
su postgres -c "psql -q -c 'DROP ROLE IF EXISTS foodsafety'"          2>/dev/null

echo "Removing Citus extension files..."
rm -f  /usr/lib/postgresql/18/lib/citus*.so
rm -rf /usr/lib/postgresql/18/lib/bitcode/citus* /usr/lib/postgresql/18/lib/bitcode/columnar*
rm -f  /usr/share/postgresql/18/extension/citus* /usr/share/postgresql/18/extension/columnar*

echo "Removing the project copy, Python venvs, Kafka/ClickHouse/Grafana and the Citus source..."
rm -rf /root/eda /root/venv /root/citus /root/citus-*.log /root/run_all.log

echo "Removing apt packages added for the set-up (Java, Citus build tools)..."
DEBIAN_FRONTEND=noninteractive apt-get remove -y -qq openjdk-21-jre-headless postgresql-server-dev-18 libicu-dev \
  libcurl4-openssl-dev liblz4-dev libzstd-dev libssl-dev libkrb5-dev libselinux1-dev libxslt1-dev libpam0g-dev \
  libreadline-dev autoconf flex bison >/dev/null 2>&1
apt-get autoremove -y -qq >/dev/null 2>&1
echo "Done."
