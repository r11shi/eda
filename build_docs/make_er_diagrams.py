"""Draws the Star, Snowflake and Fact Constellation diagrams (matplotlib, no extra software needed)."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
FACT, DIM, SUB = "#f4b183", "#9dc3e6", "#c5e0b4"


class Canvas:
    def __init__(self, w, h, title):
        self.fig, self.ax = plt.subplots(figsize=(w, h)); self.ax.set_xlim(0, w); self.ax.set_ylim(0, h); self.ax.axis("off")
        self.ax.set_title(title, fontsize=14, fontweight="bold"); self.boxes = {}

    def table(self, name, x, y, cols, colour, width=2.6):
        h = 0.32 + 0.22 * len(cols)
        self.ax.add_patch(FancyBboxPatch((x, y), width, h, boxstyle="round,pad=0.02", fc=colour, ec="black", lw=1))
        self.ax.text(x + width / 2, y + h - 0.17, name, ha="center", va="center", fontsize=8.5, fontweight="bold")
        for i, c in enumerate(cols):
            self.ax.text(x + 0.08, y + h - 0.42 - 0.22 * i, c, fontsize=7, va="center")
        self.boxes[name] = (x, y, width, h)

    def link(self, a, b):
        xa, ya, wa, ha = self.boxes[a]; xb, yb, wb, hb = self.boxes[b]
        self.ax.annotate("", xy=(xb + wb / 2, yb + hb / 2), xytext=(xa + wa / 2, ya + ha / 2), arrowprops=dict(arrowstyle="-", lw=1, color="#555"), zorder=0)

    def save(self, name):
        self.fig.tight_layout(); self.fig.savefig(OUT / name, dpi=130); plt.close(self.fig)


def star(c, with_second_fact=False):
    c.table("FactInspection", 5.2, 3.0, ["inspection_key (PK)", "inspection_id (degenerate)", "date_key (FK)", "facility_key (FK)", "inspection_type_key (FK)",
                                         "result_key (FK)", "location_key (FK)", "inspection_count", "violation_count", "fail_count / pass_count",
                                         "conditional_pass_count", "high_violation_flag", "batch_id, loaded_at"], FACT, 2.8)
    c.table("DimDate", 0.6, 6.3, ["date_key (PK)", "full_date", "day, day_name", "month, month_name", "quarter, year", "is_weekend, season"], DIM)
    c.table("DimFacility", 0.6, 3.1, ["facility_key (PK)", "facility_nk, license_number", "dba_name", "facility_type", "facility_group", "risk_category, risk_group"], DIM)
    c.table("DimInspectionType", 0.6, 0.4, ["inspection_type_key (PK)", "inspection_type", "inspection_type_group"], DIM)
    c.table("DimResult", 9.0, 6.4, ["result_key (PK)", "result", "result_group", "failure_flag"], DIM)
    c.table("DimLocation", 9.0, 3.1, ["location_key (PK)", "zip, city", "latitude_band", "longitude_band", "geographic_area_group"], DIM)
    for d in ["DimDate", "DimFacility", "DimInspectionType", "DimResult", "DimLocation"]:
        c.link("FactInspection", d)
    if with_second_fact:
        c.table("FactFacilityAnnualInspectionPerformance", 4.6, 0.2, ["facility_key (FK, PK)", "reporting_year (PK)", "inspection_count", "fail_count / pass_count",
                                                                        "conditional_pass_count", "violation_count", "average_violations", "failure_rate"], FACT, 4.0)
        c.link("FactFacilityAnnualInspectionPerformance", "DimFacility")


c = Canvas(12.6, 9, "Star schema: FactInspection (grain: one completed inspection)"); star(c); c.save("star_schema.png")
c = Canvas(12.6, 9, "Fact constellation (selected model): FactInspection + FactFacilityAnnualInspectionPerformance sharing DimFacility"); star(c, True); c.save("fact_constellation.png")

s = Canvas(15, 10, "Snowflake schema: dimension hierarchies normalised (16 tables)")
s.table("fact_inspection", 6.2, 3.6, ["inspection_key (PK)", "inspection_id", "date_key", "facility_key", "inspection_type_key", "result_key", "location_key", "violation_count, fail_count ..."], FACT, 2.6)
s.table("dim_date", 3.2, 7.6, ["date_key", "full_date, day", "day_name, is_weekend", "month_key (FK)"], DIM, 2.4)
s.table("dim_month", 3.2, 9.0, ["month_key", "month, month_name, season", "quarter_key (FK)"], SUB, 2.4)
s.table("dim_quarter", 6.0, 9.0, ["quarter_key", "quarter, year (FK)"], SUB, 2.0)
s.table("dim_year", 8.6, 9.0, ["year"], SUB, 1.4)
s.table("dim_facility", 0.2, 4.6, ["facility_key", "facility_nk, license", "dba_name", "type_key (FK)", "risk_key (FK)"], DIM, 2.4)
s.table("dim_facility_type", 0.2, 2.2, ["type_key", "facility_type", "group_key (FK)"], SUB, 2.4)
s.table("dim_facility_group", 0.2, 0.5, ["group_key", "facility_group"], SUB, 2.4)
s.table("dim_risk", 3.1, 5.6, ["risk_key", "risk_category, risk_group"], SUB, 2.4)
s.table("dim_inspection_type", 3.1, 2.6, ["inspection_type_key", "inspection_type", "group_key (FK)"], DIM, 2.4)
s.table("dim_inspection_type_group", 3.1, 0.7, ["group_key", "inspection_type_group"], SUB, 2.4)
s.table("dim_result", 9.8, 6.3, ["result_key", "result, failure_flag", "group_key (FK)"], DIM, 2.4)
s.table("dim_result_group", 12.4, 6.3, ["group_key", "result_group"], SUB, 2.4)
s.table("dim_location", 9.8, 3.4, ["location_key", "zip_key (FK), area_key (FK)", "latitude_band", "longitude_band"], DIM, 2.4)
s.table("dim_zip", 12.4, 3.4, ["zip_key", "zip, city"], SUB, 2.4)
s.table("dim_area_group", 12.4, 1.3, ["area_key", "geographic_area_group"], SUB, 2.4)
for a, b in [("fact_inspection", "dim_date"), ("fact_inspection", "dim_facility"), ("fact_inspection", "dim_inspection_type"), ("fact_inspection", "dim_result"),
             ("fact_inspection", "dim_location"), ("dim_date", "dim_month"), ("dim_month", "dim_quarter"), ("dim_quarter", "dim_year"),
             ("dim_facility", "dim_facility_type"), ("dim_facility_type", "dim_facility_group"), ("dim_facility", "dim_risk"),
             ("dim_inspection_type", "dim_inspection_type_group"), ("dim_result", "dim_result_group"), ("dim_location", "dim_zip"), ("dim_location", "dim_area_group")]:
    s.link(a, b)
s.save("snowflake_schema.png")
print("diagrams written to", OUT)
