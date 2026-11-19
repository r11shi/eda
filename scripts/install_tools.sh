#!/usr/bin/env bash
# Downloads Apache Kafka, ClickHouse and Grafana into runtime/tools and verifies the published checksums.
# (PostgreSQL 16 comes from the OS package; PySpark is installed with pip into runtime/venv-spark.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; T="$ROOT/runtime/tools"; mkdir -p "$T"; cd "$T"

KAFKA=3.9.0; CH=26.3.19.3; GRAFANA=11.3.0

if [ ! -d "kafka_2.13-$KAFKA" ]; then
  curl -fsSL -o kafka.tgz "https://archive.apache.org/dist/kafka/$KAFKA/kafka_2.13-$KAFKA.tgz"
  curl -fsSL -o kafka.tgz.sha512 "https://archive.apache.org/dist/kafka/$KAFKA/kafka_2.13-$KAFKA.tgz.sha512"
  python3 - <<PY
import hashlib,re
exp=re.sub(r"\s+","",open("kafka.tgz.sha512").read().split(":")[-1]).lower()
got=hashlib.sha512(open("kafka.tgz","rb").read()).hexdigest()
assert exp==got,"Kafka checksum mismatch"; print("Kafka sha512 verified")
PY
  tar xzf kafka.tgz
fi
if [ ! -x "clickhouse/usr/bin/clickhouse" ]; then
  mkdir -p clickhouse
  curl -fsSL -o ch.tgz "https://packages.clickhouse.com/tgz/lts/clickhouse-common-static-$CH-amd64.tgz"
  curl -fsSL -o ch.tgz.sha512 "https://packages.clickhouse.com/tgz/lts/clickhouse-common-static-$CH-amd64.tgz.sha512"
  python3 - <<PY
import hashlib
exp=open("ch.tgz.sha512").read().split()[0].lower()
got=hashlib.sha512(open("ch.tgz","rb").read()).hexdigest()
assert exp==got,"ClickHouse checksum mismatch"; print("ClickHouse sha512 verified")
PY
  tar xzf ch.tgz -C clickhouse --strip-components=1
fi
if [ ! -d "grafana-v$GRAFANA" ]; then
  curl -fsSL -o grafana.tgz "https://dl.grafana.com/oss/release/grafana-$GRAFANA.linux-amd64.tar.gz"
  curl -fsSL -o grafana.tgz.sha256 "https://dl.grafana.com/oss/release/grafana-$GRAFANA.linux-amd64.tar.gz.sha256"
  python3 - <<PY
import hashlib
exp=open("grafana.tgz.sha256").read().split()[0].lower()
got=hashlib.sha256(open("grafana.tgz","rb").read()).hexdigest()
assert exp==got,"Grafana checksum mismatch"; print("Grafana sha256 verified")
PY
  tar xzf grafana.tgz
fi
rm -f kafka.tgz ch.tgz grafana.tgz
ls "$T"
