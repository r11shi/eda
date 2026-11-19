"""Writes docs/ten_findings.md (and docs/images/finding_XX.png) from the MEASURED results:
results/analytical_query_results/*.csv (SQL on the warehouse) and the mining results exported by notebooks 07-09.
Format of every finding: Question > Analysis > Evidence > Interpretation > Recommendation."""
import collections, re
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
Q, R, IMG = ROOT / "results" / "analytical_query_results", ROOT / "results", ROOT / "docs" / "images"
GREEN, ORANGE, RED, BLUE, GREY = "#2e8b57", "#f0a030", "#d64545", "#3b6fb6", "#8c96a3"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})
rd = lambda name: pd.read_csv(Q / f"{name}.csv")
md_table = lambda df: "\n".join(["| " + " | ".join(df.columns) + " |", "|" + "|".join("---" for _ in df.columns) + "|"] + ["| " + " | ".join(str(v) for v in r) + " |" for r in df.values])
out = ["# Ten Analytical Findings", "",
       "Every finding follows **Question > Analysis > Evidence > Interpretation > Recommendation** and contains the measure, the dimensions or filters, and a chart. All numbers come from SQL on the PostgreSQL warehouse (`sql/06_analytical_queries.sql`) or from the mining notebooks 07-09. "
       "Findings 1-8 answer mandatory questions 1-8, finding 9 answers question 9 (association rules) and finding 10 question 10 (prediction).", ""]


def finding(n, title, question, analysis, evidence, interpretation, recommendation):
    out.extend([f"## Finding {n}: {title}", "", f"**Question.** {question}", "", f"**Analysis.** {analysis}", "", "**Evidence.**", "", evidence, "",
                f"**Interpretation.** {interpretation}", "", f"**Recommendation.** {recommendation}", ""])


# ---------------------------------------------------------------- 1 volume
y, m = rd("Q1a"), rd("Q1b")
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].bar(y["year"].astype(str), y["inspections"], color=BLUE); [ax[0].text(i, v + 150, f"{v:,}", ha="center") for i, v in enumerate(y["inspections"])]
ax[0].set_title("Inspections per year"); ax[0].set_ylim(0, 19000)
for yr, g in m.groupby("year"): ax[1].plot(g["month"], g["inspections"], marker="o", label=str(yr))
ax[1].set_xticks(range(1, 13)); ax[1].set_title("Inspections per month"); ax[1].legend(ncol=2)
plt.tight_layout(); plt.savefig(IMG / "finding_01.png", dpi=110); plt.close()
top3, low3 = m.nlargest(3, "inspections"), m.nsmallest(3, "inspections")
f = lambda r: f"{r.month_name} {int(r.year)} ({int(r.inspections):,})"
growth = 100 * (y.inspections.iloc[-1] / y.inspections.iloc[0] - 1)
finding(1, "Inspection volume grew 12% in four years and has no stable seasonal peak",
        "How many inspections are completed per month and per year?", "Measure: InspectionCount. Dimensions: DimDate (Year, Month). Filter: completed inspections 2022-2025. SQL: Q1a and Q1b.",
        f"Yearly totals: " + ", ".join(f"{int(a)}: {int(b):,}" for a, b in zip(y.year, y.inspections)) + f". Busiest months: {', '.join(f(r) for r in top3.itertuples())}. Quietest months: {', '.join(f(r) for r in low3.itertuples())}.\n\n![Finding 1](images/finding_01.png)",
        f"The yearly volume rose from {y.inspections.iloc[0]:,} to {y.inspections.iloc[-1]:,} (+{growth:.1f}%). The busiest and quietest months differ from year to year, so there is no month that is busy every year; two of the three quietest months are January and February 2022.",
        "Plan the inspector capacity on a steady workload of about 1,300 to 1,650 inspections per month instead of a fixed seasonal peak, and review the capacity every quarter against the actual volume.")

# ---------------------------------------------------------------- 2 facility types
f2 = rd("Q2").head(8)
fig, ax = plt.subplots(figsize=(9, 4.2)); ax.barh(f2["facility_type"][::-1], f2["inspections"][::-1], color=BLUE)
[ax.text(v + 300, i, f"{p:.1f}%", va="center") for i, (v, p) in enumerate(zip(f2["inspections"][::-1], f2["pct_of_all"][::-1]))]
ax.set_title("Facility types with the most inspections"); ax.set_xlim(0, 52000); plt.tight_layout(); plt.savefig(IMG / "finding_02.png", dpi=110); plt.close()
finding(2, "Restaurants receive seven of every ten inspections",
        "Which facility types receive the most inspections?", "Measure: InspectionCount and its share. Dimension: DimFacility (Facility Type). SQL: Q2.",
        md_table(f2[["facility_type", "inspections", "pct_of_all"]].rename(columns={"pct_of_all": "% of all"})) + "\n\n![Finding 2](images/finding_02.png)",
        f"Restaurants alone have {f2.inspections.iloc[0]:,} inspections ({f2.pct_of_all.iloc[0]:.1f}%). The top 8 facility types cover {f2.pct_of_all.sum():.1f}% of all inspections; the other types are many small groups.",
        "Direct the main training and outreach effort at restaurants because they carry the volume, but track the rarer types (such as liquor stores and retail) by their failure rate (finding 7 and 4) and not only by their volume.")

# ---------------------------------------------------------------- 3 rates by year
q3 = rd("Q3")
fig, ax = plt.subplots(figsize=(9, 4.2)); bottom = np.zeros(len(q3))
for col, c, lab in [("pass_rate", GREEN, "Pass"), ("conditional_rate", ORANGE, "Pass w/ Conditions"), ("fail_rate", RED, "Fail")]:
    ax.bar(q3["year"].astype(str), q3[col], bottom=bottom, color=c, label=lab); [ax.text(i, b + v / 2, f"{v:.1f}", ha="center", color="white") for i, (b, v) in enumerate(zip(bottom, q3[col]))]; bottom += q3[col].values
ax.set_title("Result mix by year (%)"); ax.legend(loc="lower right"); plt.tight_layout(); plt.savefig(IMG / "finding_03.png", dpi=110); plt.close()
finding(3, "The fail rate fell from 24.9% to 21.1% while passes rose",
        "How do the pass, conditional-pass and fail rates change over time?", "Measures: PassRate, ConditionalPassRate, FailureRate. Dimension: DimDate (Year). SQL: Q3.",
        md_table(q3.rename(columns={"pass_rate": "pass %", "conditional_rate": "conditional %", "fail_rate": "fail %"})) + "\n\n![Finding 3](images/finding_03.png)",
        f"The fail rate was {q3.fail_rate.iloc[0]:.2f}% in 2022 and {q3.fail_rate.iloc[1]:.2f}% in 2023, then dropped to {q3.fail_rate.iloc[2]:.2f}% in 2024 and {q3.fail_rate.iloc[3]:.2f}% in 2025. The pass rate rose from {q3.pass_rate.iloc[0]:.1f}% to {q3.pass_rate.iloc[3]:.1f}% and the conditional-pass rate fell from {q3.conditional_rate.iloc[0]:.1f}% to {q3.conditional_rate.iloc[3]:.1f}%. The data cannot show whether this is better compliance or a change in inspection practice.",
        "Investigate what changed in 2024 (inspector practice, re-inspection rules or compliance programmes) before claiming an improvement, and report the fail rate every month together with the number of inspections.")

# ---------------------------------------------------------------- 4 risk
q4 = rd("Q4"); q4 = q4[q4.risk_group != "Unknown"]
fig, ax = plt.subplots(1, 2, figsize=(12, 4)); x = np.arange(len(q4)); w = 0.27
for i, (col, c, lab) in enumerate([("pass_rate", GREEN, "Pass"), ("conditional_rate", ORANGE, "Conditional"), ("fail_rate", RED, "Fail")]):
    ax[0].bar(x + (i - 1) * w, q4[col], w, color=c, label=lab)
ax[0].set_xticks(x); ax[0].set_xticklabels([f"{r}\n(n={n:,})" for r, n in zip(q4.risk_group, q4.inspections)]); ax[0].set_title("Result rates (%) by risk category"); ax[0].legend()
ax[1].bar(q4["risk_group"], q4["avg_violations"], color=BLUE); [ax[1].text(i, v + 0.05, f"{v:.2f}", ha="center") for i, v in enumerate(q4["avg_violations"])]; ax[1].set_title("Average violations per inspection")
plt.tight_layout(); plt.savefig(IMG / "finding_04.png", dpi=110); plt.close()
finding(4, "The risk category does not change how often an inspection fails, but high-risk places record more violations",
        "How do the results compare across the risk categories?", "Measures: PassRate, ConditionalPassRate, FailureRate, AverageViolations. Dimension: DimFacility (Risk Group). SQL: Q4.",
        md_table(q4.rename(columns={"risk_group": "risk", "pass_rate": "pass %", "conditional_rate": "conditional %", "fail_rate": "fail %", "avg_violations": "avg violations"})) + "\n\n![Finding 4](images/finding_04.png)",
        f"The fail rate is {q4.fail_rate.iloc[0]:.1f}% for high, {q4.fail_rate.iloc[1]:.1f}% for medium and {q4.fail_rate.iloc[2]:.1f}% for low risk, so the risk category does not separate failing from passing. The average violation count does fall from {q4.avg_violations.iloc[0]:.2f} (high) to {q4.avg_violations.iloc[2]:.2f} (low). The risk category describes the hazard of the business and its inspection frequency, not the chance of a fail on a given visit.",
        "Keep the risk category for scheduling, but do not use it alone to decide where failures are likely; combine it with inspection type and inspection history (findings 5, 8 and 10).")

# ---------------------------------------------------------------- 5 inspection types
q5 = rd("Q5").sort_values("fail_rate")
fig, ax = plt.subplots(figsize=(9, 4.2)); ax.barh(q5["inspection_type"], q5["fail_rate"], color=[RED if v > 23.3 else GREY for v in q5["fail_rate"]])
[ax.text(v + 0.5, i, f"{v:.1f}%  (n={n:,})", va="center") for i, (v, n) in enumerate(zip(q5["fail_rate"], q5["inspections"]))]
ax.axvline(23.1, color="k", ls="--", lw=0.8); ax.set_xlim(0, 52); ax.set_title("Fail rate by inspection type (dashed line = overall 23.1%)"); plt.tight_layout(); plt.savefig(IMG / "finding_05.png", dpi=110); plt.close()
c, l, cn, sf, ri = (q5.set_index("inspection_type").loc[k, "fail_rate"] for k in ["Complaint", "License", "Canvass", "Short Form Complaint", "Canvass Re-Inspection"])
finding(5, "Complaint inspections fail most often; re-inspections fail least",
        "Which inspection types are associated with higher failure rates?", "Measures: InspectionCount, FailCount, FailureRate. Dimension: DimInspectionType (types with at least 100 inspections). SQL: Q5.",
        md_table(q5.sort_values("fail_rate", ascending=False)[["inspection_type", "inspections", "fails", "fail_rate"]].rename(columns={"fail_rate": "fail %"})) + "\n\n![Finding 5](images/finding_05.png)",
        f"Full *Complaint* inspections fail {c:.1f}% of the time, about 1.5 times the routine canvass rate ({cn:.1f}%); licence inspections are at {l:.1f}%. *Short Form Complaint* inspections fail only {sf:.1f}%, so grouping all complaints together hides a big difference. Re-inspections fail least (canvass re-inspection {ri:.1f}%), which shows that most businesses correct their problems.",
        "Triage complaint inspections first because they are the most likely to find a failure, and keep the re-inspection step for every failure (see finding 8).")

# ---------------------------------------------------------------- 6 violations
q6a, q6b = rd("Q6a"), rd("Q6b").head(10)
raw = pd.read_csv(ROOT / "data" / "raw" / "food_inspections_2022_2025.csv", dtype=str, usecols=["violations"]).violations.dropna()
titles = collections.defaultdict(collections.Counter)
for t in raw:
    for part in t.split("|"):
        mm = re.match(r"^\s*(\d+)\.\s*(.*?)\s*-\s*Comments", part.strip())
        if mm:
            titles[int(mm.group(1))][mm.group(2)] += 1
q6b["rule"] = [f"{r}. {titles[r].most_common(1)[0][0][:52].title()}" for r in q6b["rule_number"]]
fig, ax = plt.subplots(1, 2, figsize=(14, 4.2))
ax[0].bar(q6a["result_group"], q6a["avg_violations"], color=[RED, ORANGE, GREEN]); [ax[0].text(i, v + 0.1, f"{v:.2f}", ha="center") for i, v in enumerate(q6a["avg_violations"])]; ax[0].set_title("Average violations per inspection by result")
ax[1].barh(q6b["rule"][::-1], q6b["pct_of_inspections"][::-1], color=BLUE); ax[1].set_title("Most cited violation rules (% of inspections)"); ax[1].tick_params(axis="y", labelsize=8)
plt.tight_layout(); plt.savefig(IMG / "finding_06.png", dpi=110); plt.close()
finding(6, "Failing inspections cite three times the violations of passing ones, and the most common violations are about premises and cleanliness",
        "How many violations are recorded, and which violation patterns are the most common?", "Measures: AverageViolations, high-violation inspections (6 or more), citation share per rule number. Dimensions: DimResult (Result Group); rule numbers parsed from the violation text in staging (the star schema keeps only the count). SQL: Q6a and Q6b.",
        md_table(q6a.rename(columns={"inspections_with_known_count": "inspections", "avg_violations": "average", "median_violations": "median", "max_violations": "max", "high_violation_inspections": "6+ violations"})) +
        "\n\nMost cited rules:\n\n" + md_table(q6b[["rule", "inspections_citing_rule", "pct_of_inspections"]].rename(columns={"inspections_citing_rule": "inspections", "pct_of_inspections": "% of inspections"})) + "\n\n![Finding 6](images/finding_06.png)",
        f"A failed inspection records {q6a.avg_violations.iloc[0]:.2f} violations on average (median {q6a.median_violations.iloc[0]:.0f}), a conditional pass {q6a.avg_violations.iloc[1]:.2f} and a pass {q6a.avg_violations.iloc[2]:.2f}. The most cited rule is rule {int(q6b.rule_number.iloc[0])} ({q6b.pct_of_inspections.iloc[0]:.0f}% of all inspections) and the next ones are about food-contact surfaces, handwashing sinks, plumbing and pests. The leading violations are about upkeep of the premises and cleanliness, not about food temperature.",
        "Build the pre-inspection guidance and the owner training around the five most cited rules, because each of them appears in about a fifth to two thirds of all inspections.")

# ---------------------------------------------------------------- 7 geography
a, z1, z2 = rd("Q7a"), rd("Q7b").head(8), rd("Q7c").head(8)
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
ax[0].barh(z1["zip"].astype(str)[::-1], z1["fail_rate"][::-1], color=RED); ax[0].set_title("Highest fail RATE (ZIPs with 200+ inspections)"); [ax[0].text(v + 0.3, i, f"{v:.1f}%", va="center") for i, v in enumerate(z1["fail_rate"][::-1])]; ax[0].set_xlim(0, 45)
ax[1].barh(z2["zip"].astype(str)[::-1], z2["fails"][::-1], color=BLUE); ax[1].set_title("Highest fail COUNT"); [ax[1].text(v + 5, i, f"{v} ({r:.1f}%)", va="center") for i, (v, r) in enumerate(zip(z2["fails"][::-1], z2["fail_rate"][::-1]))]; ax[1].set_xlim(0, 700)
plt.tight_layout(); plt.savefig(IMG / "finding_07.png", dpi=110); plt.close()
both = sorted(set(z1.zip.astype(str)) & set(z2.zip.astype(str)))
finding(7, "The ZIP codes with the highest failure rates are mostly not the ones with the most failures",
        "Which geographic areas have high failure counts and which have high failure rates?", "Measures: FailCount and FailureRate. Dimension: DimLocation (area group and ZIP; ZIPs with at least 200 inspections for the rate). SQL: Q7a, Q7b and Q7c.",
        "Area groups:\n\n" + md_table(a.rename(columns={"geographic_area_group": "area", "fail_rate": "fail %"})) + "\n\n![Finding 7](images/finding_07.png)",
        f"By area group the Southeast has the highest fail rate ({a.set_index('geographic_area_group').loc['Southeast', 'fail_rate']:.1f}%) and the Northeast the lowest ({a.set_index('geographic_area_group').loc['Northeast', 'fail_rate']:.1f}%). By ZIP, the highest rates are in {', '.join(z1.zip.astype(str).head(4))} (up to {z1.fail_rate.iloc[0]:.1f}%), while the ZIPs with the most failures are {', '.join(z2.zip.astype(str).head(3))}. Only {', '.join(both) if both else 'no ZIP'} appears in both lists. Volume and rate point to different places, so raw totals would send inspectors to the wrong areas.",
        f"Use the failure rate to choose areas for targeted outreach (ZIP {', '.join(z1.zip.astype(str).head(5))}) and the failure count to size the inspector capacity (ZIP {', '.join(z2.zip.astype(str).head(3))}).")

# ---------------------------------------------------------------- 8 repeat inspections
r8a, r8b = rd("Q8a"), rd("Q8b").iloc[0]
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].bar(r8a["inspection_number"], r8a["fail_rate"], color=[RED if v > 25 else GREY for v in r8a["fail_rate"]]); [ax[0].text(i, v + 0.4, f"{v:.1f}%", ha="center") for i, v in enumerate(r8a["fail_rate"])]; ax[0].set_title("Fail rate by position in the facility's history"); ax[0].set_ylim(0, 35)
ax[1].bar(["Next is Pass", "Next is Fail", "Other"], [r8b.next_is_pass_pct, r8b.next_is_fail_pct, 100 - r8b.next_is_pass_pct - r8b.next_is_fail_pct], color=[GREEN, RED, GREY]); ax[1].set_title("Result of the next inspection after a Fail (%)")
[ax[1].text(i, v + 1, f"{v:.1f}%", ha="center") for i, v in enumerate([r8b.next_is_pass_pct, r8b.next_is_fail_pct, 100 - r8b.next_is_pass_pct - r8b.next_is_fail_pct])]
plt.tight_layout(); plt.savefig(IMG / "finding_08.png", dpi=110); plt.close()
finding(8, "Follow-up works: after a failed inspection the next visit passes 79% of the time, on average 13 days later",
        "What happens at repeat inspections of the same establishment?", "Measures: FailureRate by inspection sequence number and by the outcome of the next inspection. Dimensions: DimFacility (licensed facilities only, because only the licence number identifies a facility reliably), DimDate (order of inspections; window functions). SQL: Q8a and Q8b.",
        md_table(r8a.rename(columns={"fail_rate": "fail %"})) + f"\n\nAfter a failed inspection ({int(r8b.failed_inspections_with_a_next_inspection):,} cases with a later inspection): next inspection is a pass {r8b.next_is_pass_pct:.1f}%, a fail {r8b.next_is_fail_pct:.1f}%, average {r8b.avg_days_to_next:.0f} days later.\n\n![Finding 8](images/finding_08.png)",
        f"The first inspection of a facility in the data fails {r8a.fail_rate.iloc[0]:.1f}% of the time, against {r8a.fail_rate.iloc[1]:.1f}% to {r8a.fail_rate.iloc[2]:.1f}% for later ones. The history starts in January 2022, so the first inspection in the data is not always the first ever. Most failures are corrected quickly: {r8b.next_is_pass_pct:.0f}% of the next inspections pass, and only {r8b.next_is_fail_pct:.0f}% fail again.",
        f"Keep a short re-inspection cycle (about two weeks) after every failure, and put the {r8b.next_is_fail_pct:.0f}% of facilities that fail again on an escalation list.")

# ---------------------------------------------------------------- 9 association rules
ar = pd.read_csv(R / "association_rules_selected.csv")
top = ar.head(8).copy()
fig, ax = plt.subplots(figsize=(10, 4.6)); lab = [f"{r[:58]}" for r in top["Rule"]][::-1]
ax.barh(lab, top["confidence"][::-1] * 100, color=BLUE); [ax.text(c * 100 + 1, i, f"conf {c * 100:.0f}%, lift {l:.1f}, support {s * 100:.1f}%", va="center", fontsize=8) for i, (c, l, s) in enumerate(zip(top["confidence"][::-1], top["lift"][::-1], top["support"][::-1]))]
ax.set_xlim(0, 125); ax.set_title("Association rules (Apriori, support >= 2%): confidence"); ax.tick_params(axis="y", labelsize=7); plt.tight_layout(); plt.savefig(IMG / "finding_09.png", dpi=110); plt.close()
tab = ar.head(6)[["Rule", "support", "confidence", "lift"]].copy()
for col in ["support", "confidence", "lift"]: tab[col] = tab[col].round(3)
finding(9, "Ten or more violations mean a 69% chance of failing; follow-up and licence visits are the cleanest",
        "Which combinations of facility, risk, inspection type and result characteristics occur together?", "Method: Apriori and FP-Growth on 61,185 inspections, 7 categorical items each (facility type, risk, inspection type group, result, violation band, area, season); support >= 2%, confidence >= 30%, lift >= 1.3; definitional and redundant rules removed. Source: notebook 08.",
        md_table(tab) + "\n\n(The notebook lists 14 rules with an interpretation each.)\n\n![Finding 9](images/finding_09.png)",
        "Failing becomes much more likely as the violation count grows (43% at 6-9 violations, 69% at 10 or more, against 23% overall). Zero-violation inspections are concentrated in re-inspections and passed licence inspections, which agrees with finding 8. Low-risk inspections are mostly of grocery stores (62%, lift 6.5). No selected rule involves the season.",
        "Treat 10 or more violations as an automatic trigger for an early re-inspection, use the clean-licence pattern to fast-track new licences, and plan low-risk routes around grocery stores.")

# ---------------------------------------------------------------- 10 prediction
reg, dt = pd.read_csv(R / "regression_metrics.csv").set_index("Model"), pd.read_csv(R / "decision_tree_metrics.csv").set_index("Model")
bm, mm_ = reg.loc["Baseline: predict the training mean"], reg.loc["Multiple LR: all test inspections"]
d05, dopt = dt.loc["Decision tree, threshold 0.5"], dt.loc["Decision tree, validation-optimal threshold"]
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].bar(["Baseline", "Multiple linear\nregression"], [bm.MAE, mm_.MAE], color=[GREY, BLUE]); [ax[0].text(i, v + 0.03, f"{v:.2f}", ha="center") for i, v in enumerate([bm.MAE, mm_.MAE])]; ax[0].set_title(f"ViolationCount: test MAE (R2 = {mm_.R2:.3f})"); ax[0].set_ylim(0, 3.3)
ax[1].bar(["Decision tree\nROC-AUC", "Recall at\nthreshold 0.217", "Precision at\nthreshold 0.217"], [d05["ROC-AUC"], dopt.Recall, dopt.Precision], color=[BLUE, GREEN, ORANGE]); [ax[1].text(i, v + 0.02, f"{v:.2f}", ha="center") for i, v in enumerate([d05["ROC-AUC"], dopt.Recall, dopt.Precision])]
ax[1].axhline(0.5, color="k", ls="--", lw=0.8); ax[1].set_ylim(0, 1); ax[1].set_title("Failed-inspection tree on the 2025 test year")
plt.tight_layout(); plt.savefig(IMG / "finding_10.png", dpi=110); plt.close()
imp = pd.read_csv(R / "decision_tree_importance.csv").head(4)
finding(10, "Violation counts and failures are only weakly predictable from what is known before the visit",
        "Can the number of violations be predicted and can a failed inspection be classified in advance?", "Methods: multiple linear regression for ViolationCount (notebook 07) and a pruned DecisionTreeClassifier for FailedInspection (notebook 09); both trained on 2022-2024 and tested on 2025; predictors known before the visit only; prior-history features from strictly earlier inspections.",
        md_table(pd.DataFrame({"Model": ["Baseline (training mean)", "Multiple linear regression", "Decision tree, threshold 0.5", "Decision tree, threshold 0.217"], "Result on 2025": [f"MAE {bm.MAE:.2f}, RMSE {bm.RMSE:.2f}", f"MAE {mm_.MAE:.2f}, RMSE {mm_.RMSE:.2f}, R2 {mm_.R2:.3f}",
              f"AUC {d05['ROC-AUC']:.3f}, recall {d05.Recall:.2f}, precision {d05.Precision:.2f}", f"recall {dopt.Recall:.2f}, precision {dopt.Precision:.2f}, accuracy {dopt.Accuracy:.2f}"]})) +
        f"\n\nMost important tree features: " + ", ".join(f"{r.iloc[0].replace('_', ' ')} ({100 * r.importance:.0f}%)" for _, r in imp.iterrows()) + ".\n\n![Finding 10](images/finding_10.png)",
        f"The regression lowers the error only from {bm.MAE:.2f} to {mm_.MAE:.2f} violations (R2 {mm_.R2:.2f}). The tree has an AUC of {d05['ROC-AUC']:.2f}: with the threshold tuned on the validation year it finds {100 * dopt.Recall:.0f}% of the failures but only {100 * dopt.Precision:.0f}% of its alarms are real failures. What decides an inspection is mostly what the inspector finds on the day, which is not in the data.",
        "Use the models only to rank inspections for attention (previous fail, complaint inspections after a long gap, location), together with inspector judgement, and add richer data (staff training, equipment, complaint details) before relying on a prediction.")
(ROOT / "docs" / "ten_findings.md").write_text("\n".join(out))
print("written docs/ten_findings.md and 10 charts")
