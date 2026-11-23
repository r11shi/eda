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
S.append(f'''<section class="slide title"><div class="tband"><div class="kicker">Exploratory Data Analytics (PEC) · Department of Computer Engineering · 2026-27</div>
<h1>Food Safety &amp; Restaurant<br>Inspection Analytics</h1><p class="sub">What four years of Chicago food inspections tell us</p></div>
<div class="team"><div><b>Aryan Tandale</b><span>202502040013</span></div><div><b>Omkar Patil</b><span>202502040010</span></div>
<div><b>Vishwaraj Savairam</b><span>202502040035</span></div><div><b>Rushikesh Maddewad</b><span>202502040037</span></div></div>
<p class="guide">Guide: <b>Mrs. Shubhangi Kale</b></p></section>''')

S.append(slide("The problem", "Which places fail food inspections, and can we predict it?",
    two(ul("Chicago checks every restaurant, shop and school that serves food",
           "Each check ends in <b>Pass</b>, <b>Pass with conditions</b> or <b>Fail</b>",
           "The city publishes every result. We used <b>2022 – 2025</b>",
           "Our job: clean the data, store it well, answer <b>10 questions</b>, and try to <b>predict</b> failures"),
        stats(("73,630", "records we started with"), ("61,737", "real inspections"), ("17,084", "places"), ("4 years", "2022 – 2025")), "1.2fr 1fr")))

tools = [("Programming", "Python, in Jupyter notebooks"), ("Working with data", "pandas"),
         ("Charts", "Matplotlib, Seaborn, Plotly"), ("Main database", "PostgreSQL (pgAdmin to view it)"),
         ("Prediction & patterns", "scikit-learn, mlxtend"), ("Database on 3 machines", "Citus"),
         ("Live data", "Kafka, Spark, ClickHouse"), ("Live dashboard", "Grafana"),
         ("Business dashboard", "a web page (HTML)"), ("Computer setup", "Windows + Ubuntu (WSL), GitHub")]
S.append(slide("What we used", "Tools",
    '<div class="tools">' + "".join(f'<div><b>{a}</b><span>{b}</span></div>' for a, b in tools) + "</div>"))

S.append(slide("Our approach", "The whole project in one picture",
    two(ul("<b>Clean</b> the data",
           "<b>Store</b> it in a database built for questions (a data warehouse)",
           "<b>Ask</b> the 10 questions and show the answers on a dashboard",
           "<b>Predict</b> with 3 simple models",
           "<b>Copy</b> the same data into 2 other kinds of storage and <b>compare</b>"),
        svg("pipeline"), "0.85fr 1.4fr")))

S.append(slide("Step 1 · Cleaning the data", "Find every problem, fix it, write it down",
    two(ul("Some rows were visits that <b>never happened</b> (shop closed, no entry): kept, but not counted",
           "<b>29</b> reports entered twice: removed",
           "<b>217</b> spellings of shop type → <b>7</b> groups",
           "Violations were one long sentence: we <b>counted</b> them",
           "Result: <b>73,630 rows → 61,737 real inspections</b>"),
        svg("cleaning_funnel") + png("nb_02_eda_3.png", 1300), "1fr 1.2fr")))

S.append(slide("Step 2 · The database design", "A star: one main table, five lookup tables",
    two(ul("<b>Main table:</b> one row per inspection, only numbers",
           "<b>Lookup tables:</b> when, which place, why, result, where",
           "Simple and fast to ask questions",
           "A second main table: one row per place per year"),
        svg("schema_er"), "0.7fr 1.6fr"), cls="er"))

S.append(slide("Step 3 · Loading the data", "Load it, then check nothing went wrong",
    two(ul("The clean file goes into a <b>waiting table</b> first",
           "One program moves it into the database",
           "First load: <b>2022 – Nov 2025</b> (60,608)",
           "Then only <b>December 2025</b> (1,129), no reload",
           "<b>5 checks</b> after each load: all OK"),
        svg("etl") + png("screens/psql_checks.png", 1300), "1fr 1.3fr")))

S.append(slide("Step 4 · Answering the questions", "What the data says",
    two(svg("olap"),
        stats(("23%", "of inspections fail"), ("25% → 21%", "failing less each year"), ("38%", "complaint checks fail most"),
              ("79%", "pass the next visit after a fail"), ("7 in 10", "inspections are restaurants"), ("13 days", "until the follow-up visit")), "1.1fr 1fr")))

S.append(slide("Step 4 · Dashboard", "All the answers on one page",
    f'<div class="fig wide">{png("screens/dashboard_overview.png", 1600)}</div>'))

S.append(slide("Step 5 · Prediction 1", "How many problems will an inspection find?",
    two(ul("Learn from <b>2022 – 2024</b>, test on <b>2025</b>",
           "Most useful clue: the place's <b>last inspection</b>",
           "Our guess is off by <b>2.45</b> problems on average",
           "A plain average guess is off by <b>2.71</b>",
           "Hard to predict: the real causes (cleanliness, staff) are not in the data"),
        svg("regression") + png("nb_07_regression_1.png", 1100), "1fr 1.2fr")))

S.append(slide("Step 5 · Patterns", "What usually happens together?",
    two(ul("We looked for things that often appear <b>together</b>",
           "<b>10 or more problems → Fail</b>, 69% of the time",
           "That is <b>3 times</b> more often than normal",
           "<b>Low-risk places</b> are mostly <b>grocery stores</b>"),
        svg("assoc_rule") + png("nb_08_association_mining_1.png", 1100), "1fr 1.2fr")))

S.append(slide("Step 5 · Prediction 2", "Will this inspection fail?",
    two(ul("A <b>decision tree</b>: a list of yes / no questions",
           "Strongest clue: <b>did the last inspection fail?</b>",
           "It catches <b>6 in 10</b> failing places",
           "Useful to decide <b>which places to inspect first</b>"),
        svg("decision_tree") + png("nb_09_decision_tree_3.png", 1100), "1fr 1.2fr")))

S.append(slide("Step 6 · Database on 3 machines", "Same data, split across computers",
    two(ul("One <b>main computer</b> takes the question",
           "Two <b>helper computers</b> each hold half of the data",
           "All 25 test questions gave the <b>same answers</b>",
           "Slower with small data, faster with big data"),
        svg("citus") + png("citus_vs_centralized.png", 1200), "1fr 1.2fr")))

S.append(slide("Step 7 · Live dashboard", "Inspections shown as they arrive",
    two(ul("We <b>replay</b> late 2025 as if it were happening now",
           "Each inspection is sent as a message",
           "It is checked, stored and shown in about <b>2 seconds</b>",
           "All <b>24</b> broken test messages were caught"),
        svg("streaming") + png("screens/grafana_realtime.png", 1300), "1fr 1.3fr")))

S.append(slide("Comparison", "Which way of storing data is best?",
    '<table><thead><tr><th></th><th>Normal database</th><th>On 3 machines</th><th>Live</th></tr></thead><tbody>'
    '<tr><td>Shows new data</td><td>after each load</td><td>after each load</td><td>in about 2 seconds</td></tr>'
    '<tr><td>Best for</td><td>history and reports</td><td>very large data</td><td>watching things live</td></tr>'
    '<tr><td>Effort</td><td>low</td><td>medium</td><td>high</td></tr></tbody></table>'
    '<p class="rec"><b>Our choice:</b> the normal database is enough for Chicago. Add the live one only if the city wants live monitoring.</p>'))

S.append(slide("Running the project", "Four buttons",
    ul("<b>Start_Project.cmd</b>: starts everything (keep the window open)",
       "<b>Project_Menu.cmd</b>: run or show one step at a time",
       "<b>Run_All_Parts.cmd</b>: runs every step in order",
       "<b>Replay_Stream.cmd</b>: starts the live dashboard demo")))

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
ul{margin:0;padding-left:24px;font-size:23px;line-height:1.45}li{margin:0 0 16px}li::marker{color:var(--acc)}
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
