"""Writes the Grafana dashboard JSON (real-time food-safety KPIs read from ClickHouse)."""
import json
from pathlib import Path

DS = {"type": "grafana-clickhouse-datasource", "uid": "clickhouse"}
TABLE, TIMESERIES = 0, 2


def target(sql, fmt=TABLE, ref="A"):
    return {"datasource": DS, "editorType": "sql", "format": fmt, "queryType": "timeseries" if fmt == TIMESERIES else "table",
            "rawSql": sql, "refId": ref, "pluginVersion": "4.23.3"}


def stat(pid, title, sql, x, y, w=4, h=4, color="blue", unit="none", desc=""):
    return {"id": pid, "type": "stat", "title": title, "description": desc, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [target(sql)], "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "background", "graphMode": "none", "textMode": "value"},
            "fieldConfig": {"defaults": {"color": {"mode": "fixed", "fixedColor": color}, "unit": unit, "decimals": 0}, "overrides": []}}


W = "FROM food.window_agg FINAL WHERE $__timeFilter(window_start)"
panels = [
    {"id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3}, "options": {"mode": "markdown", "content":
        "## Food Safety: real-time inspection monitor  (REPLAY SIMULATION)\n**The official Chicago dataset is a historical file, not a live feed.** Completed inspections are replayed in date order through "
        "Kafka -> Spark Structured Streaming -> ClickHouse at an accelerated speed. All figures below describe the replay, not today's inspections."}},
    stat(2, "Inspections (replay, in range)", f"SELECT sum(inspections) {W}", 0, 3, color="blue"),
    stat(3, "Peak inspections / minute", f"SELECT max(c) * 6 FROM (SELECT window_start, sum(inspections) c {W} GROUP BY window_start)", 4, 3, color="purple",
         desc="Highest 10-second window, expressed as a per-minute rate (x 6)"),
    stat(4, "Fails", f"SELECT sum(inspections) {W} AND result_group = 'Fail'", 8, 3, color="red"),
    stat(5, "Passes", f"SELECT sum(inspections) {W} AND result_group = 'Pass'", 12, 3, color="green"),
    stat(6, "Violations cited", f"SELECT sum(violations) {W}", 16, 3, color="orange"),
    stat(7, "High-violation inspections (6+)", f"SELECT sum(high_violation_inspections) {W}", 20, 3, color="dark-red"),
    {"id": 8, "type": "timeseries", "title": "Inspections per minute (rate from 10-second windows) by result", "datasource": DS, "gridPos": {"x": 0, "y": 7, "w": 12, "h": 8},
     "targets": [target(f"SELECT window_start AS time, result_group, sum(inspections) * 6 AS inspections_per_minute {W} GROUP BY time, result_group ORDER BY time", TIMESERIES)],
     "fieldConfig": {"defaults": {"custom": {"drawStyle": "bars", "stacking": {"mode": "normal"}, "fillOpacity": 70}}, "overrides": []}},
    {"id": 9, "type": "bargauge", "title": "Top facility types", "datasource": DS, "gridPos": {"x": 12, "y": 7, "w": 6, "h": 8},
     "targets": [target("SELECT facility_type, count() AS inspections FROM food.inspection_events WHERE $__timeFilter(ingest_ts) GROUP BY facility_type ORDER BY inspections DESC LIMIT 8")],
     "options": {"orientation": "horizontal", "displayMode": "gradient", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": True}}},
    {"id": 10, "type": "piechart", "title": "Risk distribution", "datasource": DS, "gridPos": {"x": 18, "y": 7, "w": 6, "h": 8},
     "targets": [target(f"SELECT risk_group, sum(inspections) AS inspections {W} GROUP BY risk_group")],
     "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": True}, "pieType": "donut", "legend": {"displayMode": "table", "placement": "right", "values": ["value", "percent"]}}},
    {"id": 11, "type": "table", "title": "Area alerts: ZIP codes with at least 5 inspections and a fail rate of 40% or more (about twice the average)", "datasource": DS,
     "gridPos": {"x": 0, "y": 15, "w": 14, "h": 8},
     "targets": [target("SELECT zip AS ZIP, count() AS inspections, sum(is_fail) AS fails, round(100 * sum(is_fail) / count(), 1) AS fail_rate_pct, "
                        "if(count() >= 5 AND 100 * sum(is_fail) / count() >= 40, 'ALERT', 'ok') AS status "
                        "FROM food.inspection_events WHERE $__timeFilter(ingest_ts) GROUP BY zip HAVING count() >= 5 ORDER BY fail_rate_pct DESC LIMIT 12")],
     "fieldConfig": {"defaults": {}, "overrides": [{"matcher": {"id": "byName", "options": "status"}, "properties": [
         {"id": "mappings", "value": [{"type": "value", "options": {"ALERT": {"color": "red", "text": "ALERT"}, "ok": {"color": "green", "text": "ok"}}}]},
         {"id": "custom.cellOptions", "value": {"type": "color-background"}}]}]}},
    {"id": 12, "type": "table", "title": "Pipeline health: events, rejected events and end-to-end latency", "datasource": DS, "gridPos": {"x": 14, "y": 15, "w": 10, "h": 8},
     "targets": [target("SELECT 'valid events' AS metric, toString(count()) AS value FROM food.inspection_events WHERE $__timeFilter(ingest_ts) "
                        "UNION ALL SELECT 'rejected events (validation rules)', toString(count()) FROM food.invalid_events WHERE $__timeFilter(ingest_ts) "
                        "UNION ALL SELECT 'avg latency emit -> ClickHouse (ms)', toString(round(avg(dateDiff('millisecond', emitted_at, written_at)))) FROM food.inspection_events WHERE $__timeFilter(ingest_ts) "
                        "UNION ALL SELECT 'p95 latency (ms)', toString(round(quantile(0.95)(dateDiff('millisecond', emitted_at, written_at)))) FROM food.inspection_events WHERE $__timeFilter(ingest_ts)")]},
]
dashboard = {"uid": "food-safety-rt", "title": "Food Safety: Real-Time Inspection Monitor (replay simulation)", "tags": ["food-safety", "replay-simulation"], "timezone": "utc",
             "schemaVersion": 39, "version": 1, "refresh": "5s", "time": {"from": "now-15m", "to": "now"}, "panels": panels, "editable": True}
out = Path(__file__).with_name("food_safety_realtime_dashboard.json")
out.write_text(json.dumps(dashboard, indent=2))
print("wrote", out.name, "with", len(panels), "panels")
