# Part F: OLAP Cube Operations (PostgreSQL)

The OLAP layer is the dimensional model in schema `dw`. Hierarchies: **Time** Year > Quarter > Month > Day; **Location** Geographic Area Group / ZIP > Facility; **Facility** Facility Type > Risk Category > Establishment. Every SQL query below was executed and its output is shown. The DAX versions are given for Power BI; Power BI Desktop is not available in this environment, so **the DAX was not executed**.

Core measures (SQL and DAX):

| Measure | SQL | DAX |
|---|---|---|
| InspectionCount | `sum(inspection_count)` | `SUM(FactInspection[inspection_count])` |
| ViolationCount | `sum(violation_count)` | `SUM(FactInspection[violation_count])` |
| FailCount / PassCount / ConditionalPassCount | `sum(fail_count)` etc. | `SUM(FactInspection[fail_count])` etc. |
| HighViolationFlag (count of high-violation inspections) | `sum(high_violation_flag)` | `SUM(FactInspection[high_violation_flag])` |
| AverageViolations | `avg(violation_count)` | `AVERAGE(FactInspection[violation_count])` |
| FailureRate | `sum(fail_count) / sum(inspection_count)` | `DIVIDE([FailCount], [InspectionCount])` |

Note: the warehouse uses the **latest** attributes of each facility (Type-1 dimension), so group totals differ slightly from the EDA, which used the attributes recorded at each inspection (for example 43,080 against 43,057 restaurant inspections).

## R1 Roll-up

* **Business question:** How do the inspections and the failure rate of 2025 add up from month to quarter to year?
* **Dimensions:** DimDate (Month > Quarter > Year)
* **Measure:** InspectionCount, FailCount, FailureRate
* **OLAP operation:** Roll-up (GROUP BY ROLLUP moves from the detailed level to the total)

**SQL:**
```sql
SELECT d.year, d.quarter, d.month,
       CASE WHEN GROUPING(d.month) = 0 THEN 'month' WHEN GROUPING(d.quarter) = 0 THEN 'quarter' WHEN GROUPING(d.year) = 0 THEN 'year' ELSE 'grand total' END AS level,
       count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
 WHERE d.year = 2025
 GROUP BY ROLLUP (d.year, d.quarter, d.month)
 ORDER BY d.year, d.quarter, d.month;
```

**DAX:**
```
EVALUATE SUMMARIZECOLUMNS(DimDate[year], DimDate[quarter], DimDate[month], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
```

**Output:**

| year | quarter | month | level | inspection_count | fail_count | failure_rate_pct |
|---|---|---|---|---|---|---|
| 2025 | 1 | 1 | month | 1388 | 310 | 22.33 |
| 2025 | 1 | 2 | month | 1308 | 281 | 21.48 |
| 2025 | 1 | 3 | month | 1573 | 322 | 20.47 |
| 2025 | 1 |  | quarter | 4269 | 913 | 21.39 |
| 2025 | 2 | 4 | month | 1624 | 305 | 18.78 |
| 2025 | 2 | 5 | month | 1394 | 313 | 22.45 |
| 2025 | 2 | 6 | month | 1228 | 252 | 20.52 |
| 2025 | 2 |  | quarter | 4246 | 870 | 20.49 |
| 2025 | 3 | 7 | month | 1367 | 293 | 21.43 |
| 2025 | 3 | 8 | month | 1225 | 283 | 23.10 |
| 2025 | 3 | 9 | month | 1298 | 287 | 22.11 |
| 2025 | 3 |  | quarter | 3890 | 863 | 22.19 |
| 2025 | 4 | 10 | month | 1400 | 316 | 22.57 |
| 2025 | 4 | 11 | month | 1118 | 208 | 18.60 |
| 2025 | 4 | 12 | month | 1129 | 221 | 19.57 |
| 2025 | 4 |  | quarter | 3647 | 745 | 20.43 |
| 2025 |  |  | year | 16052 | 3391 | 21.13 |
|  |  |  | grand total | 16052 | 3391 | 21.13 |

**Interpretation:** The 16,052 inspections of 2025 roll up from 12 months into 4 quarters and one year (the grand total equals the year because the slice is 2025). Q1 was the busiest quarter (4,269) and Q4 the quietest (3,647). The failure rate is 21.13% for the year; quarters range from 20.4% to 22.2% and months from 18.6% (November) to 23.1% (August). Rolling up hides the monthly swings, which is why the monthly level is kept for monitoring.

## D1 Drill-down, step 1: facility group

* **Business question:** Which facility groups have the most failures? (top of the hierarchy)
* **Dimensions:** DimFacility (Facility Group)
* **Measure:** InspectionCount, FailCount, FailureRate
* **OLAP operation:** Drill-down, level 1 (Facility Group)

**SQL:**
```sql
SELECT fa.facility_group, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
 GROUP BY fa.facility_group ORDER BY fail_count DESC;
```

**DAX:**
```
EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_group], "Inspections", [InspectionCount], "Fails", [FailCount], "FailureRate", [FailureRate])
```

**Output:**

| facility_group | inspection_count | fail_count | failure_rate_pct |
|---|---|---|---|
| Restaurant & Food Service | 43080 | 9876 | 22.92 |
| Schools & Childcare | 8609 | 2036 | 23.65 |
| Retail Food & Grocery | 7132 | 1773 | 24.86 |
| Healthcare & Residential Care | 1303 | 299 | 22.95 |
| Mobile, Catering & Events | 1510 | 249 | 16.49 |
| Unknown | 87 | 22 | 25.29 |
| Other | 16 | 5 | 31.25 |

**Interpretation:** Restaurants and food service have the most failures (9,876) simply because they have 43,080 of the 61,737 inspections. Their failure rate (22.9%) is lower than retail food and grocery (24.9%) and schools and childcare (23.7%). Mobile, catering and events has the lowest rate (16.5%). Counts and rates give different rankings, so the next drill-down follows the higher rate (retail).

## D2 Drill-down, step 2: facility types inside Retail Food & Grocery

* **Business question:** Inside "Retail Food & Grocery" (the group with the highest failure rate among the large groups), which facility types fail most?
* **Dimensions:** DimFacility (Facility Group > Facility Type)
* **Measure:** InspectionCount, FailCount, FailureRate
* **OLAP operation:** Drill-down, level 2 (Facility Type), filtered to the group chosen in step 1 (Retail Food & Grocery: highest rate among the large groups)

**SQL:**
```sql
SELECT fa.facility_type, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
 WHERE fa.facility_group = 'Retail Food & Grocery'
 GROUP BY fa.facility_type HAVING count(*) >= 50 ORDER BY fail_count DESC LIMIT 8;
```

**DAX:**
```
EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_type], FILTER(ALL(DimFacility[facility_group]), DimFacility[facility_group] = "Retail Food & Grocery"), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
```

**Output:**

| facility_type | inspection_count | fail_count | failure_rate_pct |
|---|---|---|---|
| Grocery Store | 5857 | 1445 | 24.67 |
| Bakery | 847 | 202 | 23.85 |
| Liquor | 226 | 73 | 32.30 |

**Interpretation:** Inside retail food, Grocery Stores produce most failures (1,445 of 5,857 inspections, 24.7%), Bakeries fail 23.9% of the time, and Liquor stores have the highest rate (32.3%) on a smaller base of 226 inspections.

## D3 Drill-down, step 3: grocery stores (establishments)

* **Business question:** Which individual grocery stores had the most failed inspections in 2025?
* **Dimensions:** DimFacility (Facility Type > Risk Category > Establishment), DimDate (Year)
* **Measure:** InspectionCount, FailCount, AverageViolations
* **OLAP operation:** Drill-down, level 3 (Establishment)

**SQL:**
```sql
SELECT fa.dba_name, fa.license_number, fa.risk_group, count(*) AS inspection_count, sum(f.fail_count) AS fail_count, round(avg(f.violation_count), 1) AS avg_violations
  FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_date d USING (date_key)
 WHERE d.year = 2025 AND fa.facility_type = 'Grocery Store' AND fa.facility_id_source = 'License'
 GROUP BY fa.facility_key, fa.dba_name, fa.license_number, fa.risk_group ORDER BY fail_count DESC, inspection_count DESC LIMIT 10;
```

**DAX:**
```
EVALUATE TOPN(10, SUMMARIZECOLUMNS(DimFacility[dba_name], DimFacility[license_number], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), FILTER(ALL(DimFacility[facility_type]), DimFacility[facility_type] = "Grocery Store"), "Fails", [FailCount], "Inspections", [InspectionCount]), [Fails], DESC)
```

**Output:**

| dba_name | license_number | risk_group | inspection_count | fail_count | avg_violations |
|---|---|---|---|---|---|
| MARIANO'S #8527 UKRANIAN VILLAGE | 2307748 | High | 11 | 5 | 6.6 |
| SEAFOOD CITY SUPERMARKET/GRILL CITY/CRISPY TOWN/NO | 2469807 | High | 8 | 3 | 2.4 |
| Food 4 Less #570 | 1928152 | High | 5 | 3 | 7.4 |
| FOODSMART | 2906119 | Medium | 5 | 3 | 6.0 |
| MOHSEN FOOD MART INC | 2891013 | Medium | 4 | 3 | 3.3 |
| GREEN LINE FOOD MART | 2500876 | High | 4 | 3 | 3.0 |
| MARIANO'S #8538 | 2446998 | High | 7 | 2 | 2.9 |
| TASTY SPOT FOOD & GRILL ON 67, INC. | 2868256 | High | 5 | 2 | 9.2 |
| EL PROGRESSO | 2924421 | High | 5 | 2 | 5.6 |
| CERMAK FRESH MARKET | 2451427 | High | 4 | 2 | 2.3 |

**Interpretation:** Among licensed grocery stores in 2025 the most-failed establishment failed 5 of its 11 inspections. Several stores failed 3 times. Establishment level is useful to pick repeat offenders for follow-up, but these counts are small, so a store should be reviewed rather than ranked on this alone.

## S1 Slice

* **Business question:** In 2025 only, how do the results differ between the facility groups?
* **Dimensions:** DimDate fixed to Year = 2025; DimFacility (Facility Group); DimResult (Result Group)
* **Measure:** InspectionCount, FailureRate
* **OLAP operation:** Slice (one dimension fixed to a single value)

**SQL:**
```sql
SELECT fa.facility_group, r.result_group, count(*) AS inspection_count, round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY fa.facility_group), 1) AS pct_of_group
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key)
 WHERE d.year = 2025 AND fa.facility_group IN ('Restaurant & Food Service', 'Retail Food & Grocery', 'Schools & Childcare')
 GROUP BY fa.facility_group, r.result_group ORDER BY fa.facility_group, r.result_group;
```

**DAX:**
```
EVALUATE SUMMARIZECOLUMNS(DimFacility[facility_group], DimResult[result_group], FILTER(ALL(DimDate[year]), DimDate[year] = 2025), "Inspections", [InspectionCount])
```

**Output:**

| facility_group | result_group | inspection_count | pct_of_group |
|---|---|---|---|
| Restaurant & Food Service | Conditional Pass | 1812 | 15.8 |
| Restaurant & Food Service | Fail | 2429 | 21.2 |
| Restaurant & Food Service | Pass | 7221 | 63.0 |
| Retail Food & Grocery | Conditional Pass | 223 | 12.8 |
| Retail Food & Grocery | Fail | 407 | 23.3 |
| Retail Food & Grocery | Pass | 1118 | 64.0 |
| Schools & Childcare | Conditional Pass | 172 | 8.2 |
| Schools & Childcare | Fail | 424 | 20.2 |
| Schools & Childcare | Pass | 1507 | 71.7 |

**Interpretation:** Fixing the year to 2025: restaurants pass 63.0%, get a conditional pass 15.8% and fail 21.2%; retail food fails 23.3%; schools pass most often (71.7%) and fail 20.2%, with only 8.2% conditional passes.

## C1 Dice

* **Business question:** For restaurants and retail food in the southern areas during 2024-2025, how does the failure rate change by quarter?
* **Dimensions:** DimDate (Year in 2024, 2025; Quarter), DimFacility (2 groups), DimLocation (Southeast, Southwest)
* **Measure:** InspectionCount, FailureRate
* **OLAP operation:** Dice (several dimensions restricted to sets of values)

**SQL:**
```sql
SELECT d.year, d.quarter, fa.facility_group, count(*) AS inspection_count, round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_location l USING (location_key)
 WHERE d.year IN (2024, 2025) AND fa.facility_group IN ('Restaurant & Food Service', 'Retail Food & Grocery') AND l.geographic_area_group IN ('Southeast', 'Southwest')
 GROUP BY d.year, d.quarter, fa.facility_group ORDER BY d.year, d.quarter, fa.facility_group;
```

**DAX:**
```
EVALUATE SUMMARIZECOLUMNS(DimDate[year], DimDate[quarter], DimFacility[facility_group], FILTER(ALL(DimDate[year]), DimDate[year] IN {2024, 2025}), FILTER(ALL(DimFacility[facility_group]), DimFacility[facility_group] IN {"Restaurant & Food Service", "Retail Food & Grocery"}), FILTER(ALL(DimLocation[geographic_area_group]), DimLocation[geographic_area_group] IN {"Southeast", "Southwest"}), "Inspections", [InspectionCount], "FailureRate", [FailureRate])
```

**Output:**

| year | quarter | facility_group | inspection_count | failure_rate_pct |
|---|---|---|---|---|
| 2024 | 1 | Restaurant & Food Service | 1158 | 24.35 |
| 2024 | 1 | Retail Food & Grocery | 173 | 31.79 |
| 2024 | 2 | Restaurant & Food Service | 1192 | 23.57 |
| 2024 | 2 | Retail Food & Grocery | 192 | 27.08 |
| 2024 | 3 | Restaurant & Food Service | 877 | 23.26 |
| 2024 | 3 | Retail Food & Grocery | 209 | 27.75 |
| 2024 | 4 | Restaurant & Food Service | 1091 | 18.61 |
| 2024 | 4 | Retail Food & Grocery | 316 | 21.20 |
| 2025 | 1 | Restaurant & Food Service | 1134 | 20.02 |
| 2025 | 1 | Retail Food & Grocery | 146 | 28.08 |
| 2025 | 2 | Restaurant & Food Service | 1041 | 17.48 |
| 2025 | 2 | Retail Food & Grocery | 237 | 28.69 |
| 2025 | 3 | Restaurant & Food Service | 980 | 21.94 |
| 2025 | 3 | Retail Food & Grocery | 201 | 21.89 |
| 2025 | 4 | Restaurant & Food Service | 1075 | 18.79 |
| 2025 | 4 | Retail Food & Grocery | 259 | 19.31 |

**Interpretation:** For restaurants and retail food in the Southeast and Southwest in 2024-2025, the restaurant failure rate moved from 24.4% (Q1 2024) to 18.8% (Q4 2025). Retail food is higher than restaurants in 7 of the 8 quarters (for example 28.7% against 17.5% in Q2 2025), but its quarterly bases are small (146 to 316 inspections), so single quarters should be read with care.

## P1 Pivot

* **Business question:** How are the three results distributed in each year (years as rows, results as columns)?
* **Dimensions:** DimDate (Year) on rows, DimResult (Result Group) on columns
* **Measure:** InspectionCount
* **OLAP operation:** Pivot (rotate the result values into columns)

**SQL:**
```sql
SELECT d.year,
       count(*) FILTER (WHERE r.result_group = 'Pass') AS pass,
       count(*) FILTER (WHERE r.result_group = 'Conditional Pass') AS conditional_pass,
       count(*) FILTER (WHERE r.result_group = 'Fail') AS fail,
       count(*) AS total,
       round(100.0 * count(*) FILTER (WHERE r.result_group = 'Fail') / count(*), 2) AS fail_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_result r USING (result_key)
 GROUP BY d.year ORDER BY d.year;
```

**DAX:**
```
a Matrix visual with DimDate[year] on Rows, DimResult[result_group] on Columns and [InspectionCount] as Values
```

**Output:**

| year | pass | conditional_pass | fail | total | fail_rate_pct |
|---|---|---|---|---|---|
| 2022 | 8225 | 2503 | 3553 | 14281 | 24.88 |
| 2023 | 9223 | 2354 | 3835 | 15412 | 24.88 |
| 2024 | 9906 | 2605 | 3481 | 15992 | 21.77 |
| 2025 | 10380 | 2281 | 3391 | 16052 | 21.13 |

**Interpretation:** Pivoting the results into columns shows the trend by year: passes grew from 8,225 (2022) to 10,380 (2025), conditional passes stayed between 2,281 and 2,605 and failures fell from 3,553 to 3,391, so the failure rate dropped from 24.88% to 21.13%.

## G1 SQL CUBE

* **Business question:** What are the inspection counts for every combination of Month, Facility Group and Result Group, including all sub-totals?
* **Dimensions:** DimDate (Month), DimFacility (Facility Group), DimResult (Result Group)
* **Measure:** InspectionCount
* **OLAP operation:** SQL CUBE (all 8 grouping combinations of the three dimensions). Only the rows that aggregate over all months are shown.

**SQL:**
```sql
SELECT coalesce(d.month::text, 'ALL months') AS month, coalesce(fa.facility_group, 'ALL groups') AS facility_group, coalesce(r.result_group, 'ALL results') AS result_group,
       count(*) AS inspection_count, GROUPING(d.month, fa.facility_group, r.result_group) AS grouping_id
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key) JOIN dw.dim_result r USING (result_key)
 GROUP BY CUBE (d.month, fa.facility_group, r.result_group)
HAVING GROUPING(d.month) = 1 AND fa.facility_group IN ('Restaurant & Food Service', 'Schools & Childcare') OR GROUPING(d.month, fa.facility_group, r.result_group) = 7
 ORDER BY grouping_id, facility_group, result_group;
```

**DAX:**
```
not available as one statement; the same numbers come from a Matrix visual with the three fields and "show subtotals" turned on
```

**Output:**

| month | facility_group | result_group | inspection_count | grouping_id |
|---|---|---|---|---|
| ALL months | Restaurant & Food Service | Conditional Pass | 7536 | 4 |
| ALL months | Restaurant & Food Service | Fail | 9876 | 4 |
| ALL months | Restaurant & Food Service | Pass | 25668 | 4 |
| ALL months | Schools & Childcare | Conditional Pass | 741 | 4 |
| ALL months | Schools & Childcare | Fail | 2036 | 4 |
| ALL months | Schools & Childcare | Pass | 5832 | 4 |
| ALL months | Restaurant & Food Service | ALL results | 43080 | 5 |
| ALL months | Schools & Childcare | ALL results | 8609 | 5 |
| ALL months | ALL groups | ALL results | 61737 | 7 |

**Interpretation:** The CUBE gives every sub-total in one query: 61,737 inspections in total (grouping id 7). Restaurants and food service have 25,668 passes, 7,536 conditional passes and 9,876 fails (43,080 in total, id 5 and 4 rows); schools and childcare have 5,832, 741 and 2,036 (8,609). The same statement also produces the month-level rows (not shown here).

## G2 GROUPING SETS

* **Business question:** Give one report with the total, the total per year, the total per facility group and the total per year and facility group.
* **Dimensions:** DimDate (Year), DimFacility (Facility Group)
* **Measure:** InspectionCount, FailureRate
* **OLAP operation:** GROUPING SETS (only the chosen groupings, no full cube)

**SQL:**
```sql
SELECT coalesce(d.year::text, 'ALL years') AS year, coalesce(fa.facility_group, 'ALL 3 selected groups') AS facility_group, count(*) AS inspection_count,
       round(100.0 * sum(f.fail_count) / count(*), 2) AS failure_rate_pct
  FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
 WHERE fa.facility_group IN ('Restaurant & Food Service', 'Schools & Childcare', 'Retail Food & Grocery')
 GROUP BY GROUPING SETS ((d.year, fa.facility_group), (d.year), (fa.facility_group), ())
 ORDER BY d.year NULLS LAST, fa.facility_group NULLS LAST;
```

**DAX:**
```
not available as one statement; use a Matrix visual with subtotals
```

**Output:**

| year | facility_group | inspection_count | failure_rate_pct |
|---|---|---|---|
| 2022 | Restaurant & Food Service | 9870 | 24.96 |
| 2022 | Retail Food & Grocery | 1700 | 25.06 |
| 2022 | Schools & Childcare | 2037 | 25.72 |
| 2022 | ALL 3 selected groups | 13607 | 25.09 |
| 2023 | Restaurant & Food Service | 10555 | 24.37 |
| 2023 | Retail Food & Grocery | 1799 | 27.96 |
| 2023 | Schools & Childcare | 2304 | 25.87 |
| 2023 | ALL 3 selected groups | 14658 | 25.04 |
| 2024 | Restaurant & Food Service | 11193 | 21.54 |
| 2024 | Retail Food & Grocery | 1885 | 23.18 |
| 2024 | Schools & Childcare | 2165 | 22.73 |
| 2024 | ALL 3 selected groups | 15243 | 21.91 |
| 2025 | Restaurant & Food Service | 11462 | 21.19 |
| 2025 | Retail Food & Grocery | 1748 | 23.28 |
| 2025 | Schools & Childcare | 2103 | 20.16 |
| 2025 | ALL 3 selected groups | 15313 | 21.29 |
| ALL years | Restaurant & Food Service | 43080 | 22.92 |
| ALL years | Retail Food & Grocery | 7132 | 24.86 |
| ALL years | Schools & Childcare | 8609 | 23.65 |
| ALL years | ALL 3 selected groups | 58821 | 23.27 |

**Interpretation:** One report with four levels of totals. For the three selected groups the all-years failure rate is 22.92% (restaurants), 24.86% (retail) and 23.65% (schools), and 23.27% together (58,821 inspections). Retail food jumped to 27.96% in 2023, and schools were the lowest in 2025 (20.16%).
