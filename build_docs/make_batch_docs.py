"""Writes docs/dimensional_models.md (Part B) and docs/batch_warehouse.md (Part C) from the MEASURED results in results/*.csv."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R, D = ROOT / "results", ROOT / "docs"


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines)


mc = pd.read_csv(R / "model_comparison.csv").set_index("criterion")
mq = pd.read_csv(R / "model_comparison_queries.csv")
st = pd.read_csv(R / "model_storage.csv").set_index("schema")
mb = lambda b: f"{b / 1024 / 1024:.2f} MB"
star_dim, snow_dim = st.loc["dw (star + 2nd fact)", "dimension_bytes"], st.loc["snow (snowflake)", "dimension_bytes"]

model_doc = f"""# Part B: Dimensional Modelling

All numbers on this page were measured on the real warehouse (61,737 completed inspections, 17,083 facilities) by `etl/model_comparison.py`.

## Grain declaration
**One row in FactInspection = one completed food-establishment inspection on one inspection date.**
"Completed" means the result is Pass, Pass w/ Conditions or Fail. Rows with *Out of Business*, *No Entry*, *Not Ready* or *Business Not Located* are kept in staging but are not facts, because no inspection took place. The fact table never mixes grains: the second fact table has its own grain (one facility in one reporting year).

## 1. Star schema
![Star schema](images/star_schema.png)

* **Fact:** `FactInspection` with measures InspectionCount, ViolationCount, FailCount, PassCount, ConditionalPassCount, HighViolationFlag and the degenerate dimension `inspection_id`.
* **Dimensions:** DimDate, DimFacility, DimInspectionType, DimResult, DimLocation (all denormalised; each has an explicit *Unknown* member with key 0).
* No role-playing dimension is needed: every dimension takes part in only one role per fact row.

## 2. Snowflake schema
![Snowflake schema](images/snowflake_schema.png)

The star dimensions were normalised along their hierarchies: Date > Month > Quarter > Year; Facility > FacilityType > FacilityGroup and Facility > Risk; Location > ZIP and Location > AreaGroup; InspectionType > InspectionTypeGroup; Result > ResultGroup. It is physically implemented in schema `snow` (16 tables) so the comparison below is measured, not guessed.

## 3. Fact constellation
![Fact constellation](images/fact_constellation.png)

The star schema plus a second fact, **FactFacilityAnnualInspectionPerformance** (grain: one facility x one reporting year) with InspectionCount, FailCount, PassCount, ViolationCount, AverageViolations and FailureRate. It shares the conformed `DimFacility` with FactInspection.

## 4. Comparison of the three models
{md_table(mc.reset_index().rename(columns={"criterion": "Criterion", "star": "Star", "snowflake": "Snowflake", "fact_constellation": "Fact constellation"}))}

| Criterion | Star | Snowflake | Fact constellation |
|---|---|---|---|
| Storage of dimension tables (measured) | {mb(star_dim)} | {mb(snow_dim)} ({(1 - snow_dim / star_dim) * 100:.0f}% less) | {mb(star_dim)} |
| Storage redundancy | Group and type text repeated for each of the 17,083 facilities | Each group/type stored once (7 facility groups, 161 facility types, 100 ZIP and city pairs) | Same as star, plus the small annual fact (42,154 rows) |
| Query complexity | Simple, 2-3 joins | 5-9 joins for the same questions | Simple for both grains |
| BI / dashboard simplicity | Best: one table per dimension, hierarchies are columns | Harder: the BI tool must follow chains of tables | Best, and the facility-year question needs no aggregation |
| Maintainability | Changing a group definition means re-running the ETL rule | A group change is one row, but any new attribute needs a new table | Same as star plus one more load step |
| Hierarchy management | Hierarchies are columns (Year > Quarter > Month > Day, Facility Type > Risk > Establishment) | Hierarchies are explicit tables | Same as star |

**Query timings (median of 9 runs, ms):**

{md_table(mq.rename(columns={"query": "Query", "star_joins": "Star joins", "snowflake_joins": "Snowflake joins", "star_ms": "Star (ms)", "snowflake_ms": "Snowflake (ms)"}))}

## 5. Selected model and justification
**Selected model: fact constellation (star-based).**

1. The questions need **two grains**: inspection-level questions (volumes, rates, violations) and a facility-year question (repeat performance of an establishment). Only the constellation has a table for each, without mixing grains.
2. Denormalised dimensions give **fewer joins** (3 against 9 for question QA) and about **{mc.loc['QA median time (ms)', 'snowflake'] / mc.loc['QA median time (ms)', 'star']:.1f} times faster queries** ({mc.loc['QA median time (ms)', 'star']} ms against {mc.loc['QA median time (ms)', 'snowflake']} ms).
3. The second fact answers "facilities with at least 3 inspections and a failure rate of 50% or more in 2025" in **{mc.loc['Facility x year question: median time (ms)', 'fact_constellation']} ms against {mc.loc['Facility x year question: median time (ms)', 'star']} ms** from the inspection fact.
4. The snowflake saves only about {(star_dim - snow_dim) / 1024 / 1024:.1f} MB ({(1 - snow_dim / star_dim) * 100:.0f}%) of dimension storage. The dimensions are small, so this does not justify the extra joins.
5. The groupings (FacilityGroup, ResultGroup, ...) are derived by code in the ETL (`etl/curation.py`), so the update anomalies that normalisation prevents cannot appear in practice.

The selected model is **physically implemented** in PostgreSQL schema `dw` (see `sql/01_schema.sql` and `docs/batch_warehouse.md`).
"""
(D / "dimensional_models.md").write_text(model_doc)

# ------------------------------------------------------------------ batch warehouse doc
audit = pd.read_csv(R / "load_audit.csv")
timing = pd.read_csv(R / "batch_load_timing_all.csv")
val = pd.read_csv(R / "validation_results.csv")
inc = pd.read_csv(R / "incremental_load_demo.csv")
idx = pd.read_csv(R / "indexing_effect.csv")
qt = pd.read_csv(R / "batch_query_timing.csv")
v_pivot = val.pivot(index="check_name", columns="stage", values="value").reset_index()
batch_doc = f"""# Part C: Traditional Batch Data Warehouse (PostgreSQL)

Stack: Python (pandas) > PostgreSQL 16 > dimensional warehouse > OLAP > dashboard. Everything below was run; the numbers come from `results/`.

## Components
| Required element | Where |
|---|---|
| Staging tables | `staging.inspection_stg`, `staging.load_audit` (`sql/01_schema.sql`) |
| Dimension tables | `dw.dim_date`, `dim_facility`, `dim_inspection_type`, `dim_result`, `dim_location` |
| Fact tables | `dw.fact_inspection`, `dw.fact_facility_annual_inspection_performance` |
| Primary / foreign keys | declared in `sql/01_schema.sql` |
| Surrogate keys | `serial` keys; natural keys are kept (`facility_nk`, `inspection_id`) |
| ETL scripts | `etl/curation.py` (profile, clean, transform), `etl/run_etl.py` (stage, load), `sql/02_load_batch.sql` (`CALL dw.load_batch(batch_id)`) |
| Referential-integrity validation | `sql/04_validation.sql` |
| Indexing | `sql/03_indexes.sql` |
| Analytical SQL and execution time | `sql/06_analytical_queries.sql`, `etl/run_queries.py` |

## ETL flow
`Raw CSV > profile > clean > derive attributes (Python)  >  COPY into staging  >  data-quality rules  >  insert new dimension members  >  dimension lookup (unknown member 0 if no match)  >  fact load  >  rebuild the facility-year fact for the touched years  >  validation`

Load order follows the project document: DimDate, DimFacility, DimInspectionType, DimResult, DimLocation, FactInspection, FactFacilityAnnualInspectionPerformance. DimDate is pre-generated for 2022-2026. Facilities are identified by licence number (or name and address when there is no licence) and use a Type-1 update, so the latest name, type and risk win.

## Initial load and incremental load
The prescribed period is 1 January 2022 to 31 December 2025. The **initial load** covers 2022-01-03 to 2025-11-28; the final month (**December 2025**) was held back and loaded through the incremental ETL without rebuilding the warehouse.

{md_table(audit[['batch_id', 'batch_label', 'rows_staged', 'rows_rejected', 'rows_not_completed', 'rows_loaded_fact', 'new_facilities', 'new_locations', 'annual_rows_refreshed']])}

* `rows_not_completed` are staged rows that are not completed inspections (not facts). `staged = loaded + not completed + rejected` holds for every batch.
* Batch 3 loads December 2025 a second time. The data-quality rule rejects the 1,129 inspections that exist already and loads 0 new facts, so the load is **idempotent**.

**Incremental-load demonstration** (no rebuild: the rows of batch 1 are unchanged, which is proven with an MD5 checksum over all of its fact rows):

{md_table(inc)}

**Execution time of each step (seconds):**

{md_table(timing)}

## Validation (all checks must be 0)
{md_table(v_pivot)}

The two `facts mapped to Unknown ...` checks are 0, so no fact needed the Unknown member in this data.

## Failure test (atomic load)
A batch was loaded in which one row had a violation count that does not fit the fact column. The error occurs after the new dimension members have been inserted. All four tables were unchanged afterwards:

{md_table(pd.read_csv(R / 'fault_test.csv'))}

(`etl/fault_test.py`)

## Indexing
Indexes are created after the initial bulk load. Effect on three selective queries (median of 9 runs, parallel query disabled):

{md_table(idx[['query', 'stage', 'median_ms']])}

## Analytical SQL (mandatory questions 1-8) and execution time
{md_table(qt)}

The SQL is in `sql/06_analytical_queries.sql` and every result set is saved in `results/analytical_query_results/`. Questions 9 and 10 are answered by the association-mining and the regression / decision-tree notebooks.
"""
(D / "batch_warehouse.md").write_text(batch_doc)
print("written dimensional_models.md and batch_warehouse.md")
