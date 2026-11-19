"""Builds the single-file Colab notebook Food_Safety_Project_Colab.ipynb: every source file of the project is written out by a
%%writefile cell and run in order, and the analysis notebooks (curation, EDA, regression, association rules, decision tree) are
embedded as normal cells.  Run:  python docs/make_colab_notebook.py   (then execute it, e.g. with nbconvert, to store the outputs)."""
from pathlib import Path
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell as md, new_code_cell as code

P = Path(__file__).resolve().parents[1]
cells = []
read = lambda rel: (P / rel).read_text()


def writefile(rel, why):
    cells.append(md(f"**`{rel}`**: {why}"))
    cells.append(code(f"%%writefile Project/{rel}\n" + read(rel).rstrip("\n") + "\n"))


def embed(nb_name, skip_title=True):
    nb = nbformat.read(P / "notebooks" / f"{nb_name}.ipynb", 4)
    for i, c in enumerate(nb.cells):
        cells.append(md(c.source) if c.cell_type == "markdown" else code(c.source))


def results_table(rel, title):
    cells.append(code(f'import io, pandas as pd\n# recorded measurement from the author\'s machine ({rel})\nprint("{title}")\npd.read_csv(io.StringIO("""{read(rel)}"""))'))


cells.append(md("""# Food Safety and Restaurant Inspection Analytics: Integrated Data Warehouse, OLAP and Data Mining Project
**Rushikesh Maddewad** | PRN 202502040037 | Roll No 353 | Data: City of Chicago Food Inspections (official Data Portal), 2022-2025

**This is the single-file version of the whole project.** Every source file of the project (Python, SQL, shell) is written out by a `%%writefile` cell and then run, so the notebook alone reproduces the work. The same code is also available as a normal repository (`EDA/Project`).

**How to run (Google Colab):** *Runtime > Run all*. It takes about 10 minutes. It installs PostgreSQL inside Colab, downloads the official data, and builds everything.

| Section | What it does |
|---|---|
| 0 | Set-up: libraries, PostgreSQL |
| A | Download, profiling, curation, EDA |
| B, C | Dimensional models and the PostgreSQL batch warehouse (ETL, validation, incremental load, indexing, timing) |
| F | OLAP queries and the HTML dashboard |
| G, H, I | Regression, association-rule mining (Apriori, FP-Growth), decision tree, all on the analytical mart |
| D, E | Distributed warehouse (Citus) and real-time warehouse (Kafka, Spark, ClickHouse): code is saved here, **but not run in Colab** (they need several servers); my recorded measurements are shown |
| J | Architecture comparison and recommendation |

**Honest notes:** the real-time part is a replay of historical data; Citus ran on one machine and was not faster than one node; there is no Power BI `.pbix` (Power BI Desktop is Windows-only), the HTML dashboard replaces it."""))

# ------------------------------------------------------------------ 0 setup
cells.append(md("## 0. Set-up\nFolder layout, libraries and a local PostgreSQL server (in Colab it is installed with apt; elsewhere an existing server on port 5432 is used)."))
cells.append(code('''import os, sys, pathlib
IN_COLAB = "google.colab" in sys.modules
WORK = pathlib.Path("/content") if IN_COLAB else pathlib.Path.cwd()
os.chdir(WORK)
for d in ["etl", "sql", "scripts", "streaming", "notebooks", "data/raw", "data/curated", "results/analytical_query_results", "docs", "dashboard"]:
    os.makedirs(f"Project/{d}", exist_ok=True)
print("working folder:", WORK, "| Colab:", IN_COLAB)'''))
cells.append(code("%pip install -q psycopg2-binary mlxtend statsmodels plotly"))
cells.append(code('''%%bash
# PostgreSQL: installed only if no server answers on localhost:5432
if ! pg_isready -q -h localhost -p 5432; then
  apt-get -qq update && apt-get -qq install -y postgresql > /dev/null
  service postgresql start; sleep 4
fi
su postgres -c "psql -tc \\"SELECT 1 FROM pg_roles WHERE rolname='foodsafety'\\"" | grep -q 1 || su postgres -c "psql -c \\"CREATE ROLE foodsafety LOGIN PASSWORD 'foodsafety' SUPERUSER;\\""
su postgres -c "psql -tc \\"SELECT 1 FROM pg_database WHERE datname='foodsafety'\\"" | grep -q 1 || su postgres -c "psql -c \\"CREATE DATABASE foodsafety OWNER foodsafety;\\""
PGPASSWORD=foodsafety psql -h localhost -U foodsafety -d foodsafety -tc "select version()"'''))

# ------------------------------------------------------------------ A
cells.append(md("# Part A. Dataset, profiling, curation and EDA"))
writefile("scripts/fetch_data.py", "downloads the official records for 1 Jan 2022 - 31 Dec 2025 from the City of Chicago Data Portal (Socrata API).")
cells.append(code('''# the download is skipped when the file already exists (a later download can differ slightly because the portal is updated)
if not pathlib.Path("Project/data/raw/food_inspections_2022_2025.csv").exists():
    !python Project/scripts/fetch_data.py
else:
    print("raw file already present, download skipped")'''))
writefile("etl/curation.py", "the curation library: loading, cleaning rules (each counted and justified), derived attributes (violation count, bands, groups, area, season).")
cells.append(md("Next come the curation notebook and the EDA notebook of the project, embedded as they are. They use relative paths, so the working folder is changed to `Project/notebooks` first."))
cells.append(code('os.chdir(WORK / "Project" / "notebooks")\nprint(os.getcwd())'))
embed("01_data_curation")
embed("02_eda")
cells.append(code("os.chdir(WORK)"))

# ------------------------------------------------------------------ B, C
cells.append(md("# Parts B and C. Dimensional models and the PostgreSQL batch warehouse\nSelected model: **fact constellation** (star schema + a facility-by-year fact). The snowflake is built too, to measure the comparison."))
writefile("sql/01_schema.sql", "staging tables, dimensions with Unknown members, the two fact tables, date dimension.")
writefile("sql/02_load_batch.sql", "the PL/pgSQL load procedure `dw.load_batch`: data-quality rules, dimension inserts, fact load, annual fact. Used for the initial and the incremental load.")
writefile("sql/03_indexes.sql", "indexes on the fact table.")
writefile("sql/04_validation.sql", "the integrity and reconciliation checks (all must return 0).")
writefile("sql/05_snowflake_schema.sql", "the snowflake copy of the model, used for the star / snowflake / constellation comparison.")
writefile("etl/run_etl.py", "the batch ETL driver: stage, load, validate, incremental load of the held-back month (Dec 2025), idempotency test.")
cells.append(code("!python Project/etl/run_etl.py all"))
writefile("etl/model_comparison.py", "measures star vs snowflake vs fact constellation (tables, joins, storage, query time).")
cells.append(code("!python Project/etl/model_comparison.py"))
writefile("etl/fault_test.py", "forces a failing load and proves that it leaves no partial data (atomic load).")
cells.append(code("!python Project/etl/fault_test.py"))
writefile("sql/06_analytical_queries.sql", "the eight analytical queries for the mandatory business questions.")
writefile("etl/run_queries.py", "runs and times the analytical queries and the indexing experiment.")
cells.append(code("!python Project/etl/run_queries.py\nimport pandas as pd\npd.read_csv('Project/results/batch_query_timing.csv')"))
cells.append(code('''import pandas as pd
for f in ["load_audit", "validation_results", "model_comparison", "indexing_effect", "fault_test"]:
    print("=====", f); display(pd.read_csv(f"Project/results/{f}.csv"))'''))

# ------------------------------------------------------------------ F
cells.append(md("# Part F. OLAP and dashboard\nRoll-up, drill-down, slice, dice, pivot, CUBE and GROUPING SETS. Each block in the SQL file is documented as question, dimensions, measures, operation, DAX, SQL and interpretation. (DAX is written for Power BI but was not executed.)"))
writefile("sql/07_olap_queries.sql", "the OLAP operations.")
writefile("etl/run_olap.py", "runs each OLAP block and writes `docs/olap_operations.md`.")
cells.append(code("!python Project/etl/run_olap.py\nprint(open('Project/docs/olap_operations.md').read()[:6000])"))
writefile("dashboard/build_dashboard.py", "builds the self-contained HTML dashboard (4 sections) from the warehouse.")
cells.append(code('''!python Project/dashboard/build_dashboard.py
if IN_COLAB:
    from google.colab import files
    files.download("Project/dashboard/food_safety_dashboard.html")
else:
    print("dashboard written to Project/dashboard/food_safety_dashboard.html")'''))

# ------------------------------------------------------------------ mart + G,H,I
cells.append(md("# Analytical mart (input of Parts G, H, I)\nOne flat table with one row per completed inspection, **generated from the warehouse**. Prior-history features use only strictly earlier inspections of the same facility, so there is no leakage."))
writefile("sql/08_analytics_mart.sql", "creates `mart.food_inspection_analytics_mart` with window functions (`lag`, running count).")
cells.append(code('''import psycopg2
conn = psycopg2.connect("host=localhost port=5432 dbname=foodsafety user=foodsafety password=foodsafety"); conn.autocommit = True
cur = conn.cursor(); cur.execute(open("Project/sql/08_analytics_mart.sql").read())
cur.execute("select count(*), min(inspection_date), max(inspection_date) from mart.food_inspection_analytics_mart"); print(cur.fetchone())'''))
cells.append(code('os.chdir(WORK / "Project" / "notebooks")'))
cells.append(md("# Part G. Regression: predicting the number of violations"))
embed("07_regression")
cells.append(md("# Part H. Association-rule mining: Apriori and FP-Growth"))
embed("08_association_mining")
cells.append(md("# Part I. Decision tree: predicting a failed inspection"))
embed("09_decision_tree")
cells.append(code("os.chdir(WORK)"))

# ------------------------------------------------------------------ D
cells.append(md("""# Part D. Distributed data warehouse (Citus): code and recorded results
**Not executed in Colab.** It needs a 3-node Citus 13.2 cluster on the PostgreSQL community (PGDG) build of PostgreSQL 16. The cells below only save the code; the measured results from my machine follow.

Design: coordinator + 2 workers on one machine, 32 shards, the fact table distributed by `FacilityKey`, the five dimensions as reference tables."""))
writefile("scripts/setup_citus_cluster.sh", "creates the coordinator and two workers and registers the workers.")
writefile("etl/distributed_baseline.py", "distribution-key analysis (shard skew by simulating Citus' hash) and the centralized scaling baseline.")
writefile("etl/distributed_citus.py", "loads the Citus cluster and times the same five queries at 61,737 to 2,000,000 rows; checks that results are identical.")
results_table("results/distribution_key_experiment.csv", "Distribution-key experiment (which key gives the most even shards)")
results_table("results/distributed_scaling.csv", "Citus vs centralized timings (ms) over the data volumes")
cells.append(md("**Reading the result:** all 25 distributed results were identical to the centralized ones, but Citus was clearly faster in only 4 of 25 cases and slower in 16, because the workers shared the same 4 CPU cores, so there was no extra hardware, only extra coordination. Volumes above 61,737 rows are a synthetic scale-up (resampled real facts) used for timing only."))

# ------------------------------------------------------------------ E
cells.append(md("""# Part E. Real-time data warehouse: code and recorded results
**Not executed in Colab.** It needs Kafka 3.9 (KRaft), Spark 4.0.1, ClickHouse 26.3 and Grafana 11.3 (about 2.5 GB of memory). The cells below only save the code.

Flow: `producer.py` **replays** historical inspections into Kafka topic `food_inspections` (a simulation: every event carries `source_mode = REPLAY_SIMULATION`) -> `spark_stream.py` validates (7 rules), derives measures, aggregates 10-second and daily windows -> ClickHouse -> Grafana."""))
writefile("scripts/install_tools.sh", "downloads Kafka, ClickHouse and Grafana and verifies checksums.")
writefile("scripts/start_realtime_stack.sh", "starts ClickHouse, Kafka, the Spark job and Grafana.")
writefile("scripts/start_grafana.sh", "starts Grafana with the provisioned data source and dashboard.")
writefile("streaming/clickhouse_ddl.sql", "ClickHouse tables (events, invalid events, window aggregates, daily aggregates).")
writefile("streaming/init_clickhouse.py", "creates the ClickHouse tables.")
writefile("streaming/producer.py", "the Kafka producer (replay of historical inspections; can inject malformed test events).")
writefile("streaming/spark_stream.py", "the Spark Structured Streaming application.")
writefile("streaming/measure_streaming.py", "measures latency, completeness and rejected events.")
results_table("results/streaming_metrics.csv", "Real-time measurements from the replay (3,647 events at 80 per second)")

# ------------------------------------------------------------------ J
cells.append(md("""# Part J. Architecture evaluation and recommendation

| Parameter | Batch (PostgreSQL) | Distributed (Citus) | Real-time (Kafka, Spark, ClickHouse) |
|---|---|---|---|
| Latency | periodic (ETL of one month: 0.5 s) | same bulk-load pattern | **1.5 s average**, p95 2.5 s |
| Historical analytics | excellent, 10-74 ms per query | identical results, not faster here | operational window only |
| Live monitoring | none until next batch | none | excellent, dashboard queries 6-7 ms |
| Scalability (measured) | 2,000,000 rows (32 x the real data) still 174-269 ms | no gain on one machine | high in design, not stress-tested |
| Complexity | low: one database | medium | high: four services, about 2.5 GB |

**Recommendation: a hybrid with the batch warehouse at the centre.** Use the batch PostgreSQL warehouse as the system of record; add the real-time layer only for operational monitoring if inspections are recorded digitally as they happen; add distribution only when the data outgrows one node (Chicago has about 16,000 inspections a year, so one node is enough for decades).

**Limitations:** the dataset is historical (the real-time layer is a replay); one 4-core machine ran every component; no Power BI file; the Citus and streaming parts were measured outside this notebook."""))

nb = new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"},
                                         "colab": {"provenance": []}})
out = P / "Food_Safety_Project_Colab.ipynb"
nbformat.write(nb, out)
print("written", out, len(cells), "cells")
