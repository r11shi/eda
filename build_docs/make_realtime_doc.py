"""Writes docs/realtime_warehouse.md (Part E) using the measured values in results/streaming_metrics.csv."""
from pathlib import Path
import json
import pandas as pd
import clickhouse_connect

ROOT = Path(__file__).resolve().parents[1]
m = pd.read_csv(ROOT / "results" / "streaming_metrics.csv").set_index("metric")["value"]
g = lambda k: m[k]
# a REAL event taken from the ClickHouse event table (re-created in the JSON format of the topic)
r = clickhouse_connect.get_client(host="127.0.0.1", port=8123).query(
    "SELECT event_id, replay_run_id, toString(emitted_at), toString(event_date), inspection_id, license_number, dba_name, facility_type, facility_group, risk_group, "
    "inspection_type_group, result, result_group, violation_count, zip, area_group FROM food.inspection_events WHERE violation_count IS NOT NULL ORDER BY inspection_id LIMIT 1").result_rows[0]
keys = ["event_id", "replay_run_id", "emitted_at", "event_time", "inspection_id", "license_number", "dba_name", "facility_type", "facility_group", "risk_group",
        "inspection_type_group", "result", "result_group", "violation_count", "zip", "area_group"]
example = json.dumps({"event_id": r[0], "source_mode": "REPLAY_SIMULATION", **dict(zip(keys[1:], r[1:]))}, indent=1)
doc = f"""# Part E: Real-Time / Streaming Data Warehouse

**This is a replay simulation.** The official Chicago dataset is a historical file, not a live feed. Completed inspections are replayed in date order, at an accelerated speed, as simulated live events. Every event carries `source_mode = "REPLAY_SIMULATION"` and the Grafana dashboard says so in its header.

## Architecture
`Historical records (curated CSV)  >  Python producer  >  Kafka topic  >  Spark Structured Streaming  >  ClickHouse  >  Grafana`

| Component | Version / setup | File |
|---|---|---|
| Producer | kafka-python, replays completed inspections in chronological order at a chosen speed | `streaming/producer.py` |
| Kafka | Apache Kafka 3.9.0, one broker in KRaft mode, topic `food_inspections`, 3 partitions | `scripts/start_realtime_stack.sh` |
| Stream processing | PySpark 4.0.1 (Spark Structured Streaming, local mode, 2 cores), 2-second micro-batches | `streaming/spark_stream.py` |
| Real-time store | ClickHouse 26.3 LTS, database `food` | `streaming/clickhouse_ddl.sql` |
| Dashboard | Grafana 11.3 with the ClickHouse datasource plugin | `streaming/grafana/` |

## Event design
* **Topic:** `food_inspections`. **Key:** `inspection_id` (so one inspection always goes to the same partition). **Replay speed:** `--rate` events per second (80 per second in the test below).
* **Event timestamp:** `event_time` is the inspection date. The source has no time of day, so the time of day is NOT invented. `emitted_at` is the producer's wall-clock time and Kafka adds its own ingest timestamp.
* **Minimal operational payload** (derived from the source record, no free-text violations). Below is a real event taken from the ClickHouse event table:

```json
{example}
```
* **Validation rules** (first failing rule is stored in `food.invalid_events`): valid JSON; `inspection_id` present and > 0; `event_time` is a date; `result_group` in (Pass, Conditional Pass, Fail); `risk_group` in the documented list; `violation_count` is null or between 0 and 100; `emitted_at` present.
* To exercise the rules the producer can inject labelled malformed test events (`--bad-every N`). In the test run it injected 24: 8 not valid JSON, 8 with an invalid result group and 8 with a negative violation count. All 24 were rejected and none reached the event table.

## Required streaming operations
| Operation | Implemented in `spark_stream.py` |
|---|---|
| Parse and validate JSON | `from_json` with an explicit schema + the validation rules above; rejected events go to `food.invalid_events` |
| Create derived measures | `is_fail`, `is_pass`, `is_conditional`, `high_violation_flag` (violation count >= 6, same rule as the batch warehouse) |
| Event-time processing | one-day tumbling windows on `event_time` with a 1-day watermark, written to `food.daily_event_time_agg` |
| Aggregate over short windows | 10-second windows on ingest time by facility group, risk, area and result, written to `food.window_agg` (update mode; `ReplacingMergeTree` keeps the newest version of each window) |
| Write to ClickHouse | `foreachBatch` writers for the event table, the invalid table and both aggregate tables |
| Refresh Grafana continuously | dashboard refresh every 5 seconds |
| Live replay during evaluation | `scripts/start_realtime_stack.sh`, then `python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150` |

## Required KPIs on the dashboard
![Grafana real-time dashboard](../results/screenshots/grafana_realtime_dashboard.png)

| KPI | Panel and source |
|---|---|
| Inspections / minute during replay | time series (10-second windows x 6) and the *Peak inspections / minute* tile, from `window_agg` |
| Fails, Passes | stat tiles from `window_agg` |
| Violations, High-violation inspections | stat tiles (sum of `violations`, count of `high_violation_flag = 1`) |
| Top facility types | bar gauge from `inspection_events` |
| Risk distribution | donut chart from `window_agg` |
| Area alerts | table by ZIP: at least 5 inspections and a fail rate of 40% or more (about twice the average) is marked ALERT |

The dashboard JSON is `streaming/grafana/food_safety_realtime_dashboard.json` (provisioned automatically).

## Measured results (replay of Q4 2025: 3,647 completed inspections at 80 events per second)
| Measure | Value |
|---|---|
| Valid events stored / events replayed | {int(g('valid events stored')):,} / 3,647 (each inspection exactly once) |
| Sum of the 10-second windows and of the event-time days | 3,647 and 3,647 (both reconcile with the event table) |
| Rejected injected test events | {int(g('rejected test events'))} of 24 |
| Peak rate shown on the dashboard | 4,800 inspections per minute (80 per second x 60) |
| End-to-end latency, emit to ClickHouse | average {g('latency avg (ms), emit -> ClickHouse'):.0f} ms, median {g('latency median (ms)'):.0f} ms, p95 {g('latency p95 (ms)'):.0f} ms, max {g('latency max (ms)'):.0f} ms |
| ClickHouse dashboard queries (median of 9) | {g('ClickHouse query: KPI totals (window_agg, 6 stats) (median ms)')}, {g('ClickHouse query: top facility types (events) (median ms)')}, {g('ClickHouse query: area alerts by ZIP (events) (median ms)')} and {g('ClickHouse query: risk distribution (window_agg) (median ms)')} ms |
| Memory (resident) | Kafka {g('memory (RSS, MB): Kafka broker'):.0f} MB, ClickHouse {g('memory (RSS, MB): ClickHouse server'):.0f} MB, Spark job {g('memory (RSS, MB): Spark streaming job (python + JVM)'):.0f} MB, Grafana {g('memory (RSS, MB): Grafana'):.0f} MB |

The latency is dominated by the 2-second Spark micro-batch trigger. The test ran every component on one 4-core machine, so the figures show how the pipeline behaves, not the capacity of a production cluster. A throughput limit test was not part of this project.

## How to run
```bash
scripts/install_tools.sh            # downloads Kafka, ClickHouse and Grafana and verifies their checksums
scripts/start_realtime_stack.sh     # ClickHouse, Kafka, Spark streaming job, Grafana
python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150
# open http://127.0.0.1:3000/d/food-safety-rt   (set the time range to the last 5-10 minutes)
```
"""
(ROOT / "docs" / "realtime_warehouse.md").write_text(doc)
print("written docs/realtime_warehouse.md")
