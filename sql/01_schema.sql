-- Part C: PostgreSQL batch data warehouse (staging + dimensional model).
-- Selected model: FACT CONSTELLATION = star schema (FactInspection) + a second fact at Facility x Year grain
-- sharing the conformed DimFacility.  Grain of FactInspection: one completed inspection on one date.

DROP SCHEMA IF EXISTS staging CASCADE;
DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA staging;
CREATE SCHEMA dw;

-- ------------------------------------------------------------------ staging
CREATE TABLE staging.inspection_stg (
    inspection_id bigint, dba_name text, aka_name text, license_number text, facility_nk text, facility_id_source text,
    facility_type_clean text, facility_group text, risk_category text, risk_group text, address text, city text, state text, zip text,
    inspection_date date, inspection_type text, inspection_type_group text, results text, result_group text,
    is_completed boolean, is_failed_inspection int, violation_count numeric, has_violations numeric, high_violation_flag int,
    violation_band text, violation_codes text, latitude numeric, longitude numeric, latitude_band numeric, longitude_band numeric,
    geographic_area_group text, year int, quarter int, month int, day_of_week text, is_weekend boolean, season text,
    is_same_day_repeat boolean, is_extreme_violation_count boolean,
    batch_id int NOT NULL, reject_reason text, staged_at timestamptz DEFAULT now()
);

CREATE TABLE staging.load_audit (
    batch_id serial PRIMARY KEY, batch_label text, period_from date, period_to date,
    rows_staged int, rows_rejected int, rows_not_completed int, rows_loaded_fact int,
    new_facilities int, new_locations int, annual_rows_refreshed int,
    started_at timestamptz DEFAULT now(), finished_at timestamptz, status text DEFAULT 'running'
);

-- ------------------------------------------------------------------ dimensions
CREATE TABLE dw.dim_date (
    date_key int PRIMARY KEY, full_date date NOT NULL UNIQUE, day smallint, day_name text, month smallint, month_name text,
    quarter smallint, year smallint, is_weekend boolean, season text
);
CREATE TABLE dw.dim_facility (
    facility_key serial PRIMARY KEY, facility_nk text NOT NULL UNIQUE, license_number text, dba_name text,
    facility_type text, facility_group text, risk_category text, risk_group text, facility_id_source text,
    last_inspection_date date, created_batch int, updated_batch int
);
CREATE TABLE dw.dim_inspection_type (
    inspection_type_key serial PRIMARY KEY, inspection_type text NOT NULL UNIQUE, inspection_type_group text
);
CREATE TABLE dw.dim_result (
    result_key serial PRIMARY KEY, result text NOT NULL UNIQUE, result_group text, failure_flag smallint
);
CREATE TABLE dw.dim_location (
    location_key serial PRIMARY KEY, zip text, city text, latitude_band text, longitude_band text, geographic_area_group text,
    UNIQUE (zip, city, latitude_band, longitude_band, geographic_area_group)
);

-- explicit Unknown / Not Available members (key 0): used when a lookup finds nothing, so facts are never dropped
INSERT INTO dw.dim_facility (facility_key, facility_nk, dba_name, facility_type, facility_group, risk_category, risk_group, facility_id_source)
VALUES (0, 'UNKNOWN', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown');
INSERT INTO dw.dim_inspection_type (inspection_type_key, inspection_type, inspection_type_group) VALUES (0, 'Unknown', 'Other');
INSERT INTO dw.dim_result (result_key, result, result_group, failure_flag) VALUES (0, 'Unknown', 'Not Completed', 0);
INSERT INTO dw.dim_location (location_key, zip, city, latitude_band, longitude_band, geographic_area_group)
VALUES (0, 'Unknown', 'UNKNOWN', 'Unknown', 'Unknown', 'Unknown');

INSERT INTO dw.dim_date
SELECT to_char(d, 'YYYYMMDD')::int, d::date, extract(day FROM d), trim(to_char(d, 'Day')), extract(month FROM d), trim(to_char(d, 'Month')),
       extract(quarter FROM d), extract(year FROM d), extract(isodow FROM d) >= 6,
       CASE WHEN extract(month FROM d) IN (12,1,2) THEN 'Winter' WHEN extract(month FROM d) IN (3,4,5) THEN 'Spring'
            WHEN extract(month FROM d) IN (6,7,8) THEN 'Summer' ELSE 'Autumn' END
FROM generate_series('2022-01-01'::date, '2026-12-31'::date, '1 day') AS d;

-- ------------------------------------------------------------------ facts
CREATE TABLE dw.fact_inspection (
    inspection_key bigserial PRIMARY KEY,
    inspection_id bigint NOT NULL UNIQUE,                       -- degenerate dimension (source id)
    date_key int NOT NULL REFERENCES dw.dim_date,
    facility_key int NOT NULL REFERENCES dw.dim_facility,
    inspection_type_key int NOT NULL REFERENCES dw.dim_inspection_type,
    result_key int NOT NULL REFERENCES dw.dim_result,
    location_key int NOT NULL REFERENCES dw.dim_location,
    inspection_count smallint NOT NULL DEFAULT 1,
    violation_count smallint,                                   -- NULL = unknown (see data-quality report)
    fail_count smallint NOT NULL, pass_count smallint NOT NULL, conditional_pass_count smallint NOT NULL,
    high_violation_flag smallint NOT NULL,
    batch_id int NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dw.fact_facility_annual_inspection_performance (
    facility_key int NOT NULL REFERENCES dw.dim_facility,
    reporting_year smallint NOT NULL,                           -- degenerate time attribute (grain: facility x year)
    inspection_count int NOT NULL, fail_count int NOT NULL, pass_count int NOT NULL, conditional_pass_count int NOT NULL,
    violation_count int,                                        -- sum over inspections with a known count
    inspections_with_known_violations int NOT NULL,
    average_violations numeric(8,3), failure_rate numeric(6,4),
    batch_id int NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (facility_key, reporting_year)
);
