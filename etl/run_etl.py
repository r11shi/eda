"""Batch ETL driver:  Extract (curated CSV) -> Stage -> Data-quality rules -> Dimension lookups -> Fact load -> Validate.

  python etl/run_etl.py all          # create schema, initial load (Jan 2022-Nov 2025), indexes, validation,
                                     # then the incremental load of the held-back month (Dec 2025) and validation
  python etl/run_etl.py initial | incremental | validate
"""
import io, sys, time, csv
from pathlib import Path
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
CURATED = ROOT / "data" / "curated" / "inspections_curated.csv"
RESULTS = ROOT / "results"
from config import DSN
HOLD_BACK_FROM = "2025-12-01"          # the final month is loaded incrementally

STAGING_COLS = ["inspection_id", "dba_name", "aka_name", "license_number", "facility_nk", "facility_id_source", "facility_type_clean",
                "facility_group", "risk_category", "risk_group", "address", "city", "state", "zip", "inspection_date", "inspection_type",
                "inspection_type_group", "results", "result_group", "is_completed", "is_failed_inspection", "violation_count",
                "has_violations", "high_violation_flag", "violation_band", "violation_codes", "latitude", "longitude", "latitude_band",
                "longitude_band", "geographic_area_group", "year", "quarter", "month", "day_of_week", "is_weekend", "season",
                "is_same_day_repeat", "is_extreme_violation_count"]
timings = []


def connect():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    return conn


def timed(step, fn):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    timings.append({"step": step, "seconds": round(dt, 3)})
    print(f"  {step:<55s} {dt:8.3f} s")
    return out


def run_file(conn, name):
    with conn.cursor() as cur:
        cur.execute((SQL / name).read_text())


def load_curated():
    return pd.read_csv(CURATED, parse_dates=["inspection_date"], dtype={"zip": str, "license_number": str})


def stage(conn, df, batch_id):
    out = df[STAGING_COLS].copy()
    out["inspection_date"] = out["inspection_date"].dt.strftime("%Y-%m-%d")
    out["batch_id"] = batch_id
    buf = io.StringIO()
    out.to_csv(buf, index=False, header=False, quoting=csv.QUOTE_MINIMAL)
    buf.seek(0)
    cols = STAGING_COLS + ["batch_id"]
    with conn.cursor() as cur:
        cur.copy_expert(f"COPY staging.inspection_stg ({','.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)


def new_batch(conn, label, d_from, d_to):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO staging.load_audit (batch_label, period_from, period_to) VALUES (%s,%s,%s) RETURNING batch_id", (label, d_from, d_to))
        return cur.fetchone()[0]


def run_batch(conn, df, label, tag):
    d_from, d_to = df["inspection_date"].min().date(), df["inspection_date"].max().date()
    batch_id = timed(f"[{tag}] create audit record", lambda: new_batch(conn, label, d_from, d_to))
    timed(f"[{tag}] stage {len(df):,} rows (COPY)", lambda: stage(conn, df, batch_id))
    with conn.cursor() as cur:
        timed(f"[{tag}] DQ rules + dimensions + facts (CALL dw.load_batch)", lambda: cur.execute("CALL dw.load_batch(%s)", (batch_id,)))
    return batch_id


def validate(conn, tag):
    with conn.cursor() as cur:
        cur.execute((SQL / "04_validation.sql").read_text())
        rows = cur.fetchall()
    res = pd.DataFrame(rows, columns=["check_name", "value"])
    ri = res[~res["check_name"].str.startswith("facts mapped to Unknown")]
    print(f"  validation [{tag}]: {len(res)} checks, failures = {int((ri['value'] != 0).sum())}")
    res.insert(0, "stage", tag)
    return res


def counts(conn):
    q = {"fact_inspection": "dw.fact_inspection", "dim_facility": "dw.dim_facility", "dim_location": "dw.dim_location",
         "dim_inspection_type": "dw.dim_inspection_type", "dim_result": "dw.dim_result",
         "fact_facility_annual": "dw.fact_facility_annual_inspection_performance"}
    with conn.cursor() as cur:
        out = {}
        for k, t in q.items():
            cur.execute(f"SELECT count(*) FROM {t}")
            out[k] = cur.fetchone()[0]
        cur.execute("SELECT md5(string_agg(inspection_id::text || '|' || date_key || '|' || facility_key || '|' || coalesce(violation_count::text,'n'), ',' ORDER BY inspection_id)) FROM dw.fact_inspection WHERE batch_id = 1")
        out["checksum_batch1_rows"] = cur.fetchone()[0]
    return out


def main(mode):
    RESULTS.mkdir(exist_ok=True)
    conn = connect()
    df = load_curated()
    validations = []
    if mode in ("all", "initial"):
        print("Creating schemas, dimensions and fact tables")
        run_file(conn, "01_schema.sql")
        run_file(conn, "02_load_batch.sql")
        initial = df[df["inspection_date"] < HOLD_BACK_FROM]
        print(f"INITIAL LOAD: {len(initial):,} curated rows ({initial['inspection_date'].min().date()} .. {initial['inspection_date'].max().date()})")
        run_batch(conn, initial, "initial load Jan 2022 - Nov 2025", "initial")
        timed("[initial] create indexes + ANALYZE", lambda: run_file(conn, "03_indexes.sql"))
        validations.append(validate(conn, "after initial load"))
        before = counts(conn)
        print("  warehouse after initial load:", before)
    if mode in ("all", "incremental"):
        before = counts(conn)
        inc = df[df["inspection_date"] >= HOLD_BACK_FROM]
        print(f"INCREMENTAL LOAD: {len(inc):,} curated rows ({inc['inspection_date'].min().date()} .. {inc['inspection_date'].max().date()})")
        run_batch(conn, inc, "incremental load Dec 2025", "incremental")
        validations.append(validate(conn, "after incremental load"))
        after = counts(conn)
        print("  warehouse after incremental load:", after)
        print("  batch-1 rows untouched (checksum equal):", before["checksum_batch1_rows"] == after["checksum_batch1_rows"])
        pd.DataFrame([{"object": k, "before_incremental": before[k], "after_incremental": after[k]} for k in before]).to_csv(RESULTS / "incremental_load_demo.csv", index=False)
        # idempotency: loading the same month again must add nothing (duplicates rejected by the DQ rules)
        rerun = run_batch(conn, inc, "re-run of Dec 2025 (idempotency test)", "rerun")
        with conn.cursor() as cur:
            cur.execute("SELECT rows_staged, rows_rejected, rows_loaded_fact FROM staging.load_audit WHERE batch_id=%s", (rerun,))
            print("  re-run of the same month  (staged, rejected, loaded):", cur.fetchone())
    if validations:
        pd.concat(validations).to_csv(RESULTS / "validation_results.csv", index=False)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM staging.load_audit ORDER BY batch_id")
        cols = [c.name for c in cur.description]
        pd.DataFrame(cur.fetchall(), columns=cols).to_csv(RESULTS / "load_audit.csv", index=False)
    if timings:
        pd.DataFrame(timings).to_csv(RESULTS / f"batch_load_timing_{mode}.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
