# Part J: Architecture Evaluation

All values marked *measured* come from `results/` (batch load and query timings, centralized scaling test, streaming metrics). Everything ran on one laptop (WSL 2 Ubuntu, 12 logical CPUs, 8 GB memory), so the figures compare the architectures under the same conditions but are not production capacity numbers.

## Comparison of the three architectures
| Parameter | Batch DW (PostgreSQL) | Distributed DW (Citus) | Real-time DW (Kafka, Spark, ClickHouse) |
|---|---|---|---|
| Data arrival | Periodic: initial load plus one incremental load per reporting period | Large data hash-partitioned into 32 shards and bulk-loaded through the coordinator | Continuous events (a replay of historical records here) |
| Processing | ETL: Python curation, COPY to staging, PL/pgSQL load procedure | Parallel: each query becomes 32 shard tasks on 2 workers; the coordinator merges | Spark Structured Streaming micro-batches (2 s) |
| Storage | PostgreSQL 18 (dimensional schema) | Citus 14.3 on PostgreSQL 18.6: coordinator + 2 workers on one machine | ClickHouse (MergeTree and ReplacingMergeTree) |
| Latency | Higher: data is available after the batch run. Measured ETL time for the held-back month (1,471 rows): 1.14 s, but the real latency is the length of the reporting period | Same bulk-load pattern as the batch DW (loading and indexing 2,000,000 rows into the distributed table took about 8 s); measured query latency 39-612 ms | Low, measured: average 1763 ms, median 1755 ms, p95 2823 ms from emission to a queryable ClickHouse row |
| Historical analytics | Excellent: all 8 analytical queries run in 21-117 ms on the 61,737-inspection warehouse, with full OLAP, history and validation | Excellent: same dimensional model and SQL; every distributed result was identical to the centralized one | Moderate / operational: holds only the replayed window; the aggregates are kept in small tables |
| Live monitoring | Poor: nothing is visible until the next batch | Limited: batch-style loading; no live feed | Excellent: dashboard refreshes every 5 s; ClickHouse dashboard queries take 16.5-15.8 ms |
| Scalability | Moderate, measured on one node: 20 times more rows (100,000 to 2,000,000) made the five test queries 4.7-18.2 times slower, and 2,000,000 rows (32 times the real data) still take 319-1169 ms | Measured on 2 workers sharing one machine: 20 times more rows (100,000 to 2,000,000) made the five test queries 2.7-7.2 times slower; at 2,000,000 rows Citus took 0.52-1.19 times the single-node time, so it did not scale better on this hardware | High in design (Kafka partitions, more Spark and ClickHouse nodes); a throughput limit test was not run, only 80 events per second |
| Complexity | Low: one database, SQL scripts and one Python driver | Medium: coordinator, workers, distribution keys, reference tables | High: four services (Kafka, Spark, ClickHouse, Grafana) to deploy, monitor and keep consistent |
| Query performance (measured) | Analytical queries 21-117 ms at 61,737 rows; 319-1169 ms at 2,000,000 rows | 39-612 ms over all volumes; at 2,000,000 rows 260-612 ms, which is slower than one node except in the facility-year grouping at 0.5-1 million rows (0.6 times) | Dashboard queries 13.6-17.4 ms |
| Fault handling (batch: tested; the others: analysis of the design, no failure was injected) | Tested: a load that failed in the middle (a value that did not fit the column, after new dimension members had been inserted) left all four warehouse tables unchanged (`results/fault_test.csv`). The load is also idempotent: loading the same month again was rejected row by row (1,129 duplicates rejected, 0 loaded). Single node, so no automatic failover; recovery is by backup and re-run | Analysis of the design: each shard lives on one worker (replication factor 1 here), so a lost worker makes its shards unavailable unless replicas or standbys are configured; the coordinator is a single point of failure | Kafka keeps the events and Spark checkpoints the offsets, so the job can resume after a crash. Delivery to ClickHouse is at-least-once: window tables use ReplacingMergeTree so repeats collapse, the event table could contain repeats after a failure. Invalid events are kept in a dead-letter table |
| Resource requirement (measured) | One PostgreSQL server: about 33 MB resident memory after the 2,000,000-row workload; warehouse, staging and mart use 66 MB on disk | Three PostgreSQL instances: about 0.2 GB resident memory against 0.03 GB for the single node after the same workload (sums count shared memory per process, so both are overstated) | Four services at about 2.6 GB resident memory in total (Kafka 466 MB, ClickHouse 701 MB, Spark 1254 MB, Grafana 192 MB) |

## Evidence from the experiments
* **Initial batch load:** 72,130 staged rows, loaded into the warehouse in 30.2 s including the indexes. **Incremental load:** 1.14 s for the held-back month; the earlier fact rows were unchanged (MD5 checksum) and re-running the month added nothing.
* **Centralized scaling** (synthetic scale-up by resampling the real facts, used for performance only):

| query | 61,737 rows (ms) | 100,000 rows (ms) | 500,000 rows (ms) | 1,000,000 rows (ms) | 2,000,000 rows (ms) |
|---|---|---|---|---|---|
| Q1 results by facility type | 45.9 | 64.3 | 174.3 | 261.4 | 1169.1 |
| Q2 failure rate by area | 25.2 | 41.1 | 87.7 | 216.5 | 391.0 |
| Q3 monthly inspections | 23.0 | 39.0 | 107.0 | 175.0 | 318.9 |
| Q4 violations by risk | 32.4 | 45.6 | 96.9 | 168.3 | 362.3 |
| Q5 facility x year aggregation | 102.3 | 89.7 | 278.4 | 471.0 | 423.6 |

* **Real-time pipeline:** 3,647 events replayed at 80 per second reached ClickHouse with an average delay of 1763 ms; the 24 injected malformed events were all rejected.
* **Distributed (Citus):** on 3 PostgreSQL instances on one machine, Citus was clearly faster in only 5 of 25 test cases (two were tiny differences on small volumes; the real gain was the facility-year grouping at 0.5-1 million rows, about 0.6 times the single-node time) and clearly slower in 16; every result was identical. Details: docs/distributed_warehouse.md.

## Final architecture question
*Which architecture mix should a public-health department use for longitudinal inspection reporting, large-scale compliance analytics and operational inspection monitoring?*

**Recommendation: a hybrid with the batch warehouse at its centre.**

1. **Batch PostgreSQL warehouse as the system of record** for longitudinal reporting and compliance analytics. It held every analytical question at 10-117 ms, supports full OLAP, validation and an auditable incremental load, and needs one server and low operating effort. Two million rows (32 times the four years of Chicago data) still queried in 319-1169 ms on one node, so the data volume of this domain does not need more.
2. **Add the real-time layer only for operational monitoring,** and only if inspections are recorded digitally as they happen (for example from inspectors' devices). It gives a 1.8-second delay and live area alerts, but it costs four services and about 2.6 GB of memory, and it should feed the batch warehouse rather than replace it. The official dataset is a historical file updated over time, so for this data the layer is a demonstration of the pattern.
3. **Distributed warehouse (Citus) only when the data outgrows one node.** At about 16,000 inspections a year, one node is enough for decades. The measured Citus run did not beat one node at any tested volume except for one query shape, because the workers shared the same machine and the coordination overhead is as large as the scan. Distribution would pay off for a state-wide or national consolidation on separate hardware, where the key analysis in `docs/distributed_warehouse.md` (FacilityKey gives the most even shards, skew 1.15) applies.
