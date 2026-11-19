"""Builds docs/Presentation.pptx (14 slides, speaker notes) from the files in results/ and docs/images/.

Design: one serif typeface (Times New Roman), white background, navy-blue accent, hairline rules instead of boxes, native (editable) charts.
Run after  python run_all.py :   python build_docs/build_slides.py
"""
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
R, IMG = ROOT / "results", ROOT / "docs" / "images"
rd = lambda n: pd.read_csv(R / f"{n}.csv")
rgb = RGBColor.from_string
PAPER, INK, CLAY, STONE, RULE, SOFT = rgb("FFFFFF"), rgb("1A1F2E"), rgb("1F4E9C"), rgb("5B6577"), rgb("C9D2E3"), rgb("EEF2F9")
FONT = "Times New Roman"
FOOT = "Food Safety and Restaurant Inspection Analytics"
TOTAL = 14

prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
blank = prs.slide_layouts[6]
state = {"n": 0}


# ------------------------------------------------------------------ primitives
def runs(p, parts, size, color, bold=False, italic=False):
    for part in parts if isinstance(parts, list) else [parts]:
        txt, kw = (part, {}) if isinstance(part, str) else part
        r = p.add_run(); r.text = txt
        f = r.font; f.name = FONT; f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", bold); f.italic = kw.get("italic", italic); f.color.rgb = kw.get("color", color)


def text(s, x, y, w, h, content, size=16, color=INK, bold=False, italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=6, line=1.08):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paras = content if isinstance(content, list) and content and isinstance(content[0], (list, str)) and not (isinstance(content[0], tuple)) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space); p.line_spacing = line
        runs(p, para, size, color, bold, italic)
    return tb


def _bar(s, x, y, w, h, color):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid(); r.fill.fore_color.rgb = color; r.line.fill.background(); r.shadow.inherit = False
    st = r._element.find(qn("p:style"))
    if st is not None:
        r._element.remove(st)                     # LibreOffice draws the theme shadow of effectRef even when effectLst is empty
    return r


def rule(s, x, y, w, color=RULE, weight=0.75):
    return _bar(s, x, y, w, weight / 72, color)


def vrule(s, x, y, h, color=RULE, weight=0.75):
    return _bar(s, x, y, weight / 72, h, color)


def slide(label, title, sub=None, notes=""):
    s = prs.slides.add_slide(blank); state["n"] += 1
    s.background.fill.solid(); s.background.fill.fore_color.rgb = PAPER
    text(s, 0.8, 0.5, 9, 0.3, label, 12, CLAY, italic=True)
    text(s, 0.8, 0.82, 11.7, 0.9, title, 32, INK)
    if sub:
        text(s, 0.8, 1.62, 11.5, 0.4, sub, 15, STONE, italic=True)
    rule(s, 0.8, 7.0, 11.73)
    text(s, 0.8, 7.08, 9, 0.25, FOOT + "  |  Rushikesh Maddewad  |  PRN 202502040037", 10, STONE)
    text(s, 11.5, 7.08, 1.03, 0.25, f"{state['n'] + 1}", 10, STONE, align=PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def big(s, x, y, w, number, caption, color=INK, size=40):
    text(s, x, y, w, 0.8, number, size, color)
    text(s, x, y + 0.82, w, 0.7, caption, 13, STONE, line=1.0)


def pic(s, name, x, y, maxw, maxh, border=True):
    path = IMG / name
    w, h = Image.open(path).size; k = min(maxw / w, maxh / h); pw, ph = w * k, h * k
    px, py = x + (maxw - pw) / 2, y
    if border:
        r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px), Inches(py), Inches(pw), Inches(ph)); r.fill.background(); r.line.color.rgb = RULE; r.line.width = Pt(0.75); r.shadow.inherit = False
        st = r._element.find(qn("p:style")); r._element.remove(st) if st is not None else None
    s.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
    return px, py, pw, ph


def table(s, x, y, w, rows, widths, size=12, row_h=0.36, header=True, align=None):
    nrows, ncols = len(rows), len(rows[0])
    gf = s.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows)); tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for attr in ("firstRow", "bandRow"):
        tblPr.set(attr, "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"          # 'No Style, No Grid'
    total = sum(widths)
    for j, wd in enumerate(widths):
        tbl.columns[j].width = Emu(int(Inches(w) * wd / total))
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j); c.fill.background()
            c.margin_left = Inches(0.04); c.margin_right = Inches(0.08); c.margin_top = Inches(0.03); c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = (align[j] if align else (PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT))
            is_head = header and i == 0
            runs(p, str(val), size, STONE if is_head else INK, bold=False, italic=is_head)
            tcPr = c._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcPr, qn(tag))
                if tag == "a:lnB":
                    ln.set("w", str(12700 if is_head else 6350))
                    sf = etree.SubElement(ln, qn("a:solidFill")); clr = etree.SubElement(sf, qn("a:srgbClr")); clr.set("val", "1F4E9C" if is_head else "C9D2E3")
                else:
                    ln.set("w", "0"); etree.SubElement(ln, qn("a:noFill"))
            # border elements must come before the fill element in the schema order
            fills = [e for e in tcPr if e.tag in (qn("a:noFill"), qn("a:solidFill"))]
            for e in fills:
                tcPr.remove(e); tcPr.append(e)
    return tbl


def chart(s, kind, x, y, w, h, cats, series, colors, legend=False, fmt="0.0", labels=True, gap=70, size=12, ymax=None, point_colors=None, axis=False):
    cd = CategoryChartData(); cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    ch = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.name = FONT; ch.font.size = Pt(size); ch.font.color.rgb = INK
    ch.has_legend = legend; ch.has_title = False
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False; ch.legend.font.size = Pt(size); ch.legend.font.name = FONT
    plot = ch.plots[0]
    if kind != XL_CHART_TYPE.LINE_MARKERS:
        plot.gap_width = gap
    ca, va = ch.category_axis, ch.value_axis
    ca.format.line.color.rgb = RULE; ca.tick_labels.font.size = Pt(size); ca.tick_labels.font.name = FONT
    va.has_major_gridlines = axis; va.visible = axis; va.minimum_scale = 0
    if axis:
        va.major_gridlines.format.line.color.rgb = RULE; va.format.line.fill.background(); va.tick_labels.font.size = Pt(size - 1)
    if ymax:
        va.maximum_scale = ymax
    for i, ser in enumerate(plot.series):
        c = colors[i % len(colors)]
        if kind == XL_CHART_TYPE.LINE_MARKERS:
            ser.format.line.color.rgb = c; ser.format.line.width = Pt(2.5); ser.smooth = False
            ser.marker.format.fill.solid(); ser.marker.format.fill.fore_color.rgb = c; ser.marker.format.line.color.rgb = c; ser.marker.size = 8
        else:
            ser.format.fill.solid(); ser.format.fill.fore_color.rgb = c
    if point_colors:
        for j, c in enumerate(point_colors):
            pt = plot.series[0].points[j]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c
    if labels:
        plot.has_data_labels = True; dl = plot.data_labels; dl.font.size = Pt(size); dl.font.name = FONT; dl.font.color.rgb = INK
        dl.number_format = fmt; dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.ABOVE if kind == XL_CHART_TYPE.LINE_MARKERS else XL_LABEL_POSITION.OUTSIDE_END
    return ch



# ------------------------------------------------------------------ numbers from the results files
audit = rd("load_audit").set_index("batch_id"); mc = rd("model_comparison").set_index("criterion"); val = rd("validation_results")
q3 = pd.read_csv(R / "analytical_query_results" / "Q3.csv"); q5 = pd.read_csv(R / "analytical_query_results" / "Q5.csv")
reg = rd("regression_metrics").set_index("Model"); dtm = rd("decision_tree_metrics").set_index("Model"); rules = rd("association_rules_selected")
ds = rd("distributed_scaling"); sm = rd("streaming_metrics").set_index("metric")["value"]; imp = rd("decision_tree_importance"); qt = rd("batch_query_timing")
LAT, P95 = sm["latency avg (ms), emit -> ClickHouse"], sm["latency p95 (ms)"]
multi, base = reg.loc["Multiple LR: all test inspections"], reg.loc["Baseline: predict the training mean"]
tree5, treeT = dtm.loc["Decision tree, threshold 0.5"], dtm.loc["Decision tree, validation-optimal threshold"]
f22, f25 = q3.loc[q3["year"] == 2022, "fail_rate"].iloc[0], q3.loc[q3["year"] == 2025, "fail_rate"].iloc[0]
fast, slow, tot = int((ds.distributed_over_centralized < 0.85).sum()), int((ds.distributed_over_centralized > 1.15).sum()), len(ds)

# 1 title
s = prs.slides.add_slide(blank); s.background.fill.solid(); s.background.fill.fore_color.rgb = PAPER
text(s, 0.8, 0.8, 9, 0.3, "Data warehousing, OLAP and data mining project", 14, CLAY, italic=True)
text(s, 0.8, 1.7, 10.2, 2.4, "Food Safety and Restaurant Inspection Analytics", 54, INK, line=1.0)
rule(s, 0.8, 4.2, 1.6, CLAY, 2.25)
text(s, 0.8, 4.45, 10.5, 0.5, "Batch, distributed and real-time warehouses, OLAP and three mining models on Chicago inspection records, 2022 to 2025", 18, STONE, italic=True)
text(s, 0.8, 5.9, 8, 0.9, [[("Rushikesh Maddewad", {"color": INK})], "PRN 202502040037   |   Roll No 353"], 16, STONE, space=2)
text(s, 8.6, 6.1, 3.9, 0.6, "Data: City of Chicago Data Portal (open data)", 12, STONE, italic=True, align=PP_ALIGN.RIGHT)
s.notes_slide.notes_text_frame.text = ("One-minute version: Chicago inspects restaurants and records pass, conditional pass or fail. I took the public records for 2022 to 2025 (61,737 completed inspections), cleaned them, "
    "stored them in a data warehouse built three ways (batch, distributed, real-time), measured the three on the same data, answered ten business questions and trained three small models. "
    "The conclusion is a batch warehouse at the centre; failures are only weakly predictable before the visit.")

# 2 data
s = slide("The data", "Four years of inspection records, one row per visit", "City of Chicago Food Inspections, 1 January 2022 to 31 December 2025",
          "The unit of analysis is a completed inspection. About one record in six is not an inspection (out of business, no entry, not ready); those stay in staging.")
for i, (n, c, col) in enumerate([("73,630", "records downloaded from the data portal", INK), ("11,864", "not completed inspections, kept in staging only", STONE), ("61,737", "completed inspections: the rows of the fact table", CLAY),
                                 ("552", "failed or conditional inspections with no violation text: stored as unknown, not zero", INK)]):
    x = 0.8 + i * 3.0
    big(s, x, 2.6, 2.7, n, c, col)
    if i:
        vrule(s, x - 0.2, 2.65, 1.5)
rule(s, 0.8, 4.65, 11.73)
text(s, 0.8, 4.9, 11.7, 1.8, ["Each record has the establishment, the type of inspection, the result, the free-text list of violations, the address and the coordinates.",
                              "There is no time of day (every timestamp is midnight), so no hourly analysis was attempted.",
                              "The risk category is the city's own label. The value 'All' occurs 38 times and was mapped to Unknown."], 16, INK, space=10)

# 3 method
s = slide("Method", "Raw file to decisions, built three ways", "Batch is the core. Distributed and real-time versions use the same data so the three can be compared.",
          "Batch: Python cleaning, PostgreSQL staging and star schema, OLAP in SQL, dashboard, analytical mart for the models. Distributed: Citus. Real-time: Kafka, Spark, ClickHouse and Grafana, fed by a replay of historical data.")
for i, (a, b) in enumerate([("Raw data", "CSV from the portal"), ("Curation", "Python, pandas"), ("Staging", "PostgreSQL schema"), ("Star schema", "two fact tables"), ("Analysis", "OLAP, mart, models"), ("Delivery", "dashboard, report")]):
    x = 0.8 + i * 2.0
    text(s, x, 2.5, 1.8, 0.4, a, 20, INK); text(s, x, 2.95, 1.8, 0.5, b, 13, STONE, italic=True)
    rule(s, x, 3.5, 1.65, CLAY if i == 3 else RULE, 2.0 if i == 3 else 0.75); text(s, x, 3.6, 0.5, 0.3, str(i + 1), 12, CLAY)
text(s, 0.8, 4.5, 3.6, 2.3, [[("Batch", {"bold": True, "color": CLAY})], "PostgreSQL 16, PL/pgSQL load procedure, indexes, validation checks, incremental load."], 15, INK, space=8)
text(s, 4.8, 4.5, 3.6, 2.3, [[("Distributed", {"bold": True, "color": CLAY})], "Citus 13.2: coordinator and two workers, 32 shards split by facility."], 15, INK, space=8)
text(s, 8.8, 4.5, 3.7, 2.3, [[("Real-time", {"bold": True, "color": CLAY})], "Producer, Kafka, Spark Structured Streaming, ClickHouse, Grafana. A replay, not a live feed."], 15, INK, space=8)

# 4 cleaning
dq = pd.read_csv(ROOT / "docs" / "data_quality_report.md", sep="|", skiprows=7, skipinitialspace=True).iloc[1:, 1:6]; dq.columns = ["Problem", "Field", "Count", "Treatment", "Justification"]
dq["Problem"] = dq["Problem"].str.strip(); dq["Count"] = pd.to_numeric(dq["Count"].astype(str).str.replace(",", "").str.strip(), errors="coerce"); cnt = lambda key: int(dq[dq["Problem"].str.startswith(key)]["Count"].iloc[0])
s = slide("Part A", "Cleaning: each decision has a number and a reason", "The curation script logs every problem it checks (docs/data_quality_report.md).")
rows = [["Problem", "Rows", "Treatment"], ["Same licence, date, type, result and violations, different id", f"{cnt('Logical duplicate')}", "Removed (repeated report)"],
        ["Same licence, date and type, different content", f"{cnt('Same licence')}", "Kept and flagged: may be two visits"], ["Failed or conditional, no violation text", f"{cnt('Fail / Pass w/ Conditions')}", "Violation count unknown (NULL), not 0"],
        ["Passed, no violation text", f"{cnt('Pass with no'):,}", "Violation count 0"], ["Risk code 'All' or missing", f"{cnt('Invalid risk') + cnt('Missing risk')}", "Unknown member in the dimension"],
        ["Missing or zero licence number", f"{cnt('Missing or zero licence')}", "Facility keyed by name and address"], ["More than 14 violations (Q3 + 1.5 IQR)", f"{cnt('Extreme violation'):,}", "Kept and flagged: the worst premises"]]
table(s, 0.8, 2.3, 11.7, rows, [6.2, 1.0, 4.5], size=14, row_h=0.5)

# 5 schema
sc = lambda k, c: mc.loc[k, c]
s = slide("Part B", "Fact constellation: a star plus a second fact at facility-year grain", "Grain: one completed inspection on one date. The snowflake was built too, so the comparison is measured.",
          "Define grain first. Star: fewest joins. Snowflake: normalised dimensions, 16 tables, about twice as slow on PostgreSQL. Constellation: star plus a facility-by-year fact that answers yearly questions about 8 times faster.")
pic(s, "fact_constellation.png", 0.8, 1.95, 6.6, 4.8)
k1, k2, k3, k4 = "Number of tables", "Joins for QA (year/quarter x facility group x area)", "QA median time (ms)", "Facility x year question: median time (ms)"
rows = [["", "Star", "Snowflake", "Constellation"], ["Tables", f"{sc(k1, 'star'):.0f}", f"{sc(k1, 'snowflake'):.0f}", f"{sc(k1, 'fact_constellation'):.0f}"],
        ["Joins, question A", f"{sc(k2, 'star'):.0f}", f"{sc(k2, 'snowflake'):.0f}", f"{sc(k2, 'fact_constellation'):.0f}"], ["Question A, ms", f"{sc(k3, 'star'):.1f}", f"{sc(k3, 'snowflake'):.1f}", f"{sc(k3, 'fact_constellation'):.1f}"],
        ["Facility by year, ms", f"{sc(k4, 'star'):.1f}", f"{sc(k4, 'snowflake'):.1f}", f"{sc(k4, 'fact_constellation'):.1f}"]]
table(s, 7.8, 2.1, 4.75, rows, [2.1, 1.0, 1.3, 1.6], size=13, row_h=0.46)
text(s, 7.8, 4.6, 4.7, 2.2, "The snowflake needs three times the joins and is about twice as slow. The second fact is what turns the facility-by-year question into a lookup.", 14, STONE, italic=True)

# 6 batch
ni = audit.loc[3, "rows_rejected"]; checks = val[val["stage"] == "after incremental load"]; n_checks = len(checks)
s = slide("Part C", "One load procedure, three batches, sixteen checks", "Each batch is one transaction. A deliberately failing load left all four tables unchanged.",
          "Explain the procedure: stage, apply quality rules, add dimension members, load facts, build the annual fact, then 16 checks. December 2025 was held back and loaded later; the first 60,608 rows were unchanged (MD5 checksum). Loading December again added 0 rows.")
for i, (n, c, col) in enumerate([(f"{int(audit.loc[1, 'rows_loaded_fact']):,}", "facts, initial load (January 2022 to November 2025)", INK), (f"+{int(audit.loc[2, 'rows_loaded_fact']):,}", "facts, incremental load of December 2025; earlier rows unchanged (checksum)", CLAY),
                                 (f"{int(audit.loc[3, 'rows_loaded_fact'])}", f"facts when the same month is loaded again: {int(ni):,} rows rejected", INK), (f"{n_checks} / {n_checks}", "integrity and reconciliation checks pass (all values 0)", CLAY)]):
    x = 0.8 + i * 3.0
    big(s, x, 2.5, 2.7, n, c, col)
    if i:
        vrule(s, x - 0.2, 2.55, 1.6)
rule(s, 0.8, 4.6, 11.73)
text(s, 0.8, 4.85, 3.6, 2.0, [[("Queries", {"bold": True}), f": the eight business queries take {qt['median_ms'].min():.0f} to {qt['median_ms'].max():.0f} ms."]], 15, INK)
text(s, 4.8, 4.85, 3.6, 2.0, [[("Indexes", {"bold": True}), ": selective queries fall from 3 to 5 ms to 0.2 to 0.3 ms."]], 15, INK)
text(s, 8.8, 4.85, 3.7, 2.0, [[("Scale", {"bold": True}), ": two million rows (32 times the data) still answer in under 0.3 s on one node."]], 15, INK)

# 7 OLAP + dashboard
s = slide("Part F", "OLAP in SQL, and a dashboard built from the warehouse", "Roll-up, drill-down, slice, dice, pivot, CUBE and GROUPING SETS: SQL and output in docs/olap_operations.md.",
          "Name the operations. Show the HTML dashboard in a browser if you can. State calmly: Power BI Desktop is Windows-only, so the dashboard is an HTML page built from the warehouse; the DAX measures are written but were not executed.")
pic(s, "dashboard_exec.png", 0.8, 2.0, 7.6, 4.8)
text(s, 8.8, 2.0, 3.7, 4.8, [[("Four sections", {"bold": True})], "Executive overview", "Facility and risk", "Geography", "Inspections and violations", [("", {})], [("Open it", {"bold": True})], "dashboard/food_safety_dashboard.html"], 15, INK, space=6)

# 8 findings
s = slide("Part F", f"The fail rate fell from {f22:.1f}% to {f25:.1f}%, and complaints fail most", "Fail rate by year, and by type of inspection (single types with more than 1,000 inspections).",
          "Pick three to say aloud: the fail rate fell; complaint inspections fail most (37.6%); after a failed inspection the next visit passes about four times in five, 13 days later.")
chart(s, XL_CHART_TYPE.LINE_MARKERS, 0.8, 2.3, 5.6, 3.0, [str(y) for y in q3["year"]], [("fail rate", list(q3["fail_rate"]))], [CLAY], ymax=32)
text(s, 0.8, 2.05, 5, 0.3, "Fail rate by year (%)", 14, STONE, italic=True)
top = q5[q5["inspections"] > 1000].sort_values("fail_rate", ascending=False)
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 6.9, 2.3, 5.7, 3.0, [t.replace(" Re-Inspection", "\nre-insp.") for t in top["inspection_type"]], [("fail rate", list(top["fail_rate"]))], [STONE], ymax=45, size=11,
      point_colors=[CLAY if t == "Complaint" else STONE for t in top["inspection_type"]])
text(s, 6.9, 2.05, 5, 0.3, "Fail rate by type of inspection (%)", 14, STONE, italic=True)
rule(s, 0.8, 5.6, 11.73)
text(s, 0.8, 5.8, 3.7, 1.1, "After a failed inspection the next visit passes about four times in five (79%).", 14, INK)
text(s, 4.8, 5.8, 3.7, 1.1, "Ten or more violations: a 69% chance that the inspection fails.", 14, INK)
text(s, 8.8, 5.8, 3.7, 1.1, "ZIP codes with the highest rates are mostly not the ones with the most failures.", 14, INK)

# 9 regression + association
sel = rules.sort_values("lift", ascending=False).iloc[[0, 1, 2, 4, 6]]
s = slide("Parts G and H", f"Regression and association rules (R squared {multi['R2']:.2f}, lift up to 6.5)", "Train 2022 to 2024, test 2025; only facts known before the visit; Apriori and FP-Growth find the same 1,198 itemsets.",
          "Regression: predict the number of violations. MAE 2.45 against 2.71 for the average, R squared 0.12. Association rules: support, confidence and lift; 10 or more violations implies Fail with 69% confidence and lift 3.0.")
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.8, 2.4, 4.8, 3.2, ["Guess the average", "One input", "All inputs"], [("MAE", [round(base["MAE"], 2), round(reg.loc["Simple LR: PriorViolationCount", "MAE"], 2), round(multi["MAE"], 2)])], [STONE], fmt="0.00", ymax=3.4, point_colors=[STONE, STONE, CLAY])
text(s, 0.8, 2.05, 5, 0.3, "Average error on 2025, in violations", 14, STONE, italic=True)
text(s, 0.8, 5.8, 4.8, 1.0, f"Multiple regression: {multi['R2']:.0%} of the variation explained. Checks: 5 of 102 columns above VIF 5; error spread not constant.", 13, STONE, italic=True)
rows = [["Rule", "Conf.", "Lift"]] + [[r.Rule.replace("  =>  ", " => ").replace("FacilityType=", "").replace("InspType=", ""), f"{r.confidence:.0%}", f"{r.lift:.1f}"] for r in sel.itertuples()]
table(s, 6.2, 2.1, 6.3, rows, [5.0, 0.7, 0.6], size=12, row_h=0.62)

# 10 decision tree
s = slide("Part I", f"A decision tree ranks failures only weakly (AUC {tree5['ROC-AUC']:.2f})", "Train 2022 and 2023, settings and cut-off chosen on 2024, evaluated once on 2025. Only facts known before the visit.",
          "At the default cut-off of 0.5 the tree flags almost nothing (recall 4%). With the cut-off chosen on 2024 it finds 61% of failures with 29% precision. The past is the best clue: a previous fail, a complaint inspection, earlier violations, days since the last visit.")
rows = [["Model", "Accuracy", "Precision", "Recall", "AUC"], ["Always 'not failed'", f"{dtm.iloc[0]['Accuracy']:.3f}", "0", "0", "0.500"],
        ["Tree, cut-off 0.5", f"{tree5['Accuracy']:.3f}", f"{tree5['Precision']:.3f}", f"{tree5['Recall']:.3f}", f"{tree5['ROC-AUC']:.3f}"],
        [f"Tree, cut-off {treeT['threshold']} (from 2024)", f"{treeT['Accuracy']:.3f}", f"{treeT['Precision']:.3f}", f"{treeT['Recall']:.3f}", f"{treeT['ROC-AUC']:.3f}"]]
table(s, 0.8, 2.3, 7.0, rows, [3.2, 1.0, 1.0, 0.9, 0.8], size=14, row_h=0.55)
text(s, 0.8, 4.8, 7.0, 1.9, "Lowering the cut-off catches more failures and raises more false alarms; accuracy falls below the 79% of a rule that always predicts a pass. The right trade-off depends on what a missed failure costs.", 15, STONE, italic=True)
text(s, 8.4, 2.1, 4.1, 0.4, "Most important inputs", 16, CLAY)
rows = [[r.iloc[0].replace("_", " "), f"{100 * r.importance:.0f}%"] for _, r in imp.head(5).iterrows()]
table(s, 8.4, 2.6, 4.1, [["Input", "Share"]] + rows, [3.0, 0.8], size=13, row_h=0.5)

# 11 citus
d2 = ds[ds["rows"] == 2000000]
s = slide("Part D", "Citus: right answers, but not faster on one machine", "Coordinator and two workers on one machine; 32 shards; facts split by facility; dimensions copied to every worker.",
          f"Be upfront: results were identical to one node in all {tot} tests, but Citus was clearly faster in {fast} and slower in {slow}. The nodes shared the same four cores, so there was coordination work and no extra hardware. FacilityKey: 17,083 distinct values, most even shards. Volumes above 61,737 rows are a synthetic scale-up used only for timing.")
chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, 0.8, 2.4, 7.4, 3.6, ["Q1", "Q2", "Q3", "Q4", "Q5"], [("One node", [round(v) for v in d2["centralized_ms"]]), ("Citus", [round(v) for v in d2["distributed_ms"]])], [STONE, CLAY], legend=True, fmt="0", ymax=450)
text(s, 0.8, 2.05, 7, 0.3, "Time with 2,000,000 rows (ms)", 14, STONE, italic=True)
for i, (n, c, col) in enumerate([(f"{tot} / {tot}", "answers equal to one node", INK), (f"{fast} of {tot}", "timings where Citus was clearly faster", CLAY), (f"{slow} of {tot}", "timings where it was clearly slower", INK)]):
    big(s, 8.8, 2.2 + i * 1.5, 3.7, n, c, col, 32)
text(s, 0.8, 6.2, 11.7, 0.6, "Why: the workers shared the same CPU cores, so there was coordination work but no extra hardware.", 14, STONE, italic=True)

# 12 real-time
s = slide("Part E", "Real-time warehouse: a replay of historical data", "Kafka, Spark Structured Streaming, ClickHouse, Grafana. Every event says it is a replay.",
          "The official dataset is a historical file, so the pipeline replays it. The pipeline itself ran end to end. Spark applies seven validation rules; bad events go to a separate table. Average delay 1.5 seconds.")
pic(s, "grafana_realtime_dashboard.png", 0.8, 2.0, 7.4, 4.0)
for i, (n, c) in enumerate([(f"{LAT / 1000:.1f} s", f"average delay (95% under {P95 / 1000:.1f} s)"), ("3,647", "events, each stored exactly once"), ("24 / 24", "injected bad events rejected"), ("6 to 7 ms", "dashboard queries in ClickHouse")]):
    big(s, 8.6, 2.0 + i * 1.2, 4.0, n, c, CLAY if i == 0 else INK, 30)
text(s, 0.8, 6.3, 7.4, 0.5, "The four services used about 2.5 GB of memory.", 14, STONE, italic=True)

# 13 recommendation
s = slide("Part J", "Recommendation: keep the batch warehouse at the centre", "Measured on the same data and the same machine.",
          "Batch PostgreSQL warehouse as the system of record: every query 10 to 74 ms; two million rows still 0.2 to 0.3 s. Real-time only for live monitoring, only if inspections are captured digitally. Distribution only when the data outgrows one machine. Chicago adds about 16,000 inspections a year.")
for i, (h, t) in enumerate([("Batch warehouse: the core", "The system of record. Every analytical query takes 10 to 74 ms; a month loads in about half a second; one server, tested loads, full OLAP."),
                            ("Real-time layer: if needed", f"Only for live monitoring, and only if inspections are entered digitally. {LAT / 1000:.1f} s delay, but four services and about 2.5 GB."),
                            ("Distributed layer: only at scale", "Only when one server is not enough, and on separate machines. About 16,000 inspections a year do not need it.")]):
    y = 2.2 + i * 1.45
    rule(s, 0.8, y, 11.73, CLAY if i == 0 else RULE, 1.5 if i == 0 else 0.75)
    text(s, 0.8, y + 0.15, 4.2, 0.5, h, 20, CLAY if i == 0 else INK); text(s, 5.2, y + 0.18, 7.3, 1.0, t, 15, INK)

# 14 wrap-up
s = slide("Wrap-up", "What the project shows, and its limits", None, "State the caveats calmly; they are findings because everything was measured and reported honestly.")
text(s, 0.8, 1.7, 5.6, 0.4, "What the project shows", 20, CLAY)
text(s, 0.8, 2.3, 5.5, 4.2, ["A star-schema warehouse loads 61,737 inspections, validates itself and answers every business query in milliseconds.", "Failures became less frequent over four years; the type of inspection matters more than the risk category.",
                              "Facts known before a visit predict the outcome weakly: a model can order the work, not settle a result."], 15, INK, space=10)
vrule(s, 6.65, 1.75, 3.9)
text(s, 7.0, 1.7, 5.5, 0.4, "Limits", 20, CLAY)
text(s, 7.0, 2.3, 5.5, 4.2, ["The real-time part replays historical data.", "Citus shared one computer, so no speed-up.", "No Power BI file (Windows-only); the dashboard is an HTML page.", "Rows above 61,737 in the scale test are simulated, only for timing.", "All timings come from one machine."], 15, INK, space=10)
rule(s, 0.8, 6.0, 11.73)
text(s, 0.8, 6.2, 11.7, 0.5, "Code, report, slides and dashboard: github.com/r11shi/eda     |     python run_all.py", 14, STONE, italic=True)
assert state["n"] + 1 == TOTAL, state["n"] + 1
out = ROOT / "docs" / "Presentation.pptx"; prs.save(out); print("written", out.relative_to(ROOT), "with", len(prs.slides), "slides")
