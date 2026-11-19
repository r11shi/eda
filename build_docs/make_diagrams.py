"""Draws the architecture diagram and the fact-constellation schema in the project palette -> docs/images/architecture.png, fact_constellation.png."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]


class C:                               # colours of the project palette
    INK, CLAY, STONE, SAND = "#1a1f2e", "#1f4e9c", "#5b6577", "#dce6f5"


plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"], "text.color": C.INK})

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
PAPER_BOX, HEAD = "#fffdf8", C.SAND


def table_box(ax, x, y, w, title, cols, fact=False, fs=7.6):
    row = 0.42
    h = row * (len(cols) + 1.3)
    ax.add_patch(Rectangle((x, y), w, h, facecolor=PAPER_BOX, edgecolor=C.CLAY if fact else C.INK, linewidth=1.6 if fact else 1.0, zorder=3))
    ax.add_patch(Rectangle((x, y + h - row * 1.3), w, row * 1.3, facecolor=C.CLAY if fact else HEAD, edgecolor=C.CLAY if fact else C.INK, linewidth=1.0, zorder=4))
    ax.text(x + w / 2, y + h - row * 0.65, title, ha="center", va="center", fontsize=fs + 1.2, fontweight="bold", color="white" if fact else C.INK, zorder=5)
    for i, c in enumerate(cols):
        ax.text(x + 0.12, y + h - row * 1.3 - row * (i + 0.55), c, ha="left", va="center", fontsize=fs, color=C.INK, zorder=5)
    return x, y, w, h


def link(ax, a, b, side_a, side_b):
    def pt(box, side):
        x, y, w, h = box
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]
    ax.add_patch(FancyArrowPatch(pt(a, side_a), pt(b, side_b), arrowstyle="-", color=C.STONE, linewidth=1.0, zorder=1))


def constellation():
    fig, ax = plt.subplots(figsize=(10.5, 6.6)); ax.set_xlim(0, 21); ax.set_ylim(0, 13); ax.axis("off"); ax.grid(False)
    ax.set_title("Fact constellation: FactInspection and FactFacilityAnnualInspectionPerformance share DimFacility", fontsize=11, pad=8)
    f1 = table_box(ax, 7.2, 5.6, 6.6, "FactInspection", ["inspection_key (PK)", "inspection_id (degenerate)", "date_key, facility_key", "inspection_type_key, result_key, location_key",
                                                              "violation_count, fail_count, pass_count", "conditional_pass_count, high_violation_flag", "batch_id, loaded_at"], fact=True)
    f2 = table_box(ax, 7.2, 0.4, 6.6, "FactFacilityAnnualPerformance", ["facility_key, reporting_year (PK)", "inspection_count, fail_count", "average_violations, failure_rate", "batch_id"], fact=True)
    d_date = table_box(ax, 0.4, 8.6, 4.8, "DimDate", ["date_key (PK)", "full_date, day, day_name", "month, quarter, year", "is_weekend, season"])
    d_fac = table_box(ax, 0.4, 3.2, 4.8, "DimFacility", ["facility_key (PK)", "facility_nk, license_number", "dba_name, facility_type", "facility_group", "risk_category, risk_group"])
    d_type = table_box(ax, 0.4, 0.2, 4.8, "DimInspectionType", ["inspection_type_key (PK)", "inspection_type", "inspection_type_group"])
    d_res = table_box(ax, 15.8, 8.8, 4.8, "DimResult", ["result_key (PK)", "result, result_group", "failure_flag"])
    d_loc = table_box(ax, 15.8, 3.6, 4.8, "DimLocation", ["location_key (PK)", "zip, city", "latitude_band, longitude_band", "geographic_area_group"])
    link(ax, f1, d_date, "l", "r"); link(ax, f1, d_fac, "l", "r"); link(ax, f1, d_type, "l", "r"); link(ax, f1, d_res, "r", "l"); link(ax, f1, d_loc, "r", "l"); link(ax, f2, d_fac, "l", "b")
    fig.savefig(OUT / "fact_constellation.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(10.5, 4.3)); ax.set_xlim(0, 21); ax.set_ylim(0, 8.6); ax.axis("off"); ax.grid(False)
    layers = [("Raw zone", "data/raw", "CSV from the data portal\n(bundled .csv.gz copy)"), ("Curation", "etl/curation.py", "types, duplicates, codes,\nderived attributes, log"),
              ("Staging", "staging schema", "typed rows, batch id,\nreject reason, audit"), ("Warehouse", "dw schema (PostgreSQL 16)", "five dimensions,\ntwo fact tables"),
              ("Analysis", "OLAP, notebooks 07 to 09", "regression, association rules,\ndecision tree")]
    w, gap, x0, y0, h = 3.5, 0.7, 0.4, 4.2, 3.2
    for i, (t, sub, body) in enumerate(layers):
        x = x0 + i * (w + gap); accent = i == 3
        ax.add_patch(Rectangle((x, y0), w, h, facecolor=PAPER_BOX, edgecolor=C.CLAY if accent else C.INK, linewidth=1.8 if accent else 1.0, zorder=3))
        ax.add_patch(Rectangle((x, y0 + h - 0.95), w, 0.95, facecolor=C.CLAY if accent else HEAD, edgecolor=C.CLAY if accent else C.INK, linewidth=1.0, zorder=4))
        ax.text(x + w / 2, y0 + h - 0.48, t, ha="center", va="center", fontsize=11, fontweight="bold", color="white" if accent else C.INK, zorder=5)
        ax.text(x + w / 2, y0 + h - 1.5, sub, ha="center", va="center", fontsize=8.2, style="italic", color=C.STONE, zorder=5)
        ax.text(x + w / 2, y0 + 0.85, body, ha="center", va="center", fontsize=8.6, color=C.INK, zorder=5)
        if i < len(layers) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.05, y0 + h / 2), (x + w + gap - 0.05, y0 + h / 2), arrowstyle="-|>", mutation_scale=12, color=C.INK, linewidth=1.2, zorder=2))
    outs = [("HTML dashboard", "dashboard/"), ("Analytical mart", "sql/08_analytics_mart.sql"), ("Citus cluster", "Part D"), ("Kafka, Spark, ClickHouse", "Part E (replay)")]
    bx = x0 + 3 * (w + gap)
    for j, (t, sub) in enumerate(outs):
        x = x0 + 2.0 + j * 4.65
        ax.add_patch(Rectangle((x, 0.3), 4.0, 1.9, facecolor="white", edgecolor=C.STONE, linewidth=1.0, zorder=3))
        ax.text(x + 2.0, 1.5, t, ha="center", va="center", fontsize=9.6, fontweight="bold", color=C.INK, zorder=5)
        ax.text(x + 2.0, 0.85, sub, ha="center", va="center", fontsize=8, style="italic", color=C.STONE, zorder=5)
    wx = x0 + 3 * (w + gap) + w / 2
    for j in range(4):
        ax.add_patch(FancyArrowPatch((wx if j < 2 else x0 + 4 * (w + gap) + w / 2, y0 - 0.05), (x0 + 2.0 + j * 4.65 + 2.0, 2.25), arrowstyle="-|>", mutation_scale=10, color=C.STONE, linewidth=1.0, zorder=2,
                                     connectionstyle="arc3,rad=0.0"))
    fig.savefig(OUT / "architecture.png", dpi=170, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    architecture()
    print("written docs/images/architecture.png")
