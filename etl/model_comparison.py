"""Builds the snowflake copy of the warehouse and compares Star, Snowflake and Fact Constellation with MEASURED values."""
import statistics, time
from pathlib import Path
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
from config import DSN
conn = psycopg2.connect(DSN); conn.autocommit = True
cur = conn.cursor()
cur.execute((ROOT / "sql" / "05_snowflake_schema.sql").read_text())

QUERIES = {
 "QA: fail rate by year, quarter, facility group and area group": (
  """SELECT d.year, d.quarter, f.facility_group, l.geographic_area_group, count(*) inspections, round(100.0*sum(x.fail_count)/count(*),2) fail_rate
       FROM dw.fact_inspection x JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility f USING (facility_key) JOIN dw.dim_location l USING (location_key)
      GROUP BY 1,2,3,4""",
  """SELECT y.year, q.quarter, g.facility_group, a.geographic_area_group, count(*) inspections, round(100.0*sum(x.fail_count)/count(*),2) fail_rate
       FROM snow.fact_inspection x JOIN snow.dim_date d USING (date_key) JOIN snow.dim_month m USING (month_key) JOIN snow.dim_quarter q USING (quarter_key)
       JOIN snow.dim_year y ON y.year = q.year JOIN snow.dim_facility f USING (facility_key) JOIN snow.dim_facility_type t ON t.type_key = f.type_key
       JOIN snow.dim_facility_group g ON g.group_key = t.group_key JOIN snow.dim_location l USING (location_key) JOIN snow.dim_area_group a ON a.area_key = l.area_key
      GROUP BY 1,2,3,4"""),
 "QB: inspections by facility type, risk group and result group": (
  """SELECT f.facility_type, f.risk_group, r.result_group, count(*) FROM dw.fact_inspection x JOIN dw.dim_facility f USING (facility_key)
       JOIN dw.dim_result r USING (result_key) GROUP BY 1,2,3""",
  """SELECT t.facility_type, k.risk_group, g.result_group, count(*) FROM snow.fact_inspection x JOIN snow.dim_facility f USING (facility_key)
       JOIN snow.dim_facility_type t ON t.type_key = f.type_key JOIN snow.dim_risk k ON k.risk_key = f.risk_key
       JOIN snow.dim_result r USING (result_key) JOIN snow.dim_result_group g ON g.group_key = r.group_key GROUP BY 1,2,3"""),
}
ANNUAL_STAR = """SELECT f.facility_key, d.year, count(*) n, round(100.0*sum(x.fail_count)/count(*),1) fr, round(avg(x.violation_count),2) av
                   FROM dw.fact_inspection x JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility f USING (facility_key)
                  WHERE d.year = 2025 GROUP BY 1,2 HAVING count(*) >= 3 AND sum(x.fail_count)::numeric/count(*) >= 0.5"""
ANNUAL_CONST = """SELECT facility_key, reporting_year, inspection_count, failure_rate, average_violations
                    FROM dw.fact_facility_annual_inspection_performance WHERE reporting_year = 2025 AND inspection_count >= 3 AND failure_rate >= 0.5"""


def bench(sql, runs=9):
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter(); cur.execute(sql); cur.fetchall(); ts.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(ts), 1)


def size(schema):
    cur.execute("SELECT count(*), pg_size_pretty(sum(pg_total_relation_size(c.oid))), sum(pg_total_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r'", (schema,))
    return cur.fetchone()


def dim_bytes(schema):
    cur.execute("SELECT sum(pg_total_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r' AND c.relname LIKE 'dim_%%'", (schema,))
    return cur.fetchone()[0]

star_tables, star_size, star_bytes = size("dw")           # dw includes the second fact (constellation)
snow_tables, snow_size, snow_bytes = size("snow")
rows = []
for name, (q_star, q_snow) in QUERIES.items():
    j_star, j_snow = q_star.upper().count(" JOIN "), q_snow.upper().count(" JOIN ")
    rows.append({"query": name, "star_joins": j_star, "snowflake_joins": j_snow, "star_ms": bench(q_star), "snowflake_ms": bench(q_snow)})
perf = pd.DataFrame(rows)
annual = {"star: facility x year from FactInspection (ms)": bench(ANNUAL_STAR), "constellation: from FactFacilityAnnual (ms)": bench(ANNUAL_CONST)}
cur.execute("SELECT count(*) FROM dw.fact_inspection"); n_fact = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM dw.fact_facility_annual_inspection_performance"); n_ann = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM dw.dim_facility"); n_dimfac = cur.fetchone()[0]

summary = pd.DataFrame([
    {"criterion": "Number of tables", "star": 6, "snowflake": snow_tables, "fact_constellation": 7},
    {"criterion": "Joins for QA (year/quarter x facility group x area)", "star": int(perf.loc[0, "star_joins"]), "snowflake": int(perf.loc[0, "snowflake_joins"]), "fact_constellation": int(perf.loc[0, "star_joins"])},
    {"criterion": "QA median time (ms)", "star": perf.loc[0, "star_ms"], "snowflake": perf.loc[0, "snowflake_ms"], "fact_constellation": perf.loc[0, "star_ms"]},
    {"criterion": "QB median time (ms)", "star": perf.loc[1, "star_ms"], "snowflake": perf.loc[1, "snowflake_ms"], "fact_constellation": perf.loc[1, "star_ms"]},
    {"criterion": "Facility x year question: median time (ms)", "star": annual["star: facility x year from FactInspection (ms)"], "snowflake": annual["star: facility x year from FactInspection (ms)"], "fact_constellation": annual["constellation: from FactFacilityAnnual (ms)"]},
])
summary.to_csv(ROOT / "results" / "model_comparison.csv", index=False)
perf.to_csv(ROOT / "results" / "model_comparison_queries.csv", index=False)
print(summary.to_string(index=False)); print(perf.to_string(index=False))
print("star+constellation schema (dw):", star_tables, "tables,", star_size, "| snowflake (snow):", snow_tables, "tables,", snow_size)
print("dimension bytes: dw", dim_bytes("dw"), " snow", dim_bytes("snow"))
print("rows: fact", n_fact, "annual fact", n_ann, "dim_facility", n_dimfac)
cur.execute("""SELECT 'dw.dim_facility' t, count(*) FROM dw.dim_facility UNION ALL SELECT 'snow.dim_facility', count(*) FROM snow.dim_facility
               UNION ALL SELECT 'snow.dim_facility_type', count(*) FROM snow.dim_facility_type UNION ALL SELECT 'snow.dim_facility_group', count(*) FROM snow.dim_facility_group
               UNION ALL SELECT 'dw.dim_date', count(*) FROM dw.dim_date UNION ALL SELECT 'snow.dim_date', count(*) FROM snow.dim_date UNION ALL SELECT 'snow.dim_month', count(*) FROM snow.dim_month
               UNION ALL SELECT 'dw.dim_location', count(*) FROM dw.dim_location UNION ALL SELECT 'snow.dim_location', count(*) FROM snow.dim_location UNION ALL SELECT 'snow.dim_zip', count(*) FROM snow.dim_zip""")
print(cur.fetchall())
pd.DataFrame([{"schema": "dw (star + 2nd fact)", "tables": star_tables, "total_bytes": star_bytes, "dimension_bytes": dim_bytes("dw")},
              {"schema": "snow (snowflake)", "tables": snow_tables, "total_bytes": snow_bytes, "dimension_bytes": dim_bytes("snow")}]).to_csv(ROOT / "results" / "model_storage.csv", index=False)
