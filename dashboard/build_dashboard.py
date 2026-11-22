"""Part F - the project dashboard: one self-contained HTML page (open it by double-clicking, no server needed).

The charts read the PostgreSQL warehouse (schema dw). Pages: Overview, Facilities and risk, Locations, Inspections and violations
(the four sections the brief asks for), Data mining (regression, association rules, decision tree) and The three warehouses.

    python dashboard/build_dashboard.py       ->  dashboard/food_safety_dashboard.html
"""
import base64
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
IMG, RES = ROOT / "docs" / "images", ROOT / "results"
sys.path.insert(0, str(ROOT / "etl"))
from config import connect  # noqa: E402

conn = connect()


def q(sql):
    """Run a query on the warehouse and return a DataFrame (numbers as numbers)."""
    cur = conn.cursor(); cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    for c in df.columns:
        if c not in ("zip", "license_number"):
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass
    return df


GREEN, ORANGE, RED, BLUE, GREY = "#2f9e6b", "#e8a23a", "#d9534f", "#4a6cf7", "#a3acb9"
RES_COLORS = {"Pass": GREEN, "Conditional Pass": ORANGE, "Fail": RED}
BASE = dict(template="plotly_white", font=dict(family="Inter, system-ui, sans-serif", size=12, color="#3f4752"), margin=dict(l=50, r=20, t=16, b=45),
            height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.18))

# ------------------------------------------------------------------ data (SQL on the star schema)
kpi = q("""SELECT count(*) inspections, sum(pass_count) passes, sum(conditional_pass_count) conditional, sum(fail_count) fails,
                  sum(violation_count) violations, sum(high_violation_flag) high_violation FROM dw.fact_inspection""").iloc[0]
yearly = q("""SELECT d.year, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY 1 ORDER BY 1""")
ftypes = q("""SELECT fa.facility_type, count(*) inspections FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
fgroups = q("""SELECT fa.facility_group, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1 ORDER BY 2 DESC""")
risk = q("""SELECT fa.risk_group, r.result_group, count(*) n FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key) GROUP BY 1, 2""")
bands = q("""SELECT CASE WHEN violation_count IS NULL THEN 'Unknown' WHEN violation_count = 0 THEN 'None (0)' WHEN violation_count <= 2 THEN 'Low (1-2)' WHEN violation_count <= 5 THEN 'Medium (3-5)'
                       WHEN violation_count <= 9 THEN 'High (6-9)' ELSE 'Very High (10+)' END AS band, count(*) n FROM dw.fact_inspection GROUP BY 1""")
repeat = q("""WITH seq AS (SELECT f.fail_count, row_number() OVER (PARTITION BY f.facility_key ORDER BY f.date_key, f.inspection_id) n
                FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) WHERE fa.facility_id_source = 'License')
             SELECT CASE WHEN n >= 4 THEN '4th or later' WHEN n = 3 THEN '3rd' WHEN n = 2 THEN '2nd' ELSE '1st' END AS inspection_number, count(*) inspections,
                    100.0*sum(fail_count)/count(*) fail_rate FROM seq GROUP BY 1 ORDER BY 1""")
area = q("""SELECT l.geographic_area_group area, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) GROUP BY 1 ORDER BY 2 DESC""")
zips = q("""SELECT l.zip, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate, avg(f.violation_count) avg_violations
              FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) WHERE l.zip <> 'Unknown' GROUP BY 1""")
cells = q("""SELECT round(s.latitude / 0.01) * 0.01 AS lat, round(s.longitude / 0.01) * 0.01 AS lon, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate, avg(f.violation_count) avg_violations
               FROM dw.fact_inspection f JOIN staging.inspection_stg s ON s.inspection_id = f.inspection_id AND s.reject_reason IS NULL
              WHERE s.latitude IS NOT NULL GROUP BY 1, 2 HAVING count(*) >= 5""")
itype = q("""SELECT t.inspection_type_group grp, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_inspection_type t USING (inspection_type_key) GROUP BY 1 ORDER BY 2 DESC""")
results = q("""SELECT r.result_group, count(*) n FROM dw.fact_inspection f JOIN dw.dim_result r USING (result_key) GROUP BY 1""")
monthly = q("""SELECT d.year, d.month, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2 ORDER BY 1, 2""")
heat_fg = q("""SELECT fa.facility_group, d.quarter, d.year, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
                WHERE fa.facility_group IN ('Restaurant & Food Service','Retail Food & Grocery','Schools & Childcare') GROUP BY 1, 2, 3""")


# ------------------------------------------------------------------ small helpers for the page
def fig_html(fig, height=None):
    if height:
        fig.update_layout(height=height)
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True})


def bar(x, y, color=BLUE, orient="v", text=None, fmt=None):
    f = go.Figure(go.Bar(x=x if orient == "v" else y, y=y if orient == "v" else x, orientation=orient, marker_color=color, text=text, texttemplate=fmt, textposition="outside"))
    f.update_layout(**BASE)
    f.update_yaxes(type="category") if orient == "h" else f.update_xaxes(type="category")
    return f


def bars_and_rate(x, counts, rate, rate_max=35):
    """Bars = number of inspections (left axis), line = fail rate % (right axis)."""
    f = make_subplots(specs=[[{"secondary_y": True}]])
    f.add_bar(x=x, y=counts, name="Inspections", marker_color=BLUE, secondary_y=False)
    f.add_scatter(x=x, y=rate, name="Fail rate %", mode="lines+markers", line=dict(color=RED, width=3), secondary_y=True)
    f.update_layout(**BASE); f.update_yaxes(title_text="Fail rate %", range=[0, rate_max], dtick=5, showgrid=False, secondary_y=True)
    return f


def card(fig, title, note, wide=False, height=None):
    """One chart on a white card: a title, the chart, and one line saying what it shows."""
    return f'<figure class="card{" wide" if wide else ""}"><h3>{title}</h3>{fig_html(fig, height)}<figcaption>{note}</figcaption></figure>'


def img_card(name, title, note, wide=False):
    """A chart saved by a notebook (docs/images), embedded in the page."""
    path = IMG / name
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return (f'<figure class="card{" wide" if wide else ""}"><h3>{title}</h3><img alt="{title}" src="data:image/png;base64,{data}">'
            f'<figcaption>{note}</figcaption></figure>')


def kpis(items):
    return '<div class="kpis">' + "".join(f'<div class="kpi"><span>{a}</span><b>{b}</b><small>{c}</small></div>' for a, b, c in items) + "</div>"


def grid(*cards):
    return '<div class="grid">' + "".join(cards) + "</div>"


pages = []          # (id, menu label, heading, one-line intro, html)

# ------------------------------------------------------------------ 1. overview
n = kpi["inspections"]
f_year = bars_and_rate(yearly["year"].astype(str), yearly["inspections"], yearly["fail_rate"], 30)
f_mix = go.Figure(go.Pie(labels=results["result_group"], values=results["n"], hole=0.6, marker_colors=[RES_COLORS[r] for r in results["result_group"]], sort=False))
f_mix.update_layout(**BASE)
pages.append(("overview", "Overview", "Overview", f"{n:,.0f} completed food inspections in Chicago, January 2022 to December 2025.",
              kpis([("Inspections", f"{n:,.0f}", "completed, 2022-2025"), ("Pass rate", f"{100 * kpi.passes / n:.1f}%", f"{kpi.passes:,.0f} passes"),
                    ("Fail rate", f"{100 * kpi.fails / n:.1f}%", f"{kpi.fails:,.0f} fails"), ("Conditional pass", f"{100 * kpi.conditional / n:.1f}%", f"{kpi.conditional:,.0f} inspections"),
                    ("Violations", f"{kpi.violations:,.0f}", "cited in total"), ("High-violation", f"{kpi.high_violation:,.0f}", "inspections with 6+ violations")])
              + grid(card(f_year, "Inspections and fail rate by year", "Bars = number of inspections, line = share that failed."),
                     card(f_mix, "Result mix", "How the completed inspections ended."))))

# ------------------------------------------------------------------ 2. facilities and risk
f_types = bar(ftypes["facility_type"][::-1], ftypes["inspections"][::-1], BLUE, "h", ftypes["inspections"][::-1], "%{text:,}")
f_types.update_layout(margin=dict(l=190, r=40)); f_types.update_xaxes(range=[0, 50000])
f_groups = go.Figure(go.Bar(x=fgroups["facility_group"], y=fgroups["fail_rate"], marker_color=[RED if v > 23.3 else GREY for v in fgroups["fail_rate"]],
                            text=fgroups["fail_rate"].round(1), textposition="outside"))
f_groups.update_layout(**BASE); f_groups.update_xaxes(tickangle=-20); f_groups.update_layout(margin=dict(b=110))
rk = risk.pivot(index="risk_group", columns="result_group", values="n").fillna(0)
rk = rk.loc[[r for r in ["High", "Medium", "Low", "Unknown"] if r in rk.index]]
f_risk = go.Figure([go.Bar(name=c, x=rk.index, y=100 * rk[c] / rk.sum(axis=1), marker_color=RES_COLORS[c], text=(100 * rk[c] / rk.sum(axis=1)).round(1),
                           textposition="inside") for c in ["Pass", "Conditional Pass", "Fail"]])
f_risk.update_layout(barmode="stack", yaxis_title="% of inspections", **BASE)
order = ["None (0)", "Low (1-2)", "Medium (3-5)", "High (6-9)", "Very High (10+)", "Unknown"]
bands = bands.set_index("band").reindex(order).dropna().reset_index()
f_bands = go.Figure(go.Bar(x=bands["band"], y=bands["n"], marker_color=[GREEN, "#8fc9a8", ORANGE, RED, "#8b1a1a", GREY][:len(bands)], text=bands["n"],
                           texttemplate="%{text:,}", textposition="outside"))
f_bands.update_layout(**BASE)
f_repeat = bars_and_rate(repeat["inspection_number"], repeat["inspections"], repeat["fail_rate"])
pages.append(("facility", "Facilities & risk", "Facilities and risk", "Which kinds of places are inspected most, and which fail most.",
              grid(card(f_types, "Most inspected facility types", "Top 10 facility types by number of inspections."),
                   card(f_groups, "Fail rate by facility group", "Red bars fail more often than the overall average (about 23%)."),
                   card(f_risk, "Result by risk category", "Each bar adds up to 100% of that risk level's inspections."),
                   card(f_bands, "Violations per inspection", "Unknown = a fail or conditional pass with no violation text."),
                   card(f_repeat, "Repeat inspections", "1st, 2nd, 3rd ... inspection of the same licensed facility, and how often each fails.", wide=True))))

# ------------------------------------------------------------------ 3. locations
f_area = bars_and_rate(area["area"], area["inspections"], area["fail_rate"])
big = zips[zips["inspections"] >= 200].sort_values("fail_rate", ascending=False).head(12)[::-1]
f_zip = bar(big["zip"], big["fail_rate"], RED, "h", big["fail_rate"].round(1), "%{text}%"); f_zip.update_xaxes(title="Fail rate %")
sc = zips[zips["inspections"] >= 200]
f_scatter = go.Figure(go.Scatter(x=sc["inspections"], y=sc["fail_rate"], mode="markers+text", text=sc["zip"], textposition="top center", textfont=dict(size=8),
                                 marker=dict(size=10, color=sc["fail_rate"], colorscale="YlOrRd", showscale=True, colorbar=dict(title="Fail %"))))
f_scatter.update_layout(xaxis_title="Inspections in the ZIP", yaxis_title="Fail rate %", **BASE)
f_map = go.Figure(go.Scatter(x=cells["lon"], y=cells["lat"], mode="markers",
                             marker=dict(size=(cells["inspections"] ** 0.5).clip(upper=34) / 1.6 + 3, color=cells["fail_rate"], colorscale="YlOrRd", cmin=10, cmax=40,
                                         showscale=True, colorbar=dict(title="Fail %"), line=dict(width=0.5, color="#555")),
                             text=[f"{a:,} inspections, {r:.1f}% fail" for a, r in zip(cells.inspections, cells.fail_rate)], hoverinfo="text"))
f_map.update_layout(xaxis_title="Longitude", yaxis_title="Latitude", **BASE); f_map.update_yaxes(scaleanchor="x", scaleratio=1.35)
top_v = zips[zips["inspections"] >= 200].sort_values("avg_violations", ascending=False).head(10)[::-1]
f_viol = bar(top_v["zip"], top_v["avg_violations"], ORANGE, "h", top_v["avg_violations"].round(2), "%{text}")
pages.append(("geo", "Locations", "Locations", "Where inspections happen and where they fail most.",
              grid(card(f_area, "Inspections and fail rate by area", "Areas are quadrants of the Chicago street grid."),
                   card(f_zip, "ZIP codes with the highest fail rate", "Only ZIP codes with at least 200 inspections."),
                   card(f_scatter, "ZIP codes: volume vs fail rate", "Busy ZIP codes are not always the worst ones."),
                   card(f_viol, "Most violations per inspection", "Average violations per inspection, top 10 ZIP codes."),
                   card(f_map, "Map of fail rate", "Each bubble is a small grid cell: size = inspections, colour = fail rate.", wide=True, height=600))))

# ------------------------------------------------------------------ 4. inspections and violations
f_type_rate = go.Figure(go.Bar(x=itype["grp"], y=itype["fail_rate"], marker_color=[RED if v > 23.3 else GREY for v in itype["fail_rate"]],
                               text=itype["fail_rate"].round(1), textposition="outside"))
f_type_rate.update_layout(**BASE)
f_type_n = go.Figure(go.Bar(x=itype["grp"], y=itype["inspections"], marker_color=BLUE, text=itype["inspections"], texttemplate="%{text:,}", textposition="outside"))
f_type_n.update_layout(**BASE)
monthly["period"] = pd.to_datetime(dict(year=monthly.year, month=monthly.month, day=1))
f_month = bars_and_rate(monthly["period"], monthly["inspections"], monthly["fail_rate"])
hm = monthly.pivot(index="year", columns="month", values="fail_rate")
f_heat = go.Figure(go.Heatmap(z=hm.values, x=[pd.Timestamp(2000, m, 1).strftime("%b") for m in hm.columns], y=hm.index.astype(str), colorscale="YlOrRd",
                              text=hm.round(1).values, texttemplate="%{text}", colorbar=dict(title="Fail %")))
f_heat.update_layout(**BASE)
hf = heat_fg.assign(period=lambda d: d["year"].astype(str) + " Q" + d["quarter"].astype(str)).pivot(index="facility_group", columns="period", values="fail_rate")
f_heat2 = go.Figure(go.Heatmap(z=hf.values, x=hf.columns, y=hf.index, colorscale="YlOrRd", text=hf.round(1).values, texttemplate="%{text}", colorbar=dict(title="Fail %")))
f_heat2.update_layout(**BASE); f_heat2.update_layout(margin=dict(l=190, b=60))
pages.append(("insp", "Inspections", "Inspections and violations", "Why places are inspected, and how results change over time.",
              grid(card(f_type_n, "Inspections by type", "Canvass = routine visit, Complaint, License = new business, Re-inspection."),
                   card(f_type_rate, "Fail rate by inspection type", "Red bars fail more often than average."),
                   card(f_month, "Monthly trend", "Inspections per month (bars) and the fail rate (line).", wide=True),
                   card(f_heat, "Fail rate by year and month", "Darker = more fails."),
                   card(f_heat2, "Fail rate by facility group and quarter", "Darker = more fails."))))

# ------------------------------------------------------------------ 5. data mining (results and charts of notebooks 07, 08, 09)
reg = pd.read_csv(RES / "regression_metrics.csv").set_index("Model")
dt = pd.read_csv(RES / "decision_tree_metrics.csv").set_index("Model")
rules = pd.read_csv(RES / "association_rules_selected.csv")
mlr, base_ = reg.loc["Multiple LR: all test inspections"], reg.loc["Baseline: predict the training mean"]
tree = dt.loc["Decision tree, validation-optimal threshold"]
rule_rows = "".join(f"<tr><td>{r.Rule}</td><td>{r.confidence:.0%}</td><td>{r.lift:.1f}</td></tr>" for r in rules.head(8).itertuples())
pages.append(("mining", "Data mining", "Data mining", "Three models, trained on 2022-2024 and tested on 2025 (notebooks 07, 08 and 09).",
              "<h2>Regression: predict the number of violations</h2>"
              + kpis([("Model error (MAE)", f"{mlr.MAE:.2f}", "violations, on 2025 data"), ("Simple guess error", f"{base_.MAE:.2f}", "always predict the average"),
                      ("R²", f"{mlr.R2:.2f}", "share of the variation explained")])
              + grid(img_card("nb_07_regression_1.png", "Regression charts (1)", "From notebook 07."), img_card("nb_07_regression_2.png", "Regression charts (2)", "From notebook 07."))
              + "<h2>Association rules: what goes together</h2>"
              + '<figure class="card wide"><h3>Strongest rules</h3><div class="tw"><table><thead><tr><th>Rule (if &rArr; then)</th><th>Confidence</th><th>Lift</th></tr></thead>'
              + f"<tbody>{rule_rows}</tbody></table></div><figcaption>Confidence = how often the 'then' part is true when the 'if' part is. "
                "Lift above 1 = together more often than by chance.</figcaption></figure>"
              + grid(img_card("nb_08_association_mining_1.png", "Association charts (1)", "From notebook 08."), img_card("nb_08_association_mining_2.png", "Association charts (2)", "From notebook 08."))
              + "<h2>Decision tree: will this inspection fail?</h2>"
              + kpis([("AUC", f"{tree['ROC-AUC']:.3f}", "0.5 = guessing, 1 = perfect"), ("Failures caught", f"{tree.Recall:.0%}", f"recall at cut-off {tree.threshold}"),
                      ("Precision", f"{tree.Precision:.0%}", "of the flagged inspections really fail")])
              + grid(img_card("nb_09_decision_tree_2.png", "Decision tree charts (1)", "From notebook 09."), img_card("nb_09_decision_tree_3.png", "Decision tree charts (2)", "From notebook 09."),
                     img_card("nb_09_decision_tree_4.png", "Decision tree charts (3)", "From notebook 09.", wide=True))))

# ------------------------------------------------------------------ 6. the three warehouses
scal = pd.read_csv(RES / "distributed_scaling.csv")
stream = pd.read_csv(RES / "streaming_metrics.csv").set_index("metric")["value"]
same = int(scal["results_identical"].sum())
pages.append(("dw", "Warehouses", "The three warehouses", "The same data stored three ways, as the brief asks.",
              '<div class="grid three">'
              '<div class="card"><h3>1 · Batch warehouse</h3><p>PostgreSQL. A star schema (fact table in the middle, dimension tables around it), filled by the ETL: '
              'January 2022 to November 2025 first, then December 2025 as an incremental load.</p><p class="mono">pgAdmin · localhost:5432 · schema dw</p></div>'
              f'<div class="card"><h3>2 · Distributed warehouse</h3><p>Citus spreads PostgreSQL over 1 coordinator and 2 workers. The fact table is cut into 32 pieces (shards) '
              f'by facility. {same} of {len(scal)} test queries gave the same answer as the single server.</p><p class="mono">pgAdmin · localhost:5440</p></div>'
              f'<div class="card"><h3>3 · Real-time warehouse</h3><p>Past inspections are replayed as live events: Python &rarr; Kafka &rarr; Spark &rarr; ClickHouse &rarr; Grafana. '
              f'{stream.iloc[0]:,.0f} events stored, {stream.iloc[1]:.0f} bad test events rejected.</p><p class="mono"><a href="http://localhost:3000/d/food-safety-rt">Grafana · localhost:3000</a></p></div></div>'
              + grid(img_card("citus_vs_centralized.png", "Single server vs Citus: query time", "On small data one server is faster; Citus pays off as the data grows."),
                     img_card("grafana_realtime_dashboard.png", "Real-time dashboard (Grafana)", "Replay simulation of past inspections, not live data."))))

# ------------------------------------------------------------------ the page
nav = "".join(f'<a href="#{pid}" data-p="{pid}">{label}</a>' for pid, label, *_ in pages)
secs = "".join(f'<section id="{pid}"><header><h1>{title}</h1><p>{intro}</p></header>{html}</section>' for pid, _, title, intro, html in pages)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Food Safety Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script>{get_plotlyjs()}</script>
<style>
:root{{--bg:#fafafa;--card:#fff;--ink:#111;--mute:#6b7280;--line:#ececec;--accent:#4a6cf7;--soft:#f3f4f6}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}}
aside{{position:fixed;inset:0 auto 0 0;width:220px;padding:28px 16px;border-right:1px solid var(--line);background:var(--card)}}
.brand{{font-weight:600;font-size:15px;margin:0 10px 2px}} .meta{{color:var(--mute);font-size:12px;margin:0 10px 24px}}
aside a{{display:block;padding:8px 10px;margin:2px 0;border-radius:8px;color:var(--mute);text-decoration:none;font-size:14px;font-weight:500}}
aside a:hover,aside a.on{{background:var(--soft);color:var(--ink)}}
main{{margin-left:220px;padding:36px 40px 60px;max-width:1260px}}
section{{display:none}} section.on{{display:block}}
section header h1{{font-size:24px;font-weight:600;letter-spacing:-.02em;margin:0}} section header p{{color:var(--mute);margin:6px 0 24px;font-size:14px}}
h2{{font-size:16px;font-weight:600;margin:36px 0 12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}
.kpi span,.kpi small{{display:block;color:var(--mute);font-size:12px}} .kpi b{{display:block;font-size:26px;font-weight:600;letter-spacing:-.02em;margin:6px 0 2px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}} .grid.three{{grid-template-columns:repeat(3,minmax(0,1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 12px;margin:0;min-width:0}} .card.wide{{grid-column:1/-1}}
.card h3{{font-size:14px;font-weight:600;margin:0 0 8px}} .card p{{font-size:13px;color:#374151;line-height:1.6;margin:0 0 8px}}
.card img{{display:block;width:100%;height:auto;border-radius:6px}} figcaption{{color:var(--mute);font-size:12px;margin-top:6px}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px!important;color:var(--mute)!important}} a{{color:var(--accent)}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}} th{{color:var(--mute);font-weight:500}}
@media (max-width:900px){{aside{{position:static;width:auto;border-right:0;border-bottom:1px solid var(--line);padding:16px}} aside nav{{display:flex;flex-wrap:wrap;gap:4px}}
 main{{margin-left:0;padding:20px 16px 40px}} .grid,.grid.three{{grid-template-columns:1fr}}}}
</style></head><body>
<aside><div class="brand">Food Safety Analytics</div><div class="meta">Chicago inspections &middot; 2022&ndash;2025</div><nav>{nav}</nav></aside>
<main>{secs}</main>
<script>
function show(p){{if(!document.getElementById(p))p='overview';document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id===p));
 document.querySelectorAll('aside a').forEach(a=>a.classList.toggle('on',a.dataset.p===p));
 setTimeout(()=>document.querySelectorAll('#'+p+' .js-plotly-plot').forEach(x=>Plotly.Plots.resize(x)),30);window.scrollTo(0,0);}}
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));show(location.hash.slice(1));
</script></body></html>"""
out = ROOT / "dashboard" / "food_safety_dashboard.html"
out.write_text(page, encoding="utf-8")
print("written", out.relative_to(ROOT), f"{out.stat().st_size / 1e6:.1f} MB")
