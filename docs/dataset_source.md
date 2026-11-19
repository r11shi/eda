# Dataset source documentation

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
