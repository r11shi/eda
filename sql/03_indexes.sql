-- Indexes created after the initial bulk load (faster load, then faster analytics).
CREATE INDEX IF NOT EXISTS ix_fact_date        ON dw.fact_inspection (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_facility    ON dw.fact_inspection (facility_key);
CREATE INDEX IF NOT EXISTS ix_fact_insptype    ON dw.fact_inspection (inspection_type_key);
CREATE INDEX IF NOT EXISTS ix_fact_result      ON dw.fact_inspection (result_key);
CREATE INDEX IF NOT EXISTS ix_fact_location    ON dw.fact_inspection (location_key);
CREATE INDEX IF NOT EXISTS ix_fact_batch       ON dw.fact_inspection (batch_id);
CREATE INDEX IF NOT EXISTS ix_dimdate_ym       ON dw.dim_date (year, month);
CREATE INDEX IF NOT EXISTS ix_dimfac_group     ON dw.dim_facility (facility_group, risk_group);
CREATE INDEX IF NOT EXISTS ix_dimloc_zip       ON dw.dim_location (zip);
CREATE INDEX IF NOT EXISTS ix_annual_year      ON dw.fact_facility_annual_inspection_performance (reporting_year);
ANALYZE;
