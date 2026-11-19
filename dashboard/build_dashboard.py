"""Builds the batch food-safety dashboard (self-contained HTML, Plotly) directly from the PostgreSQL warehouse (schema dw).

Four sections as required by the project document: Executive, Facility and Risk, Geographic, Inspection and Violation.
Output: dashboard/food_safety_dashboard.html
"""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "etl"))
from config import connect
conn = connect()
def q(sql):
    cur = conn.cursor(); cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    for c in df.columns:                      # Decimal -> float, text stays text
        if c in ("zip", "license_number"):
            continue
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df
GREEN, ORANGE, RED, BLUE, GREY = "#2e8b57", "#f0a030", "#d64545", "#3b6fb6", "#8c96a3"
RES_COLORS = {"Pass": GREEN, "Conditional Pass": ORANGE, "Fail": RED}
BASE = dict(template="plotly_white", font=dict(family="Inter, Arial, sans-serif", size=12), margin=dict(l=50, r=20, t=50, b=45), height=380)

# ------------------------------------------------------------------ data
kpi = q("""SELECT count(*) inspections, sum(pass_count) passes, sum(conditional_pass_count) conditional, sum(fail_count) fails,
                  sum(violation_count) violations, sum(high_violation_flag) high_violation, count(*) FILTER (WHERE violation_count IS NULL) unknown_viol
             FROM dw.fact_inspection""").iloc[0]
yearly = q("""SELECT d.year, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY 1 ORDER BY 1""")
ftypes = q("""SELECT fa.facility_type, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
               GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
fgroups = q("""SELECT fa.facility_group, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1 ORDER BY 2 DESC""")
risk = q("""SELECT fa.risk_group, r.result_group, count(*) n FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key) GROUP BY 1, 2""")
bands = q("""SELECT CASE WHEN violation_count IS NULL THEN 'Unknown' WHEN violation_count = 0 THEN 'None (0)' WHEN violation_count <= 2 THEN 'Low (1-2)' WHEN violation_count <= 5 THEN 'Medium (3-5)'
                       WHEN violation_count <= 9 THEN 'High (6-9)' ELSE 'Very High (10+)' END AS band, count(*) n FROM dw.fact_inspection GROUP BY 1""")
repeat = q("""WITH seq AS (SELECT f.fail_count, row_number() OVER (PARTITION BY f.facility_key ORDER BY f.date_key, f.inspection_id) n
                FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) WHERE fa.facility_id_source = 'License')
             SELECT CASE WHEN n >= 4 THEN '4th or later' WHEN n = 3 THEN '3rd' WHEN n = 2 THEN '2nd' ELSE '1st' END AS inspection_number, count(*) inspections,
                    100.0*sum(fail_count)/count(*) fail_rate FROM seq GROUP BY 1 ORDER BY 1""")
area = q("""SELECT l.geographic_area_group area, count(*) inspections, sum(f.fail_count) fails, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) GROUP BY 1 ORDER BY 2 DESC""")
zips = q("""SELECT l.zip, count(*) inspections, sum(f.fail_count) fails, 100.0*sum(f.fail_count)/count(*) fail_rate, avg(f.violation_count) avg_violations
              FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) WHERE l.zip <> 'Unknown' GROUP BY 1""")
cells = q("""SELECT round(s.latitude / 0.01) * 0.01 AS lat, round(s.longitude / 0.01) * 0.01 AS lon, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate, avg(f.violation_count) avg_violations
               FROM dw.fact_inspection f JOIN staging.inspection_stg s ON s.inspection_id = f.inspection_id AND s.reject_reason IS NULL
              WHERE s.latitude IS NOT NULL GROUP BY 1, 2 HAVING count(*) >= 5""")
itype = q("""SELECT t.inspection_type_group grp, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate FROM dw.fact_inspection f JOIN dw.dim_inspection_type t USING (inspection_type_key) GROUP BY 1 ORDER BY 2 DESC""")
results = q("""SELECT r.result_group, count(*) n FROM dw.fact_inspection f JOIN dw.dim_result r USING (result_key) GROUP BY 1""")
monthly = q("""SELECT d.year, d.month, count(*) inspections, 100.0*sum(f.fail_count)/count(*) fail_rate, avg(f.violation_count) avg_viol FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY 1, 2 ORDER BY 1, 2""")
heat_fg = q("""SELECT fa.facility_group, d.quarter, d.year, 100.0*sum(f.fail_count)/count(*) fail_rate, count(*) n FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
                WHERE fa.facility_group IN ('Restaurant & Food Service','Retail Food & Grocery','Schools & Childcare') GROUP BY 1, 2, 3""")


def fig_html(fig, height=None):
    if height:
        fig.update_layout(height=height)
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True})


def bar(x, y, title, color=BLUE, orient="v", text=None, fmt=None):
    f = go.Figure(go.Bar(x=x if orient == "v" else y, y=y if orient == "v" else x, orientation=orient, marker_color=color, text=text, texttemplate=fmt, textposition="outside"))
    f.update_layout(title=title, **BASE)
    f.update_yaxes(type="category") if orient == "h" else f.update_xaxes(type="category")
    return f


sections = {}
# ---------------- executive
n = kpi["inspections"]
cards = [("Total inspections", f"{n:,.0f}", "completed inspections 2022-2025"), ("Pass rate", f"{100 * kpi.passes / n:.1f}%", f"{kpi.passes:,.0f} passes"),
         ("Fail rate", f"{100 * kpi.fails / n:.1f}%", f"{kpi.fails:,.0f} fails"), ("Conditional pass rate", f"{100 * kpi.conditional / n:.1f}%", f"{kpi.conditional:,.0f} conditional passes"),
         ("Total violations", f"{kpi.violations:,.0f}", f"{n - kpi.unknown_viol:,.0f} inspections with a known count"), ("High-violation inspections", f"{kpi.high_violation:,.0f}", f"6 or more violations ({100 * kpi.high_violation / n:.1f}%)")]
card_html = "".join(f'<div class="card"><div class="k">{a}</div><div class="v">{b}</div><div class="s">{c}</div></div>' for a, b, c in cards)
f1 = make_subplots(specs=[[{"secondary_y": True}]])
f1.add_bar(x=yearly["year"].astype(str), y=yearly["inspections"], name="Inspections", marker_color=BLUE, secondary_y=False)
f1.add_scatter(x=yearly["year"].astype(str), y=yearly["fail_rate"], name="Fail rate %", mode="lines+markers", line=dict(color=RED, width=3), secondary_y=True)
f1.update_layout(title="Inspections and fail rate by year", **BASE); f1.update_yaxes(title_text="Inspections", secondary_y=False); f1.update_yaxes(title_text="Fail rate %", range=[0, 30], dtick=5, showgrid=False, secondary_y=True)
f2 = go.Figure(go.Pie(labels=results["result_group"], values=results["n"], hole=0.55, marker_colors=[RES_COLORS[r] for r in results["result_group"]], sort=False))
f2.update_layout(title="Result mix (completed inspections)", **BASE)
sections["exec"] = f'<div class="cards">{card_html}</div><div class="row"><div class="col">{fig_html(f1)}</div><div class="col">{fig_html(f2)}</div></div>'

# ---------------- facility and risk
f3 = bar(ftypes["facility_type"][::-1], ftypes["inspections"][::-1], "Facility types: number of inspections (top 10)", BLUE, "h", ftypes["inspections"][::-1], "%{text:,}")
f3.update_layout(margin=dict(l=190, r=40, t=50, b=40)); f3.update_xaxes(range=[0, 50000])
f4 = go.Figure(go.Bar(x=fgroups["facility_group"], y=fgroups["fail_rate"], marker_color=[RED if v > 23.3 else GREY for v in fgroups["fail_rate"]], text=fgroups["fail_rate"].round(1), textposition="outside"))
f4.update_layout(title="Fail rate % by facility group (red = above the overall 23.1%)", **BASE); f4.update_xaxes(tickangle=-20); f4.update_layout(margin=dict(l=50, r=20, t=50, b=110))
rk = risk.pivot(index="risk_group", columns="result_group", values="n").fillna(0)
rk = rk.loc[[r for r in ["High", "Medium", "Low", "Unknown"] if r in rk.index]]
f5 = go.Figure([go.Bar(name=c, x=rk.index, y=100 * rk[c] / rk.sum(axis=1), marker_color=RES_COLORS[c], text=(100 * rk[c] / rk.sum(axis=1)).round(1), textposition="inside") for c in ["Pass", "Conditional Pass", "Fail"]])
f5.update_layout(barmode="stack", title="Result by risk category (%)", yaxis_title="% of inspections", **BASE)
order = ["None (0)", "Low (1-2)", "Medium (3-5)", "High (6-9)", "Very High (10+)", "Unknown"]
bands = bands.set_index("band").reindex(order).dropna().reset_index()
f6 = go.Figure(go.Bar(x=bands["band"], y=bands["n"], marker_color=[GREEN, "#8fbc8f", ORANGE, RED, "#8b1a1a", GREY][:len(bands)], text=bands["n"], texttemplate="%{text:,}", textposition="outside"))
f6.update_layout(title="Violation count: bands (Unknown = Fail / Conditional with no violation text)", **BASE)
f7 = make_subplots(specs=[[{"secondary_y": True}]])
f7.add_bar(x=repeat["inspection_number"], y=repeat["inspections"], name="Inspections", marker_color=BLUE, secondary_y=False)
f7.add_scatter(x=repeat["inspection_number"], y=repeat["fail_rate"], name="Fail rate %", mode="lines+markers", line=dict(color=RED, width=3), secondary_y=True)
f7.update_layout(title="Repeat inspections: position in the facility's history (licensed facilities)", **BASE); f7.update_yaxes(title_text="Fail rate %", range=[0, 35], dtick=5, showgrid=False, secondary_y=True)
sections["facility"] = (f'<div class="row"><div class="col">{fig_html(f3)}</div><div class="col">{fig_html(f4)}</div></div>'
                        f'<div class="row"><div class="col">{fig_html(f5)}</div><div class="col">{fig_html(f6)}</div></div><div class="row"><div class="col">{fig_html(f7)}</div></div>')

# ---------------- geographic
f8 = make_subplots(specs=[[{"secondary_y": True}]])
f8.add_bar(x=area["area"], y=area["inspections"], name="Inspections", marker_color=BLUE, secondary_y=False)
f8.add_scatter(x=area["area"], y=area["fail_rate"], name="Fail rate %", mode="lines+markers", line=dict(color=RED, width=3), secondary_y=True)
f8.update_layout(title="Inspections and fail rate by area group (street-grid quadrants)", **BASE); f8.update_yaxes(title_text="Fail rate %", range=[0, 35], dtick=5, showgrid=False, secondary_y=True)
big = zips[zips["inspections"] >= 200].sort_values("fail_rate", ascending=False).head(12)[::-1]
f9 = bar(big["zip"], big["fail_rate"], "ZIP codes with the highest fail rate (at least 200 inspections)", RED, "h", big["fail_rate"].round(1), "%{text}%"); f9.update_xaxes(title="Fail rate %")
sc = zips[zips["inspections"] >= 200]
f10 = go.Figure(go.Scatter(x=sc["inspections"], y=sc["fail_rate"], mode="markers+text", text=sc["zip"], textposition="top center", textfont=dict(size=8),
                           marker=dict(size=10, color=sc["fail_rate"], colorscale="YlOrRd", showscale=True, colorbar=dict(title="Fail %"))))
f10.update_layout(title="ZIP comparison: volume versus failure rate", xaxis_title="Inspections in the ZIP", yaxis_title="Fail rate %", **BASE)
f11 = go.Figure(go.Scatter(x=cells["lon"], y=cells["lat"], mode="markers", marker=dict(size=(cells["inspections"] ** 0.5).clip(upper=34) / 1.6 + 3, color=cells["fail_rate"], colorscale="YlOrRd", cmin=10, cmax=40, showscale=True,
                           colorbar=dict(title="Fail %"), line=dict(width=0.5, color="#555")), text=[f"{n:,} inspections, {r:.1f}% fail, {v:.1f} violations" for n, r, v in zip(cells.inspections, cells.fail_rate, cells.avg_violations)], hoverinfo="text"))
f11.update_layout(title="Map: 0.01-degree cells of validated coordinates (bubble = inspections, colour = fail rate)", xaxis_title="Longitude", yaxis_title="Latitude", **BASE, )
f11.update_yaxes(scaleanchor="x", scaleratio=1.35); f11.update_layout(height=640)
top_v = zips[zips["inspections"] >= 200].sort_values("avg_violations", ascending=False).head(10)[::-1]
f12 = bar(top_v["zip"], top_v["avg_violations"], "Violation concentration: average violations per inspection (top 10 ZIPs, 200+ inspections)", ORANGE, "h", top_v["avg_violations"].round(2), "%{text}")
sections["geo"] = (f'<div class="row"><div class="col">{fig_html(f8)}</div><div class="col">{fig_html(f9)}</div></div><div class="row"><div class="col">{fig_html(f10)}</div><div class="col">{fig_html(f12)}</div></div>'
                   f'<div class="row"><div class="col wide">{fig_html(f11)}</div></div>')

# ---------------- inspection and violation
f13 = go.Figure(go.Bar(x=itype["grp"], y=itype["fail_rate"], marker_color=[RED if v > 23.3 else GREY for v in itype["fail_rate"]], text=itype["fail_rate"].round(1), textposition="outside"))
f13.update_layout(title="Fail rate % by inspection type group", **BASE)
f14 = go.Figure(go.Bar(x=itype["grp"], y=itype["inspections"], marker_color=BLUE, text=itype["inspections"], texttemplate="%{text:,}", textposition="outside")); f14.update_layout(title="Inspections by inspection type group", **BASE)
monthly["period"] = pd.to_datetime(dict(year=monthly.year, month=monthly.month, day=1))
f15 = make_subplots(specs=[[{"secondary_y": True}]])
f15.add_bar(x=monthly["period"], y=monthly["inspections"], name="Inspections", marker_color=BLUE, secondary_y=False)
f15.add_scatter(x=monthly["period"], y=monthly["fail_rate"], name="Fail rate %", mode="lines+markers", line=dict(color=RED, width=2), secondary_y=True)
f15.update_layout(title="Monthly trend: inspections and fail rate", **BASE); f15.update_yaxes(title_text="Fail rate %", range=[0, 35], dtick=5, showgrid=False, secondary_y=True)
hm = monthly.pivot(index="year", columns="month", values="fail_rate")
f16 = go.Figure(go.Heatmap(z=hm.values, x=[pd.Timestamp(2000, m, 1).strftime("%b") for m in hm.columns], y=hm.index.astype(str), colorscale="YlOrRd", text=hm.round(1).values, texttemplate="%{text}", colorbar=dict(title="Fail %")))
f16.update_layout(title="Failure heat map: fail rate % by year and month", **BASE)
hf = heat_fg.assign(period=lambda d: d["year"].astype(str) + " Q" + d["quarter"].astype(str)).pivot(index="facility_group", columns="period", values="fail_rate")
f17 = go.Figure(go.Heatmap(z=hf.values, x=hf.columns, y=hf.index, colorscale="YlOrRd", text=hf.round(1).values, texttemplate="%{text}", colorbar=dict(title="Fail %")))
f17.update_layout(title="Failure heat map: fail rate % by facility group and quarter", **BASE); f17.update_layout(margin=dict(l=190, r=20, t=50, b=60))
sections["insp"] = (f'<div class="row"><div class="col">{fig_html(f14)}</div><div class="col">{fig_html(f13)}</div></div><div class="row"><div class="col wide">{fig_html(f15)}</div></div>'
                    f'<div class="row"><div class="col">{fig_html(f16)}</div><div class="col">{fig_html(f17)}</div></div>')

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Food Safety Dashboard</title><script>{get_plotlyjs()}</script>
<style>
:root {{ --bg:#f4f6f9; --card:#fff; --ink:#1f2933; --mute:#5f6b7a; --line:#dde3ea; --accent:#3b6fb6; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#10151b; --card:#1a222c; --ink:#e8edf2; --mute:#9aa7b5; --line:#2b3644; }} }}
* {{ box-sizing:border-box }} body {{ margin:0; font-family:Inter,Arial,sans-serif; background:var(--bg); color:var(--ink); }}
header {{ padding:18px 24px 8px; }} h1 {{ margin:0; font-size:22px; }} .sub {{ color:var(--mute); font-size:13px; margin-top:4px; }}
nav {{ display:flex; gap:8px; padding:8px 24px 0; flex-wrap:wrap; }} nav button {{ border:1px solid var(--line); background:var(--card); color:var(--ink); padding:9px 16px; border-radius:8px; font-size:14px; cursor:pointer; }}
nav button.on {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
section {{ display:none; padding:16px 24px 30px; }} section.on {{ display:block; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:14px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }} .card .k {{ color:var(--mute); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.card .v {{ font-size:28px; font-weight:700; margin:4px 0; }} .card .s {{ color:var(--mute); font-size:12px; }}
.row {{ display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; }} .col {{ flex:1 1 440px; min-width:0; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:6px; }} .col.wide {{ flex-basis:100%; }}
footer {{ padding:0 24px 24px; color:var(--mute); font-size:12px; }}
@media (max-width:640px) {{ header, nav, section, footer {{ padding-left:16px; padding-right:16px; }} }}
</style></head><body>
<header><h1>Food Safety and Restaurant Inspection Analytics</h1>
<div class="sub">City of Chicago food inspections, 1 Jan 2022 to 31 Dec 2025 &middot; {n:,.0f} completed inspections &middot; read from the PostgreSQL warehouse (fact constellation, schema dw)</div></header>
<nav id="tabs"><button data-t="exec" class="on">Executive</button><button data-t="facility">Facility and risk</button><button data-t="geo">Geographic</button><button data-t="insp">Inspection and violations</button></nav>
<section id="exec" class="on">{sections['exec']}</section><section id="facility">{sections['facility']}</section><section id="geo">{sections['geo']}</section><section id="insp">{sections['insp']}</section>
<footer>Fail rate = fails / completed inspections. High violation = 6 or more violations. Facility attributes are the latest known per facility (Type-1 dimension). Area groups are quadrants of the Chicago street grid, not official community areas.</footer>
<script>
function show(t){{document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id===t));document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
 setTimeout(()=>document.querySelectorAll('#'+t+' .js-plotly-plot').forEach(p=>Plotly.Plots.resize(p)),50);}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{{show(b.dataset.t);history.replaceState(null,'','#'+b.dataset.t);}});
if(location.hash){{const t=location.hash.slice(1); if(document.getElementById(t)) show(t);}}
</script></body></html>"""
out = ROOT / "dashboard" / "food_safety_dashboard.html"
out.write_text(page)
print("written", out, f"{out.stat().st_size / 1e6:.1f} MB")
