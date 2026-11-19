"""Part D, step 1 (runs on plain PostgreSQL): distribution-key analysis and the CENTRALIZED side of the scaling experiment.

Volumes above the real size (61,737 completed inspections) are produced by SYNTHETIC SCALE-UP: bootstrap resampling of the real fact rows
(same facility / date / location mix, new surrogate ids). They measure query performance only; they are not new inspections and are never used for analysis.
"""
import statistics, time
from pathlib import Path
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
from config import DSN
VOLUMES = [61737, 100_000, 500_000, 1_000_000, 2_000_000]
conn = psycopg2.connect(DSN); conn.autocommit = True; cur = conn.cursor()

# ------------------------------------------------------------------ 1. distribution-key candidates (shard simulation with PostgreSQL's hashint4, the hash Citus uses for integer keys)
rows = []
for key in ["facility_key", "location_key", "date_key"]:
    cur.execute(f"SELECT count(DISTINCT {key}), max(c)::float / sum(c) FROM (SELECT {key}, count(*) c FROM dw.fact_inspection GROUP BY 1) t")
    distinct, top_share = cur.fetchone()
    cur.execute(f"""SELECT count(*), avg(n), stddev_pop(n), max(n), min(n) FROM (
                      SELECT ((hashint4({key})::bigint + 2147483648) * 32 / 4294967296)::int AS shard, count(*) AS n FROM dw.fact_inspection GROUP BY 1) s""")
    shards, mean, std, mx, mn = cur.fetchone()
    cur.execute(f"""SELECT count(*), avg(n), stddev_pop(n), max(n) FROM (
                      SELECT ((hashint4({key})::bigint + 2147483648) * 2 / 4294967296)::int AS worker, count(*) AS n FROM dw.fact_inspection GROUP BY 1) s""")
    w, wmean, wstd, wmax = cur.fetchone()
    rows.append({"candidate_key": key, "distinct_values": distinct, "largest_single_value_share_%": round(100 * top_share, 2), "non_empty_shards_of_32": shards,
                 "rows_per_shard_mean": round(float(mean)), "rows_per_shard_max": mx, "shard_skew_max_over_mean": round(float(mx) / float(mean), 2),
                 "shard_cv": round(float(std) / float(mean), 3), "worker_split_max_over_mean_(2_workers)": round(float(wmax) / float(wmean), 3)})
pd.DataFrame(rows).to_csv(ROOT / "results" / "distribution_key_analysis.csv", index=False)
print(pd.DataFrame(rows).to_string(index=False))

# ------------------------------------------------------------------ 2. synthetic scale-up tables
cur.execute("DROP SCHEMA IF EXISTS bench CASCADE; CREATE SCHEMA bench;")
cur.execute("""CREATE TABLE bench.src AS SELECT row_number() OVER (ORDER BY inspection_key)::int AS rn, date_key, facility_key, inspection_type_key, result_key, location_key,
                      violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag FROM dw.fact_inspection""")
cur.execute("SELECT count(*) FROM bench.src"); n_src = cur.fetchone()[0]
cur.execute(f"""CREATE TABLE bench.fact_max AS
                SELECT g AS inspection_key, s.date_key, s.facility_key, s.inspection_type_key, s.result_key, s.location_key, s.violation_count, s.fail_count, s.pass_count, s.conditional_pass_count, s.high_violation_flag
                  FROM (SELECT g, 1 + floor(random() * {n_src})::int AS rn FROM generate_series(1, {max(VOLUMES)}) g) x JOIN bench.src s ON s.rn = x.rn""")
QUERIES = {
 "Q1 results by facility type": "SELECT fa.facility_type, r.result_group, count(*) FROM {f} f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key) GROUP BY 1, 2",
 "Q2 failure rate by area": "SELECT l.geographic_area_group, 100.0 * sum(f.fail_count) / count(*) FROM {f} f JOIN dw.dim_location l USING (location_key) GROUP BY 1",
 "Q3 monthly inspections": "SELECT d.year, d.month, count(*) FROM {f} f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2",
 "Q4 violations by risk": "SELECT fa.risk_group, sum(f.violation_count), avg(f.violation_count) FROM {f} f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1",
 "Q5 facility x year aggregation": "SELECT f.facility_key, d.year, count(*), sum(f.fail_count) FROM {f} f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2",
}
out = []
for n in VOLUMES:
    table = f"bench.fact_{n}"
    if n == n_src:
        cur.execute(f"CREATE TABLE {table} AS SELECT inspection_key::bigint, date_key, facility_key, inspection_type_key, result_key, location_key, violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag FROM dw.fact_inspection")
    else:
        cur.execute(f"CREATE TABLE {table} AS SELECT * FROM bench.fact_max WHERE inspection_key <= {n}")
    for c in ["date_key", "facility_key", "location_key", "result_key"]:
        cur.execute(f"CREATE INDEX ON {table} ({c})")
    cur.execute(f"ANALYZE {table}")
    for name, sql in QUERIES.items():
        q = sql.format(f=table)
        cur.execute(q); cur.fetchall()                            # warm-up
        ts = []
        for _ in range(5):
            t0 = time.perf_counter(); cur.execute(q); cur.fetchall(); ts.append((time.perf_counter() - t0) * 1000)
        out.append({"query": name, "rows": n, "centralized_ms": round(statistics.median(ts), 1)})
        print(f"{name:34s} {n:>9,d} rows  {statistics.median(ts):9.1f} ms")
    cur.execute(f"SELECT pg_total_relation_size('{table}')"); print(f"   {table}: {cur.fetchone()[0] / 1e6:.0f} MB with indexes")
pd.DataFrame(out).to_csv(ROOT / "results" / "centralized_scaling.csv", index=False)
cur.execute("DROP TABLE bench.fact_max; DROP TABLE bench.src")
