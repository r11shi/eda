#!/usr/bin/env bash
# Starts the real-time stack on one machine: ClickHouse -> Kafka (KRaft) -> Spark Structured Streaming -> Grafana.
# Afterwards run the replay:   python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150
# Dashboard: http://127.0.0.1:3000/d/food-safety-rt   (no login needed, viewer access)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; T="$ROOT/runtime/tools"; L="$ROOT/runtime/logs"; mkdir -p "$L" "$ROOT/runtime/ch-data" "$ROOT/runtime/kafka-data"
[ -x "$T/clickhouse/usr/bin/clickhouse" ] || "$ROOT/scripts/install_tools.sh"
[ -x "$ROOT/runtime/venv-spark/bin/python" ] || { python3 -m venv "$ROOT/runtime/venv-spark"; "$ROOT/runtime/venv-spark/bin/pip" install -q pyspark==4.0.1 clickhouse-connect pandas pyarrow; }

# 1. ClickHouse
if ! curl -sf http://127.0.0.1:8123/ping >/dev/null; then
  ( cd "$ROOT/runtime"; exec nohup "$T/clickhouse/usr/bin/clickhouse" server -- --path="$ROOT/runtime/ch-data/" --tcp_port=9000 --http_port=8123 --listen_host=127.0.0.1 \
      --logger.log="$L/clickhouse.log" --logger.errorlog="$L/clickhouse.err.log" ) > "$L/clickhouse.stdout" 2>&1 &
  until curl -sf http://127.0.0.1:8123/ping >/dev/null; do sleep 1; done
fi
python3 "$ROOT/streaming/init_clickhouse.py"

# 2. Kafka (single broker, KRaft mode, no ZooKeeper)
K="$T/kafka_2.13-3.9.0"; CFG="$ROOT/runtime/kafka-server.properties"
if [ ! -f "$CFG" ]; then
  cp "$K/config/kraft/server.properties" "$CFG"
  sed -i "s#^log.dirs=.*#log.dirs=$ROOT/runtime/kafka-data#; s/^num.partitions=.*/num.partitions=3/" "$CFG"
  "$K/bin/kafka-storage.sh" format -t "$("$K/bin/kafka-storage.sh" random-uuid | tail -1)" -c "$CFG" >/dev/null
fi
if ! "$K/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
  ( export KAFKA_HEAP_OPTS="-Xmx768m -Xms256m"; exec nohup "$K/bin/kafka-server-start.sh" "$CFG" ) > "$L/kafka.stdout" 2>&1 &
  until "$K/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do sleep 2; done
fi
"$K/bin/kafka-topics.sh" --bootstrap-server localhost:9092 --create --if-not-exists --topic food_inspections --partitions 3 --replication-factor 1 2>&1 | { grep -v -E "Picked up|WARNING" || true; }

# 3. Spark Structured Streaming (reads only NEW events: startingOffsets=latest)
( cd "$ROOT"; exec nohup "$ROOT/runtime/venv-spark/bin/python" streaming/spark_stream.py --fresh --starting-offsets latest ) > "$L/spark.log" 2>&1 &
until grep -q "Streaming queries started" "$L/spark.log" 2>/dev/null; do sleep 2; done

# 4. Grafana
"$ROOT/scripts/start_grafana.sh" >/dev/null
echo "Real-time stack is up. Spark needs ~20 s to settle before the replay."
