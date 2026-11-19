"""Runs the analytical SQL, records execution time (median of 7 runs) and saves the result sets.
Also demonstrates the effect of indexing on two selective queries."""
import re, statistics, time
from pathlib import Path
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
from config import DSN
out_dir = ROOT / "results" / "analytical_query_results"; out_dir.mkdir(parents=True, exist_ok=True)
conn = psycopg2.connect(DSN); conn.autocommit = True; cur = conn.cursor()
text = (ROOT / "sql" / "06_analytical_queries.sql").read_text()
blocks = re.split(r"^-- name: ", text, flags=re.M)[1:]
rows = []
for b in blocks:
    title, sql = b.split("\n", 1)
    key = title.split()[0]
    times = []
    for _ in range(7):
        t0 = time.perf_counter(); cur.execute(sql); res = cur.fetchall(); times.append((time.perf_counter() - t0) * 1000)
    cols = [c.name for c in cur.description]
    pd.DataFrame(res, columns=cols).to_csv(out_dir / f"{key}.csv", index=False)
    rows.append({"query": key, "description": title[len(key):].strip(), "result_rows": len(res), "median_ms": round(statistics.median(times), 1)})
    print(f"{key:5s} {len(res):5d} rows  {statistics.median(times):8.1f} ms  {title}")
pd.DataFrame(rows).to_csv(ROOT / "results" / "batch_query_timing.csv", index=False)

# ---- effect of indexing (selective queries on the fact table)
cur.execute("SELECT facility_key FROM dw.fact_inspection GROUP BY facility_key ORDER BY count(*) DESC LIMIT 1")
fk = cur.fetchone()[0]
tests = {"history of one facility (WHERE facility_key = x)": f"SELECT count(*), sum(fail_count) FROM dw.fact_inspection WHERE facility_key = {fk}",
         "one month of inspections (date_key range)": "SELECT count(*), sum(fail_count) FROM dw.fact_inspection WHERE date_key BETWEEN 20250601 AND 20250630",
         "one batch (WHERE batch_id = 2)": "SELECT count(*) FROM dw.fact_inspection WHERE batch_id = 2"}
cur.execute("SET max_parallel_workers_per_gather = 0")
idx_rows = []
for name, sql in tests.items():
    for stage in ("without index", "with index"):
        if stage == "without index":
            cur.execute("DROP INDEX IF EXISTS dw.ix_fact_facility, dw.ix_fact_date, dw.ix_fact_batch")
        else:
            cur.execute("CREATE INDEX ix_fact_facility ON dw.fact_inspection (facility_key); CREATE INDEX ix_fact_date ON dw.fact_inspection (date_key); CREATE INDEX ix_fact_batch ON dw.fact_inspection (batch_id); ANALYZE dw.fact_inspection")
        ts = []
        for _ in range(9):
            t0 = time.perf_counter(); cur.execute(sql); cur.fetchall(); ts.append((time.perf_counter() - t0) * 1000)
        cur.execute("EXPLAIN " + sql); plan = cur.fetchall()[0][0]
        idx_rows.append({"query": name, "stage": stage, "median_ms": round(statistics.median(ts), 2), "plan_top": plan[:60]})
pd.DataFrame(idx_rows).to_csv(ROOT / "results" / "indexing_effect.csv", index=False)
print(pd.DataFrame(idx_rows).to_string(index=False))
