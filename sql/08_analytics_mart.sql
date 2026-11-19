-- FoodInspectionAnalyticsMart: generated from the curated warehouse (fact + dimensions), NOT rebuilt from the raw file.
-- One row per completed inspection. Prior-history features use ONLY strictly earlier inspections of the same licensed facility (no leakage).
DROP SCHEMA IF EXISTS mart CASCADE;
CREATE SCHEMA mart;
CREATE TABLE mart.food_inspection_analytics_mart AS
WITH base AS (
    SELECT f.inspection_key, f.inspection_id, d.full_date AS inspection_date, d.year, d.quarter, d.month, d.day_name AS day_of_week, d.season,
           f.facility_key, fa.facility_nk, fa.dba_name AS facility, fa.facility_id_source, fa.facility_type, fa.facility_group, fa.risk_category, fa.risk_group,
           t.inspection_type, t.inspection_type_group, r.result, r.result_group, f.fail_count AS is_failed_inspection, f.high_violation_flag,
           f.violation_count, l.zip, l.geographic_area_group AS area, f.date_key
      FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
      JOIN dw.dim_inspection_type t USING (inspection_type_key) JOIN dw.dim_result r USING (result_key) JOIN dw.dim_location l USING (location_key)),
hist AS (
    SELECT b.*,
           CASE WHEN facility_id_source = 'License' THEN lag(result_group) OVER w END AS prior_result_raw,
           CASE WHEN facility_id_source = 'License' THEN lag(violation_count) OVER w END AS prior_violation_count_raw,
           CASE WHEN facility_id_source = 'License' THEN lag(date_key) OVER w END AS prior_date_key,
           CASE WHEN facility_id_source = 'License' THEN count(*) OVER (PARTITION BY facility_key ORDER BY date_key, inspection_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) END AS prior_inspection_count
      FROM base b WINDOW w AS (PARTITION BY facility_key ORDER BY date_key, inspection_id))
SELECT inspection_key, inspection_id, inspection_date, year, quarter, month, day_of_week, season, facility_key, facility, facility_type, facility_group, risk_category, risk_group,
       inspection_type, inspection_type_group, result, result_group, is_failed_inspection, violation_count, high_violation_flag,
       CASE WHEN violation_count IS NULL THEN 'Unknown' WHEN violation_count = 0 THEN 'None (0)' WHEN violation_count <= 2 THEN 'Low (1-2)' WHEN violation_count <= 5 THEN 'Medium (3-5)'
            WHEN violation_count <= 9 THEN 'High (6-9)' ELSE 'Very High (10+)' END AS violation_band,
       zip, area,
       -- history: strictly earlier inspection only (a same-day earlier inspection is ignored to stay leakage-safe)
       CASE WHEN prior_date_key IS NULL OR prior_date_key = date_key THEN 'None' ELSE prior_result_raw END AS prior_inspection_result,
       CASE WHEN prior_date_key IS NULL OR prior_date_key = date_key THEN NULL ELSE prior_violation_count_raw END AS prior_violation_count,
       CASE WHEN prior_date_key IS NULL OR prior_date_key = date_key THEN NULL
            ELSE to_date(date_key::text, 'YYYYMMDD') - to_date(prior_date_key::text, 'YYYYMMDD') END AS days_since_prior_inspection,
       CASE WHEN prior_date_key IS NULL OR prior_date_key = date_key THEN 0 ELSE coalesce(prior_inspection_count, 0) END AS prior_inspection_count,
       (prior_date_key IS NOT NULL AND prior_date_key <> date_key) AS has_prior_inspection
  FROM hist;
CREATE INDEX ON mart.food_inspection_analytics_mart (inspection_date);
ANALYZE mart.food_inspection_analytics_mart;
