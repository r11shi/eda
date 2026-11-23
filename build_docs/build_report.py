"""Builds the project report as a Word document (docs/Food_Safety_Analytics_Report.docx) and a PDF copy, in the layout of a formal project report:
cover page, declaration, abstract, table of contents, chapters 1 to 10, references. Numbers are read from results/ and docs/.

    python build_docs/build_report.py      # needs python-docx and python-pptx; the PDF copy needs LibreOffice (soffice) and pdftotext
Edit the constants below (institute, department, course, guide, students) before submitting.
"""
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------------- edit before submission
INSTITUTE = "MIT Academy of Engineering"
AFFILIATION = "(An Autonomous Institute Affiliated to Savitribai Phule Pune University)"
DEPARTMENT = "Computer Engineering"
COURSE = "Data Analytics (MDM)"
GUIDE = "Mrs. Shubhangi Kale"
YEAR = "2026-27"
REPO = "https://github.com/r11shi/eda"
TITLE = "Food Safety and Restaurant Inspection Analytics"
SUBTITLE = "Data Warehousing, OLAP and Data Mining on Chicago Food Inspections"
STUDENTS = [("Omkar Patil", "202502040010"), ("Aryan Tandale", "202502040013"), ("Rushikesh Maddewad", "202502040037"), ("Vishwaraj Savairam", "202502040035")]
PLATFORM = "one Windows 11 laptop running WSL 2 Ubuntu 26.04 (12 logical CPUs, 8 GB memory for WSL) with PostgreSQL 18.6, Citus 14.3, Kafka 3.9, Spark 4.0.1, ClickHouse 26.3 and Grafana 11.3"
# -----------------------------------------------------------------------------------------------------
R, IMG, LOGS = ROOT / "results", ROOT / "docs" / "images", ROOT / "docs" / "console_logs"
SHOTS = IMG / "screens"
SLIDES_DIR = ROOT / "docs" / "slides"
OUT_DOCX = ROOT / "docs" / "Food_Safety_Analytics_Report.docx"
FONT, HEAD_FONT, CODE_FONT = "Calibri", "Cambria", "Courier New"
INK, NAVY, CLAY, STONE = RGBColor(0x1B, 0x24, 0x28), RGBColor(0x0E, 0x3B, 0x43), RGBColor(0x0E, 0x7C, 0x66), RGBColor(0x5B, 0x6B, 0x70)
DARK, TINT, LINE = "0E3B43", "EEF4F3", "C9D9D6"
rd = lambda n: pd.read_csv(R / f"{n}.csv")
AQ = lambda n: pd.read_csv(R / "analytical_query_results" / f"{n}.csv")

# ----------------------------------------------------------------------------- data from the pipeline
audit, val, mc, mcq, qt, idx, inc, lt = (rd("load_audit").set_index("batch_id"), rd("validation_results"), rd("model_comparison").set_index("criterion"), rd("model_comparison_queries"),
                                          rd("batch_query_timing"), rd("indexing_effect"), rd("incremental_load_demo"), rd("batch_load_timing_all"))
reg, coef, rules, dtm, imp, paths = (rd("regression_metrics").set_index("Model"), rd("regression_top_coefficients"), rd("association_rules_selected"), rd("decision_tree_metrics").set_index("Model"),
                                     rd("decision_tree_importance"), rd("decision_tree_paths"))
ds, cs, dkey, cload, cres, sm = rd("distributed_scaling"), rd("centralized_scaling"), rd("distribution_key_analysis"), rd("citus_load_times"), rd("citus_resources"), rd("streaming_metrics").set_index("metric")["value"]
q3, q4, q5, q1a, q2, q8b, q7b, q7c, q6b = AQ("Q3"), AQ("Q4"), AQ("Q5"), AQ("Q1a"), AQ("Q2"), AQ("Q8b"), AQ("Q7b"), AQ("Q7c"), AQ("Q6b")
dq = pd.read_csv(ROOT / "docs" / "data_quality_report.md", sep="|", skiprows=7, skipinitialspace=True).iloc[1:, 1:6]
dq.columns = ["Problem", "Field", "Count", "Treatment", "Justification"]
dq["Problem"] = dq["Problem"].str.strip(); dq["Count"] = pd.to_numeric(dq["Count"].astype(str).str.replace(",", "").str.strip(), errors="coerce"); dq = dq.dropna(subset=["Count"])
cnt = lambda key: int(dq[dq["Problem"].str.startswith(key)]["Count"].iloc[0])


def olap_blocks():
    text = (ROOT / "docs" / "olap_operations.md").read_text(encoding="utf-8")
    out = {}
    for blk in re.split(r"^## ", text, flags=re.M)[1:]:
        head = blk.split("\n")[0].strip(); bid = head.split(" ")[0]
        table = re.search(r"\*\*Output:\*\*\s*\n\n((?:\|.*\n)+)", blk)
        interp = re.search(r"\*\*Interpretation:\*\*\s*(.+)", blk)
        quest = re.search(r"\*\*Business question:\*\*\s*(.+)", blk)
        df = None
        if table:
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in table.group(1).strip().splitlines()]
            df = pd.DataFrame(rows[2:], columns=rows[0])
        out[bid] = {"title": head, "df": df, "interp": interp.group(1).strip() if interp else "", "question": quest.group(1).strip() if quest else ""}
    return out


OLAP = olap_blocks()
FINDINGS = re.findall(r"^## Finding (\d+): (.+)$", (ROOT / "docs" / "ten_findings.md").read_text(encoding="utf-8"), flags=re.M)
f22, f25 = q3.loc[q3["year"] == 2022, "fail_rate"].iloc[0], q3.loc[q3["year"] == 2025, "fail_rate"].iloc[0]
multi, base, simple = reg.loc["Multiple LR: all test inspections"], reg.loc["Baseline: predict the training mean"], reg.loc["Simple LR: PriorViolationCount"]
tree5, treeT = dtm.loc["Decision tree, threshold 0.5"], dtm.loc["Decision tree, validation-optimal threshold"]
fast, slow, tot = int((ds.distributed_over_centralized < 0.85).sum()), int((ds.distributed_over_centralized > 1.15).sum()), len(ds)
LAT, P95 = sm["latency avg (ms), emit -> ClickHouse"], sm["latency p95 (ms)"]
CHQ = sm[[k for k in sm.index if k.startswith("ClickHouse query")]]
N_RAW, N_FACT, N_NOT = 73630, 61737, 11864

# ----------------------------------------------------------------------------- document helpers
doc = Document()
HEADS = []            # (level, text) in order, for the table of contents
state = {"tab": 0, "fig": 0, "chap": 0}


def set_font(style_or_run, size=None, bold=None, italic=None, color=None, name=FONT):
    f = style_or_run.font
    f.name = name
    rpr = style_or_run.element.get_or_add_rPr() if hasattr(style_or_run.element, "get_or_add_rPr") else style_or_run.element.rPr
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts"); rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), name)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(a), None)
    if size: f.size = Pt(size)
    if bold is not None: f.bold = bold
    if italic is not None: f.italic = italic
    if color is not None: f.color.rgb = color


def shade(cell_or_par, fill):
    el = cell_or_par._tc.get_or_add_tcPr() if hasattr(cell_or_par, "_tc") else cell_or_par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill); el.append(shd)


def border(par, sides=("bottom",), color="1F3864", size=6, space=1):
    pPr = par._p.get_or_add_pPr(); b = OxmlElement("w:pBdr")
    for side in sides:
        e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(size)); e.set(qn("w:space"), str(space)); e.set(qn("w:color"), color); b.append(e)
    pPr.append(b)


def setup():
    s = doc.sections[0]
    s.page_width, s.page_height = Emu(int(8.27 * 914400)), Emu(int(11.69 * 914400))
    s.left_margin = s.right_margin = Inches(0.75); s.top_margin = s.bottom_margin = Inches(1.0)
    s.header_distance = s.footer_distance = Inches(0.45)
    st = doc.styles
    set_font(st["Normal"], 11)
    st["Normal"].paragraph_format.space_after = Pt(6); st["Normal"].paragraph_format.line_spacing = 1.12
    for name, size, before, after in (("Heading 1", 22, 0, 12), ("Heading 2", 14, 14, 5), ("Heading 3", 12, 8, 3)):
        h = st[name]; set_font(h, size, True, False, CLAY if name == "Heading 2" else NAVY, HEAD_FONT)
        h.paragraph_format.space_before = Pt(before); h.paragraph_format.space_after = Pt(after); h.paragraph_format.keep_with_next = True
    for name, size in (("CodeLine", 7), ("Console", 7.6)):
        from docx.enum.style import WD_STYLE_TYPE
        c = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH); c.base_style = st["Normal"]; set_font(c, size, name=CODE_FONT)
        c.paragraph_format.space_after = Pt(0); c.paragraph_format.space_before = Pt(0); c.paragraph_format.line_spacing = 1.0
    set_font(st["List Bullet"], 11); st["List Bullet"].paragraph_format.space_after = Pt(3)


def fld(par, instr, size=9):
    def run_with(el):
        r = par.add_run(); set_font(r, size, color=STONE); r._r.append(el)
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); run_with(b)
    i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = f" {instr} "; run_with(i)
    sp = OxmlElement("w:fldChar"); sp.set(qn("w:fldCharType"), "separate"); run_with(sp)
    t = OxmlElement("w:t"); t.text = "1"; run_with(t)
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); run_with(e)


def header_footer():
    for nm in ("Header", "Footer"):
        doc.styles[nm].paragraph_format.tab_stops.clear_all()
    s = doc.sections[0]; s.different_first_page_header_footer = True
    width = Emu(s.page_width - s.left_margin - s.right_margin)
    hp = s.header.paragraphs[0]; hp.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
    for txt in (INSTITUTE, "\t", f"{TITLE}  ·  {COURSE}"):
        r = hp.add_run(txt); set_font(r, 9, color=STONE)
    border(hp, ("bottom",), LINE, 4, 3)
    fp = s.footer.paragraphs[0]; fp.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
    r = fp.add_run(f"Group project  ·  {COURSE}  ·  {YEAR}\tPage "); set_font(r, 9, color=STONE)
    fld(fp, "PAGE"); r = fp.add_run(" of "); set_font(r, 9, color=STONE); fld(fp, "NUMPAGES")
    border(fp, ("top",), LINE, 4, 3)


def rich(par, text, size=None, color=None, italic=False):
    """**bold**, *italic* and `code` markup inside a paragraph."""
    for part in re.split(r"(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)", text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2]); set_font(r, size, True, italic, color)
        elif part.startswith("`"):
            r = par.add_run(part[1:-1]); set_font(r, (size or 11) - 1.5, name=CODE_FONT, color=color)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = par.add_run(part[1:-1]); set_font(r, size, None, True, color)
        else:
            r = par.add_run(part); set_font(r, size, None, italic or None, color)


def P(text, size=None, align=None, after=None, color=None, italic=False, keep=False):
    p = doc.add_paragraph(); rich(p, text, size, color, italic)
    if align: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    if keep: p.paragraph_format.keep_with_next = True
    return p


def bullets(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet"); rich(p, t)


def h1(text, page_break=True):
    m = re.match(r"^(\d+) ", text)
    if m:
        k = doc.add_paragraph(); k.paragraph_format.space_after = Pt(0); k.paragraph_format.keep_with_next = True
        if page_break:
            k.paragraph_format.page_break_before = True; page_break = False
        r = k.add_run(f"CHAPTER {m.group(1)}"); set_font(r, 10.5, True, color=CLAY)
    p = doc.add_heading(text, 1)
    if page_break:
        p.paragraph_format.page_break_before = True
    border(p, ("bottom",), "0E7C66", 12, 6)
    HEADS.append((1, text))


def h2(text):
    doc.add_heading(text, 2); HEADS.append((2, text))


def h3(text):
    doc.add_heading(text, 3)


def caption(kind, text):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER if kind == "Figure" else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(8); p.paragraph_format.space_before = Pt(3 if kind == "Figure" else 6)
    if kind == "Table":
        p.paragraph_format.keep_with_next = True
    state["tab" if kind == "Table" else "fig"] += 1
    r = p.add_run(f"{kind} {state['chap']}.{state['tab' if kind == 'Table' else 'fig']}  "); set_font(r, 9.5, True, color=CLAY)
    r = p.add_run(text); set_font(r, 9.5, False, True, STONE)


def figure(path, text, width=6.3):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width))
    caption("Figure", text)


def screen(name, text, width=6.3):
    """A real output screenshot (docs/images/screens/<name>.png, made by build_docs/make_screenshots.py)."""
    path = SHOTS / f"{name}.png"
    if path.exists():
        from PIL import Image
        w, h = Image.open(path).size
        figure(path, "Output screenshot: " + text, min(width, 8.2 * w / h))      # keep tall pages on one page


def table(df, widths, text, size=9, align=None, header=True):
    caption("Table", text)
    rows = [list(map(str, df.columns))] + [[("" if (isinstance(v, float) and pd.isna(v)) else str(v)) for v in r] for r in df.values] if header else [[str(v) for v in r] for r in df.values]
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    tblPr = t._tbl.tblPr; b = OxmlElement("w:tblBorders")
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    for j, wd in enumerate(widths):
        t.columns[j].width = Inches(6.77 * wd / sum(widths))
    for side in ("top", "bottom", "insideH"):
        e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), LINE); b.append(e)
    tblPr.append(b)
    total = sum(widths); usable = 6.77
    for i, row in enumerate(rows):
        tr = t.rows[i]
        if i == 0 and header:
            trPr = tr._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); trPr.append(th)
        trPr = tr._tr.get_or_add_trPr(); cs = OxmlElement("w:cantSplit"); trPr.append(cs)
        for j, val in enumerate(row):
            c = tr.cells[j]; c.width = Inches(usable * widths[j] / total)
            par = c.paragraphs[0]; par.paragraph_format.space_after = Pt(1); par.paragraph_format.space_before = Pt(1); par.paragraph_format.line_spacing = 1.0
            is_head = header and i == 0
            r = par.add_run(val); set_font(r, size, bool(is_head), None, RGBColor(255, 255, 255) if is_head else INK)
            if not is_head and i % 2 == 0:
                shade(c, TINT)
            if align and not is_head and align[j] == "r":
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if is_head:
                shade(c, DARK)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def callout(title, text, fill="EAF2F1"):
    t = doc.add_table(rows=1, cols=1); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]; shade(c, fill)
    tcPr = c._tc.get_or_add_tcPr(); bd = OxmlElement("w:tcBorders")
    for side, col, sz in (("left", "BFD8D2", 6), ("top", "BFD8D2", 6), ("bottom", "BFD8D2", 6), ("right", "BFD8D2", 6)):
        e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz)); e.set(qn("w:color"), col); bd.append(e)
    tcPr.append(bd)
    p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
    r = p.add_run(title + " "); set_font(r, 10, True, color=CLAY)
    rich(p, text, 10)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def wrap_lines(text, width):
    out = []
    for line in text.replace("\t", "    ").splitlines():
        if len(line) <= width:
            out.append(line)
        else:
            lead = len(line) - len(line.lstrip())
            out += textwrap.wrap(line, width, subsequent_indent=" " * (lead + 4), break_long_words=True) or [""]
    return out


def console(title, text, max_lines=34, width=112):
    p = doc.add_paragraph(); p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"Console output: {title}"); set_font(r, 9, True, color=STONE)
    lines = [l.rstrip() for l in text.splitlines() if l.strip() and not set(l.strip()) <= {"="}]
    lines = wrap_lines("\n".join(lines), width)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [f"... ({len(lines) - max_lines + 1} more lines in the log file)"]
    for i, l in enumerate(lines):
        q = doc.add_paragraph(style="Console"); q.add_run(l if l else " "); shade(q, "F1F5F4")
        q.paragraph_format.left_indent = Inches(0.05)
    doc.add_paragraph().paragraph_format.space_after = Pt(3)


def log_excerpt(name, start=None, end=None, max_lines=30):
    text = (LOGS / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    if start:
        i = text.find(start); text = text[i:] if i >= 0 else text
    if end:
        j = text.find(end, 1); text = text[:j] if j > 0 else text
    console(f"{name}", text, max_lines)


def code_file(rel, lang):
    path = ROOT / rel; lines = path.read_text(encoding="utf-8").splitlines()
    doc.add_heading(rel, 2); HEADS.append((2, rel))
    p = P(f"{len(lines)} lines  ·  {lang}  ·  reproduced verbatim from the repository", 9, color=STONE, italic=True, after=3)
    p.paragraph_format.keep_with_next = True
    for i, l in enumerate(lines, 1):
        for k, seg in enumerate(wrap_lines(l, 118) or [""]):
            q = doc.add_paragraph(style="CodeLine"); q.paragraph_format.left_indent = Inches(0.42); q.paragraph_format.first_line_indent = Inches(-0.42)
            q.add_run((f"{i:>3}  " if k == 0 else "     ") + seg)


def fmt_p(v):
    v = float(v)
    return "<0.001" if v < 0.001 else f"{v:.3f}"


# ----------------------------------------------------------------------------- pages
def cover():
    logo = ROOT / "build_docs" / "assets" / "logo.png"
    if logo.exists():
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(logo), width=Inches(3.1))
    else:
        P(AFFILIATION, 9, WD_ALIGN_PARAGRAPH.CENTER, 8, STONE, True)
    P("TY B.Tech  ·  Integrated Data Warehouse, OLAP and Data Mining Project", 10.5, WD_ALIGN_PARAGRAPH.CENTER, 14, CLAY)
    band = doc.add_table(rows=1, cols=1); band.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = band.rows[0].cells[0]; c.width = Inches(6.77); shade(c, DARK)
    for txt_, size, col, bold, after in (("A PROJECT REPORT ON", 10, RGBColor(0xE9, 0xA2, 0x3B), True, 8), (TITLE, 28, RGBColor(255, 255, 255), True, 8),
                                         (SUBTITLE, 13, RGBColor(0xCF, 0xE6, 0xE1), False, 4)):
        q = c.paragraphs[0] if txt_ == "A PROJECT REPORT ON" else c.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER; q.paragraph_format.space_after = Pt(after); q.paragraph_format.space_before = Pt(14 if txt_ == "A PROJECT REPORT ON" else 0)
        r = q.add_run(txt_); set_font(r, size, bold, False, col, HEAD_FONT if size > 20 else FONT)
    c.paragraphs[-1].paragraph_format.space_after = Pt(16)
    P("", after=10)
    P("Submitted in partial fulfilment of the requirements of the course", 10.5, WD_ALIGN_PARAGRAPH.CENTER, 4)
    P(f"**{COURSE}**", 14, WD_ALIGN_PARAGRAPH.CENTER, 18)
    P("**SUBMITTED BY**", 10.5, WD_ALIGN_PARAGRAPH.CENTER, 6, CLAY)
    t = doc.add_table(rows=1 + len(STUDENTS), cols=3); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, (hd, wd) in enumerate((("Sr. No.", 0.8), ("Name of student", 3.4), ("PRN", 1.9))):
        c = t.rows[0].cells[j]; c.width = Inches(wd); shade(c, DARK); r = c.paragraphs[0].add_run(hd); set_font(r, 10, True, color=RGBColor(255, 255, 255))
    for i, (n, prn) in enumerate(STUDENTS, 1):
        for j, v in enumerate((str(i), n, prn)):
            c = t.rows[i].cells[j]; c.width = Inches((0.8, 3.4, 1.9)[j]); r = c.paragraphs[0].add_run(v); set_font(r, 11, j == 1)
            if i % 2 == 0: shade(c, TINT)
    P("", after=14)
    P("Under the guidance of", 10.5, WD_ALIGN_PARAGRAPH.CENTER, 2)
    P(f"**{GUIDE}**", 12, WD_ALIGN_PARAGRAPH.CENTER, 18)
    P(f"Department of {DEPARTMENT}", 10.5, WD_ALIGN_PARAGRAPH.CENTER, 6, STONE)
    P(f"**Academic Year {YEAR}**", 11, WD_ALIGN_PARAGRAPH.CENTER, 10)
    P(f"Source code: **{REPO}**", 10, WD_ALIGN_PARAGRAPH.CENTER, 12)
    P("All numbers in this report come from the files in `results/`, which `python run_all.py` regenerates from the data in `data/raw/`.", 9, WD_ALIGN_PARAGRAPH.CENTER, 0, STONE, True)


TOC_SOURCE = []


def front_matter(toc_pages):
    doc.add_page_break()
    p = doc.add_heading("Declaration", 1); border(p, ("bottom",), "0E7C66", 12, 6)
    P(f"We hereby declare that the project report entitled **\"{TITLE}: {SUBTITLE}\"** submitted for the course **{COURSE}** is our own work. The data pipeline, analysis, "
      "results and documentation have been prepared jointly by the students listed below. External sources, libraries and data providers are acknowledged in the References section. "
      "This work has not been submitted elsewhere for any other course or degree.")
    P("The data are public records published by the City of Chicago. Results describe those records; they are not a statement about any individual establishment.")
    t = doc.add_table(rows=1 + len(STUDENTS), cols=3); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, hd in enumerate(("Name of student", "PRN", "Signature")):
        r = t.rows[0].cells[j].paragraphs[0].add_run(hd); set_font(r, 10, True, color=RGBColor(255, 255, 255)); shade(t.rows[0].cells[j], DARK)
    for i, (n, prn) in enumerate(STUDENTS, 1):
        for j, v in enumerate((n, prn, "")):
            r = t.rows[i].cells[j].paragraphs[0].add_run(v); set_font(r, 10.5); t.rows[i].cells[j].paragraphs[0].paragraph_format.space_after = Pt(12)
    P("", after=6); P("Place: ____________________"); P("Date: _____________________")

    doc.add_page_break()
    p = doc.add_heading("Abstract", 1); border(p, ("bottom",), "0E7C66", 12, 6)
    P(f"This report presents an end-to-end data analytics project on restaurant and food-establishment inspections in Chicago. The City of Chicago publishes one record for every inspection. "
      f"The project integrates the {N_RAW:,} records of 2022 to 2025 into a PostgreSQL star schema with two fact tables, builds the same data as a distributed warehouse (Citus) and as a real-time warehouse "
      f"(Kafka, Spark Structured Streaming, ClickHouse, Grafana), measures the three architectures, analyses the warehouse with OLAP operations and ten business questions, and mines it with regression, "
      f"association rules (Apriori and FP-Growth) and decision trees.")
    P(f"Of the records, {N_FACT:,} are completed inspections. The yearly fail rate fell from {f22:.1f}% in 2022 to {f25:.1f}% in 2025. Complaint inspections fail most often "
      f"({q5.set_index('inspection_type').loc['Complaint', 'fail_rate']:.1f}%) and re-inspections least; after a failed inspection the next inspection of the same licensed establishment passes in {q8b.iloc[0]['next_is_pass_pct']:.0f}% of cases. "
      f"The batch warehouse loads the first {int(audit.loc[1, 'rows_loaded_fact']):,} facts in about ten seconds, adds the last month incrementally in under a second without changing earlier rows, passes 16 integrity checks after every load, and answers every analytical query in "
      f"{qt['median_ms'].min():.0f} to {qt['median_ms'].max():.0f} ms. The Citus cluster returned identical results but was not faster on one machine; the real-time pipeline, which replays historical data, delivered events to ClickHouse in {LAT / 1000:.1f} seconds on average.")
    P(f"Models are trained on the past and tested on 2025 using only facts known before the visit. The multiple linear regression explains {100 * multi['R2']:.0f}% of the variation in the number of violations "
      f"(mean absolute error {multi['MAE']:.2f} against {base['MAE']:.2f} for the training mean). The decision tree ranks failures with an AUC of {tree5['ROC-AUC']:.3f}. Failures are therefore only weakly predictable, "
      f"and the models are suited to ordering work, not to deciding the result of an inspection. The report recommends a batch warehouse at the centre, with a real-time layer only for live monitoring and a distributed layer only when the data outgrow one machine.")
    callout("Data note.", "The raw file is bundled as `data/raw/food_inspections_2022_2025.csv.gz` (downloaded from the City of Chicago Data Portal). The portal is updated over time; "
            "the bundled copy keeps every number in this report reproducible with `python run_all.py`.")
    P("**Keywords:** data warehouse, star schema, fact constellation, PostgreSQL, Citus, Kafka, Spark Structured Streaming, ClickHouse, OLAP, regression, association rules, Apriori, FP-Growth, decision tree, food safety.", 10.5)

    doc.add_page_break()
    p = doc.add_heading("Table of Contents", 1); border(p, ("bottom",), "0E7C66", 12, 6)
    width = Emu(doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin)
    for level, text in [(1, "Declaration"), (1, "Abstract")] + TOC_SOURCE:
        pg = toc_pages.get(text, "")
        par = doc.add_paragraph(); par.paragraph_format.space_after = Pt(1 if level == 2 else 3); par.paragraph_format.space_before = Pt(3 if level == 1 else 0)
        par.paragraph_format.left_indent = Inches(0 if level == 1 else 0.3)
        par.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = par.add_run(f"{text}\t{pg}"); set_font(r, 10.5 if level == 1 else 10, level == 1)


def md_table(bid, cols=None, rename=None):
    df = OLAP[bid]["df"].copy()
    if cols:
        df = df[cols]
    return df.rename(columns=rename or {})


# ----------------------------------------------------------------------------- content
def chapter1():
    state["chap"] = 1; state["tab"] = state["fig"] = 0
    h1("1 Introduction")
    h2("1.1 Background and motivation")
    P("Chicago inspects every place that sells or serves food: restaurants, grocery stores, bakeries, schools, day-care centres, long-term care homes and mobile vendors. "
      "An inspector visits, checks a list of numbered food-safety rules and records the result as Pass, Pass with Conditions or Fail, together with the violations found. "
      "A failed inspection is normally followed by a re-inspection. The city publishes these records as open data.")
    P("A health department that reads these records has practical questions. Is the failure rate changing? Which types of inspection, areas and kinds of establishment fail most often? "
      "Does a failed inspection lead to a clean follow-up? Could inspectors be sent first to the visits most likely to find a problem? Each question needs the same records to be defined once and queried many ways, "
      "which is what a data warehouse is for.")
    h2("1.2 Role of data warehousing and business intelligence")
    P("An operational (OLTP) system answers questions about one record, for example the result of one inspection. An analytical (OLAP) system answers questions about many records at once, "
      "for example the failure rate per quarter and facility group. The first touches a few rows; the second scans and aggregates all of them.")
    P("The project therefore keeps the analytical store apart from the source file. The raw file lands in a raw zone, a curation script types and cleans it, a staging schema holds the typed rows with a batch id and a reject reason, "
      "and a load procedure fills a star schema in PostgreSQL. OLAP queries, the dashboard and the models all read that one schema, so an inspection, a month or an establishment has a single definition everywhere. "
      "Because the brief also asks for a distributed and a real-time warehouse, the same data are loaded into Citus and streamed through Kafka, Spark and ClickHouse so that the three architectures can be compared by measurement.")
    h2("1.3 Requirement mapping")
    P("The table below maps each part of the project brief to the place where it is implemented and to the file that shows it ran.", keep=True)
    rows = pd.DataFrame([("A", "Dataset, curation, EDA", "notebooks/01, 02; etl/curation.py", "docs/data_quality_report.md"),
                         ("B", "Dimensional models", "sql/01, 05; etl/model_comparison.py", "results/model_comparison.csv"),
                         ("C", "Batch warehouse, ETL, incremental load", "etl/run_etl.py; sql/02 to 04", "results/load_audit.csv"),
                         ("D", "Distributed warehouse (Citus)", "etl/distributed_*.py; scripts/", "results/distributed_scaling.csv"),
                         ("E", "Real-time warehouse", "streaming/", "results/streaming_metrics.csv"),
                         ("F", "OLAP, dashboard, findings", "sql/07; dashboard/", "docs/olap_operations.md"),
                         ("G", "Regression", "notebooks/07_regression", "results/regression_metrics.csv"),
                         ("H", "Association rules", "notebooks/08_association_mining", "results/association_rules_selected.csv"),
                         ("I", "Decision tree", "notebooks/09_decision_tree", "results/decision_tree_metrics.csv"),
                         ("J", "Architecture evaluation", "docs/architecture_comparison.md", "section 6.6")], columns=["Part", "Topic", "Implementation", "Evidence"])
    table(rows, [0.5, 2.2, 2.5, 2.4], "Mapping of project parts to implementation and evidence", 9, ["l", "l", "l", "l"])
    h2("1.4 Organisation of the report")
    P("Chapter 2 states the problem, research questions and scope. Chapter 3 describes the dataset and the targets. Chapter 4 presents the architecture and the warehouse design. "
      "Chapter 5 explains every processing stage with its console output, tables and figures, and ends with how the project is run and monitored. Chapter 6 discusses the findings and answers the research questions. "
      "Chapter 7 maps the requirements to the work. Chapter 8 reproduces key source code, chapter 9 the presentation slides, and chapter 10 states limitations, conclusions and future work.")


def chapter2():
    state["chap"] = 2; state["tab"] = state["fig"] = 0
    h1("2 Problem Statement and Objectives")
    h2("2.1 Problem statement")
    P("The department holds a file of inspection records but no integrated store that answers questions about it quickly and consistently. Four difficulties stand in the way. "
      "The file mixes real inspections with visits that never took place (out of business, no entry). Violations are stored as one text field. "
      "Facility types are free text with more than two hundred spellings. And the records carry no cause of a failure, so any prediction has to rest on the history of the establishment and the circumstances of the visit.")
    h2("2.2 Research questions")
    for q in ["RQ1. How do inspection volume and the fail rate behave over time, and which types of inspection, facilities and places fail most often?",
              "RQ2. Does a failed inspection lead to a better next inspection?",
              "RQ3. How well can the number of violations and the failure of an inspection be predicted from facts known before the visit?",
              "RQ4. Which combinations of attributes occur together often enough to be reported as rules?",
              "RQ5. Which warehouse architecture (batch, distributed, real-time) suits this data, and what does each cost?"]:
        P(q, after=2)
    h2("2.3 Objectives")
    bullets(["**O1.** Download and document the official data, profile it and clean it with every decision logged.",
             "**O2.** Design a dimensional model (star, snowflake, fact constellation), build it and compare the designs by measurement.",
             "**O3.** Build a batch warehouse with an ETL, an initial and an incremental load, validation checks and indexes.",
             "**O4.** Build a distributed warehouse (Citus) and a real-time warehouse (Kafka, Spark, ClickHouse, Grafana) on the same data and measure them.",
             "**O5.** Demonstrate OLAP operations: roll-up, drill-down, slice, dice, pivot, CUBE and GROUPING SETS, and answer ten business questions.",
             "**O6.** Fit regression models, mine association rules with Apriori and FP-Growth, and train and interpret a decision tree.",
             "**O7.** Compare the three architectures and recommend one for a public-health department.",
             "**O8.** Deliver a dashboard, a report, slides and a repository that runs with one command."])
    h2("2.4 Scope, assumptions and constraints")
    bullets(["**Observation window:** inspections dated 1 January 2022 to 31 December 2025.",
             "**Population:** completed inspections (Pass, Pass with Conditions, Fail). Visits that did not take place are kept in staging but are not facts.",
             "**Prediction rule:** only information available before the inspection is used. History features come from strictly earlier inspections of the same licensed establishment.",
             "**Validation:** time-based, never random. Regression trains on 2022 to 2024 and tests on 2025; the tree trains on 2022 and 2023, selects settings on 2024 and is tested once on 2025.",
             f"**Machine:** every timing was measured on {PLATFORM}. Timings compare designs under equal conditions; they are not production capacity.",
             "**Scope limit:** the deliverable is a reproducible analytical pipeline, not a production scheduling system."])


def chapter3():
    state["chap"] = 3; state["tab"] = state["fig"] = 0
    h1("3 Dataset and Target Definition")
    h2("3.1 Source and file format")
    P(f"The data are the City of Chicago *Food Inspections* dataset (identifier 4ijn-s7e5), published by the Chicago Department of Public Health on the City of Chicago Data Portal and read through its Socrata API. "
      f"The project uses the {N_RAW:,} records dated 1 January 2022 to 31 December 2025. The file is bundled in compressed form so that the project runs offline; `scripts/fetch_data.py` downloads a new copy.")
    h2("3.2 Key fields")
    rows = pd.DataFrame([("inspection_id", "Source identifier of one inspection", "Degenerate dimension in the fact table"),
                         ("license_", "Licence number (0 or missing for 213 records)", "Facility key when present"),
                         ("dba_name, address, zip, latitude, longitude", "Establishment and location", "DimFacility, DimLocation"),
                         ("facility_type", "Free text, 217 distinct spellings", "Cleaned type and a derived facility group"),
                         ("risk", "Risk 1 (High), 2 (Medium), 3 (Low); 'All' occurs 38 times", "Risk category and risk group"),
                         ("inspection_type", "Canvass, Complaint, License, re-inspections and others", "DimInspectionType and a derived group"),
                         ("results", "Pass, Pass w/ Conditions, Fail, Out of Business, No Entry, Not Ready, Business Not Located", "DimResult; completed results only in the fact"),
                         ("violations", "Numbered rule texts separated by '|'", "Violation count, band and rule numbers"),
                         ("inspection_date", "Date; time of day is always 00:00:00", "DimDate")], columns=["Field", "Meaning", "Role in the analysis"])
    table(rows, [2.0, 3.2, 2.4], "Key fields used in the analysis", 9, ["l", "l", "l"])
    h2("3.3 Target definitions")
    P(f"**Violation count** is the number of numbered items in the violations text. It is defined for 61,185 completed inspections. A pass without text has zero violations. "
      f"A failed or conditional inspection without text ({cnt('Fail / Pass w/ Conditions')} cases) has an unknown count, stored as NULL, because such a result requires at least one cited violation.")
    P("**Failed inspection** equals 1 when the result is Fail and 0 for Pass and Pass with Conditions. **High violation** means six or more violations, which is just above the 75th percentile (5).")
    h2("3.4 Train, validation and test split")
    P("All models respect time. The regression trains on the 2022 to 2024 inspections (45,266 with a known count) and is tested on 2025 (15,919). The decision tree trains on 2022 and 2023 (29,693 inspections), "
      "chooses its settings and probability cut-off on 2024 (15,992) and is evaluated once on 2025 (16,052). A random split would let the model see later inspections of an establishment when predicting an earlier one.")
    h2("3.5 Data quality assessment")
    P(f"The curation script writes a log row for every problem it checks, with the number of rows affected and the treatment. The table below shows the decisions that change what the analysis means; the complete log is `docs/data_quality_report.md`. "
      f"Row counts reconcile: {N_RAW:,} raw records, 29 removed as repeated reports, 73,601 curated records, of which {N_FACT:,} are completed inspections.", keep=True)
    pick = dq[dq["Problem"].str.contains("Logical duplicate|Same licence|Invalid risk|Missing risk|Missing facility|Missing or zero|Missing coordinates|Fail / Pass|Pass with no|Extreme|not a completed|Time of day", regex=True)].copy()
    pick["Problem"] = pick["Problem"].str.replace(" (same licence, date, type, result and violation text, different inspection_id)", "", regex=False).str.replace(" (Out of Business, No Entry, Not Ready, Business Not Located)", "", regex=False)
    pick["Rows"] = pick["Count"].map(lambda v: f"{int(v):,}")
    table(pick[["Problem", "Rows", "Treatment"]], [3.7, 0.8, 2.6], "Cleaning log (selected rows)", 8.5, ["l", "r", "l"])


def chapter4():
    state["chap"] = 4; state["tab"] = state["fig"] = 0
    h1("4 System Architecture and Warehouse Design")
    h2("4.1 Layered architecture")
    P("The batch system has five layers. The raw zone holds the untouched file. The curation layer types and cleans it and records every decision. The staging schema keeps the typed rows of each load batch with a reject reason. "
      "The warehouse schema `dw` holds the dimensional model. The analysis layer (OLAP, the analytical mart and the models) and the delivery layer (dashboard, report) read the warehouse. "
      "The distributed warehouse (Citus) and the real-time warehouse (Kafka, Spark, ClickHouse) are separate architectures fed with the same data. Each stage is a script or notebook that can be rerun on its own, and `run_all.py` runs the batch stages in order.", keep=True)
    figure(IMG / "architecture.png", "End-to-end architecture of the batch system and its two companions", 6.5)
    h2("4.2 Star schema and fact constellation")
    P("The grain of the main fact table is one completed inspection on one date. It references five dimensions: date, facility, inspection type, result and location. "
      "A second fact table has the grain facility by year and shares the facility dimension. Two fact tables sharing dimensions make a fact constellation. "
      "Every dimension contains an Unknown member with key 0, so a lookup that finds nothing never drops a fact row.", keep=True)
    figure(IMG / "fact_constellation.png", "Fact constellation: FactInspection and FactFacilityAnnualInspectionPerformance share DimFacility", 5.8)
    screen("psql_tables", "the tables of the warehouse schema dw in PostgreSQL", 6.3)
    screen("psql_fact", "rows of the fact table: only keys and measures", 6.3)
    inc2 = inc.set_index("object")["after_incremental"]
    tc = pd.DataFrame([("fact_inspection", "inspection_id, date_key, facility_key, ... (grain: one inspection)", f"{int(inc2['fact_inspection']):,}"),
                       ("fact_facility_annual_inspection_performance", "facility_key, reporting_year (grain: facility x year)", f"{int(inc2['fact_facility_annual']):,}"),
                       ("dim_facility", "facility_key, facility_nk, type, group, risk (Type 1)", f"{int(inc2['dim_facility']):,}"),
                       ("dim_location", "location_key, zip, city, coordinate bands, area group", f"{int(inc2['dim_location']):,}"),
                       ("dim_inspection_type", "inspection_type_key, type, type group", f"{int(inc2['dim_inspection_type']):,}"),
                       ("dim_result", "result_key, result, result group, failure flag", f"{int(inc2['dim_result']):,}"),
                       ("dim_date", "date_key, year, quarter, month, season, is_weekend", "1,826")], columns=["Table", "Grain and key columns", "Rows"])
    table(tc, [2.9, 3.4, 0.8], "Tables of the dw schema and their row counts after the incremental load", 9, ["l", "l", "r"])
    h2("4.3 ETL pipeline")
    P("The ETL has four steps. Curation (`etl/curation.py`) types the columns, removes repeated reports, maps invalid codes to Unknown and derives the analysis attributes. "
      "A batch is staged with `COPY` into `staging.inspection_stg` under a batch id. The PL/pgSQL procedure `dw.load_batch` then applies data-quality rules (missing id or date, date outside the date dimension, inspection id already in the fact), "
      "inserts new dimension members, updates changed facility attributes in place (a Type 1 dimension: the latest value wins), loads facts with lookups on natural keys and rebuilds the annual fact for the years the batch touched. "
      "The procedure runs in one transaction and ends by writing an audit row.")
    h2("4.4 Why a fact constellation")
    P("Three designs were built from the same keys and measured on the same machine. The snowflake normalises each dimension along its hierarchy and needs three times the joins of the star for the same question. "
      "The constellation adds the annual fact to the star. The next table gives the measured values.", keep=True)
    cmp_ = mc.reset_index(); cmp_.columns = ["Criterion", "Star", "Snowflake", "Fact constellation"]
    for c in ("Star", "Snowflake", "Fact constellation"):
        cmp_[c] = cmp_[c].map(lambda v: f"{v:g}")
    table(cmp_, [3.6, 1.0, 1.1, 1.4], "Measured comparison of the three designs (median times)", 9, ["l", "r", "r", "r"])
    screen("model_comparison", "etl/model_comparison.py comparing star, snowflake and fact constellation", 6.3)
    qa_s, qa_f = mcq.iloc[0]["star_ms"], mcq.iloc[0]["snowflake_ms"]; fy = mc.loc["Facility x year question: median time (ms)"]
    st_ = rd("model_storage"); saved = (st_.iloc[0]["dimension_bytes"] - st_.iloc[1]["dimension_bytes"]) / 1048576
    P(f"The snowflake is {qa_f / qa_s:.1f} times as slow on the main question ({qa_f:.0f} ms against {qa_s:.0f} ms) and needs 9 joins instead of 3, and it saves only {saved:.1f} MB of dimension storage. "
      f"The second fact answers the facility-by-year question in {fy['fact_constellation']:.1f} ms instead of {fy['star']:.1f} ms, so the constellation was selected.")
    h2("4.5 Integrity checks")
    P("After every load the warehouse is checked with five queries (`sql/04_validation.sql`): fact rows whose key is missing in a dimension, duplicate inspection ids, completed rows that did not reach the fact table, the total of violations in staging and in the fact table, and the agreement of the two fact tables. Every check must return zero.", keep=True)
    v = val[val["stage"] == "after incremental load"][["check_name", "value"]].copy(); v["value"] = v["value"].map(lambda x: f"{int(x):,}"); v["Expected"] = "0"
    table(v.rename(columns={"check_name": "Check", "value": "Observed"}), [4.6, 1.0, 0.9], "Warehouse integrity results after the incremental load", 8.5, ["l", "r", "r"])
    screen("psql_checks", "the five checks run in psql after the incremental load", 6.3)


def chapter5():
    state["chap"] = 5; state["tab"] = state["fig"] = 0
    h1("5 Methodology and Implementation")
    P("This chapter follows the execution order of the project. Each stage states what it does and why, shows screenshots of the real output captured when the scripts ran, "
      "reproduces the main tables and figures, and ends with an interpretation. The whole batch part is started with one command:", keep=True)
    screen("run_all", "python run_all.py starting the pipeline (first steps)", 6.3)
    h2("5.1 Stage 1: data acquisition and curation")
    P("`scripts/fetch_data.py` downloads the records (or `run_all.py` unpacks the bundled file). Notebook `01_data_curation` profiles the raw file, applies the rules in `etl/curation.py` and saves the curated data. "
      "The rules are ordered: text is trimmed, dates and coordinates are typed, repeated reports are removed, invalid codes are mapped to Unknown, the facility identity is built from the licence (or name and address when the licence is missing), "
      "and the attributes used later are derived: violation count and band, result group, risk group, facility group, inspection type group, season and the area of the city (the quadrant of the Chicago street grid, not an official community area). "
      "Section 3.5 lists the decisions. Row counts reconcile before and after curation.")
    figure(IMG / "nb_02_eda_3.png", "Exploratory analysis (notebook 02): inspections per year, per quarter and per month", 6.5)
    figure(IMG / "nb_02_eda_5.png", "Exploratory analysis: inspection volume versus fail rate by facility group", 6.5)
    h2("5.2 Stage 2: batch warehouse, ETL and validation")
    P("`etl/run_etl.py all` creates the schema, loads January 2022 to November 2025 as batch 1 (the initial load), runs the checks, loads December 2025 as batch 2 (the incremental load) and runs the checks again.", keep=True)
    screen("etl", "etl/run_etl.py: initial load, incremental load and checks", 6.5)
    a = audit.reset_index()[["batch_id", "batch_label", "rows_staged", "rows_rejected", "rows_not_completed", "rows_loaded_fact", "new_facilities"]]
    table(a.rename(columns={"batch_id": "Batch", "batch_label": "Label", "rows_staged": "Staged", "rows_rejected": "Rejected", "rows_not_completed": "Not completed", "rows_loaded_fact": "Facts loaded", "new_facilities": "New facilities"}),
          [0.5, 2.6, 0.8, 0.8, 0.9, 0.8, 0.8], "Load audit of the two batches", 8.5, ["l", "l", "r", "r", "r", "r", "r"])
    P(f"Batch 1 loads {int(audit.loc[1, 'rows_loaded_fact']):,} facts. Batch 2 adds {int(audit.loc[2, 'rows_loaded_fact']):,} facts and {int(audit.loc[2, 'new_facilities'])} new facilities in about a second, "
      "so the warehouse grows month by month without being rebuilt. Visits that did not take place stay in staging and are counted in the audit as not completed.")
    screen("psql_load_audit", "the load audit table in PostgreSQL", 6.5)
    h3("Indexing and query timing")
    table(idx[["query", "stage", "median_ms"]].rename(columns={"query": "Query", "stage": "Index", "median_ms": "Median (ms)"}), [3.8, 1.2, 1.0], "Effect of indexes on selective queries", 9, ["l", "l", "r"])
    screen("queries", "etl/run_queries.py: the business questions and the effect of the indexes", 6.5)
    table(qt[["query", "description", "result_rows", "median_ms"]].assign(description=lambda d: d["description"].str.replace(r" \(rule-level.*", "", regex=True)).rename(columns={"query": "ID", "description": "Business question", "result_rows": "Rows", "median_ms": "Median (ms)"}),
          [0.6, 4.4, 0.7, 1.0], "The analytical queries Q1 to Q8: result rows and median time", 8.5, ["l", "l", "r", "r"])
    wo, wi = idx[idx["stage"] == "without index"]["median_ms"], idx[idx["stage"] == "with index"]["median_ms"]; c2m = cs[cs["rows"] == 2000000]["centralized_ms"]
    P(f"Indexes created after the bulk load take selective queries from {wo.min():.1f} to {wo.max():.1f} ms down to {wi.min():.1f} to {wi.max():.1f} ms. The business queries run in {qt['median_ms'].min():.0f} to {qt['median_ms'].max():.0f} ms. "
      f"In the scale test of Part D, two million rows (32 times the real data) still answered in {c2m.min():.0f} to {c2m.max():.0f} ms on one node.")
    h2("5.3 Stage 3: OLAP analysis")
    P("`etl/run_olap.py` runs the OLAP operations written in `sql/07_olap_queries.sql` and writes `docs/olap_operations.md` with the question, the SQL, the output and an interpretation for each. "
      "Roll-up uses `GROUP BY ROLLUP`, CUBE and GROUPING SETS use the SQL standard constructs, and pivot uses conditional counts.")
    for bid, cols in (("R1", None), ("D1", None), ("P1", None)):
        o = OLAP[bid]
        P(f"**{o['title']}.** {o['question']}", keep=True)
        d = o["df"].copy()
        table(d, [1] * len(d.columns), f"{o['title']}: output", 8.5, ["l"] + ["r"] * (len(d.columns) - 1))
        P(o["interp"].replace("`", ""))
    screen("psql_star_query", "a star-schema query: fail rate by facility group", 6.0)
    screen("psql_rollup", "roll-up from quarters to years with GROUP BY ROLLUP", 6.0)
    screen("psql_slice_dice", "dice: 2025 and high-risk facilities, by inspection type", 6.0)
    screen("psql_pivot", "pivot: one column per result", 6.0)
    h2("5.4 Stage 4: exploratory analysis and ten findings")
    P("Notebook `02_eda` analyses the curated data numerically, by category, over time and by place. The business queries and the ten findings in `docs/ten_findings.md` use the warehouse. The findings are:", keep=True)
    for n, t in FINDINGS:
        P(f"{n}. {t}", after=2)
    figure(IMG / "finding_03.png", "Fail rate by year (finding 3)", 5.3)
    figure(IMG / "finding_05.png", "Fail rate by type of inspection (finding 5)", 5.3)
    figure(IMG / "finding_08.png", "What happens at the inspection after a failed one (finding 8)", 5.3)
    h2("5.5 Stage 5: regression")
    P("Notebook `07_regression` predicts the number of violations of an inspection. Inputs are facility type, risk category, inspection type, month, weekday, ZIP code, the result of the previous inspection and its violation count. "
      "Categorical inputs are one-hot encoded (rare categories are grouped), which gives 102 columns. The model trains on 2022 to 2024 and is tested on 2025.")
    m = reg.reset_index()[["Model", "Rows", "MAE", "RMSE", "R2"]]; m[["MAE", "RMSE", "R2"]] = m[["MAE", "RMSE", "R2"]].round(3)
    table(m, [3.6, 0.7, 0.7, 0.7, 0.7], "Regression results on the 2025 test year (violation count)", 9, ["l", "r", "r", "r", "r"])
    P(f"**Simple regression:** violations = 2.737 + 0.209 x previous violations, with R squared {simple['R2']:.3f}. **Multiple regression** lowers the mean absolute error from {base['MAE']:.2f} to {multi['MAE']:.2f} violations and reaches R squared {multi['R2']:.3f} on 2025 "
      "against 0.248 on the training years, so most of the variation is not explained by what is known before the visit. The largest coefficients belong to ZIP codes 60617, 60633, 60620, 60636 and 60628.")
    P("**Diagnostics** (from the notebook): only 5 of 102 columns have a variance inflation factor above 5, so collinearity is not a problem. The Breusch-Pagan test rejects constant error variance. "
      "1.9% of 2025 inspections have more than 14 violations and cause 25% of the squared error. The linear model predicts a negative count 304 times out of 15,919, which a Poisson regression would avoid; it is the natural next step.")
    screen("jupyter_07", "notebook 07 (regression) open in JupyterLab", 6.5)
    screen("psql_mart", "the analytical mart: every inspection carries the result of the previous one", 6.3)
    figure(IMG / "nb_07_regression_2.png", "Multiple regression on 2025: actual versus predicted, residuals versus predicted and the residual distribution", 6.5)
    cf = coef.copy(); cf["feature"] = cf["feature"].str.replace("cat__", "", regex=False); cf["coefficient"] = cf["coefficient"].round(3)
    table(cf.head(8).rename(columns={"feature": "Feature", "coefficient": "Coefficient"}), [4.0, 1.0], "Largest coefficients of the multiple regression", 9, ["l", "r"])
    h2("5.6 Stage 6: association rule mining")
    P("Notebook `08_association_mining` treats each completed inspection as a transaction of seven items: facility type (the eight most frequent types, the rest as Other), risk group, inspection type group, result group, violation band, area and season. "
      "The violation count is discretised into the bands none, 1 to 2, 3 to 5, 6 to 9 and 10 or more. There are 61,185 transactions and 35 distinct items.")
    P("Apriori builds candidate sets level by level and prunes those with an infrequent subset. FP-Growth compresses the data into a prefix tree (the FP-tree) and reads the patterns from it without generating candidates. "
      "Both return exactly the same 1,198 frequent itemsets at a minimum support of 2%. With minimum confidence 30% and lift of at least 1.3, rules that are always true or redundant were removed and 14 remain.")
    r = rules[["Rule", "support", "confidence", "lift"]].copy(); r["support"] = r["support"].map(lambda v: f"{v:.1%}"); r["confidence"] = r["confidence"].map(lambda v: f"{v:.0%}"); r["lift"] = r["lift"].map(lambda v: f"{v:.2f}")
    r["Rule"] = r["Rule"].str.replace("  =>  ", " => ", regex=False)
    table(r.rename(columns={"support": "Support", "confidence": "Confidence", "lift": "Lift"}), [4.7, 0.8, 0.9, 0.6], "Selected association rules", 8.5, ["l", "r", "r", "r"])
    figure(IMG / "nb_08_association_mining_2.png", "All rules with support of at least 2% and confidence of at least 50% (notebook 08)", 5.2)
    P("Low-risk inspections are mostly grocery stores (lift 6.5). An inspection with ten or more violations ends in a fail in 69% of cases, three times the base rate. Licence inspections of restaurants that pass are often completely clean, and clean inspections of high-risk restaurants are often re-inspections, which suggests that follow-ups work. "
      "Lift measures association, not cause; a fail is partly defined by its violations.")
    h2("5.7 Stage 7: decision tree")
    P("Notebook `09_decision_tree` predicts whether an inspection fails. A tree asks at every node the yes/no question that makes the two resulting groups purer; purity is measured by entropy (ID3), gain ratio (C4.5) or the Gini index (CART). "
      "Scikit-learn builds CART trees. Settings were tuned on the 2024 validation year: maximum depth, minimum samples to split, minimum samples per leaf and cost-complexity pruning. The best validation AUC is about 0.636 on a plateau of nearly equal settings; "
      "the simplest of the best was chosen (maximum depth 8, at least 200 inspections in every leaf). A fully grown tree reaches a training AUC of 0.995 but a validation AUC of 0.525, which shows why the limits are needed.")
    figure(IMG / "nb_09_decision_tree_1.png", "Tuning on the 2024 validation year: training versus validation AUC for each setting", 6.6)
    d = dtm.reset_index()[["Model", "threshold", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]]
    d[["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]] = d[["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]].astype(float).round(3)
    table(d, [3.1, 0.7, 0.8, 0.8, 0.7, 0.6, 0.7], "Decision tree on the 2025 test year", 9, ["l", "r", "r", "r", "r", "r", "r"])
    P(f"With the default cut-off of 0.5 the tree flags almost nothing (recall {tree5['Recall']:.1%}), because only 21% of inspections fail and the predicted probability rarely exceeds one half. The cut-off chosen on 2024 ({treeT['threshold']}) catches {treeT['Recall']:.0%} of the 2025 failures "
      f"with a precision of {treeT['Precision']:.0%}; accuracy falls to {treeT['Accuracy']:.0%}, below the 79% of the rule that always predicts a pass. Which cut-off is right depends on what a missed failure costs. The AUC of {tree5['ROC-AUC']:.3f} does not depend on the cut-off and shows that the ranking is weak.")
    figure(IMG / "nb_09_decision_tree_2.png", "Confusion matrices and ROC curve on the 2025 test year", 6.6)
    i2 = imp.copy(); i2.columns = ["Feature", "Importance"]; i2["Importance"] = i2["Importance"].map(lambda v: f"{100 * v:.1f}%")
    table(i2.head(8), [3.4, 1.0], "Most important inputs of the tree", 9, ["l", "r"])
    pt = paths.copy(); pt.columns = ["Path", "Conditions", "n train", "Fail % train", "n 2025", "Fail % 2025"]
    table(pt[["Path", "n train", "Fail % train", "n 2025", "Fail % 2025"]], [1.8, 0.9, 1.1, 0.9, 1.1], "Three leaves of the tree", 9, ["l", "r", "r", "r", "r"])
    P("The past is the best clue: a previous failed inspection, a complaint inspection, the number of earlier violations and the days since the last visit. Highest fail rate: a complaint inspection, no previous failure, more than six earlier violations and a long gap since the last visit (55 to 58%). "
      "Lowest: a quick re-inspection after a failure (4 to 5%), which agrees with the finding that follow-ups work. The tree is weak overall and is a ranking aid, not a decision tool.")
    figure(IMG / "nb_09_decision_tree_4.png", "The trained decision tree (first three levels)", 6.6)
    h2("5.8 Stage 8: distributed warehouse (Citus)")
    P("The same warehouse was loaded into a Citus 14.3 cluster on PostgreSQL 18 (built from source; a coordinator and two workers on one machine, 32 shards). The fact table is distributed by a key; the five dimensions are reference tables copied to every worker, so every join is local. "
      "The key was chosen by simulating the shard assignment with PostgreSQL's integer hash.")
    dk = dkey[["candidate_key", "distinct_values", "largest_single_value_share_%", "shard_skew_max_over_mean"]].rename(columns={"candidate_key": "Candidate key", "distinct_values": "Distinct values", "largest_single_value_share_%": "Largest share %", "shard_skew_max_over_mean": "Shard skew (max/mean)"})
    table(dk, [1.6, 1.3, 1.4, 1.6], "Distribution-key analysis (32 shards, two workers)", 9, ["l", "r", "r", "r"])
    P(f"FacilityKey has the most distinct values and the most even shards, so it was chosen. In {tot} test cases (five queries at 61,737, 100,000, 500,000, 1,000,000 and 2,000,000 rows) the distributed results were identical to the single-node results, "
      f"but Citus was clearly faster in {fast} and clearly slower in {slow}. The workers shared the same CPUs, so there was coordination work and no additional hardware. Row counts above 61,737 are a synthetic scale-up by resampling the real facts, used only to time queries.")
    d2 = ds[ds["rows"] == 2000000][["query", "centralized_ms", "distributed_ms", "distributed_over_centralized"]]
    table(d2.rename(columns={"query": "Query (2,000,000 rows)", "centralized_ms": "One node (ms)", "distributed_ms": "Citus (ms)", "distributed_over_centralized": "Ratio"}), [3.0, 1.0, 1.0, 0.7], "Citus against one PostgreSQL node at 2,000,000 rows", 9, ["l", "r", "r", "r"])
    figure(IMG / "citus_vs_centralized.png", "Ratio of Citus time to single-node time (below 1.0 means Citus is faster)", 6.0)
    screen("citus_cluster", "the Citus cluster: one coordinator, two workers, distributed and reference tables", 6.5)
    screen("citus_shards", "the 32 shards are split evenly between the two workers", 6.0)
    h2("5.9 Stage 9: real-time warehouse")
    P("A producer replays historical inspections in date order into the Kafka topic `food_inspections`, with the key set to the inspection id. A Spark Structured Streaming job validates every JSON event with seven rules, derives measures and runs four streaming queries: valid events, rejected events (a dead-letter table with the reason), "
      "10-second windows and daily event-time windows with a one-day watermark. ClickHouse stores the results (MergeTree for events, ReplacingMergeTree for the updated windows) and Grafana refreshes every five seconds. "
      "The official data is a historical file, so this is a **replay simulation**, and every event says so (`source_mode = REPLAY_SIMULATION`).")
    s2 = pd.DataFrame([("Events replayed and stored", f"{int(sm['valid events stored']):,} (each stored once)"), ("Injected malformed events rejected", f"{int(sm['rejected test events'])} of {int(sm['rejected test events'])}"),
                       ("Throughput producer to ClickHouse", f"{int(sm['sustained throughput (events/s, producer to ClickHouse)'])} events per second"),
                       ("Delay emit to ClickHouse (average / 95th percentile)", f"{LAT:.0f} ms / {P95:.0f} ms"), ("ClickHouse dashboard queries", f"{CHQ.min():.1f} to {CHQ.max():.1f} ms"),
                       ("Memory of Kafka, ClickHouse, Spark, Grafana", f"{int(sm['memory (RSS, MB): Kafka broker'])}, {int(sm['memory (RSS, MB): ClickHouse server'])}, {int(sm['memory (RSS, MB): Spark streaming job (python + JVM)'])}, {int(sm['memory (RSS, MB): Grafana'])} MB")],
                      columns=["Measure", "Value"])
    table(s2, [3.8, 3.0], "Real-time measurements from the replay", 9, ["l", "l"])
    screen("stream_producer", "the producer replaying inspections into Kafka", 6.5)
    screen("stream_clickhouse", "the events stored in ClickHouse and the rejected test events", 6.0)
    if (SHOTS / "grafana_realtime.png").exists():
        screen("grafana_realtime", "Grafana real-time dashboard during the replay", 6.4)
    else:
        figure(IMG / "grafana_realtime_dashboard.png", "Grafana real-time dashboard during the replay", 6.2)
    h2("5.10 Stage 10: dashboard")
    P("`dashboard/build_dashboard.py` builds a self-contained HTML dashboard with Plotly directly from the warehouse; it opens with a double-click and needs no server. A side menu leads to six pages: "
      "the four sections required by the brief (overview, facilities and risk, locations, inspections and violations), a data-mining page with the results of the three models, and a page that summarises the three warehouses. "
      "Every chart has a title and one line that says what it shows.")
    for page, label in (("overview", "Overview page: key figures, inspections and fail rate by year, result mix"), ("facility", "Facilities and risk page"),
                        ("geo", "Locations page: areas, ZIP codes and the map"), ("insp", "Inspections and violations page: types, monthly trend and heat maps"),
                        ("mining", "Data-mining page: regression, association rules and decision tree"), ("dw", "Warehouses page: batch, distributed and real-time")):
        screen(f"dashboard_{page}", "dashboard, " + label, 6.3)
    stage11()


def stage11():
    h2("5.11 Stage 11: running the project and where each part is shown")
    P(f"All parts were rebuilt from the raw file on {PLATFORM}. Because Windows has no PostgreSQL or Docker on this machine, every server runs inside WSL 2 (the Ubuntu disk lives on drive E:). "
      "Citus has no package for Ubuntu 26.04 and was compiled from source for PostgreSQL 18. One script, `scripts/run_everything_wsl.sh`, copies the project to the Linux disk and runs it; "
      "`Start_Project.cmd` starts everything with a double-click after a reboot.", keep=True)
    runs = pd.DataFrame([("install", "once: Java, Citus, Python packages, Kafka, ClickHouse, Grafana (checksums verified)", "~15 min"),
                         ("full", "rebuild everything from the raw data: run_all.py, Citus benchmark, streaming replay", "~20 min"),
                         ("start", "after a reboot: start PostgreSQL, Citus, Kafka, Spark, ClickHouse, Grafana and JupyterLab, and replay the stream", "~3 min"),
                         ("stop", "stop the streaming services", "seconds")], columns=["Mode", "What it does", "Time"])
    table(runs, [0.8, 5.0, 0.9], "Modes of scripts/run_everything_wsl.sh", 9, ["l", "l", "r"])
    P("Each part is demonstrated with the simplest tool that shows it: SQL queries in pgAdmin for the warehouses, the executed notebooks for cleaning and mining, "
      "the HTML dashboard for Part F and Grafana only for the real-time warehouse. `README.md` (and its web version `README.html`) explains every part in plain language with the commands and their real output.", keep=True)
    where = pd.DataFrame([("A", "Curation and EDA", "notebooks 01 and 02 (JupyterLab)"), ("B", "Dimensional models", "pgAdmin: schemas dw and snow; results/model_comparison.csv"),
                          ("C", "Batch warehouse", "pgAdmin: staging.load_audit, sql/04_validation.sql"), ("D", "Distributed (Citus)", "pgAdmin on port 5440: pg_dist_node, citus_tables, citus_shards"),
                          ("E", "Real-time", "Grafana real-time dashboard; ClickHouse queries"), ("F", "OLAP and dashboard", "pgAdmin: sql/07_olap_queries.sql; dashboard/food_safety_dashboard.html"),
                          ("G, H, I", "Regression, rules, tree", "notebooks 07, 08 and 09 (JupyterLab)"), ("J", "Architecture evaluation", "docs/architecture_comparison.md")],
                         columns=["Part", "Topic", "Where it is shown"])
    table(where, [0.7, 1.8, 4.3], "Where each part of the project is shown", 9, ["l", "l", "l"])


def chapter6():
    state["chap"] = 6; state["tab"] = state["fig"] = 0
    h1("6 Results and Discussion")
    h2("6.1 Key findings")
    for n, t in FINDINGS:
        P(f"{n}. {t}", after=3)
    h2("6.2 Answers to the research questions")
    ans = pd.DataFrame([("RQ1", f"Volume grew 12% in four years without a stable seasonal peak. The fail rate fell from {f22:.1f}% to {f25:.1f}%. Complaint inspections fail most ({q5.set_index('inspection_type').loc['Complaint', 'fail_rate']:.1f}%), re-inspections least. The risk category barely changes the fail rate."),
                        ("RQ2", f"Yes. After a failed inspection the next inspection passes in {q8b.iloc[0]['next_is_pass_pct']:.0f}% of cases, on average {q8b.iloc[0]['avg_days_to_next']:.0f} days later."),
                        ("RQ3", f"Weakly. R squared {multi['R2']:.2f} for the number of violations and AUC {tree5['ROC-AUC']:.2f} for failure."),
                        ("RQ4", "Fourteen rules after filtering, led by low risk implying grocery store (lift 6.5) and ten or more violations implying a fail (lift 3.0). Apriori and FP-Growth agree on all 1,198 itemsets."),
                        ("RQ5", "A batch warehouse as the system of record; a real-time layer only for live monitoring; a distributed layer only when one machine is not enough (section 6.6).")], columns=["Question", "Answer"])
    table(ans, [0.8, 6.0], "Research questions and answers", 9.5, ["l", "l"])
    h2("6.3 Model selection")
    P(f"For the number of violations the multiple linear regression is the reference model (MAE {multi['MAE']:.2f}). For failure the decision tree is used because it can be read and explained to an inspector; its AUC of {tree5['ROC-AUC']:.3f} "
      "is modest, and it is reported together with the baseline that always predicts a pass so that accuracy is not mistaken for skill.")
    h2("6.4 Business interpretation")
    for line in (ROOT / "docs" / "domain_recommendations.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"^\d+\. ", line):
            P(re.sub(r"\(finding[^)]*\)", "", line.replace("`", "")).strip(), after=3)
    h2("6.5 Threats to validity")
    bullets(["**Data window.** History starts in January 2022, so the previous-inspection features are missing for the first inspection of an establishment in the window; 2025 also behaves differently from 2022 to 2024.",
             "**Missing causes.** Staff training, equipment and the size of the kitchen are not in the data; they probably explain much of the variation the models cannot.",
             "**Selection.** Which establishments are inspected, and when, is decided by the department. Complaint inspections are triggered by a problem, so their higher fail rate partly reflects that.",
             "**Facility attributes** are the latest values (Type 1), so older inspections show a facility's current type and risk.",
             "**Areas** are quadrants of the street grid, not official community areas.",
             "**Synthetic scale-up.** Row counts above 61,737 in the Citus experiment are resampled facts used only to time queries."])
    h2("6.6 Architecture comparison and recommendation")
    P("The three architectures were measured on the same data and the same machine. The table summarises the comparison; `docs/architecture_comparison.md` has the full version with the evidence.", keep=True)
    one_month = lt[lt["step"].str.startswith("[incremental]")]["seconds"].sum()
    arch = pd.DataFrame([("Data arrival", f"periodic loads; one month in about {one_month:.1f} s", "bulk load through a coordinator", "continuous events (a replay here)"),
                         ("Processing", "SQL procedure in one process", "32 shard tasks merged by the coordinator", "Spark micro-batches every 2 seconds"),
                         ("Historical analytics", f"all queries {qt['median_ms'].min():.0f} to {qt['median_ms'].max():.0f} ms", "same results; faster only on heavy queries", "operational window only"),
                         ("Live monitoring", "none until the next load", "none", f"{LAT / 1000:.1f} s delay; queries {CHQ.min():.0f} to {CHQ.max():.0f} ms"),
                         ("Complexity", "one database", "coordinator, workers, distribution keys", "four services, about 2.5 GB"),
                         ("If something fails", "a load runs in one transaction: all or nothing", "a lost worker makes its shards unavailable", "Kafka keeps the events, so the job can resume")],
                        columns=["Parameter", "Batch (PostgreSQL)", "Distributed (Citus)", "Real-time"])
    table(arch, [1.4, 2.2, 1.8, 1.8], "Comparison of the three architectures", 8.5, ["l", "l", "l", "l"])
    callout("Recommendation.", "Use a batch warehouse as the system of record. Chicago adds about 16,000 inspections a year; one node answers every analytical question in milliseconds. "
            "Add the real-time layer only if inspections are recorded digitally as they happen and live monitoring is needed. Add a distributed layer only when the data outgrow one machine on separate hardware.", "E6EEF9")


def chapter7():
    state["chap"] = 7; state["tab"] = state["fig"] = 0
    h1("7 Requirement Achievement")
    P("This chapter lists the parts of the project brief, what was delivered for each and where the evidence is. Where a part differs from what the brief names, it says so.")
    rows = pd.DataFrame([("A. Dataset and curation", "Official data, documented source, profiling, logged cleaning decisions, derived attributes, exploratory analysis", "Done", "data_quality_report.md"),
                         ("B. Dimensional modelling", "Star, snowflake and fact constellation built and measured; constellation selected", "Done", "model_comparison.csv"),
                         ("C. Batch warehouse", "Staging, ETL, initial and incremental load, surrogate keys, five integrity checks, indexing, query timing", "Done", "load_audit.csv, validation_results.csv"),
                         ("D. Distributed warehouse", "Citus cluster, distribution-key analysis, 25 timed comparisons", "Done; not faster on one machine", "distributed_scaling.csv"),
                         ("E. Real-time warehouse", "Kafka, Spark, ClickHouse, Grafana, validation and dead-letter handling", "Done; replay simulation", "streaming_metrics.csv"),
                         ("F. OLAP and dashboard", "Roll-up, drill-down, slice, dice, pivot, CUBE, GROUPING SETS; ten findings; dashboard", "Done; HTML dashboard instead of Power BI", "olap_operations.md"),
                         ("G. Regression", "Simple and multiple regression with diagnostics", "Done", "regression_metrics.csv"),
                         ("H. Association rules", "Apriori and FP-Growth, rule selection, interpretation", "Done", "association_rules_selected.csv"),
                         ("I. Decision tree", "CART, tuning on a validation year, cut-off, paths, importance", "Done", "decision_tree_metrics.csv"),
                         ("J. Architecture evaluation", "Three architectures compared with measured values and a recommendation", "Done", "architecture_comparison.md")], columns=["Part", "What was delivered", "Status", "Evidence"])
    table(rows, [1.4, 2.9, 1.6, 1.5], "Requirement achievement matrix", 8.5, ["l", "l", "l", "l"])
    P("The three mining parts use one analytical mart generated from the warehouse, not from the raw file, and one time-based split. The conclusion that failures are only weakly predictable is a finding, not an omission.")


def chapter8():
    state["chap"] = 8
    h1("8 Code Appendix")
    P(f"The complete source code, notebooks, data, results and documentation are published at **{REPO}**. Clone it with `git clone {REPO}.git`; "
      "`README.md` explains how to run every part.")
    P("The files below are reproduced verbatim from the repository. The curation rules (`etl/curation.py`), the remaining SQL files, the notebooks (curation, EDA, regression, association rules, decision tree) and the Citus and streaming set-up scripts are in the repository and are listed in the README.")
    for rel, lang in [("run_all.py", "Python"), ("etl/config.py", "Python"), ("etl/run_etl.py", "Python"), ("sql/01_schema.sql", "SQL (PostgreSQL)"), ("sql/02_load_batch.sql", "SQL (PL/pgSQL)"), ("sql/04_validation.sql", "SQL (PostgreSQL)"),
                      ("sql/08_analytics_mart.sql", "SQL (PostgreSQL)"), ("etl/model_comparison.py", "Python"), ("etl/distributed_citus.py", "Python"), ("streaming/producer.py", "Python"),
                      ("streaming/spark_stream.py", "Python (PySpark)"), ("dashboard/build_dashboard.py", "Python (Plotly)")]:
        code_file(rel, lang)


def chapter9():
    state["chap"] = 9
    h1("9 Presentation Slides")
    pngs = sorted(SLIDES_DIR.glob("slide-*.png"))
    P(f"The {len(pngs) if pngs else 17}-slide deck is `docs/Presentation.pptx` (made by `build_docs/build_slides.py`, also as the slideshow "
      "`deliverables/Food_Safety_Slides.html`). It follows the story of the report: the problem, the tools, the approach, the seven steps and the comparison.")
    if not pngs:
        P("(Slide images are created by this script when LibreOffice is installed; they were not available for this build.)", italic=True); return
    titles = ["Title", "The problem", "Tools", "The whole project in one picture", "Step 1: cleaning the data", "Step 2: the database design",
              "Step 3: loading the data", "Step 4: answering the questions", "Step 4: dashboard", "Step 5: prediction 1 (regression)",
              "Step 5: patterns (association rules)", "Step 5: prediction 2 (decision tree)", "Step 6: the database on 3 machines (Citus)",
              "Step 7: live dashboard (real-time warehouse)", "Comparison of the three warehouses", "Running the project", "Thank you"]
    for i, png in enumerate(pngs):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(2)
        p.add_run().add_picture(str(png), width=Inches(5.9))
        cp = doc.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER; cp.paragraph_format.space_after = Pt(10)
        r = cp.add_run(f"Slide {i + 1}: "); set_font(r, 9.5, True, color=CLAY); r = cp.add_run(titles[i] if i < len(titles) else ""); set_font(r, 9.5, False, True, STONE)


def chapter10():
    state["chap"] = 10
    h1("10 Limitations, Conclusion and Future Work")
    h2("10.1 Limitations")
    bullets(["The data are historical records. The real-time layer replays them; it was not exercised on a live feed, and its throughput was tested only at 80 events per second.",
             "All timings come from one laptop and compare designs under equal conditions; they are not production capacity. The Citus nodes shared that machine.",
             "Row counts above 61,737 in the scale test are a synthetic resampling of real facts, used only for timing.",
             "The record has no cause of failure other than the violations themselves, so prediction rests on history and circumstances; the models are weak.",
             "Facility attributes are the latest values (Type 1). Areas are quadrants of the street grid. There is no time of day.",
             "The brief recommends Power BI; the dashboard was built as an HTML page with Plotly instead, which shows the same sections and opens on any computer."])
    h2("10.2 Conclusion")
    P(f"The project built a reproducible pipeline from a public file to a dimensional warehouse, an OLAP layer, three kinds of mining models and a dashboard, and compared three warehouse architectures by measurement. "
      f"The batch warehouse holds {N_FACT:,} completed inspections in a fact constellation; it is loaded in an initial and an incremental batch, checked after each load, and every business question runs in milliseconds. "
      "The whole batch part runs with one command (`python run_all.py`) in about nine minutes, and `scripts/run_everything_wsl.sh full` rebuilds all three warehouses in about twenty.")
    P(f"The substantive findings are modest and clear. Failures became less frequent ({f22:.1f}% to {f25:.1f}%). The type of inspection and the history of the establishment matter more than the risk category. A failed inspection is usually followed by a clean one. "
      f"What is known before a visit predicts the outcome only weakly (R squared {multi['R2']:.2f}; AUC {tree5['ROC-AUC']:.2f}), so the models are useful for ordering inspections and not for deciding their results.")
    h2("10.3 Future work")
    bullets(["Model violation counts with a Poisson or negative binomial regression and failure with a gradient-boosted model, and compare them with the tree on the same split.",
             "Store one row per violation so that rule-level analysis (which rules cluster together) becomes an OLAP question.",
             "Add the time of day and staff or equipment information if the department can supply them; these are the most likely missing causes.",
             "Repeat the Citus experiment on separate machines and the streaming experiment on a live feed.",
             "Rebuild the dashboard in Power BI directly on the star schema."])


def references():
    state["chap"] = 11
    h1("References")
    for ref in ["City of Chicago, Data Portal. *Food Inspections* (dataset 4ijn-s7e5). https://data.cityofchicago.org/Health-Human-Services/Food-Inspections/4ijn-s7e5",
                "Kimball, R. and Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling*, 3rd edition. Wiley.",
                "Agrawal, R. and Srikant, R. (1994). Fast algorithms for mining association rules. *Proceedings of the 20th VLDB Conference*.",
                "Han, J., Pei, J. and Yin, Y. (2000). Mining frequent patterns without candidate generation. *Proceedings of the ACM SIGMOD Conference*.",
                "Breiman, L., Friedman, J., Olshen, R. and Stone, C. (1984). *Classification and Regression Trees*. Wadsworth.",
                "Quinlan, J. R. (1986). Induction of decision trees. *Machine Learning*, 1(1), 81-106.",
                "Quinlan, J. R. (1993). *C4.5: Programs for Machine Learning*. Morgan Kaufmann.",
                "Hastie, T., Tibshirani, R. and Friedman, J. (2009). *The Elements of Statistical Learning*, 2nd edition. Springer.",
                "Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. *Journal of Machine Learning Research*, 12, 2825-2830.",
                "Seabold, S. and Perktold, J. (2010). Statsmodels: econometric and statistical modeling with Python. *Proceedings of the 9th Python in Science Conference*.",
                "Raschka, S. (2018). MLxtend: providing machine learning and data science utilities and extensions to Python's scientific computing stack. *Journal of Open Source Software*, 3(24), 638.",
                "McKinney, W. (2010). Data structures for statistical computing in Python. *Proceedings of the 9th Python in Science Conference*.",
                "PostgreSQL Global Development Group. *PostgreSQL 18 Documentation*. https://www.postgresql.org/docs/18/",
                "Grafana Labs. *Grafana documentation*. https://grafana.com/docs/grafana/latest/",
                "Citus Data. *Citus documentation*. https://docs.citusdata.com",
                "Apache Software Foundation. *Apache Kafka* and *Apache Spark Structured Streaming* documentation. https://kafka.apache.org, https://spark.apache.org",
                "ClickHouse, Inc. *ClickHouse documentation*. https://clickhouse.com/docs",
                f"Project repository (source code, notebooks, data and documentation of this report): {REPO}"]:
        p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.3); p.paragraph_format.space_after = Pt(4)
        rich(p, ref, 10.5)


CHAPTERS = [chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8, chapter9, chapter10, references]


def build(toc_pages):
    global doc
    doc = Document(); HEADS.clear(); state.update(tab=0, fig=0, chap=0)
    setup(); header_footer(); cover(); front_matter(toc_pages)
    for ch in CHAPTERS:
        ch()
    doc.save(OUT_DOCX)


def to_pdf():
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(OUT_DOCX.parent), str(OUT_DOCX)], check=True, capture_output=True)
    return OUT_DOCX.with_suffix(".pdf")


def render_slides():
    soffice, pdftoppm = shutil.which("soffice") or shutil.which("libreoffice"), shutil.which("pdftoppm")
    pptx = ROOT / "docs" / "Presentation.pptx"
    if not (soffice and pdftoppm and pptx.exists()):
        return
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SLIDES_DIR / "_tmp"; tmp.mkdir(exist_ok=True)
    ready = ROOT / "docs" / "Presentation.pdf"          # PDF exported with the deck: exact fonts and images
    if ready.exists():
        shutil.copy(ready, tmp / "Presentation.pdf")
    else:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)], check=True, capture_output=True)
    for old in SLIDES_DIR.glob("slide-*.png"):
        old.unlink()
    subprocess.run([pdftoppm, "-r", "110", "-png", str(tmp / "Presentation.pdf"), str(SLIDES_DIR / "slide")], check=True)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    for png in SLIDES_DIR.glob("slide-*.png"):          # slide-01.png ... naming already sortable
        pass


def heading_pages(pdf):
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    pages = text.split("\f")
    found, cursor = {}, 1
    for level, h in [(1, "Declaration"), (1, "Abstract")] + HEADS:
        for n in range(cursor, len(pages) + 1):
            if any(line.strip() == h and "...." not in line for line in pages[n - 1].splitlines()):
                found[h] = n; cursor = n; break
    return found


def main():
    render_slides()
    # discover the headings first (they do not depend on page numbers), then build twice: once to measure pages, once with the numbers
    build({})
    TOC_SOURCE[:] = list(HEADS)
    pages = {}
    pdf = None
    for _ in range(2):
        build(pages)
        pdf = to_pdf()
        if not pdf or not shutil.which("pdftotext"):
            break
        pages = heading_pages(pdf)
    print("written", OUT_DOCX.relative_to(ROOT), ("and " + pdf.relative_to(ROOT).as_posix()) if pdf else "(PDF copy skipped: LibreOffice not found)")


if __name__ == "__main__":
    main()
