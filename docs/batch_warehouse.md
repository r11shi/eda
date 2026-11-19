# Part C: Traditional Batch Data Warehouse (PostgreSQL)

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

| batch_id | batch_label | rows_staged | rows_rejected | rows_not_completed | rows_loaded_fact | new_facilities | new_locations | annual_rows_refreshed |
|---|---|---|---|---|---|---|---|---|
| 1 | initial load Jan 2022 - Nov 2025 | 72130 | 0 | 11522 | 60608 | 16901 | 252 | 41546 |
| 2 | incremental load Dec 2025 | 1471 | 0 | 342 | 1129 | 182 | 0 | 10957 |
| 3 | re-run of Dec 2025 (idempotency test) | 1471 | 1129 | 342 | 0 | 0 | 0 | 0 |

* `rows_not_completed` are staged rows that are not completed inspections (not facts). `staged = loaded + not completed + rejected` holds for every batch.
* Batch 3 loads December 2025 a second time. The data-quality rule rejects the 1,129 inspections that exist already and loads 0 new facts, so the load is **idempotent**.

**Incremental-load demonstration** (no rebuild: the rows of batch 1 are unchanged, which is proven with an MD5 checksum over all of its fact rows):

| object | before_incremental | after_incremental |
|---|---|---|
| fact_inspection | 60608 | 61737 |
| dim_facility | 16902 | 17084 |
| dim_location | 253 | 253 |
| dim_inspection_type | 15 | 15 |
| dim_result | 4 | 4 |
| fact_facility_annual | 41546 | 42154 |
| checksum_batch1_rows | b6de0058b871f24df482411546209e5d | b6de0058b871f24df482411546209e5d |

**Execution time of each step (seconds):**

| step | seconds |
|---|---|
| [initial] create audit record | 0.002 |
| [initial] stage 72,130 rows (COPY) | 1.64 |
| [initial] DQ rules + dimensions + facts (CALL dw.load_batch) | 6.72 |
| [initial] create indexes + ANALYZE | 1.051 |
| [incremental] create audit record | 0.002 |
| [incremental] stage 1,471 rows (COPY) | 0.034 |
| [incremental] DQ rules + dimensions + facts (CALL dw.load_batch) | 0.503 |
| [rerun] create audit record | 0.001 |
| [rerun] stage 1,471 rows (COPY) | 0.031 |
| [rerun] DQ rules + dimensions + facts (CALL dw.load_batch) | 0.333 |

## Validation (all checks must be 0)
| check_name | after incremental load | after initial load |
|---|---|---|
| annual fact inspections - fact rows | 0 | 0 |
| annual fact violations - fact violations | 0 | 0 |
| batches where staged <> loaded + not_completed + rejected | 0 | 0 |
| duplicate inspection_id in fact | 0 | 0 |
| fact rows not in staging | 0 | 0 |
| facts mapped to Unknown facility (key 0) | 0 | 0 |
| facts mapped to Unknown location (key 0) | 0 | 0 |
| fail_count difference staging vs fact | 0 | 0 |
| orphan annual facility_key | 0 | 0 |
| orphan date_key | 0 | 0 |
| orphan facility_key | 0 | 0 |
| orphan inspection_type_key | 0 | 0 |
| orphan location_key | 0 | 0 |
| orphan result_key | 0 | 0 |
| staging completed rows not in fact | 0 | 0 |
| violation_count difference staging vs fact | 0 | 0 |

The two `facts mapped to Unknown ...` checks are 0, so no fact needed the Unknown member in this data.

## Failure test (atomic load)
A batch was loaded in which one row had a violation count that does not fit the fact column. The error occurs after the new dimension members have been inserted. All four tables were unchanged afterwards:

| object | before | after_failed_load | unchanged |
|---|---|---|---|
| dw.fact_inspection | 61737 | 61737 | True |
| dw.dim_facility | 17084 | 17084 | True |
| dw.dim_location | 253 | 253 | True |
| dw.fact_facility_annual_inspection_performance | 42154 | 42154 | True |

(`etl/fault_test.py`)

## Indexing
Indexes are created after the initial bulk load. Effect on three selective queries (median of 9 runs, parallel query disabled):

| query | stage | median_ms |
|---|---|---|
| history of one facility (WHERE facility_key = x) | without index | 3.17 |
| history of one facility (WHERE facility_key = x) | with index | 0.24 |
| one month of inspections (date_key range) | without index | 5.35 |
| one month of inspections (date_key range) | with index | 0.34 |
| one batch (WHERE batch_id = 2) | without index | 4.45 |
| one batch (WHERE batch_id = 2) | with index | 0.18 |

## Analytical SQL (mandatory questions 1-8) and execution time
| query | description | result_rows | median_ms |
|---|---|---|---|
| Q1a | Annual inspection volume | 4 | 10.1 |
| Q1b | Monthly inspection volume | 48 | 14.2 |
| Q2 | Facility types receiving the most inspections | 15 | 23.5 |
| Q3 | Pass, conditional-pass and fail rates by year | 4 | 15.5 |
| Q4 | Results across risk categories | 4 | 34.8 |
| Q5 | Inspection types associated with higher failure rates | 8 | 34.6 |
| Q6a | Violation counts by result group | 3 | 43.2 |
| Q6b | Most common violation rule numbers (rule-level detail is kept in staging, not in the star schema) | 15 | 62.6 |
| Q7a | Geographic area groups: failures and failure rate | 5 | 25.5 |
| Q7b | ZIP codes with the highest failure rate (at least 200 inspections) | 10 | 26.1 |
| Q7c | ZIP codes with the most failures (counts, not rates) | 10 | 15.0 |
| Q8a | Repeat inspections: fail rate by the position of the inspection in the facility's history (licensed facilities only) | 4 | 56.4 |
| Q8b | Repeat inspections: what happens at the next inspection after a failed one | 1 | 73.9 |
| Q8c | Facilities with the most inspections in the period | 10 | 32.3 |

The SQL is in `sql/06_analytical_queries.sql` and every result set is saved in `results/analytical_query_results/`. Questions 9 and 10 are answered by the association-mining and the regression / decision-tree notebooks.
