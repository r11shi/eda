# Power BI dashboard package

**Status: not built as a `.pbix` file.** Power BI Desktop runs only on Windows and is not available in the environment where this project was prepared. The same four dashboard sections were built as a self-contained web page, `dashboard/food_safety_dashboard.html`, directly from the PostgreSQL warehouse. This folder gives everything needed to rebuild the dashboard in Power BI Desktop in a few minutes.

## 1. Get the data
Either connect Power BI to PostgreSQL (Get data > PostgreSQL database; server `localhost`, database `foodsafety`, schema `dw`, import the 7 tables), or export CSV files and load them (Get data > Text/CSV):

```bash
python3 dashboard/export_for_powerbi.py      # writes dashboard/powerbi/data/*.csv (not stored in git)
```

## 2. Model (relationships: many-to-one, single direction, from the fact to the dimension)
| From (many) | To (one) |
|---|---|
| FactInspection[date_key] | DimDate[date_key] |
| FactInspection[facility_key] | DimFacility[facility_key] |
| FactInspection[inspection_type_key] | DimInspectionType[inspection_type_key] |
| FactInspection[result_key] | DimResult[result_key] |
| FactInspection[location_key] | DimLocation[location_key] |
| FactFacilityAnnualInspectionPerformance[facility_key] | DimFacility[facility_key] |

Hierarchies: **Time** DimDate[year] > [quarter] > [month_name] > [day]; **Facility** DimFacility[facility_group] > [facility_type] > [risk_category] > [dba_name]; **Location** DimLocation[geographic_area_group] > [zip].

## 3. DAX measures (create them in the FactInspection table)
```dax
InspectionCount          = SUM ( FactInspection[inspection_count] )
PassCount                = SUM ( FactInspection[pass_count] )
FailCount                = SUM ( FactInspection[fail_count] )
ConditionalPassCount     = SUM ( FactInspection[conditional_pass_count] )
ViolationCount           = SUM ( FactInspection[violation_count] )
HighViolationInspections = SUM ( FactInspection[high_violation_flag] )
AverageViolations        = AVERAGE ( FactInspection[violation_count] )
PassRate                 = DIVIDE ( [PassCount], [InspectionCount] )
FailRate                 = DIVIDE ( [FailCount], [InspectionCount] )
ConditionalPassRate      = DIVIDE ( [ConditionalPassCount], [InspectionCount] )
HighViolationShare       = DIVIDE ( [HighViolationInspections], [InspectionCount] )
```
`violation_count` is NULL (unknown) for the 552 Fail / Conditional inspections without violation text; `AVERAGE` and `SUM` ignore NULLs, which is the intended behaviour.

## 4. Pages and visuals (same content as the HTML dashboard)
| Page | Visuals |
|---|---|
| Executive Food Safety | Cards: InspectionCount, PassRate, FailRate, ConditionalPassRate, ViolationCount, HighViolationInspections; column + line chart by year; donut of result group |
| Facility and Risk Analytics | Bar: facility types by InspectionCount; column: FailRate by facility group; 100% stacked column: result group by risk group; column: violation bands; repeat inspections (use the annual fact or the window query in `sql/06_analytical_queries.sql`, Q8a) |
| Geographic Food Safety Analytics | Bar: InspectionCount and FailRate by area group; bar: FailRate by ZIP (top 12, filter InspectionCount >= 200); scatter: InspectionCount against FailRate by ZIP; map visual with latitude/longitude from the staging table (validated coordinates only) |
| Inspection and Violation Analytics | Column: inspection type group; line: monthly InspectionCount and FailRate; matrix with conditional formatting as the failure heat map (year x month) |

**Expected check values** (the numbers the report pages must show): 61,737 inspections; pass rate 61.1%; fail rate 23.1%; conditional pass rate 15.8%; 230,929 violations; 14,999 high-violation inspections.
