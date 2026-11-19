# Data dictionary

## 1. Source fields (City of Chicago Food Inspections)

| Source field | Meaning |
|---|---|
| inspection_id | Source identifier of one inspection |
| dba_name / aka_name | Establishment names (doing-business-as / also-known-as) |
| license_ | Licence number (0 or missing for some records) |
| facility_type | Facility category (free text, many spellings) |
| risk | Risk category: Risk 1 (High), Risk 2 (Medium), Risk 3 (Low); the value 'All' also occurs |
| address, city, state, zip | Location fields |
| inspection_date | Date of the inspection (time of day is always 00:00:00) |
| inspection_type | Reason / type of inspection (Canvass, Complaint, License, Re-inspections, ...) |
| results | Pass, Pass w/ Conditions, Fail, Out of Business, No Entry, Not Ready, Business Not Located |
| violations | Violation text: numbered items separated by '|' |
| latitude, longitude, location | Coordinates where available |

## 2. Fields added or standardised during curation

| Field | Meaning |
|---|---|
| facility_nk | Natural key of the facility: 'L' + licence, or 'N|' + name + '|' + address when there is no licence |
| facility_type_clean | Trimmed, title-cased facility type (the original wording is kept) |
| risk_category | Risk with invalid / missing values set to 'Unknown' |
| is_completed | TRUE when the result is Pass, Pass w/ Conditions or Fail |
| violation_count_raw / violation_count | Count of numbered violations; see derived attributes for the NULL rules |
| violation_codes | Rule numbers cited, comma separated |
| is_same_day_repeat, is_extreme_violation_count | Quality flags (retained rows) |

## 3. Derived attributes (NOT source fields)

Each derived attribute is calculated by `etl/curation.py`. No external enrichment source was used.

| Derived attribute | Formula | Threshold / code mapping | External enrichment |
|---|---|---|---|
| Year | YEAR(inspection_date) | - | None |
| Quarter | QUARTER(inspection_date) | 1-4 | None |
| Month | MONTH(inspection_date) | 1-12 | None |
| DayOfWeek | Day name of inspection_date | Monday-Sunday | None |
| IsWeekend | DayOfWeek in (Saturday, Sunday) | TRUE/FALSE | None |
| ViolationCount | Number of numbered items ('34. FLOORS ...') in the Violations text | Completed inspections only. Pass without text = 0. Fail / Pass w/ Conditions without text = NULL (unknown). Not completed = NULL | None |
| HasViolations | ViolationCount > 0 | NULL when ViolationCount is NULL | None |
| ResultGroup | Mapping of Results | Pass -> Pass; Pass w/ Conditions -> Conditional Pass; Fail -> Fail; Out of Business, No Entry, Not Ready, Business Not Located -> Not Completed | None |
| RiskGroup | Mapping of Risk | Risk 1 (High) -> High; Risk 2 (Medium) -> Medium; Risk 3 (Low) -> Low; 'All', missing -> Unknown | None |
| FacilityGroup | Ordered keyword rules on lower-cased Facility Type | Restaurant & Food Service; Schools & Childcare; Healthcare & Residential Care; Mobile, Catering & Events; Retail Food & Grocery; Other; missing -> Unknown | None (rules are in etl/curation.py) |
| InspectionTypeGroup | Rules on Inspection Type | contains 're-inspection' -> Re-inspection; Canvass -> Routine (Canvass); License -> License; Complaint / Food Poisoning -> Complaint / Illness; else Other | None |
| IsFailedInspection | Results = 'Fail' | 1 / 0 | None |
| HighViolationFlag | ViolationCount >= 6 | Threshold 6 is just above the 75th percentile (5) of completed inspections; NULL count -> 0 | None |
| ViolationBand | Banding of ViolationCount | None (0); Low (1-2); Medium (3-5); High (6-9); Very High (10+); Unknown | None |
| Season | Month -> season | Dec-Feb Winter; Mar-May Spring; Jun-Aug Summer; Sep-Nov Autumn | None |
| GeographicAreaGroup | Quadrant of the coordinates relative to the origin of the Chicago street grid (State St and Madison St, 41.8820, -87.6278) | Northwest / Northeast / Southwest / Southeast; missing coordinates -> Unknown | External reference: location of the street-grid origin only. No external dataset joined. |
| LatitudeBand / LongitudeBand | FLOOR(coordinate / 0.05) x 0.05 | 0.05 degree cells (about 5 km) | None |
| FacilityNK (facility natural key) | 'L' + licence number; if licence is missing or 0: 'N|' + DBA name + '|' + address | Used to build DimFacility | None |

## 4. Warehouse and mart tables

| Table | Columns |
|---|---|
| dw.dim_date | date_key (yyyymmdd), full_date, day, day_name, month, month_name, quarter, year, is_weekend, season |
| dw.dim_facility | facility_key, facility_nk, license_number, dba_name, facility_type, facility_group, risk_category, risk_group, facility_id_source, last_inspection_date, created_batch, updated_batch |
| dw.dim_inspection_type | inspection_type_key, inspection_type, inspection_type_group |
| dw.dim_result | result_key, result, result_group, failure_flag |
| dw.dim_location | location_key, zip, city, latitude_band, longitude_band, geographic_area_group |
| dw.fact_inspection | inspection_key, inspection_id (degenerate), date_key, facility_key, inspection_type_key, result_key, location_key, inspection_count, violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag, batch_id, loaded_at |
| dw.fact_facility_annual_inspection_performance | facility_key, reporting_year, inspection_count, fail_count, pass_count, conditional_pass_count, violation_count, inspections_with_known_violations, average_violations, failure_rate, batch_id, loaded_at |
| mart.food_inspection_analytics_mart | one row per completed inspection: keys, date parts, facility / risk / inspection type / result, violation count and band, zip, area, and the prior-history features (prior_inspection_result, prior_violation_count, days_since_prior_inspection, prior_inspection_count, has_prior_inspection) |

Unknown members: key 0 in `dim_facility`, `dim_inspection_type`, `dim_result` and `dim_location` (used when a lookup finds no match).
