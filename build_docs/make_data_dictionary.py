"""Writes docs/dataset_source.md and docs/data_dictionary.md (source fields, curated fields, derived attributes, warehouse tables)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
import curation as cur

def table(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"] + ["| " + " | ".join(r) + " |" for r in rows])

(ROOT / "docs" / "dataset_source.md").write_text("""# Dataset source documentation

| Item | Value |
|---|---|
| Dataset | Food Inspections |
| Publisher / authority | City of Chicago / Chicago Department of Public Health (Food Protection Program) |
| Official link | https://data.cityofchicago.org/Health-Human-Services/Food-Inspections/4ijn-s7e5 |
| Access method | City of Chicago Data Portal API: `https://data.cityofchicago.org/resource/4ijn-s7e5.csv` (Socrata) |
| Extraction date | 29 October 2026 |
| Selected period | 1 January 2022 to 31 December 2025 (period prescribed in the project document) |
| Filter applied | `inspection_date between '2022-01-01T00:00:00' and '2025-12-31T23:59:59'`, ordered by date and id |
| Rows extracted | 73,630 rows, 17 columns (`scripts/fetch_data.py` repeats the extraction) |
| File fingerprint | SHA-256 of `data/raw/food_inspections_2022_2025.csv`: `11dd8f5c6cb6d5baf35de583134068ae6fd02ac5de5c6ae98d63e0d92b510b84` |
| Columns used | all 17 source columns (see the data dictionary); the redundant `location` text is not used |
| Enrichment sources | none; no external dataset was joined |
| Derived attributes | documented with formula, threshold and mapping in `docs/data_dictionary.md` and in `etl/curation.py` |

The source notes that duplicate reports may remain and that results describe the conditions observed at the time of inspection. The portal data is updated over time, so a later download can differ slightly from the file used here; the fingerprint above identifies the exact file.

*Earlier course assignments in this repository (Assignments 4, 5 and 6) used the Kaggle snapshot of the same dataset (2010-2019). This project uses the official portal and the period prescribed in the project document.*
""")

raw_cols = [("inspection_id", "Source identifier of one inspection"), ("dba_name / aka_name", "Establishment names (doing-business-as / also-known-as)"), ("license_", "Licence number (0 or missing for some records)"),
            ("facility_type", "Facility category (free text, many spellings)"), ("risk", "Risk category: Risk 1 (High), Risk 2 (Medium), Risk 3 (Low); the value 'All' also occurs"),
            ("address, city, state, zip", "Location fields"), ("inspection_date", "Date of the inspection (time of day is always 00:00:00)"), ("inspection_type", "Reason / type of inspection (Canvass, Complaint, License, Re-inspections, ...)"),
            ("results", "Pass, Pass w/ Conditions, Fail, Out of Business, No Entry, Not Ready, Business Not Located"), ("violations", "Violation text: numbered items separated by '|'"),
            ("latitude, longitude, location", "Coordinates where available")]
cur_cols = [("facility_nk", "Natural key of the facility: 'L' + licence, or 'N|' + name + '|' + address when there is no licence"), ("facility_type_clean", "Trimmed, title-cased facility type (the original wording is kept)"),
            ("risk_category", "Risk with invalid / missing values set to 'Unknown'"), ("is_completed", "TRUE when the result is Pass, Pass w/ Conditions or Fail"), ("violation_count_raw / violation_count", "Count of numbered violations; see derived attributes for the NULL rules"),
            ("violation_codes", "Rule numbers cited, comma separated"), ("is_same_day_repeat, is_extreme_violation_count", "Quality flags (retained rows)")]
wh = [("dw.dim_date", "date_key (yyyymmdd), full_date, day, day_name, month, month_name, quarter, year, is_weekend, season"), ("dw.dim_facility", "facility_key, facility_nk, license_number, dba_name, facility_type, facility_group, risk_category, risk_group, facility_id_source, last_inspection_date, created_batch, updated_batch"),
      ("dw.dim_inspection_type", "inspection_type_key, inspection_type, inspection_type_group"), ("dw.dim_result", "result_key, result, result_group, failure_flag"),
      ("dw.dim_location", "location_key, zip, city, latitude_band, longitude_band, geographic_area_group"),
      ("dw.fact_inspection", "inspection_key, inspection_id (degenerate), date_key, facility_key, inspection_type_key, result_key, location_key, inspection_count, violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag, batch_id, loaded_at"),
      ("dw.fact_facility_annual_inspection_performance", "facility_key, reporting_year, inspection_count, fail_count, pass_count, conditional_pass_count, violation_count, inspections_with_known_violations, average_violations, failure_rate, batch_id, loaded_at"),
      ("mart.food_inspection_analytics_mart", "one row per completed inspection: keys, date parts, facility / risk / inspection type / result, violation count and band, zip, area, and the prior-history features (prior_inspection_result, prior_violation_count, days_since_prior_inspection, prior_inspection_count, has_prior_inspection)")]
(ROOT / "docs" / "data_dictionary.md").write_text("# Data dictionary\n\n## 1. Source fields (City of Chicago Food Inspections)\n\n" + table(raw_cols, ["Source field", "Meaning"]) +
    "\n\n## 2. Fields added or standardised during curation\n\n" + table(cur_cols, ["Field", "Meaning"]) +
    "\n\n## 3. Derived attributes (NOT source fields)\n\nEach derived attribute is calculated by `etl/curation.py`. No external enrichment source was used.\n\n" + table([list(r) for r in cur.DERIVED_ATTRIBUTES], ["Derived attribute", "Formula", "Threshold / code mapping", "External enrichment"]) +
    "\n\n## 4. Warehouse and mart tables\n\n" + table(wh, ["Table", "Columns"]) + "\n\nUnknown members: key 0 in `dim_facility`, `dim_inspection_type`, `dim_result` and `dim_location` (used when a lookup finds no match).\n")
print("written dataset_source.md and data_dictionary.md")
