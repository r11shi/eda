# Data-Quality Report

Source: City of Chicago Food Inspections, 1 Jan 2022 to 31 Dec 2025 (extracted 29 Oct 2026). Every count below is computed by `etl/curation.py` (see `notebooks/01_data_curation.ipynb`).

Raw rows: 73,630. Curated rows: 73,601. Completed inspections (FactInspection grain): 61,737.

| Quality problem | Field | Count | Treatment | Justification |
|---|---|---:|---|---|
| Invalid timestamp | inspection_date | 0 | Exclude (none found) | A date that cannot be parsed cannot be placed in DimDate. |
| Exact duplicate record | all columns | 0 | Remove | Identical rows add no information. |
| Repeated inspection_id | inspection_id | 0 | Investigate (none found) | inspection_id is the source identifier of one inspection. |
| Logical duplicate (same licence, date, type, result and violation text, different inspection_id) | inspection_id | 29 | Remove later copies | The source documentation says duplicate reports may remain; identical content for the same licence and day is a repeated report. |
| Same licence, date and type but different result/violations | license_number | 496 | Retain and flag | Different content means they may be separate visits (e.g. morning and afternoon); cannot be proven duplicates. |
| Result value not in documented list | results | 0 | Map to Not Completed (none found) | Results are checked against the source documentation. |
| Invalid risk code 'All' | risk | 38 | Map to Unknown member | Only Risk 1/2/3 are documented, so 'All' is not a real category. |
| Missing risk | risk | 17 | Map to Unknown member | Facts are kept; excluding them would bias counts. |
| Missing facility type | facility_type | 320 | Map to Unknown member | Facts are kept; type is not needed for counts. |
| Free-text facility types (distinct raw spellings) | facility_type | 217 | Title-case + keyword grouping into FacilityGroup | Raw type is free text with spelling variants; the group is a DERIVED attribute, the clean type keeps the original wording. |
| Misspelt city (CCHICAGO) | city | 13 | Correct to CHICAGO | Obvious typo; coordinates confirm Chicago. |
| State other than IL | state | 13 | Retain and flag | Coordinates are checked separately; state may be a data-entry error. |
| Missing city/state | city, state | 67 | Retain (not used as a key) | Location is analysed via ZIP and coordinates. |
| Missing ZIP | zip | 6 | Map to 'Unknown' | Facts are kept. |
| ZIP outside the 606xx Chicago range | zip | 555 | Retain and flag | Could be a real suburb address or a typo; not removed. |
| Missing or zero licence number | license_number | 213 | Identify facility by name + address instead | Licence 0 is a placeholder; such facilities are excluded from repeat-inspection analysis only. |
| Missing coordinates | latitude, longitude | 255 | Keep row; LocationKey -> Unknown area | ZIP is still available for these rows. |
| Coordinates outside Chicago bounding box | latitude, longitude | 0 | Set to missing (none found) | Impossible for a Chicago establishment; the box is a quality check, not the exact city boundary. |
| Inspection on Saturday/Sunday | inspection_date | 7 | Retain and flag | Possible but rare; no evidence of error. |
| Time of day not available | inspection_date | 73,601 | No hourly analysis possible | All timestamps are 00:00:00 in the source, so hourly patterns are NOT derived or invented. |
| Fail / Pass w/ Conditions without violation text | violations | 552 | ViolationCount = NULL (unknown) | These results require at least one cited violation, so zero would be wrong; the row is kept for counts. |
| Pass with no violation text | violations | 10,823 | ViolationCount = 0 | A passing inspection with nothing recorded cited no violations. |
| Extreme violation count (above Q3 + 1.5 x IQR) | violation_count | 2,686 | Retain and flag | Large counts are plausible for badly failing premises; capping would hide the very inspections of interest. |
| Negative or impossible violation count | violation_count | 0 | None found | A count cannot be negative. |
| Result is not a completed inspection (Out of Business, No Entry, Not Ready, Business Not Located) | results | 11,864 | Keep in curated/staging data, exclude from FactInspection | The fact grain is one COMPLETED inspection; these rows are status outcomes with no assessment. |
| Rows before / after curation | - | 29 | 73,630 raw rows -> 73,601 curated rows | Row reconciliation (rows removed = exact + id + logical duplicates). |
