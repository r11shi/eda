"""Fault test of the batch load: a batch that fails in the middle must leave NO partial data in the warehouse."""
from pathlib import Path
import pandas as pd
import psycopg2
from config import connect

ROOT = Path(__file__).resolve().parents[1]
conn = connect(); conn.autocommit = True; cur = conn.cursor()
tables = ["dw.fact_inspection", "dw.dim_facility", "dw.dim_location", "dw.fact_facility_annual_inspection_performance"]
snap = lambda: {t: (cur.execute(f"SELECT count(*) FROM {t}"), cur.fetchone()[0])[1] for t in tables}
before = snap()
cur.execute("INSERT INTO staging.load_audit (batch_label, period_from, period_to) VALUES ('FAULT TEST: one row has a violation_count that cannot be stored', '2025-12-31', '2025-12-31') RETURNING batch_id")
bid = cur.fetchone()[0]
# 3 valid, new completed inspections + 1 row whose violation_count (99999) overflows the smallint fact column AFTER the dimensions have been loaded
cur.execute("""INSERT INTO staging.inspection_stg (inspection_id, dba_name, license_number, facility_nk, facility_id_source, facility_type_clean, facility_group, risk_category, risk_group, zip, city, inspection_date,
                 inspection_type, inspection_type_group, results, result_group, is_completed, is_failed_inspection, violation_count, high_violation_flag, geographic_area_group, year, batch_id)
               SELECT 900000000 + g, 'FAULT TEST FACILITY ' || g, '9990' || g, 'L9990' || g, 'License', 'Restaurant', 'Restaurant & Food Service', 'Risk 1 (High)', 'High', '60601', 'CHICAGO', DATE '2025-12-31',
                      'Canvass', 'Routine (Canvass)', 'Pass', 'Pass', true, 0, CASE WHEN g = 4 THEN 99999 ELSE 1 END, 0, 'Northwest', 2025, %s FROM generate_series(1, 4) g""", (bid,))
try:
    cur.execute("CALL dw.load_batch(%s)", (bid,)); outcome = "load succeeded (unexpected)"
except Exception as e:
    outcome = "load FAILED as intended: " + str(e).splitlines()[0]
after = snap()
cur.execute("DELETE FROM staging.inspection_stg WHERE batch_id = %s", (bid,))
cur.execute("DELETE FROM staging.load_audit WHERE batch_id = %s", (bid,))
rows = [{"object": t, "before": before[t], "after_failed_load": after[t], "unchanged": before[t] == after[t]} for t in tables]
res = pd.DataFrame(rows); res.to_csv(ROOT / "results" / "fault_test.csv", index=False)
print(outcome); print(res.to_string(index=False))
