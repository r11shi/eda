# Guide 4: Probable Questions and Simple Answers
Marked **[B]** basic, **[M]** medium, **[H]** harder. Learn all the **[B]** answers first. Answers are short on purpose: say them in your own words.

**Golden rules**
1. If you do not know: *"I did not go that deep, but my understanding is ..."* and say one sentence. Never invent a number. Say *"it is in the report, section X"*.
2. The caveats (replay, no Power BI file, Citus not faster) are honest findings. Say them calmly before they are asked.
3. Say the story first: **clean the data, build a warehouse three ways, measure, analyse, predict, recommend.**

---

## A. The whole project

1. **[B] What is your project about?** Analysing Chicago restaurant inspection data (2022–2025, 61,737 completed inspections). I cleaned it, built a data warehouse three ways (batch, distributed, real-time), measured them, answered ten business questions, and trained three small data-mining models.
2. **[B] Why did you choose this data?** It is the official public data prescribed in the project document. It has dates, places, types and results, so it suits a warehouse with several dimensions.
3. **[B] What did you build?** A cleaning script, a PostgreSQL warehouse with a load procedure, OLAP queries and a dashboard, a Citus cluster, a Kafka–Spark–ClickHouse–Grafana pipeline, and regression, association-rule and decision-tree models.
4. **[B] What is your main conclusion?** Use a batch warehouse as the core, add real-time only for live monitoring, and add distribution only when data outgrows one machine.
5. **[M] What are the limits of your work?** The real-time part is a replay of historical data; all timings come from one 4-core machine; no Power BI file (Windows-only); scale-up beyond 61,737 rows is synthetic and used only for timing; the models are weak.
6. **[B] Where is the code?** In the `EDA/Project` folder (and the single Colab notebook). The file-by-file map is in `Project_Source_of_Truth.pdf`.

## B. Data and cleaning

7. **[B] Where did the data come from?** The City of Chicago Data Portal (official), downloaded through its API for 1 Jan 2022 to 31 Dec 2025.
8. **[B] How big is it?** 73,630 records. 61,737 are completed inspections. 11,864 are not completed inspections (Out of Business, No Entry, Not Ready, Business Not Located) and are kept in staging only.
9. **[B] What problems did you find?** Duplicates (29 removed), invalid risk code "All" (38) and missing risk (17), missing facility type (320), missing or zero licence number (213), missing coordinates (255), no time of day (all 00:00:00).
10. **[M] Why did you keep 496 same-day pairs?** They have different results or violations, so they may be separate visits (for example morning and afternoon). I cannot prove they are duplicates, so I kept and flagged them.
11. **[M] Why is a fail without violation text "unknown" and not zero?** A fail must have at least one violation, so zero would be wrong. NULL means unknown. A pass without text is 0.
12. **[M] Why not remove outliers?** The 2,686 very high violation counts are the worst premises. Removing them would hide the most important inspections, so I kept them and flagged them.
13. **[B] What new columns did you create?** Violation count, violation band, result group, risk group, facility group, inspection type group, season, area group (from coordinates), fail flag, high-violation flag, and others (documented in the data dictionary).
14. **[M] Why no hourly analysis?** Every time stamp is 00:00:00, so hours do not exist in the data. I did not invent them.

## C. Warehouse design

15. **[B] What is a data warehouse?** A database built for analysing history, not for everyday transactions.
16. **[B] What is ETL?** Extract, transform, load: take raw data, clean it, load it into the warehouse.
17. **[B] What are fact and dimension tables?** Facts are the measurable events (one row per inspection, with violation count and fail flag). Dimensions describe them (date, facility, location, inspection type, result).
18. **[B] What is the grain?** One completed inspection on one date.
19. **[B] Star vs snowflake vs fact constellation?** Star: one fact, flat dimensions, fewest joins. Snowflake: dimensions split into sub-tables, more joins, less repetition. Constellation: several fact tables sharing dimensions.
20. **[B] Which did you choose and why?** Fact constellation: star speed (37 ms) plus a second fact at facility-by-year level that answers yearly questions in 2.7 ms instead of 21.7 ms. The snowflake took 78 ms and needed 9 joins.
21. **[M] What are surrogate keys?** Meaningless integer IDs created by the warehouse, so it does not depend on the source's IDs.
22. **[M] What is the Unknown member?** A dimension row with key 0 used when a lookup fails, so no fact row is lost.
23. **[M] What is Type 1 versus Type 2?** Type 1 overwrites an old value with the new one (no history). Type 2 keeps history by adding a new row. I used Type 1 for facility attributes; the limit is that old facts show the latest attributes.
24. **[M] What is staging?** A holding area where raw-ish data lands before rules are applied and it is moved to the real tables.

## D. Batch warehouse (PostgreSQL)

25. **[B] How does the load work?** Python writes the cleaned rows into staging; one stored procedure (`dw.load_batch`) applies the rules, adds new dimension rows, loads the facts and the annual fact.
26. **[B] What is an incremental load?** Loading only new data without rebuilding. December 2025 was loaded after the rest: +1,129 facts in 0.5 s, and the earlier 60,608 rows were unchanged (MD5 checksum).
27. **[M] What is idempotent?** Running it twice gives the same result as once. Loading December again rejected 1,129 rows and added 0.
28. **[M] How did you check the warehouse is right?** 16 validation checks after each load (no orphan keys, no duplicates, row counts and measures reconcile with staging). All came out 0.
29. **[M] What is an atomic load?** All or nothing. A deliberately failing load left every table unchanged.
30. **[B] What did indexes do?** Selective queries went from 3–5 ms to 0.2–0.3 ms.
31. **[B] How fast were the queries?** The eight analytical queries ran in 10–74 ms.

## E. OLAP and dashboard

32. **[B] What is OLAP?** Analysing facts by slicing them along dimensions.
33. **[B] Name the operations.** Roll-up (summarise upwards), drill-down (go into detail), slice (fix one dimension), dice (filter several), pivot (rotate the table), CUBE and GROUPING SETS (all subtotals in one query).
34. **[M] Give an example.** Roll-up: 2025's 16,052 inspections from months to quarters to the year. Drill-down: facility group → grocery types → individual grocery stores.
35. **[B] Why no Power BI file?** Power BI Desktop runs only on Windows. I built an equivalent HTML dashboard and a rebuild package. The DAX measures are written but were not run.
36. **[B] Name three findings.** The fail rate fell from 24.9% to 21.1%. Complaint inspections fail most (37.6%). After a failed inspection, 79% of the next visits pass, about 13 days later.

## F. Distributed (Citus)

37. **[B] What is Citus?** A PostgreSQL extension that splits tables into shards across servers and runs queries in parallel.
38. **[B] What was your set-up?** A coordinator plus 2 workers on one machine, 32 shards, facts split by FacilityKey, dimensions copied to every worker (reference tables).
39. **[M] Why FacilityKey?** It has 17,083 different values and the most even shards (skew 1.10). LocationKey has only 252 values (skew 2.56), and DateKey has only weekdays.
40. **[B] Was Citus faster?** No. Results were identical in all 25 tests, but Citus was clearly faster in only 4 and slower in 16.
41. **[B] Why not faster?** All nodes shared the same 4 CPU cores, so there was no extra hardware, only the cost of coordination.
42. **[M] When would Citus help?** When the data outgrows one machine and the nodes have their own hardware.
43. **[M] Was the 2,000,000-row data real?** It is real fact rows resampled to a larger size. It was only for timing and is labelled synthetic.

## G. Real-time

44. **[B] What does each tool do?** Kafka: a message queue. Spark Structured Streaming: reads the stream, validates and aggregates it. ClickHouse: a fast database for the results. Grafana: a live dashboard.
45. **[B] Is it really live?** No. It replays historical inspections as if they were live, and every event says `REPLAY_SIMULATION`. The pipeline itself ran end to end.
46. **[B] How fast was it?** Average delay 1.5 s (95% under 2.5 s), 3,647 events at 80 per second, dashboard queries about 6–7 ms.
47. **[M] How did you handle bad data?** Spark applies 7 validation rules. Failing events go to a separate table with the reason. All 24 injected bad events were rejected.
48. **[M] What is a window and a watermark?** A window groups events by time (10 seconds). A watermark says how late an event may arrive before the window is final.
49. **[M] Exactly once?** Each of the 3,647 events was stored once in the test. The design is at-least-once, and ReplacingMergeTree collapses repeats in the aggregate tables.

## H. Regression (see Guide 1)

50. **[B] What is regression?** Predicting a number. I predicted the number of violations.
51. **[B] What are your inputs?** Facility type, risk, inspection type, month, weekday, ZIP, previous result, previous violation count.
52. **[M] How were categories handled?** One-hot encoding: each category becomes a 0/1 column. That gave 102 columns.
53. **[B] What are MAE and R-squared?** MAE is the average miss, in violations. R-squared is the share of the ups and downs explained.
54. **[B] What were your results?** MAE 2.45 against 2.71 for the lazy baseline; R-squared 0.12.
55. **[B] Is R-squared 0.12 bad?** It is weak but honest: most of what decides violations (kitchen, staff, inspector) is not in the data.
56. **[B] What is leakage and how did you avoid it?** Using information not available at prediction time. I did not use the current result or band, only earlier inspections, and I split by time (train 2022–2024, test 2025).
57. **[M] What are VIF and Breusch-Pagan?** VIF checks whether inputs copy each other (only 5 of 102 were above 5). Breusch-Pagan checks whether the misses are equally spread (they are not).
58. **[H] Why is a straight line not ideal here?** A count cannot be negative, but 304 predictions were negative, and the spread of the errors is not constant. Poisson regression would be the next step.

## I. Association rules (see Guide 2)

59. **[B] What is an association rule?** "If X then Y", found from items that occur together.
60. **[B] What are support, confidence and lift?** Support: how common. Confidence: how often the right side follows the left. Lift: how much more than chance (1 means no relation).
61. **[B] Give one rule.** Violations 10+ ⇒ Fail, support 5.4%, confidence 69%, lift 3.0.
62. **[B] What is a transaction here?** One inspection with 7 labels.
63. **[M] How did you handle the violation count?** Turned into bands: 0, 1–2, 3–5, 6–9, 10+.
64. **[B] Apriori versus FP-Growth?** Apriori builds and counts candidate sets level by level. FP-Growth compresses the data into a tree and avoids candidates. Same result, FP-Growth is faster.
65. **[M] What is the Apriori principle?** If a set is rare, every bigger set containing it is also rare, so it can be skipped.
66. **[M] What is an FP-tree?** A compact prefix tree of the baskets, with counts, ordered by item frequency, so shared beginnings are stored once.
67. **[M] How did you pick the final rules?** Minimum support 2%, confidence 30%, lift 1.3; I removed obvious or repeated rules and kept 14.
68. **[M] Does a rule prove cause?** No, only that items occur together.

## J. Decision tree (see Guide 3)

69. **[B] What is a decision tree?** A flowchart of yes/no questions that ends in a prediction.
70. **[B] How does it pick questions?** It picks the question that makes the groups purest, measured by Gini or entropy.
71. **[M] ID3 vs C4.5 vs CART?** ID3: information gain, categories only. C4.5: gain ratio, handles numbers and missing values. CART: Gini, always two branches. scikit-learn builds CART.
72. **[B] What is over-fitting and how did you fight it?** Memorising the training data. I limited depth and leaf size (max depth 8, at least 200 cases per leaf), chosen on 2024.
73. **[B] What was the result?** AUC 0.64 on the 2025 test year, which is weak.
74. **[M] Why was recall only 4% at first?** Failures are only about 21% of the cases, so the predicted probability rarely passes the default 0.5 cut-off.
75. **[M] What did the tuned cut-off do?** A cut-off of 0.217 (chosen on validation data) caught 61% of fails but with many false alarms (precision 29%).
76. **[B] What are the most important inputs?** A previous fail (29%), a complaint inspection (15%), previous violation count (13%) and days since the last inspection (10%).
77. **[M] Why not use the number of violations as an input?** That is leakage: it is only known after the inspection and decides the result.
78. **[H] What is AUC?** The chance that a random failed inspection gets a higher fail-score than a random passed one. 0.5 is a coin flip.

## K. Trap questions
79. **"Your models are weak. Did the project fail?"** No. The weak result is a finding: what is known before a visit predicts little. It means use the models only to rank, and collect better data.
80. **"Why not use a random forest or deep learning?"** The brief asks for a decision tree, which is readable. A forest would probably score a little higher but cannot be read.
81. **"Is the real-time pipeline production-ready?"** No. It is a demonstration on one machine with a replay, and I did not test its limits beyond 80 events per second.
82. **"Which parts did you test hardest?"** The batch warehouse: validation checks, incremental load, repeat load, forced failure, indexing, and query timing.
83. **"What would you do with more time?"** Poisson regression, a stress test of the streaming part, Citus on separate machines, and the Power BI file on Windows.
84. **"What did you learn?"** More hardware and more tools are not automatically better; I measured them and a plain batch warehouse was enough.
