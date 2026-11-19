# Presenter's Guide: Food Safety Analytics Project
**For Rushikesh Maddewad (Roll 353)**. Read Parts 1-3 first (30 minutes), then Part 7 (questions). That is enough to present confidently.

---

## Part 1. The project in one minute (say this first)

> "Chicago inspects restaurants and records whether each one passes or fails. I took four years of that public data, 2022 to 2025, about 61,700 completed inspections. I cleaned it, then stored it in a **data warehouse**, a database designed for analysis rather than day-to-day transactions. I built that warehouse three ways: a normal **batch** warehouse in PostgreSQL, a **distributed** one using Citus, and a **real-time** one using Kafka, Spark and ClickHouse. I measured all three on the same data. Then I used the warehouse to answer ten business questions and to build three small data-mining models: regression, association rules and a decision tree. My conclusion is that a department like this should use a **batch warehouse as the core**, and add real-time or distributed parts only if a real need appears."

That paragraph is the whole project. Everything else is detail behind it.

---

## Part 2. Concepts you must understand (plain language)

| Term | What it means | Example from this project |
|---|---|---|
| **Data warehouse (DW)** | A database built to answer analysis questions over history (reports, trends), not to process live transactions. | `dw` schema in PostgreSQL holding all inspections. |
| **ETL** | Extract, Transform, Load: take raw data, clean/reshape it, load it into the warehouse. | `etl/curation.py` cleans; `sql/02_load_batch.sql` loads. |
| **Staging** | A holding area where raw-ish data lands before rules are applied and it is loaded into the real tables. | `staging.inspection_stg`. |
| **Fact table** | The table of *events/measurements*, one row per thing that happened, with numbers you can add up. | `fact_inspection`: one row per inspection (violation count, fail flag). |
| **Dimension table** | The table of *descriptions* you slice by: who, where, when, what type. | `dim_date`, `dim_facility`, `dim_location`, `dim_inspection_type`, `dim_result`. |
| **Grain** | What exactly one row of the fact table means. Must be stated first. | "One completed inspection on one date." |
| **Surrogate key** | A meaningless integer ID the warehouse makes up for a dimension row (instead of using business IDs). | `facility_key`. |
| **Unknown member** | A dimension row with key 0 used when a lookup fails, so facts are never thrown away. | `facility_key = 0`. |
| **Star schema** | One fact table in the middle, dimension tables around it, each one join away. Simple and fast. | 6 tables. |
| **Snowflake schema** | Same, but dimensions are split into sub-tables (normalised). Saves space, needs more joins. | 16 tables, about 2x slower here. |
| **Fact constellation** | Several fact tables sharing the same dimensions. | `fact_inspection` + `fact_facility_annual_performance` sharing `dim_facility`. **This is what I chose.** |
| **OLAP** | Interactive analysis by slicing a "cube" of facts along dimensions. | Roll-up, drill-down, slice, dice, pivot, CUBE. |
| **Roll-up / drill-down** | Roll-up: go from detail to summary (month to quarter to year). Drill-down: reverse. | R1, D1-D3 in `sql/07_olap_queries.sql`. |
| **Slice / dice** | Slice: fix one dimension (only 2025). Dice: filter on several (2025 AND restaurants AND high risk). | |
| **Incremental load** | Loading only the *new* data without rebuilding. | December 2025 loaded after the rest. |
| **Idempotent** | Running it twice gives the same result as once. | Re-loading December added 0 rows. |
| **Batch vs streaming** | Batch: process data in periodic chunks. Streaming: process each event as it arrives. | |
| **Kafka** | A message queue. A producer writes events to a "topic"; consumers read them. Buffers and keeps order. | Topic `food_inspections`. |
| **Spark Structured Streaming** | Reads a stream (here from Kafka), validates it, aggregates it over time windows. | `streaming/spark_stream.py`. |
| **ClickHouse** | A very fast column-store database for analytics on fresh data. | Stores the streamed events. |
| **Grafana** | Live dashboard tool that queries ClickHouse every 5 s. | The real-time dashboard. |
| **Citus** | A PostgreSQL extension that splits big tables into **shards** across several servers and runs queries in parallel. | Coordinator + 2 workers, 32 shards. |
| **Distribution key** | The column used to decide which shard a row goes to. | `FacilityKey`. |
| **Reference table** | A small table copied to every worker so joins stay local. | The five dimensions. |
| **Data leakage** | Accidentally letting a model see information it would not have at prediction time. | Avoided: only *earlier* inspections are used as features; train on past, test on future. |

---

## Part 3. The data and the pipeline

**Data:** City of Chicago Food Inspections, official Data Portal. 73,630 records for 2022-2025, of which **61,737 are completed inspections** (the rest are "Out of Business", "No Entry", etc., which are not assessments).

```
Raw CSV  ->  profiling & curation (Python)  ->  staging tables  ->  PL/pgSQL load procedure
   ->  dimensional warehouse (PostgreSQL)  ->  OLAP queries + dashboard + 10 findings
   ->  analytics mart (one flat table)     ->  regression / association rules / decision tree

Same data, other architectures:
   Citus (distributed copy of the warehouse)
   Producer -> Kafka -> Spark Streaming -> ClickHouse -> Grafana   (real-time)
```

### The 10 parts (A to J) — what, how, result, why

**A. Data, curation, EDA** (`etl/curation.py`, notebooks 01, 02)
- *What:* downloaded official data, checked quality, fixed problems, explored it.
- *How:* every decision is counted and justified. Examples: 29 repeated reports removed; 38 invalid risk code "All" mapped to Unknown; 552 failed/conditional inspections with no violation text got violation count = NULL (not 0, because a failure must have at least one violation); 11,864 non-assessment rows kept in staging but excluded from the fact.
- *Say:* "I did not delete rows silently; each treatment has a count and a reason."
- *Honest point:* no time-of-day exists (all 00:00:00), so I did no hourly analysis.

**B. Dimensional modelling** (`sql/01_schema.sql`, `sql/05_snowflake_schema.sql`, `etl/model_comparison.py`)
- *What:* designed star, snowflake and fact constellation; built the snowflake physically to measure.
- *Result:* star 6 tables/3 joins/37 ms; snowflake 16 tables/9 joins/78 ms; constellation = star speed plus a facility-by-year fact that answers yearly questions about 8x faster (2.7 ms vs 21.7 ms).
- *Why constellation:* snowflake is about 2x slower with 3x the joins; the second fact table gives fast yearly summaries.

**C. Batch warehouse (PostgreSQL 16)** (`sql/02_load_batch.sql`, `etl/run_etl.py`)
- *What:* the real warehouse. Load procedure does: quality rules, insert new dimension members, load facts, build the annual fact, count everything.
- *Results:* initial load 60,608 facts in 9.4 s; incremental load of Dec 2025 added 1,129 facts in 0.5 s without changing earlier rows (MD5 checksum identical); re-running Dec added 0 (idempotent); 16 validation checks all 0 failures; a deliberately failing load left tables unchanged (atomic); indexes cut selective queries from 3-5 ms to 0.2-0.3 ms; the 8 analytical queries run in 10-74 ms.

**D. Distributed warehouse (Citus)** (`scripts/setup_citus_cluster.sh`, `etl/distributed_citus.py`)
- *What:* same data on a 3-node Citus cluster (1 coordinator + 2 workers), facts split into 32 shards by `FacilityKey`, dimensions copied everywhere.
- *Why FacilityKey:* 17,083 distinct values, even shards (skew 1.10). `LocationKey` has only 252 values and one holds 3% of rows (skew 2.56), `DateKey` only has weekdays.
- *Result (be upfront):* results identical to one node in all 25 tests, but Citus was **not faster**: clearly faster in 4 of 25, slower in 16, because all nodes shared the same 4 CPU cores and coordination costs time. Volumes above 61,737 rows were a synthetic scale-up for timing only.
- *Say:* "Distribution is not automatically faster. It helps when data outgrows one machine and nodes have their own hardware. Chicago's data is 16,000 inspections a year, so one node is plenty."

**E. Real-time warehouse** (`streaming/producer.py`, `spark_stream.py`, `clickhouse_ddl.sql`)
- *What:* the producer replays historical inspections into Kafka as if live; Spark validates each JSON event (7 rules), computes measures, aggregates in 10-second windows, writes to ClickHouse; Grafana shows it.
- *Result:* 3,647 events, each stored exactly once; 24 of 24 deliberately malformed events rejected (kept in a dead-letter table); average delay 1.5 s (p95 2.5 s); dashboard queries about 6-7 ms; four services use about 2.5 GB memory.
- *Must say:* **it is a replay simulation**, because the official dataset is a historical file. Every event carries `source_mode = REPLAY_SIMULATION`.

**F. OLAP and dashboard** (`sql/07_olap_queries.sql`, `dashboard/`, `docs/olap_operations.md`)
- *What:* roll-up, drill-down (3 steps), slice, dice, pivot, CUBE and GROUPING SETS, each with business question, SQL, DAX and interpretation. Dashboard: 4 sections (executive, facility & risk, geographic, inspections & violations).
- *Honest point:* no Power BI `.pbix` (Power BI Desktop runs only on Windows). I built an equivalent HTML dashboard from the warehouse and a rebuild package. The DAX was written but not run.

**G. Regression** (notebook 07) — *predict number of violations before the visit.*
- Features: facility type, risk, inspection type, month, weekday, ZIP, prior result, prior violation count. Train 2022-2024, test 2025.
- Result: MAE 2.45 vs 2.71 for "just predict the average"; **R-squared 0.12** (explains only 12% of the variation). Weak: inspection outcomes depend on things the data does not hold.

**H. Association rules** (notebook 08) — *which things occur together?*
- Apriori and FP-Growth give identical results (1,198 frequent itemsets at 2% support).
- Terms: **support** = how common the pattern is; **confidence** = how often the right side is true given the left; **lift** = how much more often than chance (lift 1 = no relation).
- Best rule: "10+ violations => Fail", confidence 69%, lift 3.0. Also: "Low risk => Grocery store" lift 6.5.

**I. Decision tree** (notebook 09) — *predict whether an inspection fails.*
- Train 2022-23, validate 2024, test 2025. **AUC 0.64**: only a weak ranking aid. Top features: prior result = Fail (29%), Complaint inspection (15%), prior violation count (13%), days since last inspection (10%).
- Note: with the default 0.5 cut-off recall is 3.9%; I tuned the threshold on validation data to get recall 61% (accuracy falls to 60%). Explain the trade-off if asked.

**J. Architecture evaluation** (`docs/architecture_comparison.md`)
- Compared batch, distributed, real-time on latency, history analytics, monitoring, scalability, complexity, fault handling, resources. Recommendation: **hybrid with the batch warehouse as the centre**.

---

## Part 4. Numbers to remember (memorise these ten)

1. **61,737** completed inspections, 2022-2025 (73,630 raw rows).
2. **Fact constellation**: 2 facts + 5 dimensions; **2x faster than snowflake**.
3. **60,608** facts initially + **1,129** incremental; **16 checks, 0 failures**.
4. Batch queries **10-74 ms**; 2,000,000 rows still **174-269 ms**.
5. Citus: results identical, but **faster in only 4 of 25 tests**.
6. Real-time: **1.5 s** average delay, **24/24** bad events rejected.
7. Fail rate fell **24.9% to 21.1%** (2022 to 2025).
8. Complaint inspections fail **37.6%**; after a fail, the next visit passes **79%** of the time (about 13 days later).
9. 10+ violations means **69%** chance of failing.
10. Regression R-squared **0.12**, decision tree AUC **0.64**: weakly predictable.

---

## Part 5. Source code tour (what each file does)

| Folder / file | Purpose | Key idea to point at |
|---|---|---|
| `scripts/fetch_data.py` | Downloads official data from the portal. | Reproducibility: anyone can re-fetch. |
| `etl/curation.py` (282 lines) | Cleaning and derived columns (violation count, bands, area group...). | Every rule counted and justified. |
| `sql/01_schema.sql` | Creates staging, dimensions, facts, Unknown members. | `facility_key = 0` row. |
| `sql/02_load_batch.sql` | `dw.load_batch(batch_id)` PL/pgSQL procedure: reject bad rows, insert dimension members, load facts, annual fact. | Same procedure for initial and incremental load; rejects already-loaded IDs (so it is idempotent). |
| `sql/03_indexes.sql`, `04_validation.sql` | Indexes; 16 integrity checks. | Orphan keys = 0, reconciliation of counts. |
| `sql/05_snowflake_schema.sql` | Snowflake copy for comparison. | |
| `sql/06_analytical_queries.sql` | Eight mandatory business queries. | |
| `sql/07_olap_queries.sql` | ROLLUP, CUBE, GROUPING SETS etc. | `GROUP BY ROLLUP (year, quarter, month)`. |
| `sql/08_analytics_mart.sql` | Flat table for ML; prior-history features via window functions (`lag`). | Features use only *strictly earlier* inspections: no leakage. |
| `etl/run_etl.py` | Orchestrates schema, load, validation, incremental load, idempotency test. | |
| `etl/fault_test.py` | Proves a failed load leaves no partial data. | Atomic transaction. |
| `etl/distributed_*.py`, `scripts/setup_citus_cluster.sh` | Distribution-key analysis, baseline, Citus cluster and timing. | `create_distributed_table(..., 'facility_key')`, `create_reference_table(...)`. |
| `streaming/producer.py` | Replays inspections into Kafka; can inject bad events. | `source_mode = REPLAY_SIMULATION`. |
| `streaming/spark_stream.py` | Validation rules, derived measures, windows, writes to ClickHouse. | 4 streaming queries: events, invalid, 10-s windows, daily. |
| `streaming/clickhouse_ddl.sql` | ClickHouse tables. | ReplacingMergeTree collapses duplicates. |
| `streaming/grafana/` | Dashboard JSON and data-source config. | |
| `notebooks/01,02,07,08,09` | Curation, EDA, regression, association rules, decision tree. | Open these live if asked to show results. |
| `dashboard/food_safety_dashboard.html` | The OLAP dashboard (opens in any browser, offline). | **Easiest thing to demo.** |
| `docs/` | Technical report, presentation, all write-ups, and the scripts that generate them. | |
| `results/` | Raw measurement CSVs behind every number. | Evidence if challenged. |

---

## Part 6. Demonstration plan (what to actually show)

The real-time stack and Citus need installed servers (about 2.5 GB, not in the repo), so **do not plan a live start-up of Kafka/Spark during your slot**. Safest plan, in order of reliability:

1. **Slides** (`Presentation.pptx`), 12 slides, about 8-10 minutes.
2. **Dashboard** (`dashboard/food_safety_dashboard.html`): open in a browser, click through the four sections, say one finding from each.
3. **Grafana screenshot** (`results/screenshots/grafana_realtime_dashboard.png`): "this is the real-time view during the replay".
4. **Code**: open `sql/02_load_batch.sql` (the load procedure) and `streaming/spark_stream.py` (the validation rules) and walk through 3-4 lines each.
5. **Notebook** results for regression, rules, tree (`notebooks/07-09`), already executed so outputs are visible.
6. If asked about the live demo: "It starts with `scripts/start_realtime_stack.sh` and the producer command in the README. I ran it end to end; I can show the recorded dashboard."

### Slide-by-slide script (12 slides)
1. **Title.** Who you are, dataset, what the project is.
2. **Lifecycle.** "One pipeline: raw to curated to warehouse to analytics, and three architectures on the same data."
3. **Curation.** "Decisions are counted, not guessed." Quote two examples (29 duplicates removed; 552 NULL not 0).
4. **Dimensional model.** Define grain; show star/snowflake/constellation numbers; "I chose constellation because ... ".
5. **Batch warehouse.** Staging, rules, load, 16 checks; incremental and idempotent.
6. **Real-time.** Kafka, Spark, ClickHouse, Grafana; 1.5 s; "this is a replay simulation".
7. **OLAP and dashboard.** Name the operations; say the no-Power-BI caveat briefly and calmly.
8. **Ten findings.** Pick 3: fail rate falling, complaint inspections fail most, follow-up works.
9. **Citus.** "Correct but not faster here, and here is why."
10. **Mining.** Regression 0.12, rules (10+ violations), tree AUC 0.64. "Honest conclusion: weakly predictable."
11. **Recommendation.** Hybrid, batch at the centre.
12. **Limitations.** Replay, one machine, no `.pbix`, synthetic scale-up.

---

## Part 7. Likely questions and good answers

**Concepts**
1. *Why a warehouse and not just the raw CSV?* Raw data has duplicates, missing values and no structure for fast slicing. The warehouse gives clean history, consistent keys and fast aggregates, and keeps an audit trail of loads.
2. *What is the grain, and why does it matter?* One completed inspection on one date. Every measure must agree with that, otherwise totals double count.
3. *Star vs snowflake vs constellation?* Star: simple, fewest joins. Snowflake: normalised, saves space, more joins (I measured about 2x slower). Constellation: several facts sharing dimensions; I use it because I need both inspection-level and facility-year facts.
4. *Why surrogate keys and an Unknown member?* Surrogate keys protect the warehouse from changes in source IDs; Unknown member (key 0) keeps facts whose lookup failed instead of dropping them.
5. *Fact vs dimension?* Fact = measurable events (violation count, fail flag). Dimension = context to slice by (date, facility, location, type, result).
6. *What is a Type-1 dimension?* Overwrite changed attributes with the latest value, no history. I used it; limitation: older facts show the latest facility attributes.
7. *What is idempotency and how did you prove it?* Re-running the same load changes nothing. Re-loading December rejected 1,129 rows already loaded and added 0.
8. *OLAP operations?* Roll-up (detail to summary), drill-down (reverse), slice (one dimension fixed), dice (several filters), pivot (rotate dimensions), CUBE (all combinations of subtotals).

**Choices and honesty**
9. *Why FacilityKey as the distribution key?* Many distinct values, even shards (skew 1.10 measured by simulating Citus' hash), and it is the grouping column of the facility-year query, so work stays local. LocationKey (252 values, one with 3%) and DateKey (weekdays only) are skewed.
10. *Why wasn't Citus faster?* Both workers and the coordinator shared one 4-core machine, so there was no extra hardware, only extra coordination and a final merge. It would help on separate machines with much more data.
11. *Is the real-time part real?* It is a replay of historical data, labelled as such; the pipeline itself (Kafka, Spark, ClickHouse, Grafana) genuinely ran end to end and was measured.
12. *Where is the Power BI file?* Power BI Desktop is Windows-only and could not run here. I built an HTML dashboard from the same warehouse and provided CSV exports plus rebuild instructions; DAX measures are written but untested.
13. *Why not hourly analysis?* Every timestamp is 00:00:00 in the source, so hours would be invented.
14. *Your scale-up to 2,000,000 rows is fake data?* It is resampled real fact rows, used only for query timing, and labelled as synthetic.
15. *Why is NULL used for some violation counts?* A Fail or Conditional Pass must cite at least one violation, so 0 would be wrong; NULL means unknown.
16. *How do you know the load is correct?* 16 validation checks after each load (orphan keys, duplicates, row and measure reconciliation) all return 0; a checksum of earlier facts is unchanged after the incremental load.

**Real-time**
17. *Why Kafka?* It buffers and orders events, decouples producer from consumer, and lets Spark resume after a crash from stored offsets.
18. *What is a window / watermark?* A window groups events by time (10 seconds). The watermark says how late an event may arrive before the window is closed.
19. *What happens with bad data?* Spark applies 7 validation rules; failing events go to a separate `invalid_events` table with the reason. 24 of 24 injected bad events were caught.
20. *Exactly-once?* Each of the 3,647 events was stored once in the test; the design is at-least-once, and ReplacingMergeTree collapses repeats in aggregate tables. (Admit it: event table could duplicate after a crash.)

**Mining**
21. *What do support, confidence, lift mean?* Support: share of all records containing the pattern. Confidence: given the left side, how often the right is true. Lift: confidence divided by the base rate; above 1 means positive association.
22. *Why Apriori and FP-Growth?* Same results; FP-Growth is faster because it avoids generating all candidate sets. I used both and checked they match.
23. *How did you avoid leakage?* Features use only strictly earlier inspections of the same facility; the split is chronological (train on past years, test on 2025).
24. *Your models are weak, did you fail?* No: the result is honest. R-squared 0.12 and AUC 0.64 mean what is known before a visit predicts little; the models are only a ranking aid. That finding is itself a recommendation (do not decide by model).
25. *What is AUC?* The probability that the model ranks a randomly chosen failed inspection above a randomly chosen passed one. 0.5 = coin flip, 1.0 = perfect. 0.64 is modest.
26. *What is the tree's threshold trade-off?* At 0.5 it almost never predicts a fail (recall 4%). Lowering the cut-off to 0.217 catches 61% of fails but with many false alarms (precision 29%).

**Recommendation**
27. *What would you recommend to the department?* Batch PostgreSQL warehouse as the system of record; add the real-time layer only for live monitoring if inspections are recorded digitally on site; Citus only when data outgrows one node. At about 16,000 inspections a year, one node lasts decades.

---

## Part 8. If something goes wrong or you do not know

- **Never invent a number.** Say "that is in `results/` / the report, section X" and open it.
- If asked about something not covered (security, cloud cost, ML deployment): "That was outside the scope of this project; here is what I would consider ..." then give one sentence.
- If a live demo fails: switch to screenshots and the HTML dashboard.
- Stay calm about the caveats (replay, no `.pbix`, Citus not faster). They are **strengths**: you measured honestly and reported it.

## Part 9. Reproduce commands (for reference)

See `README.md` in the project folder. In short: `scripts/fetch_data.py` then curation notebook, `scripts/setup_postgres.sh`, `etl/run_etl.py all`, `etl/run_queries.py`, `etl/run_olap.py`, `dashboard/build_dashboard.py`; Part D with `scripts/setup_citus_cluster.sh` and `etl/distributed_citus.py`; Part E with `scripts/start_realtime_stack.sh` then `streaming/producer.py`.
