-- Referential-integrity validation and row/measure reconciliation. Every check must return 0 (or TRUE).
-- name | value
SELECT 'orphan date_key'            AS check_name, count(*)::bigint AS value FROM dw.fact_inspection f LEFT JOIN dw.dim_date d USING (date_key) WHERE d.date_key IS NULL
UNION ALL SELECT 'orphan facility_key',        count(*) FROM dw.fact_inspection f LEFT JOIN dw.dim_facility d USING (facility_key) WHERE d.facility_key IS NULL
UNION ALL SELECT 'orphan inspection_type_key', count(*) FROM dw.fact_inspection f LEFT JOIN dw.dim_inspection_type d USING (inspection_type_key) WHERE d.inspection_type_key IS NULL
UNION ALL SELECT 'orphan result_key',          count(*) FROM dw.fact_inspection f LEFT JOIN dw.dim_result d USING (result_key) WHERE d.result_key IS NULL
UNION ALL SELECT 'orphan location_key',        count(*) FROM dw.fact_inspection f LEFT JOIN dw.dim_location d USING (location_key) WHERE d.location_key IS NULL
UNION ALL SELECT 'orphan annual facility_key', count(*) FROM dw.fact_facility_annual_inspection_performance a LEFT JOIN dw.dim_facility d USING (facility_key) WHERE d.facility_key IS NULL
UNION ALL SELECT 'duplicate inspection_id in fact', count(*) - count(DISTINCT inspection_id) FROM dw.fact_inspection
UNION ALL SELECT 'facts mapped to Unknown facility (key 0)', count(*) FROM dw.fact_inspection WHERE facility_key = 0
UNION ALL SELECT 'facts mapped to Unknown location (key 0)', count(*) FROM dw.fact_inspection WHERE location_key = 0
UNION ALL SELECT 'staging completed rows not in fact', count(*) FROM staging.inspection_stg s
        WHERE s.reject_reason IS NULL AND s.is_completed AND NOT EXISTS (SELECT 1 FROM dw.fact_inspection f WHERE f.inspection_id = s.inspection_id)
UNION ALL SELECT 'fact rows not in staging', count(*) FROM dw.fact_inspection f
        WHERE NOT EXISTS (SELECT 1 FROM staging.inspection_stg s WHERE s.inspection_id = f.inspection_id)
UNION ALL SELECT 'violation_count difference staging vs fact',
        (SELECT coalesce(sum(violation_count), 0) FROM staging.inspection_stg WHERE reject_reason IS NULL AND is_completed)::bigint
      - (SELECT coalesce(sum(violation_count), 0) FROM dw.fact_inspection)::bigint
UNION ALL SELECT 'fail_count difference staging vs fact',
        (SELECT coalesce(sum(is_failed_inspection), 0) FROM staging.inspection_stg WHERE reject_reason IS NULL AND is_completed)::bigint
      - (SELECT coalesce(sum(fail_count), 0) FROM dw.fact_inspection)::bigint
UNION ALL SELECT 'annual fact inspections - fact rows',
        (SELECT coalesce(sum(inspection_count), 0) FROM dw.fact_facility_annual_inspection_performance)::bigint - (SELECT count(*) FROM dw.fact_inspection)
UNION ALL SELECT 'annual fact violations - fact violations',
        (SELECT coalesce(sum(violation_count), 0) FROM dw.fact_facility_annual_inspection_performance)::bigint - (SELECT coalesce(sum(violation_count), 0) FROM dw.fact_inspection)::bigint
UNION ALL SELECT 'batches where staged <> loaded + not_completed + rejected', count(*)
        FROM staging.load_audit WHERE rows_staged <> rows_loaded_fact + rows_not_completed + rows_rejected;
