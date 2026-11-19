"""Part D, step 2: the DISTRIBUTED side of the scaling experiment on a 3-node Citus cluster (coordinator + 2 workers on one machine),
compared with the centralized PostgreSQL node measured in the same session.

Facts are distributed by FacilityKey (the key chosen in docs/distributed_warehouse.md); the five small dimensions are Citus REFERENCE tables
(a full copy on every node), so every join is local. Volumes above 61,737 rows are the synthetic scale-up tables made by etl/distributed_baseline.py.
"""
import io, statistics, tempfile, time, subprocess
from decimal import Decimal
from pathlib import Path
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
from config import DSN as MAIN
import os
CITUS = os.environ.get("CITUS_DSN", "host=localhost port=5440 dbname=foodsafety_citus user=postgres")
VOLUMES = [61737, 100_000, 500_000, 1_000_000, 2_000_000]
KEY_TEST_VOLUME = 1_000_000
FACT_COLS = "inspection_key bigint, date_key int, facility_key int, inspection_type_key int, result_key int, location_key int, violation_count smallint, fail_count smallint, pass_count smallint, conditional_pass_count smallint, high_violation_flag smallint"
QUERIES = {
 "Q1 results by facility type": "SELECT fa.facility_type, r.result_group, count(*) FROM {f} f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key) GROUP BY 1, 2",
 "Q2 failure rate by area": "SELECT l.geographic_area_group, 100.0 * sum(f.fail_count) / count(*) FROM {f} f JOIN dw.dim_location l USING (location_key) GROUP BY 1",
 "Q3 monthly inspections": "SELECT d.year, d.month, count(*) FROM {f} f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2",
 "Q4 violations by risk": "SELECT fa.risk_group, sum(f.violation_count), avg(f.violation_count) FROM {f} f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1",
 "Q5 facility x year aggregation": "SELECT f.facility_key, d.year, count(*), sum(f.fail_count) FROM {f} f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2",
}
main = psycopg2.connect(MAIN); main.autocommit = True; mc = main.cursor()
cit = psycopg2.connect(CITUS); cit.autocommit = True; cc = cit.cursor()


def bench(cur, sql, runs=5):
    cur.execute(sql); res = cur.fetchall()                      # warm-up (also returns the result for the correctness check)
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter(); cur.execute(sql); cur.fetchall(); ts.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(ts), 1), res


def norm(rows):
    return sorted(tuple(round(float(v), 4) if isinstance(v, (Decimal, float)) else v for v in r) for r in rows)


def copy_table(src_cur, query, dst_cur, target):
    with tempfile.TemporaryFile() as f:
        buf = io.TextIOWrapper(f, encoding="utf-8")
        src_cur.copy_expert(f"COPY ({query}) TO STDOUT WITH CSV", buf); buf.flush(); f.seek(0)
        dst_cur.copy_expert(f"COPY {target} FROM STDIN WITH CSV", io.TextIOWrapper(f, encoding="utf-8"))


# ------------------------------------------------------------------ cluster set-up: reference tables for the dimensions
cc.execute("DROP SCHEMA IF EXISTS bench CASCADE; DROP SCHEMA IF EXISTS dw CASCADE; CREATE SCHEMA dw; CREATE SCHEMA bench;")
cc.execute("""CREATE TABLE dw.dim_date (date_key int PRIMARY KEY, year smallint, month smallint);
              CREATE TABLE dw.dim_facility (facility_key int PRIMARY KEY, facility_type text, facility_group text, risk_group text);
              CREATE TABLE dw.dim_result (result_key int PRIMARY KEY, result_group text);
              CREATE TABLE dw.dim_location (location_key int PRIMARY KEY, geographic_area_group text);""")
for t in ["dim_date", "dim_facility", "dim_result", "dim_location"]:
    cc.execute(f"SELECT create_reference_table('dw.{t}')")
copy_table(mc, "SELECT date_key, year, month FROM dw.dim_date", cc, "dw.dim_date")
copy_table(mc, "SELECT facility_key, facility_type, facility_group, risk_group FROM dw.dim_facility", cc, "dw.dim_facility")
copy_table(mc, "SELECT result_key, result_group FROM dw.dim_result", cc, "dw.dim_result")
copy_table(mc, "SELECT location_key, geographic_area_group FROM dw.dim_location", cc, "dw.dim_location")
print("reference tables loaded")


def make_distributed(n, key):
    name = f"bench.fact_{n}_{key}"
    cc.execute(f"CREATE TABLE {name} ({FACT_COLS})")
    cc.execute(f"SELECT create_distributed_table('{name}', '{key}')")
    t0 = time.perf_counter()
    copy_table(mc, f"SELECT inspection_key, date_key, facility_key, inspection_type_key, result_key, location_key, violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag FROM bench.fact_{n}", cc, name)
    for c in ["date_key", "facility_key", "location_key", "result_key"]:
        cc.execute(f"CREATE INDEX ON {name} ({c})")
    cc.execute(f"ANALYZE {name}")
    return name, round(time.perf_counter() - t0, 1)


rows, load_rows = [], []
for n in VOLUMES:
    name, load_s = make_distributed(n, "facility_key"); load_rows.append({"rows": n, "distribution_key": "facility_key", "load_and_index_s": load_s})
    for qname, sql in QUERIES.items():
        c_ms, c_res = bench(mc, sql.format(f=f"bench.fact_{n}"))
        d_ms, d_res = bench(cc, sql.format(f=name))
        rows.append({"query": qname, "rows": n, "centralized_ms": c_ms, "distributed_ms": d_ms, "distributed_over_centralized": round(d_ms / c_ms, 2), "results_identical": norm(c_res) == norm(d_res)})
        print(f"{qname:34s} {n:>9,d}  central {c_ms:8.1f} ms  citus {d_ms:8.1f} ms  identical={rows[-1]['results_identical']}", flush=True)
scal = pd.DataFrame(rows)
scal.to_csv(ROOT / "results" / "distributed_scaling.csv", index=False)
scal[["query", "rows", "centralized_ms"]].to_csv(ROOT / "results" / "centralized_scaling.csv", index=False)     # re-measured in this session
pd.DataFrame(load_rows).to_csv(ROOT / "results" / "citus_load_times.csv", index=False)

# ------------------------------------------------------------------ which distribution key? same queries at 1,000,000 rows for each candidate
key_rows = []
for key in ["facility_key", "location_key", "date_key"]:
    name = f"bench.fact_{KEY_TEST_VOLUME}_{key}"
    if key != "facility_key":
        name, _ = make_distributed(KEY_TEST_VOLUME, key)
    for qname, sql in QUERIES.items():
        d_ms, _ = bench(cc, sql.format(f=name)); key_rows.append({"query": qname, "distribution_key": key, "distributed_ms": d_ms})
    cc.execute(f"""SELECT s.nodeport, count(*), sum(s.shard_size), max(s.shard_size), min(s.shard_size) FROM citus_shards s WHERE s.table_name = '{name}'::regclass GROUP BY 1 ORDER BY 1""")
    for port, shards, tot, mx, mn in cc.fetchall():
        key_rows.append({"query": "SHARD SIZES", "distribution_key": key, "distributed_ms": None, "worker_port": port, "shards": shards, "bytes_total": int(tot), "bytes_largest_shard": int(mx), "bytes_smallest_shard": int(mn)})
    cc.execute(f"SELECT max(shard_size)::float / avg(shard_size) FROM citus_shards WHERE table_name = '{name}'::regclass")
    key_rows.append({"query": "SHARD SKEW max/mean", "distribution_key": key, "distributed_ms": float(cc.fetchone()[0])})
pd.DataFrame(key_rows).to_csv(ROOT / "results" / "distribution_key_experiment.csv", index=False)

# ------------------------------------------------------------------ how the queries are executed (parallel plans) and resources
with open(ROOT / "results" / "citus_explain.txt", "w") as f:
    for qname in ["Q1 results by facility type", "Q5 facility x year aggregation"]:
        cc.execute("EXPLAIN (COSTS OFF) " + QUERIES[qname].format(f=f"bench.fact_{KEY_TEST_VOLUME}_facility_key"))
        f.write(f"--- {qname} (distributed by facility_key, {KEY_TEST_VOLUME:,} rows)\n" + "\n".join(r[0] for r in cc.fetchall()) + "\n\n")
ps = subprocess.run("ps -eo rss,args", shell=True, capture_output=True, text=True).stdout.splitlines()
res = {name: round(sum(int(l.split(None, 1)[0]) for l in ps if f"16/{name}" in l) / 1024) for name in ["main", "coord", "worker1", "worker2"]}
pd.DataFrame([{"cluster": k, "resident_memory_MB": v} for k, v in res.items()]).to_csv(ROOT / "results" / "citus_resources.csv", index=False)
print("resident memory (MB):", res)
print(scal.to_string(index=False))
