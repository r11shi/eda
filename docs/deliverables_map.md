# Food Safety and Restaurant Inspection Analytics: Integrated Data Warehouse, OLAP and Data Mining Project

**Student:** Rushikesh Maddewad | **PRN:** 202502040037 | **Roll No:** 353
**Data:** City of Chicago Food Inspections (official Data Portal), 1 Jan 2022 to 31 Dec 2025: 73,630 records, 61,737 completed inspections.
**Start with:** `docs/Technical_Report.pdf` (summary of everything) and `docs/Presentation.pptx`.

One lifecycle: *raw data > profiling > curation > staging > dimensional warehouse > OLAP / dashboard > analytical mart > regression, association rules, decision tree*, with three warehouse architectures compared on the same data.

## Status of the required parts

| Part | Status |
|---|---|
| A. Dataset, curation, EDA | Done |
| B. Dimensional modelling (star, snowflake, fact constellation, comparison, selection) | Done; snowflake built physically for a measured comparison |
| C. Batch data warehouse (PostgreSQL, ETL, initial + incremental load, validation, indexing, SQL timing) | Done |
| D. Distributed data warehouse (Citus) | **Done and measured**, with an honest result: a 3-node Citus 13.2 cluster (coordinator + 2 workers) on one machine, facts distributed by FacilityKey, dimensions as reference tables, 25 test cases from 61,737 to 2,000,000 rows, all results identical to the centralized ones. Citus was **not faster** than the single node in most cases (clearly faster in 4 of 25, slower in 16) because the workers share the same 4 cores. See `docs/distributed_warehouse.md`. |
| E. Real-time warehouse (Kafka, Spark Structured Streaming, ClickHouse, Grafana) | Done, run end to end. **A replay simulation of historical data, labelled as such.** |
| F. OLAP and dashboard | OLAP done (SQL run; DAX written but **not executed**). Dashboard delivered as a self-contained HTML page built from the warehouse. **No Power BI `.pbix`** (Power BI Desktop is Windows-only); a rebuild package is in `dashboard/powerbi/`. |
| G. Regression | Done |
| H. Association-rule mining (Apriori + FP-Growth) | Done |
| I. Decision tree | Done |
| J. Architecture evaluation and recommendation | Done, all three architectures measured |

The *individual viva and contribution* part of the marking scheme is personal and is not covered by files.

## Where each required deliverable is

| # | Deliverable | Location |
|---|---|---|
| 24 | Official dataset and dataset-source documentation | `docs/dataset_source.md`, `scripts/fetch_data.py`, `data/raw/socrata_metadata.json` |
| 25 | Data dictionary | `docs/data_dictionary.md` |
| 26 | Data-quality report | `docs/data_quality_report.md` |
| 27 | Data-curation notebook | `notebooks/01_data_curation.ipynb` (logic in `etl/curation.py`) |
| 28 | EDA notebook | `notebooks/02_eda.ipynb` |
| 29-31 | Star schema, snowflake schema, fact constellation | `docs/dimensional_models.md`, `docs/images/*.png`, `sql/01_schema.sql`, `sql/05_snowflake_schema.sql` |
| 32 | PostgreSQL schema and scripts | `sql/01` to `sql/08` |
| 33 | ETL scripts | `etl/curation.py`, `etl/run_etl.py`, `sql/02_load_batch.sql` |
| 34 | Batch DW implementation | `docs/batch_warehouse.md` |
| 35 | Incremental-load demonstration | `results/incremental_load_demo.csv`, `results/load_audit.csv`, `docs/batch_warehouse.md` |
| 36-37 | Distributed DW and performance results | `docs/distributed_warehouse.md`, `scripts/setup_citus_cluster.sh`, `etl/distributed_baseline.py`, `etl/distributed_citus.py`, `results/distributed_scaling.csv`, `results/distribution_key_experiment.csv` |
| 38 | Kafka producer | `streaming/producer.py` |
| 39 | Spark streaming application | `streaming/spark_stream.py` |
| 40 | ClickHouse real-time warehouse | `streaming/clickhouse_ddl.sql`, `streaming/init_clickhouse.py` |
| 41 | Power BI dashboard | **Not built as `.pbix`.** `dashboard/food_safety_dashboard.html` and `dashboard/powerbi/` |
| 42 | Grafana real-time dashboard | `streaming/grafana/food_safety_realtime_dashboard.json`, screenshot `results/screenshots/` |
| 43-44 | OLAP queries and CUBE demonstration | `sql/07_olap_queries.sql`, `docs/olap_operations.md` |
| 45 | Ten analytical findings | `docs/ten_findings.md` |
| 46-48 | Regression, association-mining, decision-tree notebooks | `notebooks/07_regression.ipynb`, `08_association_mining.ipynb`, `09_decision_tree.ipynb` |
| 49 | Architecture comparison | `docs/architecture_comparison.md` |
| 50 | Final domain recommendations | `docs/domain_recommendations.md` |
| 51 | Source-code repository | this repository (`EDA/Project`) |
| 52 | Technical report | `docs/Technical_Report.pdf` (`.md` source alongside) |
| 53 | Presentation | `docs/Presentation.pptx` |
| 54 | Live demonstration | `scripts/start_realtime_stack.sh` and the commands below |

## Reproducing the project

Tested on Ubuntu 24.04, Python 3.13, PostgreSQL 16, Java 21 (4 cores, 15 GB RAM).

```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn statsmodels mlxtend psycopg2-binary plotly nbformat nbconvert ipykernel markdown python-pptx clickhouse-connect kafka-python-ng

# Part A: data and curation
python3 scripts/fetch_data.py                                   # official data, 2022-2025
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 01_data_curation.ipynb 02_eda.ipynb && cd ..

# Parts B, C: warehouse
scripts/setup_postgres.sh                                       # PostgreSQL 16 + role/database "foodsafety"
python3 etl/run_etl.py all                                      # schema, initial load, validation, incremental load, idempotency test
python3 etl/model_comparison.py                                 # snowflake copy + measured star / snowflake / constellation comparison
python3 etl/run_queries.py                                      # analytical SQL timing and indexing effect
python3 etl/fault_test.py                                       # failed load leaves no partial data
python3 etl/run_olap.py                                         # OLAP operations -> docs/olap_operations.md
PGPASSWORD=foodsafety psql -h localhost -U foodsafety -d foodsafety -f sql/08_analytics_mart.sql   # analytical mart

# Part D: distribution-key analysis and centralized baseline, then the Citus cluster
python3 etl/distributed_baseline.py
# Citus needs the PGDG build of PostgreSQL 16 plus the package postgresql-16-citus-13.2 (see docs/distributed_warehouse.md)
scripts/setup_citus_cluster.sh && python3 etl/distributed_citus.py

# Part E: real-time stack and replay
scripts/install_tools.sh                                        # downloads Kafka, ClickHouse, Grafana; verifies checksums
scripts/start_realtime_stack.sh                                 # ClickHouse, Kafka, Spark job, Grafana
python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150
python3 streaming/measure_streaming.py                          # open http://127.0.0.1:3000/d/food-safety-rt

# Parts F-I
python3 dashboard/build_dashboard.py
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 07_regression.ipynb 08_association_mining.ipynb 09_decision_tree.ipynb && cd ..

# documents
python3 build_docs/make_batch_docs.py && python3 build_docs/make_distributed_doc.py && python3 build_docs/make_realtime_doc.py && python3 build_docs/make_findings.py && python3 build_docs/make_architecture_doc.py && python3 build_docs/make_technical_report.py
```

The raw and curated CSV files (about 100 MB) and the downloaded tools in `runtime/` are not stored in git; the commands above recreate them. The portal data is updated over time, so a later download can differ slightly from the file fingerprinted in `docs/dataset_source.md`.

## Honest notes
* The official dataset is a **historical file**. The real-time layer replays it and says so on the dashboard and in every event (`source_mode = REPLAY_SIMULATION`).
* Citus was installed from its official repository, which needs the PostgreSQL community (PGDG) build of PostgreSQL 16; both repositories were added with explicit approval and the PostgreSQL 16 packages were replaced by the PGDG build of the same minor version (16.15).
* Volumes above 61,737 rows in the performance experiment are a **synthetic scale-up** by resampling real fact rows. They were used for query timing only.
* All timings come from one 4-core machine, so they compare the designs under equal conditions but are not production capacity.
* Earlier course assignments in this repository (EDA Assignments 4-6) used the Kaggle snapshot of the same dataset (2010-2019); this project uses the official portal and the period prescribed in the project document.
