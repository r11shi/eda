-- OLAP operations on the dw star schema (PostgreSQL). Cube hierarchies used in the dimensions:
--   Time: Year > Quarter > Month > Day        Location: Geographic Area Group / ZIP > Facility        Facility: Facility Group/Type > Risk Category > Establishment
-- Each block: question / dimensions / measures / operation / dax / sql / interpretation (filled in after the run).

-- ##### R1 Roll-up
-- question: How do the inspections and the failure rate of 2025 add up from month to quarter to year?
-- dimensions: DimDate (Month > Quarter > Year)
-- measures: InspectionCount, FailCount, FailureRate
-- operation: Roll-up (GROUP BY ROLLUP moves from the detailed level to the total)
-- dax: EVALUATE SUMMARIZECOLUMNS(DimDate[year], DimDate[quarter], DimDate[month], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
-- interpretation: The 16,052 inspections of 2025 roll up from 12 months into 4 quarters and one year (the grand total equals the year because the slice is 2025). Q1 was the busiest quarter (4,269) and Q4 the quietest (3,647). The failure rate is 21.13% for the year; quarters range from 20.4% to 22.2% and months from 18.6% (November) to 23.1% (August). Rolling up hides the monthly swings, which is why the monthly level is kept for monitoring.
SELECT d.year, d.quarter, d.month,
       CASE WHEN GROUPING(d.month) = 0 THEN 'month' WHEN GROUPING(d.quarter) = 0 THEN 'quarter' WHEN GROUPING(d.year) = 0 THEN 'year' ELSE 'grand total' END AS level,
       count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
 WHERE d.year = 2025
 GROUP BY ROLLUP (d.year, d.quarter, d.month)
 ORDER BY d.year, d.quarter, d.month;

-- ##### D1 Drill-down, step 1: facility group
-- question: Which facility groups have the most failures? (top of the hierarchy)
-- dimensions: DimFacility (Facility Group)
-- measures: InspectionCount, FailCount, FailureRate
-- operation: Drill-down, level 1 (Facility Group)
-- dax: EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_group], "Inspections", [InspectionCount], "Fails", [FailCount], "FailureRate", [FailureRate])
-- interpretation: Restaurants and food service have the most failures (9,876) simply because they have 43,080 of the 61,737 inspections. Their failure rate (22.9%) is lower than retail food and grocery (24.9%) and schools and childcare (23.7%). Mobile, catering and events has the lowest rate (16.5%). Counts and rates give different rankings, so the next drill-down follows the higher rate (retail).
SELECT fa.facility_group, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
 GROUP BY fa.facility_group ORDER BY fail_count DESC;

-- ##### D2 Drill-down, step 2: facility types inside Retail Food & Grocery
-- question: Inside "Retail Food & Grocery" (the group with the highest failure rate among the large groups), which facility types fail most?
-- dimensions: DimFacility (Facility Group > Facility Type)
-- measures: InspectionCount, FailCount, FailureRate
-- operation: Drill-down, level 2 (Facility Type), filtered to the group chosen in step 1 (Retail Food & Grocery: highest rate among the large groups)
-- dax: EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_type], FILTER(ALL(DimFacility[facility_group]), DimFacility[facility_group] = "Retail Food & Grocery"), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
-- interpretation: Inside retail food, Grocery Stores produce most failures (1,445 of 5,857 inspections, 24.7%), Bakeries fail 23.9% of the time, and Liquor stores have the highest rate (32.3%) on a smaller base of 226 inspections.
SELECT fa.facility_type, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
 WHERE fa.facility_group = 'Retail Food & Grocery'
 GROUP BY fa.facility_type HAVING count(*) >= 50 ORDER BY fail_count DESC LIMIT 8;

-- ##### D3 Drill-down, step 3: grocery stores (establishments)
-- question: Which individual grocery stores had the most failed inspections in 2025?
-- dimensions: DimFacility (Facility Type > Risk Category > Establishment), DimDate (Year)
-- measures: InspectionCount, FailCount, AverageViolations
-- operation: Drill-down, level 3 (Establishment)
-- dax: EVALUATE TOPN(10, SUMMARIZECOLUMNS(DimFacility[dba_name], DimFacility[license_number], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), FILTER(ALL(DimFacility[facility_type]), DimFacility[facility_type] = "Grocery Store"), "Fails", [FailCount], "Inspections", [InspectionCount]), [Fails], DESC)
-- interpretation: Among licensed grocery stores in 2025 the most-failed establishment failed 5 of its 11 inspections. Several stores failed 3 times. Establishment level is useful to pick repeat offenders for follow-up, but these counts are small, so a store should be reviewed rather than ranked on this alone.
SELECT fa.dba_name, fa.license_number, fa.risk_group, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(avg(f.violation_count), 1) AS avg_violations
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_date d USING (date_key)
 WHERE d.year = 2025 AND fa.facility_type = 'Grocery Store' AND fa.facility_id_source = 'License'
 GROUP BY fa.facility_key, fa.dba_name, fa.license_number, fa.risk_group ORDER BY fail_count DESC, inspection_count DESC LIMIT 10;

-- ##### S1 Slice
-- question: In 2025 only, how do the results differ between the facility groups?
-- dimensions: DimDate fixed to Year = 2025; DimFacility (Facility Group); DimResult (Result Group)
-- measures: InspectionCount, FailureRate
-- operation: Slice (one dimension fixed to a single value)
-- dax: EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_group], DimResult[result_group], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), "Inspections", [InspectionCount])
-- interpretation: Fixing the year to 2025: restaurants pass 63.0%, get a conditional pass 15.8% and fail 21.2%; retail food fails 23.3%; schools pass most often (71.7%) and fail 20.2%, with only 8.2% conditional passes.
SELECT fa.facility_group, r.result_group, count(*) AS inspection_count, round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY fa.facility_group), 1) AS pct_of_group
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key)
 WHERE d.year = 2025 AND fa.facility_group IN ('Restaurant & Food Service', 'Retail Food & Grocery', 'Schools & Childcare')
 GROUP BY fa.facility_group, r.result_group ORDER BY fa.facility_group, r.result_group;

-- ##### C1 Dice
-- question: For restaurants and retail food in the southern areas during 2024-2025, how does the failure rate change by quarter?
-- dimensions: DimDate (Year in 2024, 2025; Quarter), DimFacility (2 groups), DimLocation (Southeast, Southwest)
-- measures: InspectionCount, FailureRate
-- operation: Dice (several dimensions restricted to sets of values)
-- dax: EVALUATE SUMMARIZECOLUMNS(DimDate[year], DimDate[quarter], DimFacility[facility_group], FILTER(ALL(DimDate[year]), DimDate[year] IN {2024, 2025}), FILTER(ALL(DimFacility[facility_group]), DimFacility[facility_group] IN {"Restaurant & Food Service", "Retail Food & Grocery"}), FILTER(ALL(DimLocation[geographic_area_group]), DimLocation[geographic_area_group] IN {"Southeast", "Southwest"}), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
-- interpretation: For restaurants and retail food in the Southeast and Southwest in 2024-2025, the restaurant failure rate moved from 24.4% (Q1 2024) to 18.8% (Q4 2025). Retail food is higher than restaurants in 7 of the 8 quarters (for example 28.7% against 17.5% in Q2 2025), but its quarterly bases are small (146 to 316 inspections), so single quarters should be read with care.
SELECT d.year, d.quarter, fa.facility_group, count(*) AS inspection_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_location l USING (location_key)
 WHERE d.year IN (2024, 2025) AND fa.facility_group IN ('Restaurant & Food Service', 'Retail Food & Grocery') AND l.geographic_area_group IN ('Southeast', 'Southwest')
 GROUP BY d.year, d.quarter, fa.facility_group ORDER BY d.year, d.quarter, fa.facility_group;

-- ##### P1 Pivot
-- question: How are the three results distributed in each year (years as rows, results as columns)?
-- dimensions: DimDate (Year) on rows, DimResult (Result Group) on columns
-- measures: InspectionCount
-- operation: Pivot (rotate the result values into columns)
-- dax: a Matrix visual with DimDate[year] on Rows, DimResult[result_group] on Columns and [InspectionCount] as Values
-- interpretation: Pivoting the results into columns shows the trend by year: passes grew from 8,225 (2022) to 10,380 (2025), conditional passes stayed between 2,281 and 2,605 and failures fell from 3,553 to 3,391, so the failure rate dropped from 24.88% to 21.13%.
SELECT d.year,
       count(*) FILTER (WHERE r.result_group = 'Pass') AS pass,
       count(*) FILTER (WHERE r.result_group = 'Conditional Pass') AS conditional_pass,
       count(*) FILTER (WHERE r.result_group = 'Fail') AS fail,
       count(*) AS total,
       round(100.0 * count(*) FILTER (WHERE r.result_group = 'Fail') / count(*), 2) AS fail_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_result r USING (result_key)
 GROUP BY d.year ORDER BY d.year;

-- ##### G1 SQL CUBE
-- question: What are the inspection counts for every combination of Month, Facility Group and Result Group, including all sub-totals?
-- dimensions: DimDate (Month), DimFacility (Facility Group), DimResult (Result Group)
-- measures: InspectionCount
-- operation: SQL CUBE (all 8 grouping combinations of the three dimensions). Only the rows that aggregate over all months are shown.
-- dax: not available as one statement; the same numbers come from a Matrix visual with the three fields and "show subtotals" turned on
-- interpretation: The CUBE gives every sub-total in one query: 61,737 inspections in total (grouping id 7). Restaurants and food service have 25,668 passes, 7,536 conditional passes and 9,876 fails (43,080 in total, id 5 and 4 rows); schools and childcare have 5,832, 741 and 2,036 (8,609). The same statement also produces the month-level rows (not shown here).
SELECT coalesce(d.month::text, 'ALL months') AS month, coalesce(fa.facility_group, 'ALL groups') AS facility_group, coalesce(r.result_group, 'ALL results') AS result_group,
       count(*) AS inspection_count, GROUPING(d.month, fa.facility_group, r.result_group) AS grouping_id
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key)
 GROUP BY CUBE (d.month, fa.facility_group, r.result_group)
HAVING GROUPING(d.month) = 1 AND fa.facility_group IN ('Restaurant & Food Service', 'Schools & Childcare') OR GROUPING(d.month, fa.facility_group, r.result_group) = 7
 ORDER BY grouping_id, facility_group, result_group;

-- ##### G2 GROUPING SETS
-- question: Give one report with the total, the total per year, the total per facility group and the total per year and facility group.
-- dimensions: DimDate (Year), DimFacility (Facility Group)
-- measures: InspectionCount, FailureRate
-- operation: GROUPING SETS (only the chosen groupings, no full cube)
-- dax: not available as one statement; use a Matrix visual with subtotals
-- interpretation: One report with four levels of totals. For the three selected groups the all-years failure rate is 22.92% (restaurants), 24.86% (retail) and 23.65% (schools), and 23.27% together (58,821 inspections). Retail food jumped to 27.96% in 2023, and schools were the lowest in 2025 (20.16%).
SELECT coalesce(d.year::text, 'ALL years') AS year, coalesce(fa.facility_group, 'ALL 3 selected groups') AS facility_group, count(*) AS inspection_count,
       round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
 WHERE fa.facility_group IN ('Restaurant & Food Service', 'Schools & Childcare', 'Retail Food & Grocery')
 GROUP BY GROUPING SETS ((d.year, fa.facility_group), (d.year), (fa.facility_group), ())
 ORDER BY d.year NULLS LAST, fa.facility_group NULLS LAST;
