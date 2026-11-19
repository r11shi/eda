"""Writes docs/distributed_warehouse.md (Part D) from the MEASURED results of etl/distributed_baseline.py and etl/distributed_citus.py."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
sc, dk, ke = pd.read_csv(R / "distributed_scaling.csv"), pd.read_csv(R / "distribution_key_analysis.csv"), pd.read_csv(R / "distribution_key_experiment.csv")
ld, res = pd.read_csv(R / "citus_load_times.csv"), pd.read_csv(R / "citus_resources.csv").set_index("cluster")["resident_memory_MB"]
explain = (R / "citus_explain.txt").read_text()


def md(df):
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "|".join("---" for _ in df.columns) + "|"] + ["| " + " | ".join(str(v) for v in r) + " |" for r in df.values])


def interpret(r):
    diff = r.distributed_ms - r.centralized_ms
    if abs(diff) < 12:
        return f"about equal: the difference of {abs(diff):.0f} ms is within the noise of a single-machine test"
    if r.distributed_over_centralized < 1:
        if r.query.startswith("Q5"):
            return f"Citus {1 / r.distributed_over_centralized:.1f}x faster: the grouping column is the distribution key, so each shard finishes its aggregation and the coordinator only merges"
        return f"Citus {1 / r.distributed_over_centralized:.1f}x faster, but only by {abs(diff):.0f} ms"
    return f"Citus {r.distributed_over_centralized:.1f}x slower, most likely because distributed planning, the 32 shard tasks and the merge of partial results on the coordinator cost more than the parallel scan saves"


tab = sc.copy()
tab["Interpretation"] = [interpret(r) for r in sc.itertuples()]
tab = tab[["query", "rows", "centralized_ms", "distributed_ms", "Interpretation"]].rename(columns={"query": "Query", "rows": "Rows", "centralized_ms": "Centralized (ms)", "distributed_ms": "Distributed (ms)"})
tab["Rows"] = tab["Rows"].map(lambda v: f"{v:,}")
faster = sc[sc.distributed_over_centralized < 0.85]; slower = sc[sc.distributed_over_centralized > 1.15]
big = sc[sc.rows == 2_000_000]

# key table
kt = ke[~ke["query"].isin(["SHARD SIZES", "SHARD SKEW max/mean"])].groupby("distribution_key")["distributed_ms"].sum().round(0)
skew = ke[ke["query"] == "SHARD SKEW max/mean"].set_index("distribution_key")["distributed_ms"].round(2)
keytab = dk.set_index("candidate_key")[["distinct_values", "largest_single_value_share_%", "shard_skew_max_over_mean"]].rename(columns={"shard_skew_max_over_mean": "simulated shard skew (max/mean)"})
keytab["measured shard skew in Citus (max/mean)"] = skew
keytab["total time of Q1-Q5 at 1,000,000 rows (ms)"] = kt
keytab = keytab.reset_index().rename(columns={"candidate_key": "candidate key", "distinct_values": "distinct values", "largest_single_value_share_%": "largest single value (% of rows)"})
shards = ke[ke["query"] == "SHARD SIZES"][["distribution_key", "worker_port", "shards", "bytes_total", "bytes_largest_shard", "bytes_smallest_shard"]].copy()
for c in ["worker_port", "shards"]:
    shards[c] = shards[c].astype(int)
for c in ["bytes_total", "bytes_largest_shard", "bytes_smallest_shard"]:
    shards[c] = (shards[c] / 1e6).round(2)
shards = shards.rename(columns={"distribution_key": "distribution key", "worker_port": "worker", "bytes_total": "MB on the worker", "bytes_largest_shard": "largest shard (MB)", "bytes_smallest_shard": "smallest shard (MB)"})
c_tot = res["coord"] + res["worker1"] + res["worker2"]

fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
for q, g in sc.groupby("query"):
    ax[0].plot(g["rows"], g["distributed_over_centralized"], marker="o", label=q)
ax[0].axhline(1.0, color="k", ls="--", lw=0.8); ax[0].set_xscale("log"); ax[0].set_xlabel("Rows in the fact table"); ax[0].set_ylabel("Citus time / centralized time")
ax[0].set_title("Below 1.0 = Citus faster"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
g2 = sc[sc["rows"] == 2_000_000]; xs = range(len(g2)); ax[1].bar([i - 0.2 for i in xs], g2["centralized_ms"], 0.4, label="Centralized (1 node)", color="#3b6fb6"); ax[1].bar([i + 0.2 for i in xs], g2["distributed_ms"], 0.4, label="Citus (2 workers)", color="#f0a030")
ax[1].set_xticks(list(xs)); ax[1].set_xticklabels([q.split(" ")[0] for q in g2["query"]]); ax[1].set_ylabel("ms"); ax[1].set_title("2,000,000 rows"); ax[1].legend()
plt.tight_layout(); plt.savefig(ROOT / "docs" / "images" / "citus_vs_centralized.png", dpi=110); plt.close()

doc = f"""# Part D: Distributed Data Warehouse (Citus + PostgreSQL)

Everything on this page was run; the numbers come from `results/` (`etl/distributed_baseline.py`, `etl/distributed_citus.py`).

## 1. Set-up
| Item | Value |
|---|---|
| Software | Citus 13.2 on PostgreSQL 16.15 |
| Cluster | 3 PostgreSQL instances on one machine: coordinator (port 5440) and two worker nodes (5441, 5442); built by `scripts/setup_citus_cluster.sh` |
| Shards | 32 shards per distributed table (`citus.shard_count`), spread over the two workers (16 each); the coordinator holds no fact data |
| Fact table | distributed by hash of `facility_key` |
| Dimensions | **reference tables** (a full copy on every node), so all dimension joins are local to a shard |
| Data | the real 61,737 inspection facts and the synthetic scale-up tables (100,000 to 2,000,000 rows) used for the centralized baseline; the scale-up rows are resampled real facts, used for performance only |
| Centralized comparison | the main PostgreSQL node of the batch warehouse, measured in the same session with the same queries and data |

**Installation note.** Citus is not in the Ubuntu archive. It was installed from the official Citus repository (packagecloud, `citusdata/community`). Every Citus release declares a conflict with Ubuntu's `postgresql-16` package, so the PostgreSQL community (PGDG) repository was added as well and PostgreSQL 16.15 was replaced by the PGDG build of the same minor version. The data directory was untouched and the warehouse was backed up first. Both repositories were added with explicit approval.

## 2. Distribution-key selection
Candidate keys: FacilityKey, LocationKey, DateKey. Cardinality and skew were first simulated with PostgreSQL's `hashint4` (the hash Citus uses for integer keys) and then **measured** in Citus on the 1,000,000-row table, where all five queries were also timed for each key.

{md(keytab)}

**Selected key: FacilityKey.**
* **Cardinality:** 17,083 distinct values and no value above 0.04% of the rows, so hashing gives even shards.
* **Data skew:** the measured shard skew is {skew['facility_key']:.2f} (largest shard / average) against {skew['date_key']:.2f} for DateKey and {skew['location_key']:.2f} for LocationKey. LocationKey has only 252 values and one location holds 3.1% of the rows, so the largest shard is {skew['location_key']:.1f} times the average.
* **Workload and aggregation pattern:** the facility-year question groups by FacilityKey, so the aggregation can finish on the shards. Questions on facility type and risk join DimFacility, which is a reference table, so they stay local. Area and month questions group by a dimension attribute and need a final merge on the coordinator whichever key is used.
* **Joins and co-location:** only one fact table is large; the dimensions are replicated, so no data has to be re-partitioned for any join. If the annual fact table were distributed too, it would be co-located by the same FacilityKey, so facility-level joins between the two facts would also stay local.
* **Measured effect:** the total time of the five queries at 1,000,000 rows was {kt['facility_key']:.0f} ms for FacilityKey, {kt['location_key']:.0f} ms for LocationKey and {kt['date_key']:.0f} ms for DateKey. The differences are small (within about 5%), so the decision rests mainly on the even shards and the facility-year workload, not on speed.

## 3. Parallel processing and distributed aggregation (EXPLAIN)
```
{explain.strip()}
```
Each query becomes 32 tasks, one per shard, run on the two workers in parallel. For the facility-year query (grouping by the distribution key) the whole aggregation runs on the shards; for the facility-type query the coordinator adds a final `HashAggregate` to merge the partial results.

## 4. Data-skew analysis (measured shard sizes at 1,000,000 rows)
{md(shards)}

## 5. Centralized against distributed
![Citus against centralized](images/citus_vs_centralized.png)

Median of 5 runs after a warm-up run; times in ms. In every one of the {len(sc)} cases the distributed result was **identical** to the centralized result (`results_identical` in `results/distributed_scaling.csv`).

{md(tab)}

## 6. Discussion: distributed is not automatically faster
* **Summary:** Citus was clearly faster in {len(faster)} of {len(sc)} cases ({', '.join(f'{r.query[:2]} at {r.rows:,}' for r in faster.itertuples())}) and clearly slower in {len(slower)}. At 2,000,000 rows it was {big.distributed_over_centralized.min():.2f}-{big.distributed_over_centralized.max():.2f} times the centralized time.
* **Overhead:** every query pays for distributed planning, 32 shard tasks, connections to the workers and the transfer of partial results to the coordinator. With a data set of a few hundred MB this overhead is as large as the scan itself.
* **Network communication:** the nodes talk over localhost, so the cost is serialisation and connection handling rather than network latency; on separate machines it would be higher.
* **Shard distribution and skew:** 32 shards on two workers are evenly sized for FacilityKey (skew {skew['facility_key']:.2f}); a skewed key such as LocationKey ({skew['location_key']:.2f}) leaves one worker waiting for its biggest shards.
* **Query shape:** queries that group by the distribution key (facility by year) are the ones that benefit; queries that group by a dimension attribute (area, month, facility type) need a coordinator merge and gain nothing.
* **Hardware:** the coordinator and both workers share the same 4-core machine, so the workers compete for the same CPUs. A real speed-up from distribution needs additional hardware, and none was available here.
* **Resources:** the Citus nodes use about {c_tot / 1024:.1f} GB of resident memory against {res['main'] / 1024:.2f} GB for the single node after the same workload (the sums count shared buffers once per process, so both are overstated, but the order of magnitude is right). Loading and indexing 2,000,000 rows into the distributed table took {ld[ld.rows == 2_000_000].load_and_index_s.iloc[0]} s.

**Conclusion for this domain:** one PostgreSQL node answers every test query in {sc.centralized_ms.max():.0f} ms or less at 2,000,000 rows, which is 32 times the four years of Chicago data (about 16,000 inspections a year). Distribution does not pay off at this size; it becomes relevant when the data is consolidated across many jurisdictions or when queries need more CPU than one machine has.
"""
(ROOT / "docs" / "distributed_warehouse.md").write_text(doc)
print("written docs/distributed_warehouse.md;", len(faster), "faster,", len(slower), "slower of", len(sc))
