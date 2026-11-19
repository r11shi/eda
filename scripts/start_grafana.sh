#!/usr/bin/env bash
# Starts Grafana with the ClickHouse datasource and the real-time dashboard provisioned (anonymous viewer access, port 3000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; G="$ROOT/runtime/tools/grafana-v11.3.0"; R="$ROOT/runtime/grafana"
mkdir -p "$R"/{data,logs,plugins,provisioning/datasources,provisioning/dashboards,dashboards}
cp "$ROOT/streaming/grafana/datasource.yml" "$R/provisioning/datasources/clickhouse.yml"
cp "$ROOT/streaming/grafana/food_safety_realtime_dashboard.json" "$R/dashboards/"
cat > "$R/provisioning/dashboards/dashboards.yml" <<YML
apiVersion: 1
providers:
  - name: food-safety
    type: file
    options: {path: $R/dashboards}
YML
cat > "$R/custom.ini" <<INI
[paths]
data = $R/data
logs = $R/logs
plugins = $R/plugins
provisioning = $R/provisioning
[server]
http_addr = 127.0.0.1
http_port = 3000
[auth.anonymous]
enabled = true
org_role = Viewer
[analytics]
reporting_enabled = false
check_for_updates = false
INI
( cd "$G"; exec nohup ./bin/grafana server --homepath "$G" --config "$R/custom.ini" ) > "$ROOT/runtime/logs/grafana.stdout" 2>&1 &
sleep 12; curl -s http://127.0.0.1:3000/api/health
