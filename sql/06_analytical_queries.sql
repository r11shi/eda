-- Historical analytical SQL for the mandatory business questions 1-8 (questions 9 and 10 are answered by the mining notebooks).

-- name: Q1a Annual inspection volume
SELECT d.year, count(*) AS inspections FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY d.year ORDER BY d.year;

-- name: Q1b Monthly inspection volume
SELECT d.year, d.month, d.month_name, count(*) AS inspections FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
 GROUP BY d.year, d.month, d.month_name ORDER BY d.year, d.month;

-- name: Q2 Facility types receiving the most inspections
SELECT fa.facility_type, fa.facility_group, count(*) AS inspections, round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_of_all
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) GROUP BY 1, 2 ORDER BY inspections DESC LIMIT 15;

-- name: Q3 Pass, conditional-pass and fail rates by year
SELECT d.year, count(*) AS inspections, round(100.0 * sum(f.pass_count) / count(*), 2) AS pass_rate,
       round(100.0 * sum(f.conditional_pass_count) / count(*), 2) AS conditional_rate, round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) GROUP BY d.year ORDER BY d.year;

-- name: Q4 Results across risk categories
SELECT fa.risk_group, count(*) AS inspections, round(100.0 * sum(f.pass_count) / count(*), 2) AS pass_rate,
       round(100.0 * sum(f.conditional_pass_count) / count(*), 2) AS conditional_rate, round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate,
       round(avg(f.violation_count), 2) AS avg_violations
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) GROUP BY fa.risk_group ORDER BY inspections DESC;

-- name: Q5 Inspection types associated with higher failure rates
SELECT t.inspection_type, t.inspection_type_group, count(*) AS inspections, sum(f.fail_count) AS fails,
       round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate
  FROM dw.fact_inspection f JOIN dw.dim_inspection_type t USING (inspection_type_key) GROUP BY 1, 2 HAVING count(*) >= 100 ORDER BY fail_rate DESC;

-- name: Q6a Violation counts by result group
SELECT r.result_group, count(f.violation_count) AS inspections_with_known_count, round(avg(f.violation_count), 2) AS avg_violations,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.violation_count) AS median_violations, max(f.violation_count) AS max_violations,
       sum(f.high_violation_flag) AS high_violation_inspections
  FROM dw.fact_inspection f JOIN dw.dim_result r USING (result_key) GROUP BY r.result_group ORDER BY avg_violations DESC;

-- name: Q6b Most common violation rule numbers (rule-level detail is kept in staging, not in the star schema)
SELECT v.rule AS rule_number, count(*) AS inspections_citing_rule, round(100.0 * count(*) / (SELECT count(*) FROM staging.inspection_stg WHERE is_completed AND reject_reason IS NULL AND batch_id IN (1,2)), 2) AS pct_of_inspections
  FROM (SELECT unnest(string_to_array(violation_codes, ',')) AS rule FROM staging.inspection_stg
         WHERE is_completed AND reject_reason IS NULL AND batch_id IN (1,2) AND violation_codes <> '') v
 GROUP BY v.rule ORDER BY inspections_citing_rule DESC LIMIT 15;

-- name: Q7a Geographic area groups: failures and failure rate
SELECT l.geographic_area_group, count(*) AS inspections, sum(f.fail_count) AS fails, round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate
  FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) GROUP BY 1 ORDER BY fail_rate DESC;

-- name: Q7b ZIP codes with the highest failure rate (at least 200 inspections)
SELECT l.zip, count(*) AS inspections, sum(f.fail_count) AS fails, round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate
  FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) WHERE l.zip <> 'Unknown' GROUP BY l.zip HAVING count(*) >= 200
 ORDER BY fail_rate DESC LIMIT 10;

-- name: Q7c ZIP codes with the most failures (counts, not rates)
SELECT l.zip, count(*) AS inspections, sum(f.fail_count) AS fails, round(100.0 * sum(f.fail_count) / count(*), 2) AS fail_rate
  FROM dw.fact_inspection f JOIN dw.dim_location l USING (location_key) WHERE l.zip <> 'Unknown' GROUP BY l.zip ORDER BY fails DESC LIMIT 10;

-- name: Q8a Repeat inspections: fail rate by the position of the inspection in the facility's history (licensed facilities only)
WITH seq AS (
  SELECT f.facility_key, f.fail_count, f.date_key, row_number() OVER (PARTITION BY f.facility_key ORDER BY f.date_key, f.inspection_id) AS n
    FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) WHERE fa.facility_id_source = 'License')
SELECT CASE WHEN n >= 4 THEN '4th or later' WHEN n = 3 THEN '3rd' WHEN n = 2 THEN '2nd' ELSE '1st' END AS inspection_number,
       count(*) AS inspections, round(100.0 * sum(fail_count) / count(*), 2) AS fail_rate FROM seq GROUP BY 1 ORDER BY 1;

-- name: Q8b Repeat inspections: what happens at the next inspection after a failed one
WITH seq AS (
  SELECT f.facility_key, f.fail_count, f.pass_count, f.date_key, f.inspection_id,
         lead(f.fail_count) OVER w AS next_fail, lead(f.pass_count) OVER w AS next_pass, lead(f.date_key) OVER w AS next_date
    FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) WHERE fa.facility_id_source = 'License'
  WINDOW w AS (PARTITION BY f.facility_key ORDER BY f.date_key, f.inspection_id))
SELECT count(*) AS failed_inspections_with_a_next_inspection, round(100.0 * sum(next_pass) / count(*), 2) AS next_is_pass_pct,
       round(100.0 * sum(next_fail) / count(*), 2) AS next_is_fail_pct,
       round(avg(to_date(next_date::text, 'YYYYMMDD') - to_date(date_key::text, 'YYYYMMDD'))) AS avg_days_to_next
  FROM seq WHERE fail_count = 1 AND next_date IS NOT NULL;

-- name: Q8c Facilities with the most inspections in the period
SELECT fa.dba_name, fa.facility_group, count(*) AS inspections, sum(f.fail_count) AS fails
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) WHERE fa.facility_id_source = 'License' GROUP BY fa.facility_key, 1, 2
 ORDER BY inspections DESC LIMIT 10;
