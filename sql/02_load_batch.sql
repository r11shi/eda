-- ETL: staging -> data-quality rules -> dimension lookups / inserts -> fact load -> annual fact -> validation counts.
-- The same procedure is used for the initial load and for the incremental load.
CREATE OR REPLACE PROCEDURE dw.load_batch(p_batch int)
LANGUAGE plpgsql AS $$
DECLARE
    v_staged int; v_rejected int; v_notcomp int; v_fact int; v_newfac int; v_newloc int; v_annual int; v_before int;
BEGIN
    SELECT count(*) INTO v_staged FROM staging.inspection_stg WHERE batch_id = p_batch;

    -- 1. data-quality rules
    UPDATE staging.inspection_stg SET reject_reason = 'missing inspection_id or inspection_date'
     WHERE batch_id = p_batch AND (inspection_id IS NULL OR inspection_date IS NULL);
    UPDATE staging.inspection_stg s SET reject_reason = 'date not in dim_date'
     WHERE batch_id = p_batch AND reject_reason IS NULL AND NOT EXISTS (SELECT 1 FROM dw.dim_date d WHERE d.full_date = s.inspection_date);
    UPDATE staging.inspection_stg s SET reject_reason = 'already loaded (inspection_id exists in fact)'
     WHERE batch_id = p_batch AND reject_reason IS NULL AND EXISTS (SELECT 1 FROM dw.fact_inspection f WHERE f.inspection_id = s.inspection_id);
    SELECT count(*) INTO v_rejected FROM staging.inspection_stg WHERE batch_id = p_batch AND reject_reason IS NOT NULL;
    SELECT count(*) INTO v_notcomp FROM staging.inspection_stg WHERE batch_id = p_batch AND reject_reason IS NULL AND NOT is_completed;

    -- 2. dimensions: insert new members (completed inspections only)
    INSERT INTO dw.dim_inspection_type (inspection_type, inspection_type_group)
    SELECT DISTINCT s.inspection_type, s.inspection_type_group FROM staging.inspection_stg s
     WHERE s.batch_id = p_batch AND s.reject_reason IS NULL AND s.is_completed
    ON CONFLICT (inspection_type) DO NOTHING;

    INSERT INTO dw.dim_result (result, result_group, failure_flag)
    SELECT DISTINCT s.results, s.result_group, s.is_failed_inspection FROM staging.inspection_stg s
     WHERE s.batch_id = p_batch AND s.reject_reason IS NULL AND s.is_completed
    ON CONFLICT (result) DO NOTHING;

    SELECT count(*) INTO v_before FROM dw.dim_location;
    INSERT INTO dw.dim_location (zip, city, latitude_band, longitude_band, geographic_area_group)
    SELECT DISTINCT coalesce(s.zip, 'Unknown'), coalesce(s.city, 'UNKNOWN'), coalesce(s.latitude_band::text, 'Unknown'),
           coalesce(s.longitude_band::text, 'Unknown'), s.geographic_area_group
      FROM staging.inspection_stg s WHERE s.batch_id = p_batch AND s.reject_reason IS NULL AND s.is_completed
    ON CONFLICT (zip, city, latitude_band, longitude_band, geographic_area_group) DO NOTHING;
    SELECT count(*) - v_before INTO v_newloc FROM dw.dim_location;

    SELECT count(*) INTO v_before FROM dw.dim_facility;
    INSERT INTO dw.dim_facility (facility_nk, license_number, dba_name, facility_type, facility_group, risk_category, risk_group,
                                 facility_id_source, last_inspection_date, created_batch, updated_batch)
    SELECT DISTINCT ON (s.facility_nk) s.facility_nk, s.license_number, s.dba_name, s.facility_type_clean, s.facility_group,
           s.risk_category, s.risk_group, s.facility_id_source, s.inspection_date, p_batch, p_batch
      FROM staging.inspection_stg s WHERE s.batch_id = p_batch AND s.reject_reason IS NULL AND s.is_completed
     ORDER BY s.facility_nk, s.inspection_date DESC, s.inspection_id DESC
    ON CONFLICT (facility_nk) DO NOTHING;
    SELECT count(*) - v_before INTO v_newfac FROM dw.dim_facility;

    -- existing facilities: Type-1 update (latest inspection wins) when an attribute changed
    UPDATE dw.dim_facility f SET dba_name = l.dba_name, facility_type = l.facility_type_clean, facility_group = l.facility_group,
           risk_category = l.risk_category, risk_group = l.risk_group, last_inspection_date = l.inspection_date, updated_batch = p_batch
      FROM (SELECT DISTINCT ON (facility_nk) * FROM staging.inspection_stg
             WHERE batch_id = p_batch AND reject_reason IS NULL AND is_completed
             ORDER BY facility_nk, inspection_date DESC, inspection_id DESC) l
     WHERE f.facility_nk = l.facility_nk AND l.inspection_date >= coalesce(f.last_inspection_date, '1900-01-01')
       AND (f.dba_name, f.facility_type, f.facility_group, f.risk_category) IS DISTINCT FROM
           (l.dba_name, l.facility_type_clean, l.facility_group, l.risk_category);

    -- 3. fact load (dimension lookups on natural keys; unknown member 0 when no match)
    INSERT INTO dw.fact_inspection (inspection_id, date_key, facility_key, inspection_type_key, result_key, location_key,
                                    violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag, batch_id)
    SELECT s.inspection_id, d.date_key, coalesce(f.facility_key, 0), coalesce(t.inspection_type_key, 0), coalesce(r.result_key, 0),
           coalesce(l.location_key, 0), s.violation_count::smallint,
           (s.results = 'Fail')::int, (s.results = 'Pass')::int, (s.results = 'Pass w/ Conditions')::int, s.high_violation_flag, p_batch
      FROM staging.inspection_stg s
      JOIN dw.dim_date d ON d.full_date = s.inspection_date
      LEFT JOIN dw.dim_facility f ON f.facility_nk = s.facility_nk
      LEFT JOIN dw.dim_inspection_type t ON t.inspection_type = s.inspection_type
      LEFT JOIN dw.dim_result r ON r.result = s.results
      LEFT JOIN dw.dim_location l ON l.zip = coalesce(s.zip, 'Unknown') AND l.city = coalesce(s.city, 'UNKNOWN')
           AND l.latitude_band = coalesce(s.latitude_band::text, 'Unknown') AND l.longitude_band = coalesce(s.longitude_band::text, 'Unknown')
           AND l.geographic_area_group = s.geographic_area_group
     WHERE s.batch_id = p_batch AND s.reject_reason IS NULL AND s.is_completed
    ON CONFLICT (inspection_id) DO NOTHING;
    GET DIAGNOSTICS v_fact = ROW_COUNT;

    -- 4. second fact (grain: facility x reporting year): rebuild the years touched by this batch
    DELETE FROM dw.fact_facility_annual_inspection_performance
     WHERE reporting_year IN (SELECT DISTINCT year FROM staging.inspection_stg WHERE batch_id = p_batch AND reject_reason IS NULL AND is_completed);
    INSERT INTO dw.fact_facility_annual_inspection_performance
    SELECT f.facility_key, d.year, sum(f.inspection_count), sum(f.fail_count), sum(f.pass_count), sum(f.conditional_pass_count),
           sum(f.violation_count), count(f.violation_count),
           round(avg(f.violation_count), 3), round(sum(f.fail_count)::numeric / sum(f.inspection_count), 4), p_batch, now()
      FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
     WHERE d.year IN (SELECT DISTINCT year FROM staging.inspection_stg WHERE batch_id = p_batch AND reject_reason IS NULL AND is_completed)
     GROUP BY f.facility_key, d.year;
    GET DIAGNOSTICS v_annual = ROW_COUNT;

    UPDATE staging.load_audit SET rows_staged = v_staged, rows_rejected = v_rejected, rows_not_completed = v_notcomp,
           rows_loaded_fact = v_fact, new_facilities = v_newfac, new_locations = v_newloc, annual_rows_refreshed = v_annual,
           finished_at = now(), status = 'loaded' WHERE batch_id = p_batch;
END $$;
