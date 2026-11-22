-- Demo queries for the presentation. Open this file in pgAdmin (server localhost:5432, database foodsafety,
-- user/password foodsafety), select ONE query with the mouse and press F5. Every result is in the project guide.

-- D1. Part B: the tables of the warehouse (schema dw)
SELECT table_name FROM information_schema.tables WHERE table_schema = 'dw' ORDER BY table_name;

-- D2. Part B: a fact row is only keys and numbers
SELECT inspection_id, date_key, facility_key, inspection_type_key, result_key, location_key, violation_count, fail_count
FROM dw.fact_inspection ORDER BY inspection_id LIMIT 5;

-- D3. Part B: a dimension holds the words (row 0 = Unknown)
SELECT * FROM dw.dim_result ORDER BY result_key;

-- D4. Part C: the two loads (initial + incremental)
SELECT batch_id, batch_label, rows_staged, rows_not_completed, rows_loaded_fact, new_facilities
FROM staging.load_audit ORDER BY batch_id;

-- D5. Part C: the five checks (all must be 0)  -> open sql/04_validation.sql and run the whole file

-- D6. Part F: a star-schema query (fact JOIN dimension)
SELECT fa.facility_group, count(*) AS inspections, round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
GROUP BY fa.facility_group ORDER BY inspections DESC;

-- D7. Part F: roll-up (quarters -> year -> grand total)
SELECT coalesce(d.year::text, 'ALL') AS year, coalesce('Q' || d.quarter, 'ALL') AS quarter, count(*) AS inspections,
       round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
WHERE d.year = 2025
GROUP BY ROLLUP (d.year, d.quarter) ORDER BY d.year, d.quarter;

-- D8. Part F: slice (one year) and dice (year AND risk)
SELECT t.inspection_type_group, count(*) AS inspections, round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f
JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_inspection_type t USING (inspection_type_key)
WHERE d.year = 2025 AND fa.risk_group = 'High'
GROUP BY 1 ORDER BY 2 DESC;

-- D9. Part F: pivot (results become columns)
SELECT d.year,
       count(*) FILTER (WHERE r.result_group = 'Pass')             AS pass,
       count(*) FILTER (WHERE r.result_group = 'Conditional Pass') AS conditional,
       count(*) FILTER (WHERE r.result_group = 'Fail')             AS fail
FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_result r USING (result_key)
GROUP BY d.year ORDER BY d.year;

-- D10. Parts G-I: the analytics table the models read (each row remembers the previous inspection)
SELECT inspection_date, inspection_type, result_group, violation_count, prior_inspection_result, prior_violation_count, days_since_prior_inspection
FROM mart.food_inspection_analytics_mart WHERE facility = 'JERK MAN' ORDER BY inspection_date LIMIT 6;

-- Part D (Citus): connect pgAdmin to localhost:5440, database foodsafety_citus, user postgres (no password), then run:
--   SELECT nodename, nodeport, noderole, isactive FROM pg_dist_node;
--   SELECT table_name, citus_table_type, distribution_column, shard_count FROM citus_tables;
--   SELECT nodeport AS worker, count(*) AS shards, pg_size_pretty(sum(shard_size)) AS data
--   FROM citus_shards WHERE table_name = 'bench.fact_2000000_facility_key'::regclass GROUP BY nodeport;   -- 16 + 16 shards
