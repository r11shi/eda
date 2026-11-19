"""Builds docs/Presentation.pptx (12 slides, dark theme, native editable charts, speaker notes) from the project's results."""
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMG, R = ROOT / "docs" / "images", ROOT / "results"
rgb = lambda h: RGBColor.from_string(h)
BG, CARD, CARD2, EDGE = rgb("0B1B2B"), rgb("12304A"), rgb("0F2740"), rgb("1F4668")
WHITE, MUTE, TEAL, AMBER, CORAL, BLUE, GREEN = rgb("F4F8FB"), rgb("9FB3C8"), rgb("35D0BA"), rgb("FFB547"), rgb("FF6B6B"), rgb("5AA9FF"), rgb("4CD08B")
INK = rgb("0B1B2B")
FONT = "Calibri"
TOTAL = 12
prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
blank = prs.slide_layouts[6]
sm = pd.read_csv(R / "streaming_metrics.csv").set_index("metric")["value"]
reg = pd.read_csv(R / "regression_metrics.csv").set_index("Model"); dt = pd.read_csv(R / "decision_tree_metrics.csv").set_index("Model")
cs = pd.read_csv(R / "centralized_scaling.csv"); ds = pd.read_csv(R / "distributed_scaling.csv")
dk2 = pd.read_csv(R / "distribution_key_experiment.csv"); sk = dk2[dk2["query"] == "SHARD SKEW max/mean"].set_index("distribution_key")["distributed_ms"]
bq = pd.read_csv(R / "batch_query_timing.csv"); q3 = pd.read_csv(R / "analytical_query_results" / "Q3.csv"); q5 = pd.read_csv(R / "analytical_query_results" / "Q5.csv")
ar = pd.read_csv(R / "association_rules_selected.csv")
lat, p95 = sm["latency avg (ms), emit -> ClickHouse"], sm["latency p95 (ms)"]
state = {"n": 0}


def shape(s, kind, x, y, w, h, fill=None, line=None, lw=1.0, radius=None):
    sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None: sh.fill.background()
    else: sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None: sh.line.fill.background()
    else: sh.line.color.rgb = line; sh.line.width = Pt(lw)
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE: sh.adjustments[0] = radius
    sh.shadow.inherit = False
    return sh


def write(sh, lines, size=14, color=WHITE, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, margin=0.1, space=4):
    tf = sh.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin); tf.margin_top = tf.margin_bottom = Inches(0.04)
    for i, line in enumerate(lines if isinstance(lines, list) else [lines]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.alignment = align; p.space_after = Pt(space)
        r = p.add_run(); r.text = line; f = r.font; f.size = Pt(size); f.color.rgb = color; f.bold = bold; f.name = FONT
    return sh


def label(s, x, y, w, h, t, size=14, color=WHITE, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    return write(s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)), t, size, color, bold, align, anchor, margin=0.02)


def card(s, x, y, w, h, fill=CARD, line=EDGE, radius=0.06): return shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, line, 1.0, radius)


def bullets(s, x, y, w, h, items, size=14, color=WHITE, dot=TEAL, gap=7):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.03); tf.margin_top = Inches(0.02)
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(gap)
        d = p.add_run(); d.text = "●  "; d.font.size = Pt(size - 5); d.font.color.rgb = dot; d.font.name = FONT
        r = p.add_run(); r.text = it; r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = FONT
    return tb


def stat(s, x, y, w, h, big, small, accent=TEAL, bigsize=30):
    card(s, x, y, w, h); shape(s, MSO_SHAPE.RECTANGLE, x + 0.02, y + 0.15, 0.06, h - 0.3, accent)
    label(s, x + 0.22, y + 0.06, w - 0.3, h * 0.55, big, bigsize, accent, True, anchor=MSO_ANCHOR.MIDDLE)
    label(s, x + 0.22, y + h * 0.58, w - 0.3, h * 0.4, small, 12, MUTE)


def pill(s, x, y, w, h, t, fill=TEAL, color=INK, size=11):
    sh = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, None, radius=0.5); write(sh, t, size, color, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, margin=0.05); return sh


def pic(s, name, x, y, maxw, maxh, pad=0.07):
    w, h = Image.open(IMG / name).size; k = min(maxw / w, maxh / h); pw, ph = w * k, h * k
    px, py = x + (maxw - pw) / 2, y + (maxh - ph) / 2
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, px - pad, py - pad, pw + 2 * pad, ph + 2 * pad, WHITE, EDGE, 1.0, 0.02)
    s.shapes.add_picture(str(IMG / name), Inches(px), Inches(py), Inches(pw), Inches(ph))


def chart(s, kind, x, y, w, h, cats, series, colors=None, legend=False, labels=True, fmt="0.0", gap=60, point_colors=None, axis_max=None, vis_axis=False, size=11):
    cd = CategoryChartData(); cd.categories = cats
    for name, vals in series: cd.add_series(name, vals)
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd); ch = gf.chart
    ch.font.size = Pt(size); ch.font.color.rgb = MUTE; ch.font.name = FONT
    ch.has_legend = legend
    if legend: ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False; ch.legend.font.color.rgb = WHITE; ch.legend.font.size = Pt(size)
    ch.has_title = False
    plot = ch.plots[0]
    if kind not in (XL_CHART_TYPE.DOUGHNUT, XL_CHART_TYPE.LINE_MARKERS):
        plot.gap_width = gap
        ca, va = ch.category_axis, ch.value_axis
        ca.format.line.color.rgb = EDGE; ca.tick_labels.font.color.rgb = WHITE; ca.tick_labels.font.size = Pt(size)
        va.has_major_gridlines = vis_axis; va.visible = vis_axis
        if vis_axis: va.major_gridlines.format.line.color.rgb = EDGE; va.format.line.fill.background(); va.tick_labels.font.color.rgb = MUTE
        if axis_max: va.maximum_scale = axis_max
        va.minimum_scale = 0
    if kind == XL_CHART_TYPE.LINE_MARKERS:
        ca, va = ch.category_axis, ch.value_axis
        ca.format.line.color.rgb = EDGE; ca.tick_labels.font.color.rgb = WHITE
        va.major_gridlines.format.line.color.rgb = EDGE; va.format.line.fill.background(); va.tick_labels.font.color.rgb = MUTE
        if axis_max: va.maximum_scale = axis_max
    for i, ser in enumerate(plot.series):
        c = (colors or [TEAL, AMBER, BLUE, CORAL])[i % 4]
        if kind == XL_CHART_TYPE.LINE_MARKERS:
            ser.format.line.color.rgb = c; ser.format.line.width = Pt(3); ser.smooth = False
            ser.marker.format.fill.solid(); ser.marker.format.fill.fore_color.rgb = c; ser.marker.format.line.color.rgb = c; ser.marker.size = 9
        elif kind != XL_CHART_TYPE.DOUGHNUT:
            ser.format.fill.solid(); ser.format.fill.fore_color.rgb = c
    if point_colors:
        for j, c in enumerate(point_colors):
            pt = plot.series[0].points[j]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c
    if labels:
        plot.has_data_labels = True; dl = plot.data_labels; dl.font.size = Pt(size); dl.font.color.rgb = WHITE; dl.font.bold = True
        dl.number_format = fmt; dl.number_format_is_linked = False
        if kind in (XL_CHART_TYPE.COLUMN_CLUSTERED, XL_CHART_TYPE.BAR_CLUSTERED): dl.position = XL_LABEL_POSITION.OUTSIDE_END
        if kind == XL_CHART_TYPE.LINE_MARKERS: dl.position = XL_LABEL_POSITION.ABOVE
    return ch


def slide(tag, title, sub=None, notes=""):
    s = prs.slides.add_slide(blank); state["n"] += 1; n = state["n"] + 1
    s.background.fill.solid(); s.background.fill.fore_color.rgb = BG
    shape(s, MSO_SHAPE.OVAL, 11.4, -1.6, 3.6, 3.6, None, rgb("163450"), 2.0)
    label(s, 0.6, 0.3, 9, 0.3, tag.upper(), 12, TEAL, True)
    label(s, 0.6, 0.55, 12.1, 0.7, title, 29, WHITE, True)
    shape(s, MSO_SHAPE.RECTANGLE, 0.62, 1.22, 0.9, 0.05, AMBER)
    if sub: label(s, 0.6, 1.32, 12.1, 0.4, sub, 14, MUTE)
    shape(s, MSO_SHAPE.RECTANGLE, 0.6, 7.08, 12.13, 0.04, CARD2); shape(s, MSO_SHAPE.RECTANGLE, 0.6, 7.08, 12.13 * n / TOTAL, 0.04, TEAL)
    label(s, 0.6, 7.14, 10, 0.28, "Food Safety and Restaurant Inspection Analytics  |  Rushikesh Maddewad  |  PRN 202502040037  |  Roll 353", 10, MUTE)
    label(s, 11.2, 7.14, 1.53, 0.28, f"{n:02d} / {TOTAL}", 10, WHITE, True, PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def flow(s, x, y, w, labels, colors=None):
    n = len(labels); step = w / (n - 1) if n > 1 else w
    shape(s, MSO_SHAPE.RECTANGLE, x + 0.25, y + 0.24, w - 0.5, 0.04, EDGE)
    for i, t in enumerate(labels):
        cx = x + i * step; c = (colors or [TEAL])[i % len(colors or [TEAL])]
        o = shape(s, MSO_SHAPE.OVAL, cx - 0.26 + (0.26 if i == 0 else 0) - (0.26 if i == n - 1 else 0), y, 0.52, 0.52, c); write(o, str(i + 1), 14, INK, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, margin=0)
        lx = max(0.4, min(cx - 0.8, 13.333 - 1.6 - 0.4))
        label(s, lx, y + 0.6, 1.6, 0.6, t, 11.5, WHITE, True, PP_ALIGN.CENTER)


# ------------------------------------------------------------------ 1 title
s = prs.slides.add_slide(blank); s.background.fill.solid(); s.background.fill.fore_color.rgb = BG
for d, x, y, c in [(7.5, 8.4, -2.4, "163450"), (5.2, 10.6, 3.6, "163450"), (3.0, 7.3, 4.6, "1F4668")]: shape(s, MSO_SHAPE.OVAL, x, y, d, d, None, rgb(c), 2.0)
shape(s, MSO_SHAPE.RECTANGLE, 0.7, 1.15, 0.9, 0.07, AMBER)
label(s, 0.7, 0.7, 9, 0.35, "DATA WAREHOUSING, OLAP AND DATA MINING", 14, TEAL, True)
label(s, 0.7, 1.45, 7.4, 2.6, "Food Safety and Restaurant Inspection Analytics", 44, WHITE, True)
label(s, 0.7, 4.2, 7.0, 0.9, "One dataset, three ways to store it, ten findings and three prediction models.", 19, MUTE)
for i, (t, w) in enumerate([("Rushikesh Maddewad", 2.7), ("PRN 202502040037", 2.45), ("Roll No 353", 1.6)]): pill(s, 0.7 + sum([2.85, 2.6][:i]), 5.2, w, 0.44, t, CARD, WHITE, 13).line.color.rgb = EDGE
label(s, 0.7, 5.8, 7.5, 0.4, "City of Chicago Food Inspections (official Data Portal), 2022-2025", 13, MUTE)
for i, (b, t, c) in enumerate([("61,737", "completed inspections", TEAL), ("3", "ways to build the warehouse", AMBER), ("10", "findings", BLUE), ("3", "prediction models", CORAL)]):
    x, y = 8.55 + (i % 2) * 2.15, 1.55 + (i // 2) * 1.75; card(s, x, y, 2.0, 1.55); label(s, x + 0.18, y + 0.15, 1.7, 0.8, b, 34, c, True, anchor=MSO_ANCHOR.MIDDLE); label(s, x + 0.18, y + 0.95, 1.75, 0.5, t, 12, MUTE)
s.notes_slide.notes_text_frame.text = ("Introduce yourself. One-minute pitch: Chicago inspects restaurants and records pass or fail. I took four years of that public data (61,737 completed inspections), cleaned it, "
    "stored it in a data warehouse built three ways (batch, distributed, real-time), measured them on the same data, then answered ten business questions and trained three small mining models. Conclusion: a batch warehouse at the centre.")

# ------------------------------------------------------------------ 2 overview
s = slide("Overview", "One project, three ways to build it", "The same data goes through every part. Every number in this deck comes from code we ran",
          "Walk the numbered flow left to right. Then the three cards: batch is the core, distributed ran on one machine, real-time is a replay simulation. The mining models use a flat mart table generated from the warehouse, not the raw file.")
flow(s, 0.9, 1.95, 11.5, ["Raw data", "Clean it", "Staging (holding area)", "Warehouse", "Reports and dashboard", "One flat table", "Prediction models"], [TEAL, BLUE, TEAL, AMBER, BLUE, TEAL, CORAL])
for i, (h, c, items) in enumerate([("BATCH", TEAL, ["Cleaned with Python, stored in PostgreSQL", "Fact and dimension tables", "Reports and an HTML dashboard", "The main, trusted copy"]),
                                   ("DISTRIBUTED", BLUE, ["Same data split over 3 servers (Citus)", "Split into 32 pieces by facility", "Same answers as one server", "All on one computer in our test"]),
                                   ("REAL-TIME", AMBER, ["Data flows through Kafka and Spark", "Shown live in ClickHouse and Grafana", "A replay of old data, not live", "About 1.5 seconds delay"])]):
    x = 0.6 + i * 4.1; card(s, x, 3.55, 3.95, 3.2); shape(s, MSO_SHAPE.RECTANGLE, x + 0.25, 3.55, 1.2, 0.07, c)
    label(s, x + 0.25, 3.8, 3.5, 0.4, h, 17, c, True); bullets(s, x + 0.25, 4.35, 3.5, 2.3, items, 15, gap=11, dot=c)

# ------------------------------------------------------------------ 3 curation
s = slide("Part A", "Cleaning the data: every decision is counted", "Official Chicago data, 2022-2025. The code computed every count",
          "Say: I did not delete rows silently; every treatment has a count and a reason. 11,864 rows are not inspections at all (Out of Business, No Entry), so they stay in staging and out of the fact table. 552 failed inspections without violation text get NULL not 0 because a fail must cite at least one violation. No time of day exists in the source, so no hourly analysis.")
card(s, 0.6, 1.9, 4.6, 4.9); label(s, 0.85, 2.0, 4.1, 0.4, "Where the records go", 14, WHITE, True)
ch = chart(s, XL_CHART_TYPE.DOUGHNUT, 0.7, 2.4, 4.4, 3.4, ["Completed inspections", "Not completed"], [("Rows", [61737, 11864])], legend=True, labels=True, fmt="#,##0", size=11)
for j, c in enumerate([TEAL, AMBER]): pt = ch.plots[0].series[0].points[j]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c; pt.format.line.color.rgb = CARD
label(s, 0.85, 5.9, 4.1, 0.8, "61,737 are real inspections and become facts. 29 repeated reports were removed first (73,630 records at the start).", 12, MUTE)
for i, (h, t, c) in enumerate([("Duplicates", "29 repeated reports removed. 496 same-day pairs kept, because they may be separate visits", CORAL), ("Unknown, not zero", "552 failed inspections have no violation list. We mark them unknown, because a fail must have at least one violation", AMBER),
                               ("Invalid values", "Risk 'All' (38) and missing risk (17) become 'Unknown'", BLUE), ("Extreme cases kept", "2,686 inspections with very many violations. They are the worst places, so we keep them", TEAL)]):
    x, y = 5.5 + (i % 2) * 3.65, 1.9 + (i // 2) * 2.5; card(s, x, y, 3.5, 2.35); shape(s, MSO_SHAPE.RECTANGLE, x + 0.2, y, 0.9, 0.07, c)
    label(s, x + 0.2, y + 0.2, 3.1, 0.4, h, 16, c, True); label(s, x + 0.2, y + 0.7, 3.1, 1.5, t, 13.5, WHITE)
card(s, 5.5, 6.9 - 0.02, 7.15, 0.01, BG, BG)

# ------------------------------------------------------------------ 4 model
s = slide("Part B", "Designing the tables: fact constellation", "One row = one completed inspection. We built three designs and timed them",
          "Define grain first. Star = fewest joins. Snowflake = normalised dimensions, 16 tables, about twice as slow here. Constellation = star plus a second fact table at facility-by-year grain, answering yearly questions 8 times faster. That is why I chose it.")
pic(s, "fact_constellation.png", 0.6, 1.9, 6.9, 4.9)
card(s, 7.75, 1.9, 4.98, 4.9); label(s, 8.0, 2.0, 4.5, 0.4, "Query time in milliseconds (lower is better)", 14, WHITE, True)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 7.85, 2.4, 4.8, 3.3, ["Main question", "Facility x year"], [("Star", [37.3, 21.7]), ("Snowflake", [78.3, 21.7]), ("Constellation", [37.3, 2.7])], colors=[BLUE, CORAL, TEAL], legend=True, gap=70, size=11)
label(s, 8.0, 5.8, 4.5, 0.9, "Constellation is as fast as the star design and answers yearly questions in 2.7 ms. The snowflake needs 16 tables and 9 joins, and is 2x slower.", 12, MUTE)

# ------------------------------------------------------------------ 5 batch
s = slide("Part C", "Batch warehouse (PostgreSQL)", "One load routine is used for the first load and for later top-ups",
          "Explain the procedure: land the data in staging, apply quality rules, add new dimension members, load facts, build the annual fact, then 16 checks. Incremental: December 2025 was held back and loaded later; the first 60,608 rows were unchanged (MD5 checksum). Idempotent: re-loading December added 0 rows. Atomic: a deliberately failing load changed nothing.")
flow(s, 0.9, 1.9, 4.9, ["Staging", "Check rules", "Dimensions", "Facts", "16 checks"], [TEAL, BLUE, TEAL, BLUE, AMBER])
for i, (b, t, c) in enumerate([("60,608", "rows in the first load", TEAL), ("+1,129", "added later, in 0.5 seconds", BLUE), ("16 / 16", "quality checks passed", GREEN), ("0", "rows added when we re-ran it", AMBER)]):
    stat(s, 0.6 + (i % 2) * 2.9, 3.35 + (i // 2) * 1.55, 2.75, 1.4, b, t, c, 26)
card(s, 0.6, 6.45, 5.65, 0.4); label(s, 0.75, 6.47, 5.4, 0.36, "A load that failed halfway changed nothing (all or nothing).", 11.5, MUTE, anchor=MSO_ANCHOR.MIDDLE)
card(s, 6.55, 1.9, 6.18, 4.95); label(s, 6.8, 2.0, 5.7, 0.4, "Time for each business query (milliseconds)", 14, WHITE, True)
names = {"Q1a": "Q1 yearly volume", "Q1b": "Q1 monthly volume", "Q2": "Q2 facility types", "Q3": "Q3 results by year", "Q4": "Q4 by risk", "Q5": "Q5 inspection types", "Q6a": "Q6 violations", "Q6b": "Q6 top rules", "Q7a": "Q7 areas", "Q7b": "Q7 ZIP rate", "Q7c": "Q7 ZIP count", "Q8a": "Q8 history", "Q8b": "Q8 after a fail", "Q8c": "Q8 top facilities"}
sel = bq[bq["query"].isin(["Q1a", "Q2", "Q3", "Q4", "Q5", "Q6a", "Q7a", "Q8b"])]
chart(s, XL_CHART_TYPE.BAR_CLUSTERED, 6.65, 2.4, 6.0, 4.35, [names[q] for q in sel["query"]], [("ms", list(sel["median_ms"]))], colors=[TEAL], gap=45, fmt="0.0", size=11).category_axis.reverse_order = True

# ------------------------------------------------------------------ 6 real-time
s = slide("Part E", "Real-time warehouse (a replay)", "Old data is sent through the pipeline as if it were live",
          "Say clearly: this is a replay of historical data, because the official dataset is a historical file; every event carries source_mode = REPLAY_SIMULATION. The pipeline itself ran end to end. Spark applies 7 validation rules; bad events go to a dead-letter table. Average delay 1.5 seconds.")
flow(s, 0.9, 1.85, 11.5, ["Replay of old data", "Kafka (message queue)", "Spark (processing)", "ClickHouse (database)", "Grafana (live charts)"], [AMBER, TEAL, BLUE, TEAL, AMBER])
pic(s, "grafana_realtime_dashboard.png", 0.6, 3.15, 7.7, 3.75); pill(s, 6.0, 3.0, 2.4, 0.36, "REPLAY SIMULATION", AMBER, INK, 11)
for i, (b, t, c) in enumerate([(f"{lat / 1000:.1f} s", f"average delay (almost always under {p95 / 1000:.1f} s)", TEAL), ("3,647", "records, each stored once", BLUE), ("24 / 24", "bad records caught", GREEN), ("6-7 ms", "dashboard speed", AMBER)]):
    stat(s, 8.6 + (i % 2) * 2.1, 3.15 + (i // 2) * 1.5, 2.0, 1.4, b, t, c, 22)
label(s, 8.6, 6.2, 4.1, 0.7, "Uses about 2.5 GB of memory: a live system costs more to run.", 12, MUTE)

# ------------------------------------------------------------------ 7 OLAP
s = slide("Part F", "Reports and dashboard", "Different ways to slice the data, each written as SQL code",
          "Name the operations: roll-up, drill-down, slice, dice, pivot, CUBE and GROUPING SETS. Show the HTML dashboard in a browser if you can. Caveat to state calmly: Power BI Desktop is Windows-only, so I built an equivalent HTML dashboard plus a rebuild package; DAX is written but was not executed.")
pic(s, "dashboard_exec.png", 0.6, 1.9, 7.9, 4.9)
card(s, 8.8, 1.9, 3.93, 4.9); label(s, 9.05, 2.0, 3.5, 0.4, "Ways to slice the data", 14, WHITE, True)
for i, (t, c) in enumerate([("Roll-up", TEAL), ("Drill-down", BLUE), ("Slice", TEAL), ("Dice", BLUE), ("Pivot", TEAL), ("CUBE", BLUE)]): pill(s, 9.05 + (i % 2) * 1.75, 2.5 + (i // 2) * 0.52, 1.65, 0.4, t, c, INK, 12)
bullets(s, 9.05, 4.2, 3.5, 2.6, ["Roll-up: months to year. Drill-down: the reverse", "Slice, dice, pivot: filter and rotate the table", "4 dashboard pages: summary, facilities, areas, violations", "Power BI only runs on Windows, so we built an HTML dashboard"], 12.5, gap=7)

# ------------------------------------------------------------------ 8 findings
s = slide("Part F", "Ten findings", "What the data tells us",
          "Pick three to say aloud: the fail rate fell from 24.9% to 21.1%; complaint inspections fail most (37.6%); after a failed inspection the next visit passes 79% of the time, 13 days later. The ten findings are in the report.")
card(s, 0.6, 1.85, 6.0, 2.7); label(s, 0.8, 1.9, 5.6, 0.35, "Fail rate by year (%)", 13, WHITE, True)
chart(s, XL_CHART_TYPE.LINE_MARKERS, 0.7, 2.2, 5.8, 2.3, [str(y) for y in q3["year"]], [("Fail rate", list(q3["fail_rate"]))], colors=[AMBER], fmt="0.0", axis_max=30, size=11)
card(s, 6.75, 1.85, 5.98, 2.7); label(s, 6.95, 1.9, 5.6, 0.35, "Fail rate by type of inspection (%)", 13, WHITE, True)
top = q5[q5["inspections"] > 1000].sort_values("fail_rate", ascending=False)
pc = [AMBER if t == "Complaint" else (TEAL if "Re-Inspection" in t else BLUE) for t in top["inspection_type"]]
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 6.85, 2.2, 5.8, 2.3, [t.replace(" Re-Inspection", " re-insp.") for t in top["inspection_type"]], [("Fail rate", list(top["fail_rate"]))], gap=40, fmt="0.0", point_colors=pc, size=10)
F = ["Inspections grew 12% in 4 years, no clear busy season", "Fail rate fell from 24.9% to 21.1%", "Restaurants get 70% of inspections", "High-risk and low-risk places fail equally often", "Complaint visits fail most, re-checks least",
     "Common problems: dirty premises and cleanliness", "Worst-rate ZIPs differ from highest-count ZIPs", "After a fail, 79% pass the next visit", "10+ violations: 69% chance of failing", "Failures are only weakly predictable"]
for i, t in enumerate(F):
    x, y = 0.6 + (i % 5) * 2.45, 4.75 + (i // 5) * 1.05; card(s, x, y, 2.33, 0.95)
    o = shape(s, MSO_SHAPE.OVAL, x + 0.1, y + 0.1, 0.36, 0.36, TEAL if i % 2 == 0 else AMBER); write(o, str(i + 1), 11, INK, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, margin=0)
    label(s, x + 0.52, y + 0.05, 1.75, 0.85, t, 11, WHITE, anchor=MSO_ANCHOR.MIDDLE)

# ------------------------------------------------------------------ 9 Citus
fast, slow, tot = int((ds.distributed_over_centralized < 0.85).sum()), int((ds.distributed_over_centralized > 1.15).sum()), len(ds)
s = slide("Part D", "Citus: right answers, but not faster", "3 servers on one computer; data split into 32 pieces by facility",
          "Be upfront: results were identical to one node in all 25 tests, but Citus was clearly faster in only 4 and slower in 16. Reason: all nodes shared the same 4 CPU cores, so there was no extra hardware, only coordination overhead. Why FacilityKey: 17,083 distinct values and the most even shards. Volumes above 61,737 rows are a synthetic scale-up used only for timing.")
d2 = ds[ds["rows"] == 2000000]
card(s, 0.6, 1.9, 7.4, 4.1); label(s, 0.85, 2.0, 7, 0.4, "Time with 2,000,000 rows (ms): one server vs Citus", 14, WHITE, True)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.7, 2.4, 7.2, 3.55, ["Q1 facility type", "Q2 fail rate", "Q3 monthly", "Q4 violations", "Q5 facility x year"], [("One server", [round(v) for v in d2["centralized_ms"]]), ("Citus (2 workers)", [round(v) for v in d2["distributed_ms"]])], colors=[BLUE, AMBER], legend=True, gap=60, fmt="0", size=10)
for i, (b, t, c) in enumerate([(f"{tot} / {tot}", "answers matched one server", GREEN), (f"{fast} of {tot}", "tests where Citus was clearly faster", TEAL), (f"{slow} of {tot}", "tests where it was clearly slower", CORAL)]):
    stat(s, 8.3, 1.9 + i * 1.4, 4.43, 1.28, b, t, c, 26)
card(s, 0.6, 6.15, 12.13, 0.7, CARD2, EDGE); label(s, 0.85, 6.17, 11.7, 0.66, f"Why: the 3 servers shared one computer, so there was extra coordination work but no extra power. We split by facility because it gives the most even pieces (unevenness {sk['facility_key']:.2f}, against {sk['location_key']:.2f} for location).", 13, WHITE, anchor=MSO_ANCHOR.MIDDLE)

# ------------------------------------------------------------------ 10 mining
s = slide("Parts G, H, I", "Three prediction models", "Learned from the past, tested on 2025. Only facts known before the visit were used",
          "Regression: predict violation count, MAE 2.45 against 2.71 for the average, R-squared 0.12. Association rules: Apriori and FP-Growth give identical itemsets; best rule 10+ violations implies Fail, confidence 69%, lift 3.0 (explain support, confidence, lift). Decision tree: AUC 0.64; with the default threshold it predicts almost no fails, with a tuned threshold recall is 61%. Honest conclusion: weakly predictable.")
r2 = reg.loc["Multiple LR: all test inspections", "R2"]; mae = reg.loc["Multiple LR: all test inspections", "MAE"]; mae0 = reg.loc["Baseline: predict the training mean", "MAE"]; mae1 = reg.loc["Simple LR: PriorViolationCount", "MAE"]
auc = dt.loc["Decision tree, threshold 0.5", "ROC-AUC"]
d05, dtu = dt.loc["Decision tree, threshold 0.5"], dt.loc["Decision tree, validation-optimal threshold"]
toprules = ar.sort_values("lift", ascending=False).head(4)
cols = [("Regression: a number", f"R² {r2:.2f}", "how many violations?", TEAL), ("Association rules: patterns", "lift 3.0", "10+ violations => fail (69%)", AMBER), ("Decision tree: yes or no", f"AUC {auc:.2f}", "will it fail?", BLUE)]
for i, (h, big, sub, c) in enumerate(cols):
    x = 0.6 + i * 4.1; card(s, x, 1.9, 3.95, 4.95); shape(s, MSO_SHAPE.RECTANGLE, x + 0.25, 1.9, 1.2, 0.07, c)
    label(s, x + 0.25, 2.1, 3.5, 0.35, h, 16, WHITE, True); label(s, x + 0.25, 2.45, 3.5, 0.75, big, 34, c, True); label(s, x + 0.25, 3.2, 3.5, 0.3, sub, 12, MUTE)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.7, 3.5, 3.75, 2.2, ["Guess average", "1 input", "All inputs"], [("MAE", [round(mae0, 2), round(mae1, 2), round(mae, 2)])], gap=50, fmt="0.00", point_colors=[MUTE, BLUE, TEAL], size=10)
label(s, 0.85, 5.75, 3.4, 1.0, "Average miss, in violations. Better than guessing the average, but it explains only 12% of the differences.", 11.5, MUTE)
chart(s, XL_CHART_TYPE.BAR_CLUSTERED, 4.7, 3.5, 3.75, 2.2, ["Low risk => Grocery", "10+ => Fail", "Licence+Pass => clean", "High risk clean => Re-insp."], [("Lift", [round(v, 1) for v in [6.5, 3.0, 2.8, 2.1]])], gap=45, fmt="0.0", point_colors=[BLUE, AMBER, TEAL, TEAL], size=10).category_axis.reverse_order = True
label(s, 4.95, 5.75, 3.4, 1.0, "Lift = how much more often than chance (1 = no link). Two methods agreed: 1,198 patterns, 14 rules kept.", 11.5, MUTE)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 8.8, 3.5, 3.75, 2.2, ["Recall", "Precision"], [("Cut-off 0.5", [round(d05["Recall"], 2), round(d05["Precision"], 2)]), ("Tuned 0.217", [round(dtu["Recall"], 2), round(dtu["Precision"], 2)])], colors=[MUTE, BLUE], legend=True, gap=60, fmt="0.00", size=10)
label(s, 9.05, 5.75, 3.4, 1.0, "A lower cut-off finds 61% of fails but gives more false alarms. Good for ranking, not for deciding.", 11.5, MUTE)

# ------------------------------------------------------------------ 11 recommendation
c2 = cs[cs.rows == 2000000].centralized_ms
s = slide("Part J", "Our recommendation: keep the batch warehouse at the centre", "A mix of the three, measured on the same data and the same computer",
          "Core: batch PostgreSQL warehouse as the system of record: every query 10-74 ms, 2,000,000 rows (32 times the real data) still 0.2-0.3 s. Add real-time only for live monitoring and only if inspections are captured digitally. Add distribution only if the data outgrows one machine. Chicago adds about 16,000 inspections a year, so one node is enough for decades.")
for i, (tag, h, t, c, fill, tc) in enumerate([("ONLY IF DATA GETS HUGE", "Distributed layer (Citus)", "Only when one server is not enough, on separate machines. Not needed for about 16,000 inspections a year.", BLUE, CARD2, WHITE),
                                              ("ADD IF NEEDED", "Real-time layer", f"Only for live monitoring, if inspections are entered digitally. {lat / 1000:.1f} s delay, but it needs four services and about 2.5 GB.", AMBER, CARD, WHITE),
                                              ("CORE", "Batch warehouse (PostgreSQL)", f"The trusted main copy. Every query takes 10-74 ms. Even 2,000,000 rows (32 times our data) take {c2.min():.0f}-{c2.max():.0f} ms on one server.", TEAL, TEAL, INK)]):
    inset = (2 - i) * 0.55; y = 1.9 + i * 1.62; w = 7.9 - 2 * inset
    b = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6 + inset, y, w, 1.5, fill, c, 1.5, 0.08)
    pill(s, 0.85 + inset, y + 0.13, 1.7, 0.3, tag, c if fill != TEAL else INK, INK if fill != TEAL else TEAL, 10)
    label(s, 0.85 + inset, y + 0.5, w - 0.5, 0.4, h, 17, tc, True); label(s, 0.85 + inset, y + 0.88, w - 0.5, 0.6, t, 11.5, tc if fill == TEAL else MUTE)
card(s, 8.85, 1.9, 3.88, 4.7); label(s, 9.1, 2.0, 3.4, 0.4, "Advice for the health department", 15, AMBER, True)
bullets(s, 9.1, 2.5, 3.4, 4.0, ["Check complaint reports first", "Re-inspect about two weeks after a fail", "Re-inspect early when there are 10+ violations", "Target ZIP codes by fail rate; plan staff by fail count", "Use the models to rank, never to decide", "Record the time of day and one row per violation"], 13, gap=11, dot=AMBER)

# ------------------------------------------------------------------ 12 status
s = slide("Wrap-up", "Summary and honest limits", None,
          "State the caveats calmly; they are strengths because everything is measured and reported honestly. Everything is reproducible: the README lists the commands, and the single Colab notebook reruns the batch, OLAP and mining parts. Then invite questions.")
card(s, 0.6, 1.5, 5.95, 4.4); shape(s, MSO_SHAPE.RECTANGLE, 0.85, 1.5, 1.2, 0.07, GREEN); label(s, 0.85, 1.7, 5.5, 0.45, "Delivered and measured", 18, GREEN, True)
bullets(s, 0.85, 2.3, 5.5, 3.5, ["All 10 parts (A to J) built and measured", "Citus tested on a 3-server cluster", "All 54 required items listed in the README", "Code, notebooks, report and slides", "One Colab notebook that runs the main parts"], 15, gap=12, dot=GREEN)
card(s, 6.78, 1.5, 5.95, 4.4); shape(s, MSO_SHAPE.RECTANGLE, 7.03, 1.5, 1.2, 0.07, AMBER); label(s, 7.03, 1.7, 5.5, 0.45, "Honest notes", 18, AMBER, True)
bullets(s, 7.03, 2.3, 5.5, 3.5, ["The real-time part replays old data", "Citus shared one computer, so no speed-up", "No Power BI file (Windows only); HTML dashboard instead", "Data above 61,737 rows is simulated, only for timing", "History starts in 2022; 2025 behaves differently"], 15, gap=12, dot=AMBER)
b = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 6.1, 12.13, 0.8, TEAL, None, radius=0.2); write(b, "Thank you  |  Questions?", 22, INK, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)

prs.save(ROOT / "docs" / "Presentation.pptx")
print("written docs/Presentation.pptx with", len(prs.slides), "slides")
