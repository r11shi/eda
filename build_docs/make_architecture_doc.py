"""Writes docs/architecture_comparison.md (Part J) and docs/domain_recommendations.md from MEASURED results."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
t = pd.read_csv(R / "batch_load_timing_all.csv").set_index("step")["seconds"]
qt = pd.read_csv(R / "batch_query_timing.csv")
sm = pd.read_csv(R / "streaming_metrics.csv").set_index("metric")["value"]
cs = pd.read_csv(R / "centralized_scaling.csv")
dist = ROOT / "results" / "distributed_scaling.csv"
has_citus = dist.exists()
if has_citus:
    ds = pd.read_csv(dist); cres = pd.read_csv(R / "citus_resources.csv").set_index("cluster")["resident_memory_MB"]
    d_all = ds.distributed_ms; d2 = ds[ds.rows == 2000000]; ratio2 = d2.distributed_over_centralized
init = t[[k for k in t.index if k.startswith("[initial]") and "create audit" not in k]].sum()
inc = t[[k for k in t.index if k.startswith("[incremental]") and "create audit" not in k]].sum()
c100, c2m = cs[cs.rows == 100000].set_index("query")["centralized_ms"], cs[cs.rows == 2000000].set_index("query")["centralized_ms"]
ratio = (c2m / c100)
rss = {k: sm[f"memory (RSS, MB): {k}"] for k in ["Kafka broker", "ClickHouse server", "Spark streaming job (python + JVM)", "Grafana"]}
CIT = "Not measured: Citus could not be installed in this run (see `docs/distributed_warehouse.md`)"
if has_citus:
    CIT_LAT = f"Same bulk-load pattern as the batch DW (loading and indexing 2,000,000 rows into the distributed table took about 8 s); measured query latency {d_all.min():.0f}-{d_all.max():.0f} ms"
    CIT_SCAL = f"Measured on 2 workers sharing one machine: 20 times more rows (100,000 to 2,000,000) made the five test queries {(d2.set_index('query').distributed_ms / ds[ds.rows == 100000].set_index('query').distributed_ms).min():.1f}-{(d2.set_index('query').distributed_ms / ds[ds.rows == 100000].set_index('query').distributed_ms).max():.1f} times slower; at 2,000,000 rows Citus took {ratio2.min():.2f}-{ratio2.max():.2f} times the single-node time, so it did not scale better on this hardware"
    CIT_PERF = f"{d_all.min():.0f}-{d_all.max():.0f} ms over all volumes; at 2,000,000 rows {d2.distributed_ms.min():.0f}-{d2.distributed_ms.max():.0f} ms, which is slower than one node except in the facility-year grouping at 0.5-1 million rows (0.6 times)"
    CIT_RES = f"Three PostgreSQL instances: about {(cres['coord'] + cres['worker1'] + cres['worker2']) / 1024:.1f} GB resident memory against {cres['main'] / 1024:.2f} GB for the single node after the same workload (sums count shared memory per process, so both are overstated)"

rows = [
 ("Data arrival", "Periodic: initial load plus one incremental load per reporting period", "Large data hash-partitioned into 32 shards and bulk-loaded through the coordinator", "Continuous events (a replay of historical records here)"),
 ("Processing", "ETL: Python curation, COPY to staging, PL/pgSQL load procedure", "Parallel: each query becomes 32 shard tasks on 2 workers; the coordinator merges", "Spark Structured Streaming micro-batches (2 s)"),
 ("Storage", "PostgreSQL 16 (dimensional schema)", ("Citus 13.2 on PostgreSQL 16.15: coordinator + 2 workers on one machine" if has_citus else "Citus on PostgreSQL (not installed here)"), "ClickHouse (MergeTree and ReplacingMergeTree)"),
 ("Latency", f"Higher: data is available after the batch run. Measured ETL time for the held-back month (1,471 rows): {inc:.2f} s, but the real latency is the length of the reporting period", CIT_LAT if has_citus else CIT, f"Low, measured: average {sm['latency avg (ms), emit -> ClickHouse']:.0f} ms, median {sm['latency median (ms)']:.0f} ms, p95 {sm['latency p95 (ms)']:.0f} ms from emission to a queryable ClickHouse row"),
 ("Historical analytics", f"Excellent: all 8 analytical queries run in {qt.median_ms.min():.0f}-{qt.median_ms.max():.0f} ms on the 61,737-inspection warehouse, with full OLAP, history and validation", "Excellent: same dimensional model and SQL; every distributed result was identical to the centralized one" if has_citus else "Excellent in principle (not measured)", "Moderate / operational: holds only the replayed window; the aggregates are kept in small tables"),
 ("Live monitoring", "Poor: nothing is visible until the next batch", "Limited: batch-style loading; no live feed" if has_citus else "Limited (not measured)", f"Excellent: dashboard refreshes every 5 s; ClickHouse dashboard queries take {sm['ClickHouse query: risk distribution (window_agg) (median ms)']:.1f}-{sm['ClickHouse query: KPI totals (window_agg, 6 stats) (median ms)']:.1f} ms"),
 ("Scalability", f"Moderate, measured on one node: 20 times more rows (100,000 to 2,000,000) made the five test queries {ratio.min():.1f}-{ratio.max():.1f} times slower, and 2,000,000 rows (32 times the real data) still take {c2m.min():.0f}-{c2m.max():.0f} ms", CIT_SCAL if has_citus else CIT, "High in design (Kafka partitions, more Spark and ClickHouse nodes); a throughput limit test was not run, only 80 events per second"),
 ("Complexity", "Low: one database, SQL scripts and one Python driver", "Medium: coordinator, workers, distribution keys, reference tables", "High: four services (Kafka, Spark, ClickHouse, Grafana) to deploy, monitor and keep consistent"),
 ("Query performance (measured)", f"Analytical queries {qt.median_ms.min():.0f}-{qt.median_ms.max():.0f} ms at 61,737 rows; {c2m.min():.0f}-{c2m.max():.0f} ms at 2,000,000 rows", CIT_PERF if has_citus else CIT, f"Dashboard queries {min(sm[k] for k in sm.index if k.startswith('ClickHouse query')):.1f}-{max(sm[k] for k in sm.index if k.startswith('ClickHouse query')):.1f} ms"),
 ("Fault handling (batch: tested; the others: analysis of the design, no failure was injected)", "Tested: a load that failed in the middle (a value that did not fit the column, after new dimension members had been inserted) left all four warehouse tables unchanged (`results/fault_test.csv`). The load is also idempotent: loading the same month again was rejected row by row (1,129 duplicates rejected, 0 loaded). Single node, so no automatic failover; recovery is by backup and re-run", "Analysis of the design: each shard lives on one worker (replication factor 1 here), so a lost worker makes its shards unavailable unless replicas or standbys are configured; the coordinator is a single point of failure", "Kafka keeps the events and Spark checkpoints the offsets, so the job can resume after a crash. Delivery to ClickHouse is at-least-once: window tables use ReplacingMergeTree so repeats collapse, the event table could contain repeats after a failure. Invalid events are kept in a dead-letter table"),
 ("Resource requirement (measured)", f"One PostgreSQL server: about {cres['main']:.0f} MB resident memory after the 2,000,000-row workload; warehouse, staging and mart use 66 MB on disk" if has_citus else "One PostgreSQL server: about 250 MB resident memory; warehouse, staging and mart use 66 MB on disk", CIT_RES if has_citus else CIT, f"Four services at about {sum(rss.values()) / 1024:.1f} GB resident memory in total (Kafka {rss['Kafka broker']:.0f} MB, ClickHouse {rss['ClickHouse server']:.0f} MB, Spark {rss['Spark streaming job (python + JVM)']:.0f} MB, Grafana {rss['Grafana']:.0f} MB)"),
]
doc = f"""# Part J: Architecture Evaluation

All values marked *measured* come from `results/` (batch load and query timings, centralized scaling test, streaming metrics). Everything ran on one 4-core, 15 GB machine, so the figures compare the architectures under the same conditions but are not production capacity numbers.

## Comparison of the three architectures
| Parameter | Batch DW (PostgreSQL) | Distributed DW (Citus) | Real-time DW (Kafka, Spark, ClickHouse) |
|---|---|---|---|
""" + "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows) + f"""

## Evidence from the experiments
* **Initial batch load:** 72,130 staged rows, loaded into the warehouse in {init:.1f} s including the indexes. **Incremental load:** {inc:.2f} s for the held-back month; the earlier fact rows were unchanged (MD5 checksum) and re-running the month added nothing.
* **Centralized scaling** (synthetic scale-up by resampling the real facts, used for performance only):

{pd.read_csv(R / 'centralized_scaling.csv').pivot(index='query', columns='rows', values='centralized_ms').rename(columns=lambda c: f'{c:,} rows (ms)').reset_index().to_markdown(index=False) if False else ''}
"""
piv = cs.pivot(index="query", columns="rows", values="centralized_ms")
piv.columns = [f"{c:,} rows (ms)" for c in piv.columns]
piv = piv.reset_index()
doc = doc.replace("\n\n\n", "\n\n") + "\n".join(["| " + " | ".join(piv.columns) + " |", "|" + "|".join("---" for _ in piv.columns) + "|"] + ["| " + " | ".join(str(v) for v in r) + " |" for r in piv.values]) + "\n"
doc += f"""
* **Real-time pipeline:** 3,647 events replayed at 80 per second reached ClickHouse with an average delay of {sm['latency avg (ms), emit -> ClickHouse']:.0f} ms; the 24 injected malformed events were all rejected.
* **Distributed (Citus):** {"on 3 PostgreSQL instances on one machine, Citus was clearly faster in only " + str(int((ds.distributed_over_centralized < 0.85).sum())) + " of " + str(len(ds)) + " test cases (two were tiny differences on small volumes; the real gain was the facility-year grouping at 0.5-1 million rows, about 0.6 times the single-node time) and clearly slower in " + str(int((ds.distributed_over_centralized > 1.15).sum())) + "; every result was identical. Details: docs/distributed_warehouse.md" if has_citus else "not measured, because Citus could not be installed in this run."}.

## Final architecture question
*Which architecture mix should a public-health department use for longitudinal inspection reporting, large-scale compliance analytics and operational inspection monitoring?*

**Recommendation: a hybrid with the batch warehouse at its centre.**

1. **Batch PostgreSQL warehouse as the system of record** for longitudinal reporting and compliance analytics. It held every analytical question at 10-{qt.median_ms.max():.0f} ms, supports full OLAP, validation and an auditable incremental load, and needs one server and low operating effort. Two million rows (32 times the four years of Chicago data) still queried in {c2m.min():.0f}-{c2m.max():.0f} ms on one node, so the data volume of this domain does not need more.
2. **Add the real-time layer only for operational monitoring,** and only if inspections are recorded digitally as they happen (for example from inspectors' devices). It gives a {sm['latency avg (ms), emit -> ClickHouse']/1000:.1f}-second delay and live area alerts, but it costs four services and about {sum(rss.values()) / 1024:.1f} GB of memory, and it should feed the batch warehouse rather than replace it. The official dataset is a historical file updated over time, so for this data the layer is a demonstration of the pattern.
3. **Distributed warehouse (Citus) only when the data outgrows one node.** At about 16,000 inspections a year, one node is enough for decades. The measured Citus run did not beat one node at any tested volume except for one query shape, because the workers shared the same machine and the coordination overhead is as large as the scan. Distribution would pay off for a state-wide or national consolidation on separate hardware, where the key analysis in `docs/distributed_warehouse.md` (FacilityKey gives the most even shards, skew 1.15) applies.
"""
(ROOT / "docs" / "architecture_comparison.md").write_text(doc)

rec = """# Final Domain Recommendations for the Public-Health Department

Each recommendation points to the finding or experiment that supports it (`docs/ten_findings.md`, notebooks 07-09, `docs/architecture_comparison.md`).

## Operations
1. **Triage complaint inspections first.** Full complaint inspections fail 37.6% of the time against 25.0% for routine canvass inspections (finding 5).
2. **Keep the short re-inspection cycle and escalate repeat failures.** After a failed inspection the next visit passes 79.4% of the time, on average 13 days later; the 12.9% that fail again belong on an escalation list (finding 8).
3. **Set 10 or more violations as an automatic follow-up trigger.** 69% of these inspections end in a fail, three times the normal rate; 43% do at 6-9 violations (finding 9).
4. **Use the failure rate to target outreach, and the failure count to size capacity.** ZIP codes 60617, 60620, 60628, 60619 and 60636 have the highest rates (31-37%); 60614, 60608 and 60617 have the most failures (finding 7).
5. **Base inspector training and owner guidance on the five most cited violations,** which are about premises and cleanliness (rules 55, 47, 49, 10 and 51) and appear in 21-67% of all inspections (finding 6).
6. **Plan capacity on a steady workload of about 1,300-1,650 inspections a month,** because there is no stable seasonal peak (finding 1).
7. **Do not rely on the risk category alone to predict failure.** The fail rate is about the same for high, medium and low risk (finding 4).

## Using predictions
8. **Use the models only as a ranking aid.** The failure tree has an AUC of 0.64 and the violation regression an R-squared of 0.12; together with the facility's history and inspector judgement they can help to order the work, but not to decide a result (finding 10).

## Data and platform
9. **Improve the data at the source:** record the time of day of each inspection, keep violations as a separate table (one row per violation) so that rule-level analysis is possible, use a stable establishment identifier for every record (210 records have licence 0), and remove the undocumented risk code `All`.
10. **Build on a batch warehouse first** and add streaming and distribution only when a real need appears (`docs/architecture_comparison.md`).
"""
(ROOT / "docs" / "domain_recommendations.md").write_text(rec)
print("written architecture_comparison.md and domain_recommendations.md")
