"""Measures the real-time pipeline after a replay: end-to-end latency, ClickHouse query times, memory of the processes."""
import statistics, subprocess, time
from pathlib import Path
import clickhouse_connect
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
c = clickhouse_connect.get_client(host="127.0.0.1", port=8123)
q = lambda s: c.query(s).result_rows
rows = []
n, runs = q("SELECT count(), uniqExact(replay_run_id) FROM food.inspection_events")[0]
lat = q("SELECT round(avg(dateDiff('millisecond', emitted_at, written_at))), round(quantile(0.5)(dateDiff('millisecond', emitted_at, written_at))), "
        "round(quantile(0.95)(dateDiff('millisecond', emitted_at, written_at))), max(dateDiff('millisecond', emitted_at, written_at)) FROM food.inspection_events")[0]
span = q("SELECT dateDiff('millisecond', min(emitted_at), max(emitted_at)) / 1000 FROM food.inspection_events")[0][0]
rows += [("valid events stored", n), ("rejected test events", q("SELECT count() FROM food.invalid_events")[0][0]),
         ("sustained throughput (events/s, producer to ClickHouse)", round(n / span, 1)), ("latency avg (ms), emit -> ClickHouse", lat[0]),
         ("latency median (ms)", lat[1]), ("latency p95 (ms)", lat[2]), ("latency max (ms)", lat[3])]
QUERIES = {"KPI totals (window_agg, 6 stats)": "SELECT sum(inspections), sumIf(inspections, result_group='Fail'), sumIf(inspections, result_group='Pass'), sum(violations), sum(high_violation_inspections) FROM food.window_agg FINAL",
           "top facility types (events)": "SELECT facility_type, count() c FROM food.inspection_events GROUP BY facility_type ORDER BY c DESC LIMIT 8",
           "area alerts by ZIP (events)": "SELECT zip, count(), sum(is_fail), round(100*sum(is_fail)/count(),1) FROM food.inspection_events GROUP BY zip HAVING count() >= 5 ORDER BY 4 DESC LIMIT 12",
           "risk distribution (window_agg)": "SELECT risk_group, sum(inspections) FROM food.window_agg FINAL GROUP BY risk_group"}
for name, sql in QUERIES.items():
    ts = []
    for _ in range(9):
        t0 = time.perf_counter(); c.query(sql); ts.append((time.perf_counter() - t0) * 1000)
    rows.append((f"ClickHouse query: {name} (median ms)", round(statistics.median(ts), 1)))
ps = subprocess.run("ps -eo rss,args", shell=True, capture_output=True, text=True).stdout.splitlines()
for label, pat in [("Kafka broker", "kafka.Kafka"), ("ClickHouse server", "clickhouse server"), ("Spark streaming job (python + JVM)", "spark_stream.py"), ("Grafana", "grafana server")]:
    rss = sum(int(l.split(None, 1)[0]) for l in ps if pat in l and "grep" not in l)
    if pat == "spark_stream.py":
        rss += sum(int(l.split(None, 1)[0]) for l in ps if "org.apache.spark.deploy.SparkSubmit" in l or "SparkSubmit" in l)
    rows.append((f"memory (RSS, MB): {label}", round(rss / 1024)))
out = pd.DataFrame(rows, columns=["metric", "value"])
out.to_csv(ROOT / "results" / "streaming_metrics.csv", index=False)
print(out.to_string(index=False))
