#!/usr/bin/env bash
# Runs the demo queries of the report in psql and saves the REAL output to docs/console_logs/ (used for the report screenshots).
#   bash scripts/capture_outputs.sh            (inside WSL, from the project folder, after run_all.py)
cd "$(dirname "$0")/.." || exit 1
OUT=docs/console_logs
export PGPASSWORD=foodsafety
DW="psql -h localhost -U foodsafety -d foodsafety -P pager=off"
CITUS="sudo -u postgres psql -p 5440 -d foodsafety_citus -P pager=off"

shot() {   # shot <name> <shown command> <sql>
  { echo "\$ $2"; echo "$3" | $DW -e 2>&1; } > "$OUT/$1.log"; echo "  $1"
}

shot psql_tables "psql -d foodsafety -c '\\dt+ dw.*'" "\\dt+ dw.*"
shot psql_fact "psql -d foodsafety" "SELECT inspection_id, date_key, facility_key, inspection_type_key AS type_key, result_key, location_key, violation_count, fail_count
FROM dw.fact_inspection ORDER BY inspection_id LIMIT 6;"
shot psql_checks "psql -d foodsafety -f sql/04_validation.sql" "$(cat sql/04_validation.sql | grep -v '^--')"
shot psql_load_audit "psql -d foodsafety" "SELECT batch_id, batch_label, rows_staged, rows_not_completed, rows_loaded_fact, new_facilities, status FROM staging.load_audit ORDER BY batch_id;"
shot psql_star_query "psql -d foodsafety" "SELECT fa.facility_group, count(*) AS inspections, round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f JOIN dw.dim_facility fa USING (facility_key)
GROUP BY fa.facility_group ORDER BY inspections DESC;"
shot psql_rollup "psql -d foodsafety" "SELECT coalesce(d.year::text, 'ALL') AS year, coalesce('Q' || d.quarter, 'ALL') AS quarter, count(*) AS inspections,
       round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key)
GROUP BY ROLLUP (d.year, d.quarter) ORDER BY d.year, d.quarter;"
shot psql_pivot "psql -d foodsafety" "SELECT d.year,
       count(*) FILTER (WHERE r.result_group = 'Pass') AS pass,
       count(*) FILTER (WHERE r.result_group = 'Conditional Pass') AS conditional,
       count(*) FILTER (WHERE r.result_group = 'Fail') AS fail
FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_result r USING (result_key)
GROUP BY d.year ORDER BY d.year;"
shot psql_slice_dice "psql -d foodsafety" "SELECT t.inspection_type_group, count(*) AS inspections, round(100.0 * sum(f.fail_count) / count(*), 1) AS fail_rate_pct
FROM dw.fact_inspection f JOIN dw.dim_date d USING (date_key) JOIN dw.dim_facility fa USING (facility_key)
JOIN dw.dim_inspection_type t USING (inspection_type_key)
WHERE d.year = 2025 AND fa.risk_group = 'High'          -- dice: year 2025 and high risk
GROUP BY 1 ORDER BY 2 DESC;"
shot psql_mart "psql -d foodsafety" "SELECT inspection_date, inspection_type, result_group, violation_count, prior_inspection_result AS prior_result,
       prior_violation_count AS prior_viol, days_since_prior_inspection AS days_since
FROM mart.food_inspection_analytics_mart WHERE facility = 'JERK MAN' ORDER BY inspection_date LIMIT 6;"

if sudo -u postgres psql -p 5440 -d foodsafety_citus -tAc "select 1" >/dev/null 2>&1; then
  { echo "\$ psql -p 5440 -d foodsafety_citus"; echo "SELECT nodeid, nodename, nodeport, noderole, isactive FROM pg_dist_node ORDER BY nodeid;
SELECT table_name, citus_table_type, distribution_column, shard_count, table_size FROM citus_tables ORDER BY citus_table_type, table_name LIMIT 8;" | $CITUS -e 2>&1; } > "$OUT/citus_cluster.log"
  { echo "\$ psql -p 5440 -d foodsafety_citus"; echo "SELECT nodeport AS worker, count(*) AS shards, pg_size_pretty(sum(shard_size)) AS data
FROM citus_shards WHERE table_name = 'bench.fact_2000000_facility_key'::regclass GROUP BY nodeport ORDER BY nodeport;" | $CITUS -e 2>&1; } > "$OUT/citus_shards.log"
  echo "  citus_cluster, citus_shards"
fi
