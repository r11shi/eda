#!/usr/bin/env bash
# Starts Grafana with the ClickHouse datasource and the real-time dashboard (Part E) provisioned
# (anonymous viewer access, port 3000). It also serves the HTML business dashboard (Part F) at /public/fs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; G="$ROOT/runtime/tools/grafana-v11.3.0"; R="$ROOT/runtime/grafana"
mkdir -p "$R"/{data,logs,plugins,provisioning/datasources,provisioning/dashboards,dashboards} "$ROOT/runtime/logs"
# The ClickHouse datasource is a plugin, not part of the Grafana download
[ -d "$R/plugins/grafana-clickhouse-datasource" ] || \
  "$G/bin/grafana" cli --homepath "$G" --pluginsDir "$R/plugins" plugins install grafana-clickhouse-datasource >/dev/null
cp "$ROOT/streaming/grafana/datasource.yml" "$R/provisioning/datasources/clickhouse.yml"
rm -f "$R/provisioning/datasources/warehouses.yml"
rm -f "$R"/dashboards/*.json      # remove dashboards of older layouts
cp "$ROOT/streaming/grafana/food_safety_realtime_dashboard.json" "$R/dashboards/"
# The HTML business dashboard (Part F), served at http://localhost:3000/public/fs/food_safety_dashboard.html
rm -rf "$G/public/fs" && mkdir -p "$G/public/fs" && cp "$ROOT/dashboard/food_safety_dashboard.html" "$G/public/fs/"
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
[dashboards]
default_home_dashboard_path = $R/dashboards/food_safety_realtime_dashboard.json
[analytics]
reporting_enabled = false
check_for_updates = false
INI
( cd "$G"; exec nohup ./bin/grafana server --homepath "$G" --config "$R/custom.ini" ) > "$ROOT/runtime/logs/grafana.stdout" 2>&1 &
sleep 12; curl -s http://127.0.0.1:3000/api/health
