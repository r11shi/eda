"""Builds the presentation as one self-contained HTML slideshow (deliverables/Food_Safety_Slides.html) with our real diagrams and screenshots.

Arrow keys / space / click = next slide, F = full screen, Home/End = first/last. Open #5 to jump to slide 5.
Each slide can also be captured as an image (make_pptx step), which is how the PowerPoint copy is made.
    python build_docs/build_slides.py
"""
import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"


def svg(name):
    return (IMG / "diagrams" / f"{name}.svg").read_text(encoding="utf-8")


def png(rel, max_w=1600):
    im = Image.open(IMG / rel).convert("RGB"); im.thumbnail((max_w, 2000))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=85, optimize=True)
    return f'<img alt="" src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def stats(*items):
    return '<div class="stats">' + "".join(f'<div class="stat"><b>{a}</b><span>{b}</span></div>' for a, b in items) + "</div>"


def ul(*items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def slide(kicker, title, body="", cls=""):
    return f'<section class="slide {cls}"><div class="kicker">{kicker}</div><h2>{title}</h2><div class="body">{body}</div></section>'


def two(left, right, ratio="1fr 1.25fr"):
    return f'<div class="two" style="grid-template-columns:{ratio}"><div>{left}</div><div class="fig">{right}</div></div>'


S = []
S.append(f'''<section class="slide title"><div class="tband"><div class="kicker">Data Analytics (MDM) · Department of Computer Engineering · 2026-27</div>
<h1>Food Safety &amp; Restaurant<br>Inspection Analytics</h1><p class="sub">Data warehousing, OLAP and data mining on four years of Chicago food inspections</p></div>
<div class="team"><div><b>Aryan Tandale</b><span>202502040013</span></div><div><b>Omkar Patil</b><span>202502040010</span></div>
<div><b>Vishwaraj Savairam</b><span>202502040035</span></div><div><b>Rushikesh Maddewad</b><span>202502040037</span></div></div>
<p class="guide">Guide: <b>Mrs. Shubhangi Kale</b></p></section>''')

S.append(slide("The problem", "Which places fail inspections, where, when, and can we predict it?",
    two(ul("City of Chicago <b>Food Inspections</b> open data, January 2022 – December 2025",
           "Each record: place, facility type, risk, address, date, inspection type, <b>result</b>, violations text, coordinates",
           "The brief: clean the data, build a <b>data warehouse</b>, answer <b>10 business questions</b>, build <b>3 models</b>, and compare <b>batch, distributed and real-time</b> warehouses"),
        stats(("73,630", "raw records"), ("61,737", "completed inspections"), ("17,084", "places"), ("4 years", "2022 – 2025")), "1.2fr 1fr")))

tools = [("Language & notebooks", "Python 3 · Jupyter / JupyterLab"), ("Data handling", "pandas · NumPy"),
         ("Charts", "Matplotlib · Seaborn · Plotly"), ("Warehouse", "PostgreSQL 18 · SQL · PL/pgSQL · pgAdmin"),
         ("Data mining", "scikit-learn (regression, decision tree) · statsmodels · mlxtend (Apriori, FP-Growth)"),
         ("Distributed warehouse", "Citus 14.3 (PostgreSQL extension)"), ("Streaming", "Apache Kafka 3.9 · Apache Spark 4.0 Structured Streaming"),
         ("Real-time store & dashboard", "ClickHouse 26.3 · Grafana 11.3"), ("Business dashboard", "HTML page built with Plotly"),
         ("Platform", "Windows 11 + WSL 2 (Ubuntu) · Git & GitHub")]
S.append(slide("What we used", "Tools and technologies",
    '<div class="tools">' + "".join(f'<div><b>{a}</b><span>{b}</span></div>' for a, b in tools) + "</div>"))

S.append(slide("Our approach", "One pipeline, three warehouses",
    two(ul("<b>Clean</b> the raw file with written, logged rules (Python)",
           "<b>Load</b> it into a <b>star-schema warehouse</b> in PostgreSQL (ETL)",
           "<b>Ask</b> the 10 questions with SQL and OLAP; show them on a dashboard",
           "<b>Learn</b> from the warehouse: regression, association rules, decision tree",
           "<b>Copy</b> the same data into a <b>distributed</b> (Citus) and a <b>real-time</b> (Kafka → Spark → ClickHouse → Grafana) warehouse and <b>compare</b> by measurement"),
        svg("pipeline"), "1fr 1.35fr")))

S.append(slide("Part A · Data curation", "Profile first, then fix every problem with a logged rule",
    two(ul("<b>Profiled</b> every column: missing values, odd codes, duplicates, spellings",
           "<b>29</b> duplicate reports removed; risk <b>“All”</b> → Unknown",
           "<b>217</b> hand-typed facility types → <b>7</b> groups",
           "Violation count <b>extracted from the text</b>; a fail with no text → unknown, not 0",
           "<b>11,864</b> visits that never happened: kept, not counted",
           "New columns: season, area, violation band, result / risk / facility group"),
        svg("cleaning_funnel") + png("nb_02_eda_3.png", 1300), "1fr 1.2fr")))

S.append(slide("Part B · Dimensional model", "Star schema → fact constellation", cls="er", body=
    two(ul("<b>Grain:</b> one completed inspection of one place on one date",
           "<b>Fact table:</b> only keys and numbers (violations, fail / pass flags)",
           "<b>5 dimensions:</b> date, facility, inspection type, result, location",
           "<b>Surrogate keys</b> + an <b>Unknown row (0)</b> in every dimension",
           "Snowflake: <b>9 joins vs 3</b>, about <b>2× slower</b> → star chosen",
           "<b>2nd fact</b> (place × year): yearly questions <b>~7× faster</b>"),
        svg("schema_er"), "0.8fr 1.5fr")))

S.append(slide("Part C · ETL and validation", "Staging → one load procedure → five checks",
    two(ul("<b>Extract:</b> bulk COPY into a staging table, per batch",
           "<b>Transform + load:</b> one SQL procedure adds new places and inserts facts with looked-up keys, in one transaction",
           "<b>Initial load</b> Jan 2022 – Nov 2025: <b>60,608</b>",
           "<b>Incremental load</b> Dec 2025: <b>+1,129</b>, nothing rebuilt",
           "<b>5 checks</b> after each load: all <b>0</b>",
           "<b>Indexes:</b> a lookup 6.5 ms → 0.5 ms"),
        svg("etl") + png("screens/psql_checks.png", 1300), "1fr 1.3fr")))

S.append(slide("Part F · OLAP and findings", "The 10 business questions, answered with SQL on the star schema",
    two(svg("olap"),
        stats(("23.1%", "inspections that fail"), ("24.9% → 21.1%", "fail rate, 2022 → 2025"), ("37.6%", "complaint inspections fail (highest)"),
              ("79%", "next visit passes after a fail"), ("~70%", "of inspections are restaurants"), ("13 days", "average gap to the follow-up")), "1.15fr 1fr")))

S.append(slide("Part F · Dashboard", "One HTML page, six sections, read from the warehouse",
    f'<div class="fig wide">{png("screens/dashboard_overview.png", 1600)}</div>'))

S.append(slide("Part G · Regression", "Predict the number of violations from what is known before the visit",
    two(ul("Models read an <b>analytics table built from the warehouse</b>: each inspection carries the <b>previous</b> inspection of the same place",
           "<b>Time split:</b> train 2022 – 2024, test 2025",
           "Baseline vs simple vs <b>multiple linear regression</b>",
           "<b>MAE 2.45</b> vs 2.71 for guessing the average; <b>R² 0.12</b>",
           "Low R²: the real causes (cleanliness, staff) are not in the data"),
        svg("regression") + png("nb_07_regression_1.png", 1100), "1fr 1.2fr")))

S.append(slide("Part H · Association rules", "What happens together? Apriori and FP-Growth",
    two(ul("Each inspection = a basket of <b>7 items</b> (type, risk, inspection type, result, violation band, area, season)",
           "Min support 2%: both algorithms find the <b>same 1,198</b> frequent sets",
           "Rules: confidence ≥ 30%, lift ≥ 1.3, definitional rules removed → <b>14</b> kept",
           "<b>10+ violations ⇒ Fail</b>: 69%, lift 3.0",
           "<b>Low risk ⇒ Grocery store</b>: 62%, lift 6.5"),
        svg("assoc_rule") + png("nb_08_association_mining_1.png", 1100), "1fr 1.2fr")))

S.append(slide("Part I · Decision tree", "Will this inspection fail?",
    two(ul("Train 2022 – 23, <b>tune on 2024</b>, test once on 2025",
           "<b>420</b> setting combinations; deep trees <b>overfit</b> → depth 8, ≥ 200 per leaf",
           "<b>AUC 0.635</b> (0.5 = guessing)",
           "Cut-off 0.5 catches 4% of fails; <b>0.217 catches 61%</b>",
           "Strongest clue: <b>previous result = Fail</b>"),
        svg("decision_tree") + png("nb_09_decision_tree_3.png", 1100), "1fr 1.2fr")))

S.append(slide("Part D · Distributed warehouse", "Citus: one coordinator, two workers, 32 shards",
    two(ul("Fact table <b>hash-distributed by facility</b> (17,084 values, no skew) into <b>32 shards</b>, 16 per worker",
           "Dimensions = <b>reference tables</b> copied to every node",
           "5 queries × 5 sizes (61,737 → 2,000,000 rows)",
           "<b>25 of 25</b> answers identical to the single server",
           "Slower on small data; mostly faster from ~500,000 rows"),
        svg("citus") + png("citus_vs_centralized.png", 1200), "1fr 1.2fr")))

S.append(slide("Part E · Real-time warehouse", "Replay simulation: Kafka → Spark → ClickHouse → Grafana",
    two(ul("Oct – Dec 2025 replayed in date order, labelled <b>REPLAY_SIMULATION</b>",
           "Spark checks every message every <b>2 s</b>; broken ones go to a dead-letter table",
           "<b>3,647</b> events stored; <b>24 of 24</b> broken test events caught",
           "About <b>1.8 s</b> from sending to Grafana"),
        svg("streaming") + png("screens/grafana_realtime.png", 1300), "1fr 1.3fr")))

S.append(slide("Part J · Comparison", "Three warehouses, measured on the same data",
    '<table><thead><tr><th></th><th>Batch (PostgreSQL)</th><th>Distributed (Citus)</th><th>Real-time</th></tr></thead><tbody>'
    '<tr><td>Data arrives</td><td>in batches</td><td>in batches</td><td>continuously</td></tr>'
    '<tr><td>Visible after</td><td>each load</td><td>each load</td><td>≈ 1.8 s</td></tr>'
    '<tr><td>History &amp; reports</td><td>best</td><td>same answers</td><td>recent only</td></tr>'
    '<tr><td>Live monitoring</td><td>no</td><td>no</td><td>yes</td></tr>'
    '<tr><td>Grows by</td><td>bigger server</td><td>more servers</td><td>more servers</td></tr>'
    '<tr><td>Effort</td><td>low</td><td>medium</td><td>high (4 services)</td></tr></tbody></table>'
    '<p class="rec"><b>Recommendation:</b> batch warehouse as the main system; real-time only for live monitoring; Citus only when the data outgrows one server.</p>'))

S.append(slide("Running the project", "One click, or the commands behind it",
    '<div class="two" style="grid-template-columns:1fr 1fr"><div>'
    + ul("<b>Start_Project.cmd</b>: starts PostgreSQL, Citus, Kafka, Spark, ClickHouse, Grafana, JupyterLab",
         "<b>Project_Menu.cmd</b>: runs or shows one part at a time",
         "<b>Run_All_Parts.cmd</b>: runs every part in order in a terminal and saves each part's output",
         "<b>Replay_Stream.cmd</b>: live replay for Grafana",
         "<b>python run_all.py</b>: rebuilds Parts A – I from the raw file in about 10 minutes")
    + '</div><div><div class="code">wsl -d Ubuntu -u root\n'
    'cd /mnt/e/web/EDA/.claude/worktrees/\\\n   project-setup-warehouse-verify-e60cea\n\n'
    '# everything at once (what Start_Project.cmd does)\nbash scripts/run_everything_wsl.sh start\n\n'
    '# or piece by piece\nbash scripts/setup_postgres.sh        # warehouse\nbash scripts/setup_citus_cluster.sh   # Citus\n'
    'bash scripts/start_realtime_stack.sh  # Kafka, Spark, ClickHouse\nbash scripts/start_grafana.sh         # Grafana\n'
    'bash scripts/start_notebooks.sh       # JupyterLab\n\n# one part\nbash scripts/part.sh A      # or B C F G H I D E\n</div></div></div>'))

S.append('<section class="slide title end"><div class="tband"><div class="kicker">Food Safety &amp; Restaurant Inspection Analytics</div><h1>Thank you</h1>'
         '<p class="sub">Questions?</p></div></section>')

CSS = """
:root{--bg:#f4efe6;--card:#fffdf8;--ink:#1f2430;--mute:#5b6070;--line:#e2dbcd;--acc:#2747a8;--acc2:#1f8a5b;--warm:#c2542d;
 --d-ink:#1f2430;--d-mute:#5b6070;--d-box:#fffdf8;--d-line:#cfc6b4;--d-acc:#2747a8;--d-acc2:#1f8a5b;--d-warm:#c2542d;--d-tint:#e6ebf8;--d-tint2:#e3f1e9;--d-tint3:#f8e6de;
 --serif:Georgia,"Times New Roman",serif;--sans:"Segoe UI",Inter,system-ui,sans-serif;--mono:Consolas,"Cascadia Mono",monospace}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#2a2c31}
body{font-family:var(--sans);color:var(--ink)}
.deck{position:relative;width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
.slide{position:absolute;width:1280px;height:720px;background:var(--bg);padding:48px 64px 40px;display:none;flex-direction:column;transform-origin:center;box-shadow:0 10px 40px rgba(0,0,0,.35)}
.slide.on{display:flex}
.kicker{font:600 13px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--acc)}
h1,h2{font-family:var(--serif);font-weight:400;letter-spacing:-.01em;margin:12px 0 22px;text-wrap:balance}
h2{font-size:38px;line-height:1.12}
h1{font-size:62px;line-height:1.05}
.body{flex:1;min-height:0}
.two{display:grid;gap:36px;height:100%}
.two>div{min-width:0}
ul{margin:0;padding-left:22px;font-size:19px;line-height:1.5}li{margin:0 0 10px}li::marker{color:var(--acc)}
b{font-weight:600}
.fig{display:flex;flex-direction:column;gap:14px;align-items:stretch;justify-content:flex-start;min-height:0}
.fig svg{width:100%;height:auto;max-height:300px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}
.fig img{width:100%;height:auto;max-height:280px;object-fit:contain;background:#fff;border:1px solid var(--line);border-radius:10px}
.fig.wide img{max-height:540px}
.er .fig svg{max-height:560px}.er ul{font-size:17px}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.stat b{display:block;font:400 34px/1.1 var(--serif);color:var(--acc)}.stat span{color:var(--mute);font-size:14px}
.tools{display:grid;grid-template-columns:1fr 1fr;gap:12px 28px}
.tools div{border-left:3px solid var(--acc);padding:6px 0 6px 14px;background:var(--card);border-radius:0 8px 8px 0}
.tools b{display:block;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}.tools span{font-size:18px}
table{border-collapse:collapse;width:100%;font-size:18px;background:var(--card);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:12px 16px;border-bottom:1px solid var(--line)}th{background:var(--acc);color:#fff;font-weight:600}
td:first-child{font-weight:600;color:var(--mute)}
.rec{font-size:19px;margin-top:22px;padding:14px 18px;background:#e6ebf8;border-radius:10px}
.code{font:14.5px/1.55 var(--mono);background:#1f2430;color:#e8e6df;border-radius:12px;padding:18px 20px;white-space:pre}
.title{justify-content:space-between;background:var(--acc);color:#fff}
.title .kicker{color:#c9d5ff}.title h1{color:#fff;margin-top:22px}.title .sub{font-size:22px;color:#dfe6ff;margin:0}
.team{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.team div{background:rgba(255,255,255,.1);border-radius:10px;padding:14px 16px}.team b{display:block;font-size:18px}.team span{color:#c9d5ff;font-size:14px}
.guide{margin:0;font-size:17px;color:#dfe6ff}
.end{justify-content:center}
.nav{position:fixed;bottom:14px;right:18px;color:#bbb;font:13px var(--sans)}
@media print{html,body{background:none}.deck{display:block;width:auto;height:auto}.slide{display:flex!important;position:relative;transform:none!important;box-shadow:none;page-break-after:always}.nav{display:none}@page{size:1280px 720px;margin:0}}
"""
JS = """
const slides=[...document.querySelectorAll('.slide')];let i=0;
const cap=location.search.includes('capture');if(cap)document.querySelector('.nav').style.display='none';
function fit(){const s=cap?1:Math.min(innerWidth/1280,innerHeight/720)*0.96;slides.forEach(x=>x.style.transform=`scale(${s})`)}
function show(n){i=Math.max(0,Math.min(slides.length-1,n));slides.forEach((x,k)=>x.classList.toggle('on',k===i));document.querySelector('.nav').textContent=`${i+1} / ${slides.length}   ←  →   F = full screen`;history.replaceState(null,'','#'+(i+1))}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))show(i+1);else if(['ArrowLeft','PageUp'].includes(e.key))show(i-1);else if(e.key==='Home')show(0);else if(e.key==='End')show(slides.length-1);else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen().catch(()=>{})}});
document.querySelector('.deck').addEventListener('click',e=>show(e.clientX<innerWidth/3?i-1:i+1));
addEventListener('resize',fit);fit();show((parseInt(location.hash.slice(1))||1)-1);
"""
html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Food Safety Analytics - Slides</title><style>{CSS}</style></head><body><div class="deck">{"".join(S)}</div><div class="nav"></div>'
        f'<script>{JS}</script></body></html>')
out = ROOT / "deliverables" / "Food_Safety_Slides.html"
out.write_text(html, encoding="utf-8")
print("written", out.relative_to(ROOT), len(S), "slides", f"{len(html) / 1e6:.1f} MB")
