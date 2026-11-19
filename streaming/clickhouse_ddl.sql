-- Real-time warehouse (ClickHouse). Written by the Spark Structured Streaming job; read by Grafana.
CREATE DATABASE IF NOT EXISTS food;

-- one row per validated inspection event (the "event" store)
CREATE TABLE IF NOT EXISTS food.inspection_events (
    event_id String, replay_run_id String, inspection_id UInt64, event_date Date,
    emitted_at DateTime64(3, 'UTC'), ingest_ts DateTime64(3, 'UTC'), written_at DateTime64(3, 'UTC'),
    license_number String, dba_name String, facility_type LowCardinality(String), facility_group LowCardinality(String),
    risk_group LowCardinality(String), inspection_type_group LowCardinality(String), result String, result_group LowCardinality(String),
    violation_count Nullable(UInt16), high_violation_flag UInt8, zip String, area_group LowCardinality(String),
    is_fail UInt8, is_pass UInt8, is_conditional UInt8
) ENGINE = MergeTree ORDER BY (ingest_ts, inspection_id);

-- events rejected by the validation rules (dead-letter table)
CREATE TABLE IF NOT EXISTS food.invalid_events (ingest_ts DateTime64(3, 'UTC'), reason String, raw String) ENGINE = MergeTree ORDER BY ingest_ts;

-- 10-second processing-time windows (Spark windowed aggregation, update mode => ReplacingMergeTree keeps the newest version)
CREATE TABLE IF NOT EXISTS food.window_agg (
    window_start DateTime('UTC'), facility_group LowCardinality(String), risk_group LowCardinality(String),
    area_group LowCardinality(String), result_group LowCardinality(String),
    inspections UInt32, violations UInt32, high_violation_inspections UInt32, updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (window_start, facility_group, risk_group, area_group, result_group);

-- event-time aggregation: one tumbling window per inspection DAY, with a 1-day watermark
CREATE TABLE IF NOT EXISTS food.daily_event_time_agg (
    event_day Date, result_group LowCardinality(String), inspections UInt32, updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (event_day, result_group);
