"""Exports the star-schema tables of the PostgreSQL warehouse as CSV files for Power BI (dashboard/powerbi/data/)."""
from pathlib import Path
import sys
import psycopg2
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
from config import connect

out = Path(__file__).resolve().parent / "powerbi" / "data"; out.mkdir(parents=True, exist_ok=True)
conn = connect(); cur = conn.cursor()
tables = {"DimDate": "dw.dim_date", "DimFacility": "dw.dim_facility", "DimInspectionType": "dw.dim_inspection_type", "DimResult": "dw.dim_result",
          "DimLocation": "dw.dim_location", "FactInspection": "dw.fact_inspection", "FactFacilityAnnualInspectionPerformance": "dw.fact_facility_annual_inspection_performance"}
for name, t in tables.items():
    with open(out / f"{name}.csv", "w", newline="") as f:
        cur.copy_expert(f"COPY {t} TO STDOUT WITH CSV HEADER", f)
    cur.execute(f"SELECT count(*) FROM {t}")
    print(f"{name}.csv: {cur.fetchone()[0]:,} rows")
