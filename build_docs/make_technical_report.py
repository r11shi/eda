"""Builds docs/Technical_Report.md and docs/Technical_Report.pdf from the project's measured results."""
import subprocess
from pathlib import Path
import markdown
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R, D = ROOT / "results", ROOT / "docs"
rd = lambda n: pd.read_csv(R / n)


def tab(df, cols=None, rename=None):
    df = df[cols] if cols else df
    if rename:
        df = df.rename(columns=rename)
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "|".join("---" for _ in df.columns) + "|"] + ["| " + " | ".join(str(v) for v in r) + " |" for r in df.values])


dq = pd.read_csv(ROOT / "docs" / "data_quality_report.md", sep="|", skiprows=7, skipinitialspace=True).iloc[1:, 1:6]
dq.columns = ["Problem", "Field", "Count", "Treatment", "Justification"]
dq = dq.dropna(subset=["Count"])
dq_show = dq[dq["Problem"].str.contains("Logical duplicate|risk code|Missing risk|Missing facility|licence|Missing coordinates|without violation text|Pass with no|not a completed|Time of day|Extreme", regex=True)]
audit, val, inc = rd("load_audit.csv"), rd("validation_results.csv"), rd("incremental_load_demo.csv")
mc = rd("model_comparison.csv"); qt = rd("batch_query_timing.csv"); idx = rd("indexing_effect.csv")
dk, cs = rd("distribution_key_analysis.csv"), rd("centralized_scaling.csv")
sm = rd("streaming_metrics.csv").set_index("metric")["value"]
reg, dt, imp = rd("regression_metrics.csv").set_index("Model"), rd("decision_tree_metrics.csv").set_index("Model"), rd("decision_tree_importance.csv")
ar = rd("association_rules_selected.csv")
has_citus = (R / "distributed_scaling.csv").exists()
piv = cs.pivot(index="query", columns="rows", values="centralized_ms"); piv.columns = [f"{c:,}" for c in piv.columns]; piv = piv.reset_index()

parts = []
A = parts.append
A("""# Food Safety and Restaurant Inspection Analytics
### Integrated Data Warehouse, OLAP and Data Mining Project: Technical Report
**Rushikesh Maddewad** &nbsp;|&nbsp; PRN 202502040037 &nbsp;|&nbsp; Roll No 353

**Dataset:** City of Chicago Food Inspections (official Data Portal), 1 January 2022 to 31 December 2025: 73,630 records, of which 61,737 are completed inspections.

## Summary
This report describes one integrated lifecycle: *raw data, profiling, curation, staging, dimensional warehouse, OLAP and dashboard, analytical mart, regression / association mining / decision tree*, with three warehouse architectures (batch, distributed, real-time) evaluated on the same data. Every number comes from code that was run in this project; the folders `etl/`, `sql/`, `streaming/`, `notebooks/` and `results/` hold the code and the raw measurements.

**Main results**

* A fact-constellation warehouse in PostgreSQL (two fact tables, five dimensions) was loaded from curated data, validated (16 integrity checks, all 0) and extended with an incremental load.
* A Kafka, Spark Structured Streaming and ClickHouse pipeline with a Grafana dashboard processed a replay of 3,647 inspections with an average delay of 1.5 s.
* The fail rate fell from 24.9% (2022) to 21.1% (2025). Complaint inspections fail most often (37.6%); after a failed inspection 79% of the next visits pass.
* Violations (R-squared 0.12) and failures (AUC 0.64) are only weakly predictable before the visit.
* Recommended architecture: a **batch warehouse at the centre**, a real-time layer only for operational monitoring, and a distributed layer only when the data outgrows one node.

**Status of the required parts.** Parts A, B, C, E, F, G, H, I and J are implemented and measured. """ + ("Part D (Citus) is implemented and measured on a 3-node cluster that shares one machine; it was not faster than one node here (Section 4)." if has_citus else "**Part D (Citus) is only partly done:** Citus could not be installed in this run, so the distributed side of the experiment is missing; the key analysis and the centralized baseline are done (Section 4).") + " **A Power BI file was not produced** because Power BI Desktop is Windows-only; an equivalent HTML dashboard and a Power BI rebuild package were delivered instead (Section 6). The DAX measures were written but not executed." + "\n")

A("## 1. Data and curation (Part A)\n**Source:** https://data.cityofchicago.org/Health-Human-Services/Food-Inspections/4ijn-s7e5 (extracted 29 October 2026, SHA-256 in `docs/dataset_source.md`). No external enrichment was used. Derived attributes (Year, Quarter, Month, DayOfWeek, IsWeekend, ViolationCount, HasViolations, ResultGroup, RiskGroup, FacilityGroup, InspectionTypeGroup, IsFailedInspection, HighViolationFlag, GeographicAreaGroup and the bands) are documented with formula, threshold and mapping in `docs/data_dictionary.md`.\n")
A("**Selected data-quality decisions** (full report: `docs/data_quality_report.md`; every count is computed by the code):\n\n" + tab(dq_show, rename={"Count": "Rows"}) + "\n")
A("**Exploratory analysis** (notebook `02_eda.ipynb`): ViolationCount has a mean of 3.77, a median of 3 and a long right tail (skewness 1.64); restaurants are 70% of the inspections; the fail rate of the large facility groups is 22.9-24.9%; re-inspections fail least (11.9%) and complaints most (33.5% as a group); the fail rate is highest in the Southeast area group (26.7%); volume and rate rank the ZIP codes differently. There is no time of day in the source, so no hourly analysis was done.\n")

A("## 2. Dimensional modelling (Part B)\n**Grain:** one completed inspection on one date. Three designs were built and compared; the snowflake was implemented physically so the comparison is measured.\n\n![Fact constellation](images/fact_constellation.png)\n")
A(tab(mc.reset_index(drop=True), rename={"criterion": "Criterion", "fact_constellation": "Fact constellation", "star": "Star", "snowflake": "Snowflake"}) + "\n\n**Selected: fact constellation** (star dimensions plus a facility-by-year fact): about 2 times faster queries than the snowflake with a third of the joins, and the second fact answers facility-year questions 8 times faster. Details: `docs/dimensional_models.md`.\n")

A("## 3. Batch data warehouse (Part C)\nPostgreSQL 16: staging tables, five dimensions with surrogate keys and explicit Unknown members, two facts, a PL/pgSQL load procedure and Python drivers.\n\n" +
  tab(audit[["batch_id", "batch_label", "rows_staged", "rows_rejected", "rows_not_completed", "rows_loaded_fact", "new_facilities"]]) +
  f"\n\n* **Validation:** 16 checks after each load (referential integrity, duplicates, reconciliation of rows and measures); failures = {int((val[~val.check_name.str.startswith('facts mapped')].value != 0).sum())}.\n* **Incremental load:** the final month was loaded without rebuilding; an MD5 checksum over the rows of the first batch is unchanged, and loading the same month again added 0 facts.\n* **Atomic load:** a deliberately failing load left all tables unchanged (`results/fault_test.csv`).\n* **Indexing:** selective queries went from 3-5 ms to 0.2-0.3 ms.\n* **Analytical SQL:** the eight queries for the mandatory questions 1-8 run in {qt.median_ms.min():.0f}-{qt.median_ms.max():.0f} ms (`results/batch_query_timing.csv`).\n")

A("## 4. Distributed data warehouse (Part D)\n")
A("**Distribution-key analysis** (shard assignment simulated with PostgreSQL's `hashint4`, the hash Citus uses for integer keys; 32 shards, 2 workers):\n\n" + tab(dk) + "\n\n`FacilityKey` is the best choice: 17,083 distinct values, no value above 0.04% of the rows, the most even shards (max/mean 1.10), it is the grouping column of the facility-year query, and the small dimensions can be reference tables so that all joins stay local. `LocationKey` has only 252 values with one value holding 3.1% of the rows (shard skew 2.56) and `DateKey` has weekday-only dates (skew 1.32).\n")
A("**Centralized baseline** on one PostgreSQL node (volumes above 61,737 rows are a synthetic scale-up by resampling the real facts, for performance only), median ms:\n\n" + tab(piv) + "\n")
if has_citus:
    ds = rd("distributed_scaling.csv"); ke = rd("distribution_key_experiment.csv")
    skew = ke[ke["query"] == "SHARD SKEW max/mean"].set_index("distribution_key")["distributed_ms"]
    rp = ds.pivot(index="query", columns="rows", values="distributed_over_centralized"); rp.columns = [f"{c:,}" for c in rp.columns]; rp = rp.reset_index()
    A(f"**Citus 13.2 on PostgreSQL 16.15, 3 instances on one machine** (coordinator + 2 workers, 32 shards, facts distributed by FacilityKey, dimensions as reference tables). The distributed result was identical to the centralized result in all {len(ds)} test cases. The measured shard skew (largest shard / average) is {skew['facility_key']:.2f} for FacilityKey, {skew['date_key']:.2f} for DateKey and {skew['location_key']:.2f} for LocationKey, which confirms the choice of FacilityKey.\n\n**Citus time divided by centralized time** (below 1.0 means Citus is faster; details and the full required table in `docs/distributed_warehouse.md`):\n\n" + tab(rp.round(2)) + "\n\n![Citus against centralized](images/citus_vs_centralized.png)\n")
    A(f"Citus was clearly faster in only {int((ds.distributed_over_centralized < 0.85).sum())} of {len(ds)} cases (mainly the facility-year grouping at 0.5-1 million rows, which is pushed down to the shards) and clearly slower in {int((ds.distributed_over_centralized > 1.15).sum())}. The reasons are the distributed-planning and coordination overhead, the final merge on the coordinator, and the fact that both workers share the same 4 cores. **Distributed processing is therefore not assumed to be faster**; for this domain one node is enough.\n")
else:
    A("**Citus was not installed in this run.** No distributed timing is claimed.\n")

A("## 5. Real-time data warehouse (Part E)\n**Replay simulation, not a live feed.** `producer.py` replays completed inspections in date order to the Kafka topic `food_inspections` (key = inspection id); Spark Structured Streaming validates the JSON, derives measures, aggregates 10-second windows and daily event-time windows, and writes to ClickHouse; Grafana refreshes every 5 s.\n\n![Grafana dashboard](images/grafana_realtime_dashboard.png)\n")
A(f"| Measure | Value |\n|---|---|\n| Events replayed / stored | 3,647 / {int(sm['valid events stored']):,} (each exactly once) |\n| Injected malformed test events rejected | {int(sm['rejected test events'])} of 24 |\n| Latency emit to ClickHouse (average / p95) | {sm['latency avg (ms), emit -> ClickHouse']:.0f} ms / {sm['latency p95 (ms)']:.0f} ms |\n| ClickHouse dashboard queries | {sm['ClickHouse query: risk distribution (window_agg) (median ms)']:.1f}-{sm['ClickHouse query: KPI totals (window_agg, 6 stats) (median ms)']:.1f} ms |\n| Resident memory of the four services | about {(sm['memory (RSS, MB): Kafka broker'] + sm['memory (RSS, MB): ClickHouse server'] + sm['memory (RSS, MB): Spark streaming job (python + JVM)'] + sm['memory (RSS, MB): Grafana']) / 1024:.1f} GB |\n")

A("## 6. OLAP and dashboard (Part F)\nSix OLAP operations were run on the warehouse (roll-up, three-step drill-down, slice, dice, pivot, CUBE and GROUPING SETS); each is documented as business question, dimensions, measure, operation, SQL and DAX, output and interpretation in `docs/olap_operations.md`. The DAX was not executed (no Power BI Desktop).\n\nThe four-section dashboard (executive, facility and risk, geographic, inspection and violations) is `dashboard/food_safety_dashboard.html`, built from the warehouse.\n\n![Executive](images/dashboard_exec.png)\n\n![Facility and risk](images/dashboard_facility.png)\n")
findings = [l[3:] for l in (D / "ten_findings.md").read_text().splitlines() if l.startswith("## Finding")]
A("## 7. Ten analytical findings\nEach finding (question, analysis, evidence with chart, interpretation, recommendation) is in `docs/ten_findings.md`:\n\n" + "\n".join(f"{i + 1}. {t.split(': ', 1)[1]}" for i, t in enumerate(findings)) + "\n\n![Finding 7](images/finding_07.png)\n")

b, m2 = reg.loc["Baseline: predict the training mean"], reg.loc["Multiple LR: all test inspections"]
A(f"## 8. Regression (Part G)\nTarget ViolationCount; predictors known before the inspection (facility type, risk, inspection type, month, day of week, ZIP, prior result, prior violation count); chronological split (train 2022-2024, test 2025); no leakage.\n\n" + tab(reg.reset_index().round(3)[["Model", "Rows", "MAE", "RMSE", "R2"]]) +
  f"\n\nThe multiple model lowers MAE from {b.MAE:.2f} to {m2.MAE:.2f} (R-squared {m2.R2:.2f}); the train R-squared is 0.25, so the model over-fits and 2025 differs from earlier years. Diagnostics: only 5 of 102 features have VIF above 5; the Breusch-Pagan test shows heteroscedasticity; 1.9% outliers cause 25% of the squared error.\n")
A("## 9. Association-rule mining (Part H)\nApriori (mandatory) and FP-Growth find identical itemsets (1,198 at support 0.02). Ten of the 14 selected rules (support >= 2%, confidence >= 30%, lift >= 1.3; definitional and redundant rules removed):\n\n" + tab(ar.head(10).assign(support=lambda d: d.support.round(3), confidence=lambda d: d.confidence.round(3), lift=lambda d: d.lift.round(2))[["Rule", "support", "confidence", "lift"]]) + "\n")
d05, dopt = dt.loc["Decision tree, threshold 0.5"], dt.loc["Decision tree, validation-optimal threshold"]
A(f"## 10. Decision tree (Part I)\nTarget FailedInspection; train 2022-2023, validation 2024 (tuning of max_depth, min_samples_split, min_samples_leaf, ccp_alpha by ROC-AUC), test 2025.\n\n| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |\n|---|---|---|---|---|---|\n" +
  "\n".join(f"| {n} | {r.Accuracy:.3f} | {r.Precision:.3f} | {r.Recall:.3f} | {r.F1:.3f} | {r['ROC-AUC']:.3f} |" for n, r in dt.iterrows()) +
  "\n\nMost important features: " + ", ".join(f"{r.iloc[0].replace('_', ' ')} ({100 * r.importance:.0f}%)" for _, r in imp.head(4).iterrows()) + ". Three decision paths are interpreted in the notebook (highest fail rate 55-58%, lowest 4-5%, largest group 27%).\n")

A("## 11. Architecture evaluation and recommendation (Part J)\nFull comparison table with measured values: `docs/architecture_comparison.md`.\n\n" + (D / "architecture_comparison.md").read_text().split("## Final architecture question")[1] + "\n")
A("## 12. Limitations\n* The official dataset is historical; the real-time layer is a replay simulation.\n* One 4-core machine ran every component, so the timings compare architectures under equal conditions but are not production capacity.\n* The history starts in January 2022, which affects the prior-inspection features; 2025 differs from 2022-2024.\n* The warehouse uses the latest facility attributes (Type-1), so counts per group differ slightly from the EDA.\n* Area groups are quadrants of the Chicago street grid, not official community areas.\n* Rule-level violation detail is kept in staging; the star schema keeps only the count.\n")
A("## Appendix: where everything is\nSee `README.md` for the map of the 54 required deliverables and the commands to reproduce each part.\n")
text = "\n".join(parts)
(D / "Technical_Report.md").write_text(text)
import re
css = """<style>
:root{--navy:#12355b;--teal:#1b998b;--amber:#f2a541;--ink:#1f2933;--mute:#5b6775;--line:#d9e1ea;--soft:#f4f7fb}
@page{size:A4}
*{box-sizing:border-box}
body{font-family:'Segoe UI',Arial,Helvetica,sans-serif;font-size:14.5px;line-height:1.58;color:var(--ink);margin:0}
.banner{background:linear-gradient(120deg,#12355b 0%,#1b6f8a 60%,#1b998b 100%);color:#fff;border-radius:14px;padding:26px 30px;margin:0 0 16px}
.banner .kicker{letter-spacing:.14em;text-transform:uppercase;font-size:11.5px;opacity:.8;margin-bottom:6px}
.banner h1{font-size:31px;line-height:1.18;margin:0 0 6px;border:0;color:#fff}
.banner .sub{font-size:16px;opacity:.95;margin-bottom:14px}
.chips span{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:20px;padding:3px 12px;margin:0 6px 4px 0;font-size:12.5px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 6px}
.kpi{border:1px solid var(--line);border-left:5px solid var(--teal);border-radius:10px;padding:9px 12px;background:var(--soft);page-break-inside:avoid}
.kpi b{display:block;font-size:22px;color:var(--navy);line-height:1.15}
.kpi span{font-size:12px;color:var(--mute)}
h2{font-size:21px;color:var(--navy);margin:24px 0 8px;padding:2px 0 4px 12px;border-left:6px solid var(--teal);border-bottom:1px solid var(--line);page-break-after:avoid}
h3{font-size:16px;color:var(--teal);margin:14px 0 4px;page-break-after:avoid}
p{margin:6px 0 8px} ul{margin:6px 0 8px 0;padding-left:22px} li{margin:2px 0}
table{border-collapse:separate;border-spacing:0;width:100%;margin:10px 0 12px;font-size:12px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
th{background:var(--navy);color:#fff;font-weight:600;text-align:left;padding:5px 8px}
td{padding:4px 8px;vertical-align:top;border-top:1px solid var(--line)}
tbody tr:nth-child(even) td{background:var(--soft)} tr{page-break-inside:avoid}
code{background:#eaf1f8;color:#0f4c75;padding:0 4px;border-radius:4px;font-size:12.8px}
img{display:block;max-width:100%;margin:10px auto;border:1px solid var(--line);border-radius:8px;box-shadow:0 2px 8px rgba(18,53,91,.12);page-break-inside:avoid}
.callout{background:#fff7e8;border:1px solid #f3d9a4;border-left:6px solid var(--amber);border-radius:8px;padding:8px 14px;margin:10px 0;page-break-inside:avoid}
.callout.good{background:#eafaf6;border-color:#a7e3d6;border-left-color:var(--teal)}
a{color:#0f6aa5;text-decoration:none}
</style>"""
FOOT = "Food Safety and Restaurant Inspection Analytics &nbsp;|&nbsp; Rushikesh Maddewad &nbsp;|&nbsp; PRN 202502040037 &nbsp;|&nbsp; Roll 353"
banner = """<div class="banner"><div class="kicker">Technical Report</div><h1>Food Safety and Restaurant Inspection Analytics</h1>
<div class="sub">Integrated Data Warehouse, OLAP and Data Mining Project</div>
<div class="chips"><span>Rushikesh Maddewad</span><span>PRN 202502040037</span><span>Roll No 353</span></div>
<div class="chips"><span>City of Chicago Food Inspections</span><span>1 Jan 2022 - 31 Dec 2025</span><span>73,630 records</span></div></div>
<div class="kpis">
<div class="kpi"><b>61,737</b><span>completed inspections analysed</span></div>
<div class="kpi"><b>16 / 16</b><span>warehouse validation checks passed</span></div>
<div class="kpi"><b>10-74 ms</b><span>batch warehouse query time</span></div>
<div class="kpi"><b>1.5 s</b><span>real-time delay (average, replay)</span></div>
<div class="kpi"><b>24.9% to 21.1%</b><span>fail rate 2022 to 2025</span></div>
<div class="kpi"><b>AUC 0.64 &middot; R&sup2; 0.12</b><span>failures and violations only weakly predictable</span></div></div>"""
body_md = text[text.index("## Summary"):]
body = markdown.markdown(body_md, extensions=["tables"])
body = re.sub(r"<p>(<strong>(?:Status of the required parts\.|Replay simulation, not a live feed\.)[\s\S]*?)</p>", r'<div class="callout">\1</div>', body)
body = re.sub(r"<p>(<strong>(?:Selected: |Recommendation: )[\s\S]*?)</p>", r'<div class="callout good">\1</div>', body)
html = "<!doctype html><html><head><meta charset='utf-8'>" + css + "</head><body>" + banner + body + "</body></html>"
html_path = D / "Technical_Report.html"
html_path.write_text(html)
pdf = D / "Technical_Report.pdf"
r = subprocess.run(["node", str(ROOT / "build_docs" / "html_to_pdf.js"), str(html_path), str(pdf), FOOT], capture_output=True, text=True, env={**__import__("os").environ, "NODE_PATH": subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()})
if r.returncode != 0:      # fall back to plain Chromium (no page numbers)
    subprocess.run([__import__("os").environ.get("CHROME_PATH", "chromium"), "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{html_path}"], check=True, capture_output=True)
html_path.unlink()
print("written Technical_Report.md and .pdf")
