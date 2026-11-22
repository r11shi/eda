"""Draws the simple box-and-arrow diagrams used in README.md / the guide page, as SVG files in docs/images/diagrams/.

The SVGs use CSS variables with fallbacks, so they follow the guide page's light/dark theme when inlined
and still look right when opened on their own (for example on GitHub).
    python build_docs/make_guide_diagrams.py
"""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "images" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUTE, BOX, LINE, ACC, ACC2, WARM = ("var(--d-ink,#21201c)", "var(--d-mute,#63635e)", "var(--d-box,#ffffff)", "var(--d-line,#c9c8c2)",
                                         "var(--d-acc,#2f5bd3)", "var(--d-acc2,#1f8a5b)", "var(--d-warm,#c2542d)")
TINT = {"plain": BOX, "main": "var(--d-tint,#eaf0fd)", "good": "var(--d-tint2,#e6f4ec)", "bad": "var(--d-tint3,#fbeae4)"}
EDGE = {"plain": LINE, "main": ACC, "good": ACC2, "bad": WARM}


class D:
    def __init__(self, w, h, title):
        self.w, self.h, self.title, self.parts, self.boxes = w, h, title, [], {}

    def box(self, key, x, y, w, h, lines, kind="plain", sub=None):
        self.boxes[key] = (x, y, w, h)
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" style="fill:{TINT[kind]};stroke:{EDGE[kind]};stroke-width:1.4"/>')
        lines = lines if isinstance(lines, list) else [lines]
        sub = sub if isinstance(sub, list) else ([sub] if sub else [])
        total = len(lines) * 17 + len(sub) * 14
        ty = y + h / 2 - total / 2 + 13
        for ln in lines:
            self.parts.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" style="fill:{INK};font:600 13px Inter,system-ui,sans-serif">{escape(ln)}</text>')
            ty += 17
        for ln in sub:
            self.parts.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" style="fill:{MUTE};font:400 11.5px Inter,system-ui,sans-serif">{escape(ln)}</text>')
            ty += 14

    def _edge_point(self, key, tx, ty):
        x, y, w, h = self.boxes[key]
        cx, cy = x + w / 2, y + h / 2
        dx, dy = tx - cx, ty - cy
        if dx == 0 and dy == 0:
            return cx, cy
        s = min((w / 2) / abs(dx) if dx else 1e9, (h / 2) / abs(dy) if dy else 1e9)
        return cx + dx * s, cy + dy * s

    def arrow(self, a, b, label=None, color=None, dashed=False):
        ax, ay, aw, ah = self.boxes[a]; bx, by, bw, bh = self.boxes[b]
        x1, y1 = self._edge_point(a, bx + bw / 2, by + bh / 2)
        x2, y2 = self._edge_point(b, ax + aw / 2, ay + ah / 2)
        c = color or MUTE
        dash = ';stroke-dasharray:5 4' if dashed else ''
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" marker-end="url(#ah)" style="stroke:{c};stroke-width:1.6{dash}"/>')
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.parts.append(f'<text x="{mx:.1f}" y="{my - 6:.1f}" text-anchor="middle" style="fill:{MUTE};font:500 11px Inter,system-ui,sans-serif">{escape(label)}</text>')

    def text(self, x, y, s, size=12, weight=400, color=None, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="fill:{color or MUTE};font:{weight} {size}px Inter,system-ui,sans-serif">{escape(s)}</text>')

    def rect(self, x, y, w, h, color, rx=3):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" style="fill:{color}"/>')

    def save(self, name):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
               f'<title>{escape(self.title)}</title><defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" style="fill:{MUTE}"/></marker></defs>' + "".join(self.parts) + "</svg>")
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
        print("  ", name)


# 1. the whole project
d = D(720, 350, "The whole project: where the data goes")
d.box("raw", 10, 20, 120, 56, "Raw CSV", sub="73,630 rows")
d.box("clean", 160, 20, 130, 56, "Clean (Python)", sub="notebook 01")
d.box("stg", 320, 20, 120, 56, "Staging table", sub="waiting room")
d.box("dw", 470, 14, 240, 68, "Batch warehouse", "main", "PostgreSQL · star schema")
d.box("olap", 360, 150, 110, 56, "SQL & OLAP", sub="10 questions")
d.box("dash", 485, 150, 105, 56, "Dashboard", sub="HTML page")
d.box("ml", 605, 150, 105, 56, "3 models", sub="notebooks 07-09")
d.box("citus", 470, 262, 240, 56, "Distributed copy", "good", "Citus · 3 nodes")
d.box("rt", 10, 262, 420, 56, "Real-time copy: Kafka → Spark → ClickHouse → Grafana", "bad", "past inspections replayed as live events")
for a, b in [("raw", "clean"), ("clean", "stg"), ("stg", "dw"), ("dw", "olap"), ("dw", "dash"), ("dw", "ml")]:
    d.arrow(a, b)
d.arrow("dw", "citus", dashed=True); d.arrow("clean", "rt", dashed=True)
d.text(10, 342, "blue = the main warehouse · dashed = the same data copied into the other two warehouses", 11.5)
d.save("pipeline")

# 2. cleaning funnel (to scale)
d = D(720, 190, "How many rows survive cleaning")
rows = [("Raw rows from the city", 73630, LINE), ("After removing 29 repeated reports", 73601, LINE), ("Completed inspections (the facts)", 61737, ACC)]
for i, (lab, v, c) in enumerate(rows):
    y = 18 + i * 56
    d.text(10, y + 12, lab, 12.5, 500, INK)
    d.rect(10, y + 20, 600 * v / 73630, 22, c)
    d.text(10 + 600 * v / 73630 + 8, y + 36, f"{v:,}", 12.5, 600, INK)
d.text(10, 184, "11,864 rows were visits that never happened (Out of Business, No Entry …): kept in staging, not counted.", 11.5)
d.save("cleaning_funnel")

# 3. star schema
d = D(720, 360, "Star schema: one fact table in the middle, five dimension tables around it")
d.box("f", 250, 125, 220, 110, "fact_inspection", "main", ["one row = one inspection", "keys + numbers:", "violation_count, fail_count, pass_count"])
d.box("date", 20, 20, 170, 58, "dim_date", sub="when · 1,826 days")
d.box("fac", 530, 20, 170, 58, "dim_facility", sub="which place · 17,084")
d.box("type", 20, 280, 170, 58, "dim_inspection_type", sub="why · 15 types")
d.box("res", 530, 280, 170, 58, "dim_result", sub="Pass / Cond. / Fail")
d.box("loc", 275, 290, 170, 58, "dim_location", sub="where · 252 ZIP+area")
d.box("ann", 530, 150, 170, 60, "2nd fact table", "good", "one place × one year")
for k in ("date", "fac", "type", "res", "loc"):
    d.arrow("f", k)
d.arrow("ann", "fac", dashed=True)
d.text(360, 44, "Every dimension has a row 0 = 'Unknown',", 11.5, anchor="middle")
d.text(360, 60, "so no inspection is ever dropped.", 11.5, anchor="middle")
d.save("star_schema")

# 4. ETL
d = D(720, 160, "ETL: how a batch of data enters the warehouse")
steps = [("csv", "Clean CSV", "notebook 01"), ("stg", "Staging", "COPY command"), ("dim", "Dimensions", "add new places"), ("fact", "Fact rows", "look up the keys"), ("chk", "5 checks", "all must be 0")]
for i, (k, a, b) in enumerate(steps):
    d.box(k, 8 + i * 143, 30, 120, 60, a, "main" if k == "fact" else ("good" if k == "chk" else "plain"), b)
for a, b in zip([s[0] for s in steps], [s[0] for s in steps][1:]):
    d.arrow(a, b)
d.text(8, 122, "Dimensions + fact rows are filled by one SQL procedure, dw.load_batch.", 11.5)
d.text(8, 140, "It runs once for Jan 2022 - Nov 2025 (initial load), then again for Dec 2025 (incremental load).", 11.5)
d.save("etl")

# 5. load sizes (to scale)
d = D(720, 120, "Initial load and incremental load")
d.text(10, 20, "Inspections in the warehouse", 12.5, 500, INK)
d.rect(10, 32, 690 * 60608 / 61737, 30, ACC, 3); d.rect(10 + 690 * 60608 / 61737, 32, 690 * 1129 / 61737, 30, WARM, 3)
d.text(20, 52, "Initial load: 60,608 (Jan 2022 – Nov 2025)", 12, 600, "#ffffff")
d.text(700, 84, "+1,129 incremental (Dec 2025)", 12, 600, WARM, "end")
d.text(10, 110, "Total after both loads: 61,737. The incremental load adds only the new month; nothing is rebuilt.", 11.5)
d.save("loads")

# 6. OLAP operations
d = D(720, 200, "OLAP: looking at the same numbers at different levels")
d.box("y", 20, 20, 120, 46, "Year", "main"); d.box("q", 20, 80, 120, 46, "Quarter"); d.box("m", 20, 140, 120, 46, "Month")
d.arrow("m", "q", color=ACC); d.arrow("q", "y", color=ACC)
d.text(150, 112, "roll-up ↑", 11.5, 600, ACC); d.text(150, 132, "drill-down ↓", 11.5, 600, ACC)
d.box("s", 220, 20, 220, 50, "Slice", sub="keep one value: year = 2025")
d.box("dc", 220, 80, 220, 50, "Dice", sub="2025 AND high risk")
d.box("p", 220, 140, 220, 50, "Pivot", sub="results become columns")
d.box("dd", 500, 20, 200, 50, "Drill-down", sub="group → type → one shop")
d.box("cu", 500, 80, 200, 50, "CUBE", sub="all subtotals at once")
d.box("gs", 500, 140, 200, 50, "GROUPING SETS", sub="only the subtotals you pick")
d.save("olap")

# 7. regression
d = D(720, 150, "How the regression model is trained and tested")
d.box("mart", 8, 45, 120, 60, "Analytics table", sub="61,737 rows")
d.box("tr", 168, 10, 140, 52, "Train: 2022-24", "main", "45,266 rows")
d.box("te", 168, 90, 140, 52, "Test: 2025", "bad", "15,919 rows")
d.box("fit", 348, 10, 140, 52, "Fit the line", sub="LinearRegression")
d.box("pred", 348, 90, 140, 52, "Predict 2025")
d.box("sc", 540, 45, 170, 60, "Score", "good", ["MAE 2.45  ·  R² 0.12"])
d.arrow("mart", "tr"); d.arrow("mart", "te"); d.arrow("tr", "fit"); d.arrow("fit", "pred"); d.arrow("te", "pred"); d.arrow("pred", "sc")
d.save("regression")

# 8. association rule measures
d = D(720, 150, "Support, confidence and lift for one rule")
d.box("a", 10, 40, 210, 64, "IF  10+ violations", "main", "5.4% of inspections have both parts")
d.box("b", 300, 40, 160, 64, "THEN  Fail", "bad")
d.arrow("a", "b")
d.box("m", 520, 14, 190, 116, "Support 5.4%", "good", ["Confidence 69%", "(fails, when 10+ violations)", "Lift 3.0", "(3× the normal 23%)"])
d.save("assoc_rule")

# 9. decision tree (top of the real tree, simplified)
d = D(720, 330, "The decision tree asks yes/no questions")
d.box("r", 245, 10, 230, 50, "Previous result = Fail?", "main")
d.box("n1", 40, 100, 230, 50, "Complaint inspection?")
d.box("y1", 450, 100, 230, 50, "Quick re-check after a fail", "good", "only 4-5% fail")
d.box("n2", 10, 190, 230, 52, "Previous violations > 6?", sub="and a long gap since last visit")
d.box("lo", 290, 190, 180, 52, "Not a complaint", sub="lower chance of fail")
d.box("hi", 10, 272, 230, 52, "Highest risk group", "bad", "55-58% fail")
d.arrow("r", "n1", "no"); d.arrow("r", "y1", "yes"); d.arrow("n1", "n2", "yes"); d.arrow("n1", "lo", "no"); d.arrow("n2", "hi", "yes")
d.save("decision_tree")

# 10. Citus
d = D(720, 230, "Citus: one coordinator and two workers")
d.box("q", 270, 6, 180, 40, "Your SQL query")
d.box("c", 230, 70, 260, 56, "Coordinator (port 5440)", "main", "splits the query, merges the answers")
d.box("w1", 40, 160, 280, 60, "Worker 1 (port 5441)", "good", "16 shards of the fact table + all dimensions")
d.box("w2", 400, 160, 280, 60, "Worker 2 (port 5442)", "good", "16 shards of the fact table + all dimensions")
d.arrow("q", "c"); d.arrow("c", "w1"); d.arrow("c", "w2")
d.save("citus")

# 11. streaming
d = D(720, 200, "Real-time pipeline (replay of past inspections)")
d.box("p", 8, 60, 120, 60, "producer.py", sub="80 events/s")
d.box("k", 158, 60, 110, 60, "Kafka", sub="message queue")
d.box("s", 298, 60, 130, 60, "Spark", "main", "checks each event")
d.box("ch", 460, 20, 120, 52, "ClickHouse", "good", "3,647 good events")
d.box("bad", 460, 112, 120, 52, "invalid_events", "bad", "24 broken caught")
d.box("g", 606, 20, 106, 52, "Grafana", sub="every 5 s")
d.arrow("p", "k"); d.arrow("k", "s"); d.arrow("s", "ch", "valid"); d.arrow("s", "bad", "broken"); d.arrow("ch", "g")
d.text(8, 190, "About 1.8 seconds from sending an event to seeing it on the Grafana dashboard.", 11.5)
d.save("streaming")
