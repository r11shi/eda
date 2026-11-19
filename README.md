# Food Safety and Restaurant Inspection Analytics

Integrated data warehouse, OLAP and data mining project on the City of Chicago Food Inspections open data (1 January 2022 to 31 December 2025:
73,630 records, 61,737 completed inspections).

**Rushikesh Maddewad** | PRN 202502040037 | Roll No 353

One lifecycle: *raw data > profiling > curation > staging > dimensional warehouse (PostgreSQL) > OLAP and dashboard > analytical mart > regression, association rules, decision tree*,
plus a distributed warehouse (Citus) and a real-time warehouse (Kafka, Spark, ClickHouse, Grafana) built on the same data and compared.

| Start here | |
|---|---|
| `docs/Food_Safety_Analytics_Report.pdf` | the full project report (Word version: `.docx`); `docs/Technical_Report.pdf` is the 8-page summary |
| `docs/Presentation.pptx` | the slides |
| `dashboard/food_safety_dashboard.html` | the dashboard: double-click, it opens in any browser |
| `Food_Safety_Project_Colab.ipynb` | all the code in one notebook, saved with its outputs |
| `docs/guides/` | study guides and question bank |

---

## 1. Run it on your machine

You need **Python 3.10 or newer** and **a PostgreSQL 16 database** (any recent version works). The raw data is bundled in `data/raw/`, so no download is needed and the numbers match the report.
Pick **one** way to get the database (A is the least work if you have Docker).

### Step 1. Install the Python packages
```bash
git clone https://github.com/r11shi/eda.git
cd eda
python -m venv .venv                       # optional but recommended
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2. Get PostgreSQL with the user the project expects
The project connects to host `localhost`, port `5432`, database `foodsafety`, user `foodsafety`, password `foodsafety`.

**Option A: Docker** (recommended)
```bash
docker compose up -d db
```

**Option B: PostgreSQL installed on your computer**

*Ubuntu / Debian / WSL*
```bash
sudo apt-get update && sudo apt-get install -y postgresql
sudo service postgresql start
sudo -u postgres psql -c "CREATE ROLE foodsafety LOGIN PASSWORD 'foodsafety' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE foodsafety OWNER foodsafety;"
```
*macOS (Homebrew)*
```bash
brew install postgresql@16 && brew services start postgresql@16
psql postgres -c "CREATE ROLE foodsafety LOGIN PASSWORD 'foodsafety' SUPERUSER;"
psql postgres -c "CREATE DATABASE foodsafety OWNER foodsafety;"
```
*Windows*: install PostgreSQL from postgresql.org, open **SQL Shell (psql)** and run the two `CREATE` statements above. Or use Option A with Docker Desktop.

**Option C: a database that already exists** (different host, port or password): copy `.env.example` to `.env` and edit the `FS_DB_*` values.

### Step 3. Run everything
```bash
python run_all.py
```
It checks your set-up first and tells you exactly what is missing. It takes about **5 minutes** and runs these steps in order:

| Step | What it does |
|---|---|
| Data | unpacks `data/raw/food_inspections_2022_2025.csv.gz` (downloads from the portal only if the bundle is missing) |
| Notebook 01 | profiles and cleans the data, writes `data/curated/inspections_curated.csv` |
| Notebook 02 | exploratory analysis |
| `etl/run_etl.py` | creates the warehouse, loads Jan 2022 to Nov 2025, validates, loads Dec 2025 (incremental), repeats it (idempotency), validates again |
| `etl/model_comparison.py` | measures star vs snowflake vs fact constellation |
| `etl/run_queries.py` | times the 8 analytical queries and the effect of indexes |
| `etl/fault_test.py` | proves a failed load leaves no partial data |
| `etl/run_olap.py` | roll-up, drill-down, slice, dice, pivot, CUBE, GROUPING SETS |
| `sql/08_analytics_mart.sql` | builds the flat table used by the models |
| `dashboard/build_dashboard.py` | builds the HTML dashboard |
| Notebooks 07, 08, 09 | regression, association rules (Apriori, FP-Growth), decision tree |

Options: `python run_all.py --check` (only test the set-up), `--docker` (start the container for you), `--skip-eda`, `--skip-models` (faster). It is safe to run again.

### Where the results appear
- `results/` : every measurement as a CSV (load audit, validation checks, query times, model metrics, ...)
- `dashboard/food_safety_dashboard.html` : the dashboard
- `notebooks/` : the executed notebooks with their outputs
- `docs/olap_operations.md` : the OLAP queries with their output

### No setup at all: Google Colab
Open `Food_Safety_Project_Colab.ipynb` in Google Colab and choose *Runtime > Run all*. It installs PostgreSQL inside Colab and runs the batch, OLAP and mining parts (about 10 minutes). Citus and the real-time stack are not run there.

---

## 2. What is in the repository

```
run_all.py                 one command for the batch part
requirements.txt           Python packages
docker-compose.yml         PostgreSQL 16 with the expected user and database
.env.example               database settings (optional)
data/raw/                  the bundled raw data (.csv.gz) and the source metadata
etl/                       config, ETL driver, model comparison, query timing, fault test, OLAP runner, Citus scripts
sql/                       01 schema ... 08 analytical mart (PostgreSQL, PL/pgSQL load procedure)
notebooks/                 01 curation, 02 EDA, 07 regression, 08 association rules, 09 decision tree
dashboard/                 HTML dashboard builder and the finished dashboard, Power BI rebuild package
streaming/                 Kafka producer, Spark job, ClickHouse tables, Grafana dashboard (Part E)
scripts/                   set-up helpers for PostgreSQL, Citus, Kafka, ClickHouse, Grafana
results/                   raw measurements behind every number
docs/                      report, presentation, write-ups, images, guides/
build_docs/                scripts that regenerate the documents (optional)
Food_Safety_Project_Colab.ipynb    the single-file version
```

### Status of the project parts

| Part | Status |
|---|---|
| A. Dataset, curation, EDA | Done |
| B. Dimensional models (star, snowflake, fact constellation) | Done; the snowflake is built physically so the comparison is measured |
| C. Batch warehouse (PostgreSQL, ETL, incremental load, validation, indexing, timing) | Done |
| D. Distributed warehouse (Citus) | Done and measured: results identical to one node, but **not faster** (all nodes shared one machine) |
| E. Real-time warehouse (Kafka, Spark, ClickHouse, Grafana) | Done, run end to end. **A replay of historical data**, labelled as such |
| F. OLAP and dashboard | OLAP done in SQL; dashboard is an HTML page (**no Power BI .pbix**: Power BI Desktop runs only on Windows) |
| G, H, I. Regression, association rules, decision tree | Done |
| J. Architecture evaluation | Done |

A map of every required deliverable to its file is in `docs/deliverables_map.md`.

---

## 3. Optional: the distributed and real-time parts (Linux, extra servers)

`run_all.py` does not run Parts D and E because they need server software. To repeat them:

```bash
# Part D: Citus (needs the PostgreSQL community (PGDG) build of PostgreSQL 16 and the package postgresql-16-citus-13.2)
python3 etl/distributed_baseline.py            # distribution-key analysis and the single-node baseline
scripts/setup_citus_cluster.sh && python3 etl/distributed_citus.py

# Part E: Kafka 3.9, Spark 4.0.1, ClickHouse 26.3, Grafana 11.3 (Java 21, about 2.5 GB of memory)
scripts/install_tools.sh
scripts/start_realtime_stack.sh
python3 streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 80 --bad-every 150
python3 streaming/measure_streaming.py         # dashboard: http://127.0.0.1:3000/d/food-safety-rt
```
Extra packages: `clickhouse-connect kafka-python-ng`. The measured results are already in `results/`, and `docs/distributed_warehouse.md` and `docs/realtime_warehouse.md` describe them.

## 4. Regenerating the documents (optional)
```bash
pip install python-docx python-pptx pillow markdown
python build_docs/build_slides.py      # docs/Presentation.pptx
python build_docs/build_report.py      # docs/Food_Safety_Analytics_Report.docx (and the PDF copy if LibreOffice is installed)
```
Before submitting, edit the department, guide and course name at the top of `build_docs/build_report.py`.

## 5. Troubleshooting

| Message | Cause and fix |
|---|---|
| `Missing Python packages` | `pip install -r requirements.txt` |
| `Cannot connect to PostgreSQL` | the database is not running, or the user does not exist: repeat step 2, or set `.env` |
| `password authentication failed` / `role "foodsafety" does not exist` | create the role and database as shown in step 2 |
| `permission denied to create extension` or similar | the role must be a superuser, as in the `CREATE ROLE` command above |
| A notebook step fails | open `notebooks/<name>.ipynb`, read the error, fix it and run `python run_all.py` again |
| Port 5432 is already in use | stop the other server, or set `FS_DB_PORT` (and in Docker use `FS_DB_PORT=5433 docker compose up -d db`) |

## 6. Honest notes
- The official dataset is a historical file. The real-time layer replays it and says so in every event.
- Citus ran on one 4-core machine and was not faster than one node. Row counts above 61,737 in the scale test are a synthetic resampling used only for timing.
- All timings come from one machine; they compare designs under equal conditions and are not production capacity.
- The portal data is updated over time; the bundled copy keeps the report numbers reproducible.
