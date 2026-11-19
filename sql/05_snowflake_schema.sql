-- Snowflake design: the star dimensions are normalised along their hierarchies
-- (time: year > quarter > month > day; facility: group > type > facility, risk; location: area group, ZIP > location;
--  inspection type group > type; result group > result).  Built from the star dimensions so that the keys are identical.
DROP SCHEMA IF EXISTS snow CASCADE;
CREATE SCHEMA snow;

CREATE TABLE snow.dim_year    (year smallint PRIMARY KEY);
CREATE TABLE snow.dim_quarter (quarter_key serial PRIMARY KEY, year smallint REFERENCES snow.dim_year, quarter smallint, UNIQUE (year, quarter));
CREATE TABLE snow.dim_month   (month_key serial PRIMARY KEY, quarter_key int REFERENCES snow.dim_quarter, month smallint, month_name text, season text, UNIQUE (quarter_key, month));
CREATE TABLE snow.dim_date    (date_key int PRIMARY KEY, full_date date UNIQUE, day smallint, day_name text, is_weekend boolean, month_key int REFERENCES snow.dim_month);

CREATE TABLE snow.dim_facility_group (group_key serial PRIMARY KEY, facility_group text UNIQUE);
CREATE TABLE snow.dim_facility_type  (type_key serial PRIMARY KEY, facility_type text, group_key int REFERENCES snow.dim_facility_group, UNIQUE (facility_type, group_key));
CREATE TABLE snow.dim_risk           (risk_key serial PRIMARY KEY, risk_category text, risk_group text, UNIQUE (risk_category, risk_group));
CREATE TABLE snow.dim_facility       (facility_key int PRIMARY KEY, facility_nk text UNIQUE, license_number text, dba_name text,
                                      facility_id_source text, type_key int REFERENCES snow.dim_facility_type, risk_key int REFERENCES snow.dim_risk);

CREATE TABLE snow.dim_inspection_type_group (group_key serial PRIMARY KEY, inspection_type_group text UNIQUE);
CREATE TABLE snow.dim_inspection_type (inspection_type_key int PRIMARY KEY, inspection_type text, group_key int REFERENCES snow.dim_inspection_type_group);
CREATE TABLE snow.dim_result_group (group_key serial PRIMARY KEY, result_group text UNIQUE);
CREATE TABLE snow.dim_result (result_key int PRIMARY KEY, result text, failure_flag smallint, group_key int REFERENCES snow.dim_result_group);

CREATE TABLE snow.dim_area_group (area_key serial PRIMARY KEY, geographic_area_group text UNIQUE);
CREATE TABLE snow.dim_zip        (zip_key serial PRIMARY KEY, zip text, city text, UNIQUE (zip, city));
CREATE TABLE snow.dim_location   (location_key int PRIMARY KEY, zip_key int REFERENCES snow.dim_zip, area_key int REFERENCES snow.dim_area_group, latitude_band text, longitude_band text);

CREATE TABLE snow.fact_inspection (
    inspection_key bigint PRIMARY KEY, inspection_id bigint UNIQUE, date_key int REFERENCES snow.dim_date, facility_key int REFERENCES snow.dim_facility,
    inspection_type_key int REFERENCES snow.dim_inspection_type, result_key int REFERENCES snow.dim_result, location_key int REFERENCES snow.dim_location,
    inspection_count smallint, violation_count smallint, fail_count smallint, pass_count smallint, conditional_pass_count smallint, high_violation_flag smallint);

-- ---- populate from the star schema
INSERT INTO snow.dim_year SELECT DISTINCT year FROM dw.dim_date;
INSERT INTO snow.dim_quarter (year, quarter) SELECT DISTINCT year, quarter FROM dw.dim_date;
INSERT INTO snow.dim_month (quarter_key, month, month_name, season)
    SELECT DISTINCT q.quarter_key, d.month, d.month_name, d.season FROM dw.dim_date d JOIN snow.dim_quarter q ON q.year = d.year AND q.quarter = d.quarter;
INSERT INTO snow.dim_date SELECT d.date_key, d.full_date, d.day, d.day_name, d.is_weekend, m.month_key
    FROM dw.dim_date d JOIN snow.dim_quarter q ON q.year = d.year AND q.quarter = d.quarter JOIN snow.dim_month m ON m.quarter_key = q.quarter_key AND m.month = d.month;

INSERT INTO snow.dim_facility_group (facility_group) SELECT DISTINCT facility_group FROM dw.dim_facility;
INSERT INTO snow.dim_facility_type (facility_type, group_key)
    SELECT DISTINCT f.facility_type, g.group_key FROM dw.dim_facility f JOIN snow.dim_facility_group g ON g.facility_group = f.facility_group;
INSERT INTO snow.dim_risk (risk_category, risk_group) SELECT DISTINCT risk_category, risk_group FROM dw.dim_facility;
INSERT INTO snow.dim_facility
    SELECT f.facility_key, f.facility_nk, f.license_number, f.dba_name, f.facility_id_source, t.type_key, r.risk_key
      FROM dw.dim_facility f JOIN snow.dim_facility_group g ON g.facility_group = f.facility_group
      JOIN snow.dim_facility_type t ON t.facility_type = f.facility_type AND t.group_key = g.group_key
      JOIN snow.dim_risk r ON r.risk_category = f.risk_category AND r.risk_group = f.risk_group;

INSERT INTO snow.dim_inspection_type_group (inspection_type_group) SELECT DISTINCT inspection_type_group FROM dw.dim_inspection_type;
INSERT INTO snow.dim_inspection_type SELECT t.inspection_type_key, t.inspection_type, g.group_key
    FROM dw.dim_inspection_type t JOIN snow.dim_inspection_type_group g ON g.inspection_type_group = t.inspection_type_group;
INSERT INTO snow.dim_result_group (result_group) SELECT DISTINCT result_group FROM dw.dim_result;
INSERT INTO snow.dim_result SELECT r.result_key, r.result, r.failure_flag, g.group_key FROM dw.dim_result r JOIN snow.dim_result_group g ON g.result_group = r.result_group;

INSERT INTO snow.dim_area_group (geographic_area_group) SELECT DISTINCT geographic_area_group FROM dw.dim_location;
INSERT INTO snow.dim_zip (zip, city) SELECT DISTINCT zip, city FROM dw.dim_location;
INSERT INTO snow.dim_location SELECT l.location_key, z.zip_key, a.area_key, l.latitude_band, l.longitude_band
    FROM dw.dim_location l JOIN snow.dim_zip z ON z.zip = l.zip AND z.city = l.city JOIN snow.dim_area_group a ON a.geographic_area_group = l.geographic_area_group;

INSERT INTO snow.fact_inspection
    SELECT inspection_key, inspection_id, date_key, facility_key, inspection_type_key, result_key, location_key,
           inspection_count, violation_count, fail_count, pass_count, conditional_pass_count, high_violation_flag FROM dw.fact_inspection;

CREATE INDEX ON snow.fact_inspection (date_key);  CREATE INDEX ON snow.fact_inspection (facility_key);
CREATE INDEX ON snow.fact_inspection (inspection_type_key);  CREATE INDEX ON snow.fact_inspection (result_key);  CREATE INDEX ON snow.fact_inspection (location_key);
ANALYZE;
