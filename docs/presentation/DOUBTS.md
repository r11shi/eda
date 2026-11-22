# Doubts & Answers

Every question mam may ask, with a short answer. Owner in brackets: pass the question to that person.

## The project

**What is the project?** Chicago food inspections 2022-2025 (73,630 rows): we cleaned them, built a data warehouse, answered 10 business questions with SQL and OLAP, trained three models, and compared three kinds of warehouse.

**Why this dataset?** It is official open data, large enough for a warehouse, and has dates, places, categories and outcomes, which every part of the brief needs.

**What tools?** Python (pandas, scikit-learn, mlxtend) in Jupyter; PostgreSQL; Citus; Kafka, Spark, ClickHouse, Grafana; an HTML dashboard with Plotly. Everything runs in Ubuntu on Windows (WSL).

**How do you run it?** `Start_Project.cmd` starts the servers; `Project_Menu.cmd` runs one part; `python run_all.py` runs the batch part in 10 minutes.

**What is the main finding?** The fail rate is 23.1% and fell from 24.9% to 21.1%; complaint inspections fail most (37.6%); after a fail, 79% of next visits pass.

## Part A: data and cleaning (Omkar)

**What problems did the data have?** Visits that never happened, an invalid risk code "All", "Chicago" spelled several ways, 217 hand-typed facility types, violations as one long text, 29 duplicate reports.

**Did you delete bad rows?** Only the 29 duplicates. Invalid codes became Unknown; visits that never happened are kept but not counted.

**How did you count violations?** Split the text at "|" and count the rule numbers at the start of each piece.

**Fail with no violation text?** Count = unknown (552 rows), not 0, because a fail always has violations.

**What is a derived attribute?** A column we calculated, e.g. violation band, season, result group, area.

**How is the area defined?** The quadrant of Chicago's street grid around State & Madison: NorthWest, NorthEast, SouthWest, SouthEast.

**What did EDA show?** Volume rose about 12% in four years; restaurants get 7 in 10 inspections; weekends are empty; most inspections have 0-5 violations; fails have more.

## Parts B, C, F: warehouse, ETL, OLAP (Aryan)

**What is a data warehouse?** A database designed for analysis: questions about many records at once.

**What is the grain?** One completed inspection of one place on one date.

**Fact vs dimension?** Fact = events with numbers (fail_count, violation_count). Dimension = descriptions (date, facility, type, result, location).

**Why a star schema?** Small fact table, each description stored once, every question is a simple join. The snowflake needed 9 joins instead of 3 and was about twice as slow.

**What is a fact constellation?** Two fact tables sharing dimensions; our second is one place per year, which made yearly questions about 7× faster.

**Surrogate key?** A simple number the warehouse assigns (facility_key = 4927); small, fast, independent of the city's ids.

**What is the Unknown row?** Row 0 in every dimension, so a missing value never drops a fact.

**What is ETL here?** Extract: COPY the clean file into staging. Transform + Load: one SQL procedure adds new places and inserts facts with looked-up keys.

**Initial vs incremental load?** Initial: Jan 2022-Nov 2025 (60,608). Incremental: only Dec 2025 (1,129), without rebuilding.

**How do you know it's correct?** Five checks after each load, all 0: no missing keys, no duplicates, nothing left in staging, totals match, the two facts agree.

**Why indexes?** A lookup went from about 6.5 ms to 0.5 ms.

**What is OLAP?** Same numbers at different levels: roll-up (month → year), drill-down, slice (one value), dice (several), pivot (rows → columns), CUBE (all subtotals).

**How did you do roll-up in SQL?** `GROUP BY ROLLUP (year, quarter)`.

**Why HTML dashboard, not Power BI?** Opens anywhere, reads the same warehouse, has the four required sections.

## Parts G, H, I: models (Vishwaraj)

**What data do the models use?** One table built from the warehouse, where each inspection also has the previous inspection's result, violations and days since (SQL LAG).

**Why split by time?** A random split would let the model see the future. Train on the past, test on 2025.

**Regression result?** MAE 2.45 vs 2.71 for guessing the average; R² 0.12.

**Why is R² low?** The real causes (cleanliness, staff) are not in the data.

**What is one-hot encoding?** Turning a word column into 0/1 columns, one per value.

**Support / confidence / lift?** How often together / how often the rule is true / how many times more than chance.

**Best rule?** 10+ violations ⇒ Fail: 69% confidence, lift 3.0.

**Apriori vs FP-Growth?** Same 1,198 itemsets; Apriori grows sets level by level, FP-Growth uses a tree without generating candidates.

**Decision tree result?** AUC 0.635; at cut-off 0.217 it catches 61% of fails.

**Why not accuracy?** Always saying "pass" is already 79% accurate.

**What is overfitting?** Memorising training data: a depth-20 tree scored 0.85 on training but 0.57 on 2024.

**Most important input?** Whether the previous inspection failed.

**Why change the cut-off from 0.5?** Only about 21% fail, so the tree rarely says above 50%; at 0.5 it caught only 4% of fails.

## Parts D, E, J: Citus and real-time (Rushi)

**What is Citus?** An extension that turns PostgreSQL into a cluster: one coordinator, two workers.

**What is a shard?** One of 32 pieces of the fact table; 16 per worker.

**Reference table?** A small table copied to every node so joins stay local; all dimensions are reference tables.

**Why facility_key as distribution key?** 17,084 values, spreads rows evenly; date and location gave skewed shards.

**Is Citus faster?** All 25 test queries gave identical answers; slower on small data (coordination), mostly faster from about 500,000 rows. Our nodes share one laptop.

**Where do rows above 61,737 come from?** Copies of real rows, only to time queries, never for analysis.

**Is the real-time part live?** No, a labelled replay of Oct-Dec 2025, because the city's data is historical.

**What does each tool do?** Kafka holds messages, Spark checks and counts them every 2 s, ClickHouse stores them, Grafana shows them every 5 s.

**Bad messages?** Go to `invalid_events` with a reason; all 24 test messages were caught.

**How fast?** About 1.8 seconds from sending to Grafana.

**Which warehouse would you recommend?** Batch as the main system; real-time only for live monitoring; Citus only when data outgrows one server.

**Hardest part?** Citus had no package for our Ubuntu version, so we built it from source.

## If you don't know

Say: *"That part was done by [name], they can explain it better,"* and look at them.
