# Project Quick Guide: What We Did, What Is in Each File, Basic Answers
**Rushikesh Maddewad | PRN 202502040037 | Roll 353.** Short on purpose: read it in 15 minutes and you can answer the basic questions.

---

## 1. What we did, in plain words

**Topic:** Food Safety and Restaurant Inspection Analytics, using the official City of Chicago Food Inspections data, 2022-2025 (73,630 records; **61,737 completed inspections**).

**Goal:** build a data warehouse for the data, build it three different ways, compare them, then use it to answer questions and train three small data-mining models.

| Step | What we did | Result in one line |
|---|---|---|
| **A. Data and cleaning** | Downloaded the data, checked quality, fixed problems (duplicates, missing values, invalid codes), created new columns (violation count, bands, season, area). | Every cleaning rule has a count and a reason. |
| **B. Design** | Designed star, snowflake and fact-constellation models and measured them. | **Fact constellation** chosen: 2x faster than snowflake. |
| **C. Batch warehouse** | Built it in PostgreSQL: staging, ETL procedure, indexes, 16 checks, incremental load. | 60,608 facts + 1,129 added later; all checks 0 failures. |
| **D. Distributed** | Same warehouse on a 3-node Citus cluster, 32 shards, split by `FacilityKey`. | Identical results, but **not faster** (one machine, shared CPU). |
| **E. Real-time** | Replayed inspections through Kafka, Spark Streaming, ClickHouse, Grafana. | 1.5 s average delay; 24/24 bad events rejected. |
| **F. OLAP and dashboard** | Roll-up, drill-down, slice, dice, pivot, CUBE; HTML dashboard. | Ten findings written up. |
| **G. Regression** | Predict the number of violations. | R-squared 0.12 (weak). |
| **H. Association rules** | Apriori and FP-Growth on inspection attributes. | 10+ violations => Fail (69%, lift 3.0). |
| **I. Decision tree** | Predict whether an inspection fails. | AUC 0.64 (weak, only a ranking aid). |
| **J. Evaluation** | Compared the three architectures. | **Hybrid, with the batch warehouse as the centre.** |

**Pipeline:**
```
Raw CSV -> cleaning (Python) -> staging -> load procedure -> warehouse (PostgreSQL)
        -> OLAP + dashboard + findings
        -> flat "mart" table -> regression / association rules / decision tree
Same data also through:  Citus (distributed)   and   Kafka -> Spark -> ClickHouse -> Grafana (real-time)
```

---

## 2. Folder structure: what is in each file

```
EDA/Project/
├── README.md                      status of each part, deliverable map, how to reproduce
├── Food_Safety_Project_Colab.ipynb   ALL code in one Colab notebook (single-file version)
├── scripts/                       set-up helpers
├── etl/                           Python: cleaning, loading, measuring
├── sql/                           SQL: schema, load procedure, queries, mart
├── streaming/                     real-time code (Kafka, Spark, ClickHouse, Grafana)
├── notebooks/                     Jupyter notebooks with the analysis
├── dashboard/                     the HTML dashboard + Power BI rebuild package
├── docs/                          reports, presentation, write-ups, images
└── results/                       raw measurement CSVs behind every number
```

### scripts/
| File | What it does |
|---|---|
| `fetch_data.py` | Downloads the official data from the Chicago Data Portal. |
| `setup_postgres.sh` | Starts PostgreSQL and creates the `foodsafety` user and database. |
| `setup_citus_cluster.sh` | Creates the Citus coordinator + 2 workers. |
| `install_tools.sh` | Downloads Kafka, ClickHouse and Grafana. |
| `start_realtime_stack.sh`, `start_grafana.sh` | Start the real-time services. |

### etl/ (Python)
| File | What it does |
|---|---|
| `curation.py` | **Cleaning rules** and the derived columns. The heart of Part A. |
| `run_etl.py` | **Batch ETL driver**: stage, load, validate, incremental load, repeat-load test. |
| `model_comparison.py` | Measures star vs snowflake vs constellation. |
| `run_queries.py` | Runs and times the 8 analytical queries and the indexing test. |
| `run_olap.py` | Runs the OLAP queries and writes `docs/olap_operations.md`. |
| `fault_test.py` | Proves a failed load leaves no partial data. |
| `distributed_baseline.py`, `distributed_citus.py` | Choose the distribution key; compare Citus with one node. |

### sql/
| File | What it does |
|---|---|
| `01_schema.sql` | Creates staging, **dimensions** (date, facility, location, inspection type, result), **facts**, Unknown members. |
| `02_load_batch.sql` | **The load procedure** `dw.load_batch`: apply rules, add dimension rows, load facts. |
| `03_indexes.sql` | Indexes. |
| `04_validation.sql` | The 16 integrity checks. |
| `05_snowflake_schema.sql` | Snowflake version for comparison. |
| `06_analytical_queries.sql` | The 8 business queries. |
| `07_olap_queries.sql` | Roll-up, drill-down, slice, dice, pivot, CUBE, GROUPING SETS. |
| `08_analytics_mart.sql` | Flat table for the models; adds "previous inspection" features with `lag()`. |

### streaming/
| File | What it does |
|---|---|
| `producer.py` | **Replays** inspections into Kafka (a simulation; it can inject bad events). |
| `spark_stream.py` | **Spark job**: validates events (7 rules), computes windows, writes to ClickHouse. |
| `clickhouse_ddl.sql`, `init_clickhouse.py` | ClickHouse tables. |
| `measure_streaming.py` | Measures the delay and rejected events. |
| `grafana/` | Dashboard definition and data-source config. |

### notebooks/
`01_data_curation` (profiling and cleaning), `02_eda` (exploratory analysis), `07_regression`, `08_association_mining`, `09_decision_tree`.

### dashboard/
`food_safety_dashboard.html` (open in any browser, works offline), `build_dashboard.py` (builds it from the warehouse), `powerbi/` (CSV exports and rebuild steps).

### docs/
| File | What it is |
|---|---|
| `Technical_Report.pdf` | **The main report** (8 pages). |
| `Presentation.pptx` | The 12-slide presentation. |
| `Presenter_Guide.pdf`, `Theory_Study_Guide.pdf`, `Project_Quick_Guide.pdf` | Study material for you. |
| `data_dictionary.md`, `data_quality_report.md`, `dataset_source.md` | Data documentation. |
| `dimensional_models.md`, `batch_warehouse.md`, `distributed_warehouse.md`, `realtime_warehouse.md` | Write-up of each part. |
| `olap_operations.md`, `ten_findings.md` | OLAP results and the ten findings. |
| `architecture_comparison.md`, `domain_recommendations.md` | Part J. |
| `images/`, `make_*.py` | Figures, and the scripts that generate the documents. |

### results/
CSV files with the raw measurements (load times, validation results, query times, Citus timings, streaming latency, model metrics). If anyone asks "where does this number come from?", the answer is here.

---

## 3. Basic questions and short answers

1. **What is the project about?** A data warehouse and analytics system for Chicago restaurant inspection data, built three ways and compared.
2. **What is a data warehouse?** A database designed for analysis of history, not for day-to-day transactions.
3. **What is ETL?** Extract, Transform, Load: take the raw data, clean it, load it into the warehouse.
4. **What are fact and dimension tables?** Facts hold the measurable events (one row per inspection); dimensions hold the descriptions to slice by (date, facility, location, type, result).
5. **What is the grain?** One completed inspection on one date.
6. **Which schema did you choose and why?** Fact constellation: star schema plus a second fact table by facility and year. It is about 2x faster than snowflake and answers yearly questions about 8x faster.
7. **Which database?** PostgreSQL 16 for batch; Citus for distributed; ClickHouse for real-time.
8. **What is the incremental load?** Loading only the newest month without rebuilding. December 2025 added 1,129 rows and the earlier rows stayed unchanged.
9. **What is OLAP?** Analysing facts by slicing along dimensions: roll-up, drill-down, slice, dice, pivot, CUBE.
10. **What is Kafka? Spark? ClickHouse? Grafana?** Kafka: message queue. Spark: processes the stream (validates, aggregates). ClickHouse: fast database for the results. Grafana: live dashboard.
11. **Is the real-time part really live?** No. It replays historical data like a live feed, and says so everywhere. The pipeline itself ran end to end.
12. **What is Citus and did it help?** It splits tables across servers (shards). Results were identical, but not faster, because all nodes shared one machine. It would help only when data outgrows one server.
13. **Why `FacilityKey` as the distribution key?** Most distinct values (17,083) and the most even shards.
14. **Why no Power BI file?** Power BI Desktop only runs on Windows. I built an equivalent HTML dashboard and a rebuild package.
15. **What did the models show?** Regression R-squared 0.12, decision tree AUC 0.64: what is known before an inspection only weakly predicts the result. They are a ranking aid, not a decision tool.
16. **Name two findings.** The fail rate fell from 24.9% to 21.1% (2022 to 2025). After a failed inspection, the next visit passes 79% of the time.
17. **What is your recommendation?** Batch warehouse at the centre; add real-time only for live monitoring; add distribution only when data outgrows one machine.
18. **What are the limitations?** Historical data (replay), one machine for all timings, no Power BI file, synthetic scale-up used only for timing.
19. **Where is the code?** `EDA/Project` repository, or the single Colab notebook `Food_Safety_Project_Colab.ipynb`.
20. **How can it be reproduced?** The README lists the commands; the Colab notebook does it with *Run all*.

## 4. Ten numbers
**61,737** inspections | **2 facts + 5 dimensions** | **60,608 + 1,129** facts loaded | **16 checks, 0 failures** | **10-74 ms** batch queries | **4 of 25** tests where Citus was faster | **1.5 s** real-time delay | **24.9% to 21.1%** fail rate | **69%** fail with 10+ violations | **R² 0.12 / AUC 0.64**
