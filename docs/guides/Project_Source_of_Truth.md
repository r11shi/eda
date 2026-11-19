# Project Source of Truth
**Food Safety and Restaurant Inspection Analytics: Integrated Data Warehouse, OLAP and Data Mining Project**
Rushikesh Maddewad | PRN 202502040037 | Roll No 353

This is the one document that lists **everything we did, how we did it, and what is in every file**. If another document disagrees with this one, check `results/` (the raw measurements) and the code.

**Contents:** 1 The project on one page | 2 The data | 3 What we did, part by part (A to J) | 4 File-by-file reference | 5 Results files | 6 Master number sheet | 7 How to reproduce | 8 Why we decided what we decided | 9 Limitations | 10 Study material

---

## 1. The project on one page

**Goal.** Build a data warehouse for the Chicago Food Inspections data, build it **three ways** (batch, distributed, real-time), **measure** the three ways on the same data, use the warehouse to answer business questions, and train three data-mining models.

**Story in one line:** *raw data → cleaning → staging → dimensional warehouse → OLAP and dashboard → analytical mart → regression, association rules, decision tree*, plus a distributed copy (Citus) and a real-time pipeline (Kafka, Spark, ClickHouse, Grafana).

| Part | Topic | Tools | Status |
|---|---|---|---|
| A | Data, profiling, cleaning, EDA | Python, pandas | Done |
| B | Dimensional models: star, snowflake, fact constellation | PostgreSQL | Done (all three built and measured) |
| C | Batch warehouse: staging, ETL, incremental load, validation, indexing | PostgreSQL 16, PL/pgSQL, Python | Done |
| D | Distributed warehouse | Citus 13.2 (coordinator + 2 workers) | Done; **not faster** on one machine |
| E | Real-time warehouse | Kafka 3.9, Spark 4.0.1, ClickHouse 26.3, Grafana 11.3 | Done; **a replay simulation** |
| F | OLAP, dashboard, ten findings | SQL, Plotly (HTML) | Done; **no Power BI .pbix** (Windows-only) |
| G | Regression | scikit-learn, statsmodels | Done |
| H | Association rules | mlxtend (Apriori, FP-Growth) | Done |
| I | Decision tree | scikit-learn | Done |
| J | Architecture comparison and recommendation | measured results | Done |

**Final recommendation:** a hybrid with the **batch warehouse at the centre**; add real-time only for live monitoring; add distribution only when the data outgrows one machine.

---

## 2. The data

**Source:** City of Chicago Data Portal, dataset *Food Inspections* (`4ijn-s7e5`), downloaded through the Socrata API by `scripts/fetch_data.py`. Period: **1 January 2022 to 31 December 2025**. Extracted 29 October 2026. The portal is updated over time, so a later download can differ slightly.

**Source fields:** inspection_id, dba_name, aka_name, license_, facility_type, risk, address, city, state, zip, inspection_date (always 00:00:00), inspection_type, results, violations (numbered text items separated by `|`), latitude, longitude, location.

**Row counts through the pipeline**

| Stage | Rows | Meaning |
|---|---|---|
| Raw download | 73,630 | all records in the period |
| After removing 29 repeated reports (curated, staged) | 73,601 | 72,130 initial + 1,471 incremental |
| Not completed (Out of Business, No Entry, Not Ready, Business Not Located) | 11,864 | stay in staging, **not** in the fact table |
| **Completed inspections** | **61,737** | the grain of the warehouse |
| Initial load (Jan 2022–Nov 2025) | 60,608 facts | batch 1 |
| Incremental load (Dec 2025) | +1,129 facts | batch 2 |
| Distinct facilities after both loads | 17,084 (17,083 plus the Unknown row) | `dim_facility` |

### Data-quality decisions (from `docs/data_quality_report.md`, every count computed by code)
| Problem | Field | Rows | Treatment | Why |
|---|---|---|---|---|
| Logical duplicate (same licence, date, type, result, violation text) | inspection_id | 29 | Remove later copies | Identical content = a repeated report |
| Same licence, date, type but different result/violations | license_number | 496 | Keep and flag | May be separate visits |
| Invalid risk code "All" | risk | 38 | Map to Unknown | Only Risk 1/2/3 are documented |
| Missing risk | risk | 17 | Unknown | Keep facts, avoid bias |
| Missing facility type | facility_type | 320 | Unknown | Keep facts |
| Missing or zero licence number | license_number | 213 | Identify the facility by name + address | 0 is a placeholder |
| Missing coordinates | latitude, longitude | 255 | Keep; location = Unknown area | ZIP still available |
| No time of day | inspection_date | 73,601 | No hourly analysis | All 00:00:00 |
| Fail / Conditional without violation text | violations | 552 | ViolationCount = NULL (unknown) | A fail needs at least one violation |
| Pass with no violation text | violations | 10,823 | ViolationCount = 0 | Nothing cited |
| Extreme violation count (above Q3 + 1.5 IQR, i.e. above 14) | violation_count | 2,686 | Keep and flag | The worst premises; capping would hide them |
| Not a completed inspection | results | 11,864 | Keep in staging, exclude from fact | No assessment took place |

### Derived attributes (documented in `docs/data_dictionary.md`)
| Attribute | How it is made |
|---|---|
| Year, Quarter, Month, DayOfWeek, IsWeekend, Season | from inspection_date (Season: Dec–Feb Winter, Mar–May Spring, Jun–Aug Summer, Sep–Nov Autumn) |
| ViolationCount | number of numbered items (like "34. FLOORS...") in the violation text |
| HasViolations | ViolationCount > 0 |
| ViolationBand | None (0), Low (1–2), Medium (3–5), High (6–9), Very High (10+), Unknown |
| HighViolationFlag | ViolationCount ≥ 6 (just above the 75th percentile, 5) |
| ResultGroup | Pass, Conditional Pass (Pass w/ Conditions), Fail, Not Completed |
| IsFailedInspection | Results = Fail → 1 else 0 |
| RiskGroup | Risk 1 High, Risk 2 Medium, Risk 3 Low, otherwise Unknown |
| FacilityGroup | keyword rules: Restaurant & Food Service, Schools & Childcare, Healthcare & Residential Care, Mobile / Catering & Events, Retail Food & Grocery, Other, Unknown |
| InspectionTypeGroup | Routine (Canvass), Re-inspection, License, Complaint / Illness, Other |
| GeographicAreaGroup | Northwest / Northeast / Southwest / Southeast, by coordinates against the Chicago street-grid origin (State St and Madison St); Unknown if missing |
| LatitudeBand / LongitudeBand | coordinates rounded to 0.05° cells (about 5 km) |
| FacilityNK | `L` + licence number, or `N|` + name + `|` + address if the licence is missing or 0 |

---

## 3. What we did, part by part

### Part A: Data, profiling, cleaning, EDA
- **What:** download, check quality, fix problems, create new columns, explore.
- **How:** `scripts/fetch_data.py` downloads the CSV (SHA-256 stored in `docs/dataset_source.md`). `etl/curation.py` holds the cleaning functions: `violation_codes` (extract rule numbers), `facility_group`, `inspection_type_group`, `violation_band`, `season`, `area_group`, `load_raw`, `missing_profile`, and `curate` (applies every rule and writes a log of problem, field, count, treatment and justification). Notebook `01_data_curation.ipynb` runs profiling before cleaning, curation, reconciliation of row counts and key totals before and after, the derived-attribute table, and saves `data/curated/inspections_curated.csv` plus `docs/data_quality_report.md`. Notebook `02_eda.ipynb` does numeric, categorical, temporal, geographic and outcome (volume vs rate) analysis.
- **Output:** curated CSV (about 26 MB), data-quality report, data dictionary.
- **Key facts:** mean violations 3.77, median 3, skewness 1.64; restaurants 70% of inspections; the rate of fail is highest in the Southeast area group (26.7%); re-inspections fail least (11.9%).

### Part B: Dimensional modelling
- **Grain:** one completed inspection on one date.
- **Three designs** were made and compared (diagrams in `docs/images/`): star schema, snowflake, fact constellation. The snowflake was built physically (`sql/05_snowflake_schema.sql`) so the comparison is measured by `etl/model_comparison.py`.
- **Selected: fact constellation**, which is the star plus a second fact table at facility-by-year grain.

| Table | Role | Main columns |
|---|---|---|
| `dw.dim_date` | date dimension (2022-01-01 to 2026-12-31) | date_key (YYYYMMDD), full_date, day, day_name, month, quarter, year, is_weekend, season |
| `dw.dim_facility` | facility (Type 1: latest value wins) | facility_key, facility_nk, license_number, dba_name, facility_type, facility_group, risk_category, risk_group, facility_id_source, last_inspection_date, created_batch, updated_batch |
| `dw.dim_inspection_type` | inspection type | inspection_type_key, inspection_type, inspection_type_group |
| `dw.dim_result` | result | result_key, result, result_group, failure_flag |
| `dw.dim_location` | ZIP and area | location_key, zip, city, latitude_band, longitude_band, geographic_area_group |
| `dw.fact_inspection` | **fact 1: one row per completed inspection** | inspection_key, inspection_id (degenerate), date_key, facility_key, inspection_type_key, result_key, location_key, inspection_count, violation_count (NULL = unknown), fail_count, pass_count, conditional_pass_count, high_violation_flag, batch_id, loaded_at |
| `dw.fact_facility_annual_inspection_performance` | **fact 2: facility × year** | facility_key, reporting_year, inspection_count, fail_count, pass_count, conditional_pass_count, violation_count, inspections_with_known_violations, average_violations, failure_rate, batch_id |
| `staging.inspection_stg` | staging: the curated rows as loaded | all curated columns + batch_id, reject_reason |
| `staging.load_audit` | one row per load | batch_id, label, period, rows_staged, rows_rejected, rows_not_completed, rows_loaded_fact, new_facilities, new_locations, annual_rows_refreshed, status |

Every dimension has an **Unknown member with key 0**, so a failed lookup never drops a fact.

**Measured comparison (`results/model_comparison.csv`)**
| | Star | Snowflake | Fact constellation |
|---|---|---|---|
| Tables | 6 | 16 | 7 |
| Joins for the main question | 3 | 9 | 3 |
| Query A median | 37.3 ms | 78.3 ms | 37.3 ms |
| Query B median | 30.4 ms | 46.9 ms | 30.4 ms |
| Facility × year question | 21.7 ms | 21.7 ms | **2.7 ms** |

Storage: the snowflake saves only about 0.9 MB of dimension storage (3.4 MB against 4.3 MB), which is not worth 9 joins.

### Part C: Batch warehouse (PostgreSQL 16)
- **Steps** (`etl/run_etl.py all`):
  1. Run `sql/01_schema.sql` (schemas, tables, Unknown members, date dimension) and `sql/02_load_batch.sql` (the load procedure).
  2. Take the curated rows before 2025-12-01 (initial load), write them into `staging.inspection_stg` with PostgreSQL `COPY`, and create an audit row.
  3. `CALL dw.load_batch(batch_id)`: (a) data-quality rules mark rows to reject (missing id/date, date not in dim_date, inspection_id already in the fact); (b) insert new dimension members (types, results, locations, facilities); Type-1 update of changed facility attributes; (c) load `fact_inspection` with lookups on natural keys (key 0 if nothing matches; `ON CONFLICT DO NOTHING`); (d) rebuild the facility-by-year fact for the years touched; (e) write the counts to `load_audit`.
  4. Run `sql/03_indexes.sql` (indexes on date, facility, type, result, location, batch, year; then `ANALYZE`).
  5. Run `sql/04_validation.sql`: 16 checks (orphan keys for each dimension, duplicate inspection_id, fact rows not in staging, staging completed rows not in fact, violation_count and fail_count differences, annual-fact reconciliation, batches where staged ≠ loaded + not completed + rejected, facts mapped to Unknown). All problem counts are 0.
  6. **Incremental load:** the held-back month (December 2025) is loaded by the same procedure. A checksum over the first batch's rows is unchanged afterwards.
  7. **Idempotency test:** loading December again rejects all 1,129 rows and loads 0.
- **Other tests:** `etl/fault_test.py` forces a failing load and proves all four warehouse tables stay unchanged (atomic). `etl/run_queries.py` times the analytical queries and the effect of indexes.
- **Results:** initial 60,608 facts (staged 72,130; 11,522 not completed); incremental +1,129 facts and +182 facilities in 0.5 s; initial load about 9.4 s including indexes; indexes cut selective queries from 3.2–5.4 ms to 0.2–0.3 ms; eight analytical queries 10–74 ms.

### Part D: Distributed warehouse (Citus)
- **What:** the same warehouse in a 3-node Citus 13.2 cluster on PostgreSQL 16.15 (coordinator on port 5440, workers on 5441 and 5442) built by `scripts/setup_citus_cluster.sh`. 32 shards. The fact table is **distributed by facility_key**; the five dimensions are **reference tables** (copied to every node) so joins stay local.
- **Distribution-key analysis** (`etl/distributed_baseline.py`, shard assignment simulated with PostgreSQL's hash):

| Key | Distinct values | Largest value share | Shard skew (max/mean) |
|---|---|---|---|
| **facility_key** | 17,083 | 0.04% | **1.10** |
| location_key | 252 | 3.1% | 2.56 |
| date_key | 986 | 0.17% | 1.32 |

- **Scaling test:** five queries (Q1 results by facility type, Q2 failure rate by area, Q3 monthly inspections, Q4 violations by risk, Q5 facility × year) at 61,737 / 100,000 / 500,000 / 1,000,000 / 2,000,000 rows, on one PostgreSQL node and on Citus (`etl/distributed_citus.py`). Volumes above 61,737 are a **synthetic scale-up** (real fact rows resampled), used for timing only.
- **Results:** all 25 distributed results identical to the centralized ones. Citus clearly faster in **4 of 25**, clearly slower in **16**. Reasons: coordination overhead, final merge on the coordinator, and all nodes sharing the same 4 CPU cores. At 2,000,000 rows one node answers in 174–269 ms. Loading and indexing 2,000,000 rows into Citus took 7.7 s. Memory: single node 124 MB; Citus coordinator 277 MB, workers 907 and 922 MB.

### Part E: Real-time warehouse
- **Flow:** `producer.py` → Kafka topic `food_inspections` (3 partitions) → `spark_stream.py` (Spark Structured Streaming) → ClickHouse → Grafana.
- **Producer:** reads completed inspections from the curated file in date order and sends them as JSON at a chosen rate (80 per second in the test). Every event carries `source_mode = REPLAY_SIMULATION`. With `--bad-every N` it injects malformed test events (invalid JSON, invalid result group, negative violation count).
- **Spark job:** four streaming queries run together: (1) valid events → `food.inspection_events`; (2) invalid events → `food.invalid_events` (dead-letter table with the reason); (3) 10-second processing-time windows by facility group, risk, area and result → `food.window_agg`; (4) daily event-time windows with a 1-day watermark → `food.daily_event_time_agg`.
- **Seven validation rules:** valid JSON; inspection_id present and positive; event_time is a date; result_group in (Pass, Conditional Pass, Fail); risk_group in the documented list; violation_count between 0 and 100; emitted_at present.
- **Derived measures:** is_fail, is_pass, is_conditional, high_violation_flag (≥ 6 violations).
- **ClickHouse tables** (`streaming/clickhouse_ddl.sql`): `inspection_events` (MergeTree), `invalid_events` (MergeTree), `window_agg` and `daily_event_time_agg` (ReplacingMergeTree, so the newest version of an updated window wins).
- **Grafana dashboard** (`streaming/grafana/`): KPI tiles, inspections per minute by result, top facility types, risk distribution, ZIP area alerts (at least 5 inspections and fail rate of 40% or more), pipeline-health table. Refresh every 5 s. Titled as a replay simulation.
- **Results (`results/streaming_metrics.csv`):** 3,647 events stored, each exactly once; 24 of 24 injected malformed events rejected; throughput 80 events/s; latency emit → ClickHouse average 1,518 ms, median 1,510 ms, p95 2,457 ms, max 3,541 ms; ClickHouse dashboard queries 5.6–7.3 ms; memory Kafka 396 MB, ClickHouse 704 MB, Spark 1,244 MB, Grafana 175 MB (about 2.5 GB).

### Part F: OLAP, dashboard, ten findings
- **Eight analytical queries** (`sql/06_analytical_queries.sql`, run by `etl/run_queries.py`): Q1 annual and monthly volume; Q2 facility types with most inspections; Q3 pass/conditional/fail rates by year; Q4 results by risk; Q5 inspection types with higher failure rates; Q6 violation counts by result and most common violation rule numbers; Q7 failures by area, ZIP codes by rate and by count; Q8 repeat inspections (fail rate by history position, what happens after a fail, facilities with most inspections). Timings 10–74 ms.
- **OLAP operations** (`sql/07_olap_queries.sql`, run by `etl/run_olap.py`, written to `docs/olap_operations.md` with SQL, DAX and interpretation): R1 roll-up (month → quarter → year for 2025), D1–D3 drill-down (facility group → grocery types → grocery stores), S1 slice, C1 dice, P1 pivot, G1 SQL CUBE, G2 GROUPING SETS. DAX versions are written for Power BI but **not executed**.
- **Dashboard** (`dashboard/build_dashboard.py` → `food_safety_dashboard.html`): four sections: Executive, Facility and Risk, Geographic, Inspection and Violation. Self-contained Plotly page that works offline. Headline: 61,737 inspections, fail rate 23.1%, 14,999 inspections with 6+ violations.
- **Power BI package** (`dashboard/powerbi/`): CSV export of every warehouse table plus rebuild instructions (relationships, DAX measures), because Power BI Desktop is Windows-only and no `.pbix` was produced.
- **Ten findings** (`docs/ten_findings.md`, each with question, analysis, chart, interpretation, recommendation):
  1. Volume grew 12% in four years; no stable seasonal peak (1,300–1,650 a month).
  2. Restaurants get 7 of 10 inspections.
  3. Fail rate fell from 24.9% (2022) to 21.1% (2025).
  4. Risk category does not change the fail rate, but high-risk places record more violations.
  5. Complaint inspections fail most (37.6%); re-inspections least (11.9%).
  6. Failing inspections cite about three times the violations of passing ones; top violations concern premises and cleanliness.
  7. ZIP codes with the highest failure **rate** (60617, 60620, 60628, 60619, 60636) differ from those with the most failures (60614, 60608, 60617).
  8. After a failure, 79% of the next visits pass, on average 13 days later; about 13% fail again.
  9. 10 or more violations mean a 69% chance of failing.
  10. Violation counts and failures are only weakly predictable before the visit.

### Analytical mart (input of G, H, I)
`sql/08_analytics_mart.sql` creates `mart.food_inspection_analytics_mart` **from the warehouse** (fact + dimensions), one row per completed inspection. With window functions (`lag`, running `count`) it adds **prior-history features from strictly earlier inspections of the same licensed facility** (prior_inspection_result, prior_violation_count, days_since_prior_inspection, prior_inspection_count, has_prior_inspection). A same-day earlier inspection is ignored to avoid leakage.

### Part G: Regression (`notebooks/07_regression.ipynb`, learn it in Guide 1)
- Target: ViolationCount (61,185 inspections with a known count). Inputs: facility type, risk, inspection type, month, day of week, ZIP, prior result, prior violation count. One-hot encoding (rare categories grouped) gives 102 columns.
- Split: train 2022–2024 (45,266), test 2025 (15,919). No leakage.
- Models: baseline (training mean), simple regression (prior violations only: violations = 2.737 + 0.209 × prior), multiple regression.
- Results: baseline MAE 2.71, multiple MAE 2.45, RMSE 3.28, **R² 0.12** (train R² 0.25).
- Diagnostics: VIF > 5 for 5 of 102 features; Breusch-Pagan shows non-constant error variance; 1.9% of inspections (above 14 violations) cause about 25% of the squared error; 304 of 15,919 predictions are negative. Next step would be Poisson / negative binomial regression.

### Part H: Association rules (`notebooks/08_association_mining.ipynb`, Guide 2)
- 61,185 transactions, 35 items, 7 items each (FacilityType, Risk, InspectionTypeGroup, ResultGroup, ViolationBand, AreaGroup, Season). Top 8 facility types kept, the rest "Other".
- Apriori (mandatory) and FP-Growth give **identical** 1,198 frequent item sets at minimum support 2%. Rules: confidence ≥ 30%, lift ≥ 1.3; obvious and redundant rules removed; **14 rules** kept (`results/association_rules_selected.csv`).
- Best rule: Violations Very High (10+) ⇒ Fail, support 5.4%, confidence 69%, lift 3.0.

### Part I: Decision tree (`notebooks/09_decision_tree.ipynb`, Guide 3)
- Target: FailedInspection. Inputs known before the visit including prior history. scikit-learn `DecisionTreeClassifier` (CART).
- Split: train 2022–2023, validation 2024, test 2025. Tuning of max_depth, min_samples_split, min_samples_leaf, ccp_alpha by validation ROC-AUC. Chosen: max_depth 8, min_samples_split 200, min_samples_leaf 200. Final fit on 2022–2024.
- Results (test 2025): AUC **0.635**; at threshold 0.5 accuracy 0.784, recall 0.04; at the validation-tuned threshold 0.217 recall 0.61, precision 0.29, accuracy 0.60; baseline "always pass" accuracy 0.789.
- Top inputs: prior result Fail 29%, Complaint 15%, prior violation count 13%, days since prior 10%. Three paths interpreted (highest fail rate 55–58%, lowest 4–5%, largest group 27%).

### Part J: Architecture evaluation (`docs/architecture_comparison.md`, `docs/domain_recommendations.md`)
| | Batch (PostgreSQL) | Distributed (Citus) | Real-time (Kafka, Spark, ClickHouse) |
|---|---|---|---|
| Latency | periodic; load of one month 0.5 s | same bulk-load pattern | 1.5 s average |
| History analytics | excellent, 10–74 ms | identical results, not faster here | operational window only |
| Live monitoring | none | none | excellent, 5.6–7.3 ms queries |
| Scale (measured) | 2,000,000 rows still 174–269 ms | no gain on one machine | not stress-tested beyond 80 events/s |
| Complexity | low | medium | high (four services, about 2.5 GB) |
| Fault handling | tested: failed load leaves no partial data; no automatic failover | design analysis only | Kafka keeps events, Spark checkpoints; at-least-once delivery |

**Recommendation:** batch warehouse as the system of record; real-time only for live monitoring if inspections are recorded digitally; Citus only when data outgrows one node (Chicago adds about 16,000 inspections a year). **Ten operational recommendations** include: triage complaint inspections, keep the two-week re-inspection cycle, trigger follow-up at 10+ violations, target ZIP codes by rate and size capacity by count, use models only as a ranking aid, and improve the source data (record time of day, one row per violation, stable establishment id).

---

## 4. File-by-file reference

Root of the project: `EDA/Project/`.

### Top level
| File | What is in it |
|---|---|
| `README.md` | status of each part, map of the 54 required deliverables, reproduce commands, honest notes |
| `Food_Safety_Project_Colab.ipynb` | **single-file version**: every source file is written by a `%%writefile` cell and run; the notebooks are embedded; saved with outputs |
| `.gitignore` | keeps data and runtime folders out of git |

### scripts/
| File | What it does |
|---|---|
| `fetch_data.py` | downloads the records and the dataset metadata from the Socrata API, prints the SHA-256 |
| `setup_postgres.sh` | starts PostgreSQL, creates role and database `foodsafety` |
| `setup_citus_cluster.sh` | creates coordinator (5440) and workers (5441, 5442), loads Citus, 32 shards, registers workers |
| `install_tools.sh` | downloads Kafka 3.9.0, ClickHouse 26.3 LTS and Grafana 11.3 and verifies checksums |
| `start_realtime_stack.sh` | starts ClickHouse, Kafka (KRaft), the Spark job, Grafana, in that order |
| `start_grafana.sh` | starts Grafana with the data source and dashboard provisioned |

### etl/ (Python)
| File | What it does |
|---|---|
| `curation.py` | all cleaning rules and derived attributes; the function `curate()` returns the cleaned table and a log |
| `run_etl.py` | the batch ETL driver (`all`, `initial`, `incremental`, `validate`) |
| `model_comparison.py` | builds the snowflake copy and measures star / snowflake / constellation |
| `run_queries.py` | runs and times the 8 analytical queries; indexing experiment |
| `run_olap.py` | runs the OLAP blocks and writes `docs/olap_operations.md` |
| `fault_test.py` | forces a failing load and proves nothing changes |
| `distributed_baseline.py` | distribution-key analysis; centralized scaling test with synthetic scale-up |
| `distributed_citus.py` | loads the Citus cluster, runs the same queries, compares results and times |

### sql/
| File | What it does |
|---|---|
| `01_schema.sql` | schemas, staging, dimensions, facts, Unknown members, date dimension |
| `02_load_batch.sql` | procedure `dw.load_batch` (rules, dimensions, facts, annual fact, audit) |
| `03_indexes.sql` | indexes and ANALYZE |
| `04_validation.sql` | the 16 integrity and reconciliation checks |
| `05_snowflake_schema.sql` | snowflake copy of the model |
| `06_analytical_queries.sql` | the eight business queries |
| `07_olap_queries.sql` | roll-up, drill-down ×3, slice, dice, pivot, CUBE, GROUPING SETS (with DAX in comments) |
| `08_analytics_mart.sql` | the analytical mart with prior-history features |

### streaming/
| File | What it does |
|---|---|
| `producer.py` | Kafka replay producer with optional bad-event injection |
| `spark_stream.py` | Spark Structured Streaming job (7 validation rules, 4 streaming queries) |
| `clickhouse_ddl.sql` | the four ClickHouse tables |
| `init_clickhouse.py` | runs the DDL |
| `measure_streaming.py` | measures latency, completeness, rejected events, query times, memory |
| `grafana/build_dashboard.py` | generates the dashboard JSON |
| `grafana/food_safety_realtime_dashboard.json` | the Grafana dashboard definition |
| `grafana/datasource.yml` | ClickHouse data source for Grafana |

### notebooks/
| File | What it does |
|---|---|
| `01_data_curation.ipynb` | dataset documentation, profiling, curation, reconciliation, derived attributes, saves the curated CSV |
| `02_eda.ipynb` | numeric, categorical, temporal, geographic, outcome analysis |
| `07_regression.ipynb` | Part G |
| `08_association_mining.ipynb` | Part H |
| `09_decision_tree.ipynb` | Part I |

### dashboard/
| File | What it does |
|---|---|
| `build_dashboard.py` | builds the HTML dashboard from the warehouse (Plotly) |
| `food_safety_dashboard.html` | the finished dashboard, four sections, offline |
| `export_for_powerbi.py` | exports warehouse tables as CSV |
| `powerbi/README.md`, `powerbi/data/*.csv` | Power BI rebuild instructions and data |

### docs/
| File | What is in it |
|---|---|
| `Technical_Report.pdf/.md` | the 8-page technical report |
| `Presentation.pptx` | the 12-slide presentation with speaker notes |
| `Project_Source_of_Truth.pdf/.md` | this document |
| `Guide_1_Regression`, `Guide_2_Association_Rules`, `Guide_3_Decision_Tree`, `Guide_4_Probable_Questions` | study guides (pdf and md) |
| `Presenter_Guide`, `Theory_Study_Guide`, `Project_Quick_Guide` | earlier guides |
| `dataset_source.md` | source, access method, SHA-256 |
| `data_dictionary.md` | source fields, derived fields, formulas |
| `data_quality_report.md` | every data-quality problem with count and treatment |
| `dimensional_models.md` | star, snowflake, constellation with measured comparison |
| `batch_warehouse.md` | schema, ETL, validation, incremental load, indexing, SQL timing |
| `distributed_warehouse.md` | key analysis, Citus set-up, scaling tables |
| `realtime_warehouse.md` | architecture, rules, metrics, screenshots |
| `olap_operations.md` | each OLAP operation: question, SQL, DAX, output, interpretation |
| `ten_findings.md` | the ten findings |
| `architecture_comparison.md` | Part J comparison table and evidence |
| `domain_recommendations.md` | ten final recommendations |
| `images/` | schema diagrams, finding charts, dashboard and Grafana screenshots, Citus chart |
| `make_*.py`, `html_to_pdf.js` | scripts that generate the documents, presentation and PDFs from results |

### results/ (see section 5)
### Not in the repository (recreated by the commands in section 7)
`data/raw` (78 MB), `data/curated` (26 MB), `runtime/` (installed servers and logs, about 2.3 GB).

---

## 5. Results files (the evidence behind every number)

| File | What is in it |
|---|---|
| `load_audit.csv` | one row per load batch: rows staged, rejected, not completed, loaded, new facilities |
| `validation_results.csv` | every validation check after each load |
| `incremental_load_demo.csv` | table counts before/after the incremental load, and the checksum |
| `batch_load_timing_all.csv` | time of each ETL step |
| `fault_test.csv` | table counts before/after a forced failing load |
| `batch_query_timing.csv` | median ms of each analytical query |
| `analytical_query_results/*.csv` | the output rows of each analytical query |
| `indexing_effect.csv` | query times with and without indexes |
| `model_comparison.csv`, `model_comparison_queries.csv`, `model_storage.csv` | star vs snowflake vs constellation |
| `centralized_scaling.csv` | single-node timings at 5 volumes |
| `distribution_key_analysis.csv`, `distribution_key_experiment.csv` | shard skew of the candidate keys |
| `distributed_scaling.csv` | Citus vs centralized time at each volume, with the ratio |
| `citus_load_times.csv`, `citus_resources.csv`, `citus_explain.txt` | Citus load times, memory, query plan |
| `streaming_metrics.csv` | latency, throughput, rejected events, query times, memory |
| `regression_metrics.csv`, `regression_top_coefficients.csv` | Part G |
| `association_rules_selected.csv` | the 14 selected rules with interpretation |
| `decision_tree_metrics.csv`, `decision_tree_importance.csv`, `decision_tree_paths.csv` | Part I |
| `screenshots/grafana_realtime_dashboard.png` | Grafana screenshot |

---

## 6. Master number sheet

| Topic | Number |
|---|---|
| Records / completed inspections | 73,630 / 61,737 |
| Not completed (kept in staging only) | 11,864 |
| Duplicates removed | 29 |
| Same-day pairs kept and flagged | 496 |
| Fails without violation text (NULL) | 552 |
| Initial load / incremental load / re-run | 60,608 / +1,129 / 0 |
| Facilities | 17,084 rows in `dim_facility` (17,083 plus Unknown) |
| Validation checks | 16, all problem counts 0 |
| Analytical queries | 10–74 ms |
| Index effect | 3.2–5.4 ms to 0.2–0.3 ms |
| Star / snowflake / constellation tables | 6 / 16 / 7 |
| Snowflake vs star query time | 78.3 vs 37.3 ms (2.1×) |
| Facility × year question | 21.7 ms vs 2.7 ms |
| Distribution key skew | facility 1.10, location 2.56, date 1.32 |
| Citus results identical | 25 of 25; faster in 4, slower in 16 |
| 2,000,000 rows on one node | 174–269 ms |
| Streaming events / rejected | 3,647 / 24 of 24 |
| Streaming latency | average 1,518 ms, p95 2,457 ms |
| Streaming memory | about 2.5 GB |
| Fail rate | 24.9% (2022) → 21.1% (2025); overall 23.1% |
| Complaint / re-inspection fail rate | 37.6% / 11.9% |
| After a fail: next visit passes | 79%, about 13 days later |
| 10+ violations ⇒ fail | 69% |
| Regression | MAE 2.45 (baseline 2.71), RMSE 3.28, R² 0.12 |
| Association rules | 1,198 itemsets; 14 rules; best lift 3.0 (10+ ⇒ Fail) |
| Decision tree | AUC 0.635; recall 0.61 / precision 0.29 at threshold 0.217 |

---

## 7. How to reproduce

**Easiest:** open `Food_Safety_Project_Colab.ipynb` in Google Colab and choose *Runtime → Run all* (about 10 minutes; Parts D and E only save their code there).

**From the folder** (Ubuntu 24.04, Python 3.13, PostgreSQL 16; 4 cores, 15 GB RAM):
```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn statsmodels mlxtend psycopg2-binary plotly nbformat nbconvert ipykernel markdown python-pptx clickhouse-connect kafka-python-ng
python3 scripts/fetch_data.py
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 01_data_curation.ipynb 02_eda.ipynb && cd ..
scripts/setup_postgres.sh
python3 etl/run_etl.py all            # schema, initial load, validation, incremental load, repeat-load test
python3 etl/model_comparison.py
python3 etl/run_queries.py
python3 etl/fault_test.py
python3 etl/run_olap.py
PGPASSWORD=foodsafety psql -h localhost -U foodsafety -d foodsafety -f sql/08_analytics_mart.sql
python3 dashboard/build_dashboard.py
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 07_regression.ipynb 08_association_mining.ipynb 09_decision_tree.ipynb && cd ..
# Part D
python3 etl/distributed_baseline.py && scripts/setup_citus_cluster.sh && python3 etl/distributed_citus.py
# Part E
scripts/install_tools.sh && scripts/start_realtime_stack.sh
python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150
python3 streaming/measure_streaming.py       # dashboard: http://127.0.0.1:3000/d/food-safety-rt
```

---

## 8. Why we decided what we decided

| Decision | Reason |
|---|---|
| Grain = one completed inspection | The other statuses (No Entry, Out of Business...) are not assessments |
| Fact constellation | Star speed plus fast yearly questions; snowflake was 2× slower |
| Unknown member (key 0) | Never lose a fact because a lookup failed |
| Type-1 facility dimension | Simple; latest attributes win (limit: no history) |
| NULL, not 0, for fails without violation text | A fail must cite at least one violation |
| Keep outliers | They are the worst premises |
| Load procedure in PL/pgSQL, one transaction | Atomic and repeatable; same code for initial and incremental |
| Indexes created after the bulk load | Faster load, then faster queries |
| FacilityKey as distribution key | Most distinct values and most even shards |
| Dimensions as reference tables | Joins stay local on each worker |
| Replay for the real-time part | The official data is a historical file; it is labelled everywhere |
| Chronological splits | Real prediction goes forward in time; avoids leakage |
| Prior-history features from strictly earlier inspections | No leakage |
| Threshold chosen on the validation year | The test year is used only once |
| HTML dashboard plus Power BI package | Power BI Desktop is Windows-only |
| Citus from the PGDG build of PostgreSQL 16 | Citus 13.2 needs it; approved by you earlier |

---

## 9. Limitations (state them calmly)
- The real-time part is a **replay** of historical data on one machine; throughput was tested only at 80 events/s.
- Citus ran on **one 4-core machine** and showed overhead, not a hardware speed-up; scale-up above 61,737 rows is **synthetic** and was used only for timing.
- **No Power BI `.pbix`**; DAX is written but was not run.
- Timings come from one machine and compare designs under equal conditions; they are not production capacity.
- History starts in January 2022, which affects the prior-inspection features; 2025 behaves differently from 2022–2024.
- Facility attributes are Type 1 (latest value), so old facts show current attributes.
- Area groups are quadrants of the street grid, not official community areas.
- Rule-level violation detail stays in staging; the warehouse keeps only the count.
- The models are weak (R² 0.12, AUC 0.64): they can rank, not decide.

---

## 10. Study material
| Document | Use it for |
|---|---|
| `Guide_1_Regression.pdf` | regression from zero |
| `Guide_2_Association_Rules.pdf` | association rules, Apriori, FP-Growth from zero |
| `Guide_3_Decision_Tree.pdf` | decision trees, ID3, C4.5, CART, metrics |
| `Guide_4_Probable_Questions.pdf` | 84 questions and short answers |
| `Project_Quick_Guide.pdf` | the 15-minute overview |
| `Presenter_Guide.pdf`, `Theory_Study_Guide.pdf` | extra detail |
| `Technical_Report.pdf`, `Presentation.pptx` | the deliverables |
