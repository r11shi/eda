#!/usr/bin/env bash
# Run ONE part of the project and see its real output. Each part prints what it does and every command it runs,
# so you can type the same commands yourself.
#
#   bash scripts/part.sh status         are the servers running?
#   bash scripts/part.sh all            every part in order (A B C F mart G H I), output saved to docs/run_logs/   ~9 min
#   bash scripts/part.sh full           the same plus D (Citus) and E (real-time)                               ~16 min
#   bash scripts/part.sh A              Part A  clean the data + EDA            (notebooks 01, 02)        ~1 min
#   bash scripts/part.sh B              Part B  build the star schema and load it (+ compare designs)    ~1 min
#   bash scripts/part.sh C              Part C  the 5 checks, the 10 business questions, indexes         ~15 s
#   bash scripts/part.sh F              Part F  OLAP queries + build the dashboard                       ~15 s
#   bash scripts/part.sh G | H | I      the three models (notebooks 07, 08, 09)                          ~30 s - 2 min each
#   bash scripts/part.sh D              Part D  Citus cluster and the speed test                         ~5 min
#   bash scripts/part.sh E              Part E  real-time: start the stack and replay the events         ~3 min
#   bash scripts/part.sh data | db | citus | clickhouse     SHOW things (no changes): the files, the warehouse tables, the cluster, the stream
#
# Order matters the first time: A -> B -> C -> F -> G/H/I. D needs B. E needs A.
# Windows: double-click Project_Menu.cmd instead of typing these.
set -uo pipefail
SRC="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
P=/root/eda
export PATH=/root/venv/bin:$PATH PGPASSWORD=foodsafety
DW="psql -h localhost -U foodsafety -d foodsafety -P pager=off"
CITUS="sudo -u postgres psql -p 5440 -d foodsafety_citus -P pager=off"

B="\033[1m"; C="\033[36m"; G="\033[32m"; N="\033[0m"
title() { echo; echo -e "${B}${C}=== $1 ===${N}"; echo -e "$2"; echo; }
run()   { echo -e "${G}\$ $*${N}"; eval "$@"; echo; }
nb()    {  # execute a notebook, then print the text it printed (the same output you see in JupyterLab)
  run "jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 $1 2>&1 | grep -v -i -E 'warning|kernel|nbconvert' || true"
  python - "$1" "${2:-60}" <<'PY'
import json, sys
nb = json.load(open(sys.argv[1], encoding="utf-8")); lines = []
for cell in nb["cells"]:
    for o in cell.get("outputs", []):
        if o.get("output_type") == "stream":
            lines += "".join(o["text"]).rstrip().splitlines()
print("\n".join(lines[: int(sys.argv[2])]) + ("\n   ... (more in the notebook)" if len(lines) > int(sys.argv[2]) else ""))
PY
}
sync() {   # copy the project from Windows into the Linux disk (fast to run there)
  [ -f "$SRC/run_all.py" ] || { echo "Run this from the project folder."; exit 1; }
  rsync -a --exclude .git --exclude runtime --exclude data/curated --exclude .claude --exclude deliverables "$SRC/" "$P/"
  cd "$P"
  sed -i 's/\r$//' scripts/*.sh          # Windows line endings break bash scripts
  [ -f data/raw/food_inspections_2022_2025.csv ] || gunzip -kf data/raw/food_inspections_2022_2025.csv.gz
}
need() { pg_isready -h localhost -p 5432 -q || { echo "PostgreSQL is not running. Double-click Start_Project.cmd first."; exit 1; }; }

case "${1:-}" in
  all|full)   # every part in order; each part's real output is also saved to docs/run_logs/part_<X>.log
    parts="A B C F mart G H I"; [ "$1" = full ] && parts="$parts D E"
    mkdir -p "$SRC/docs/run_logs"
    for p in $parts; do
      "$0" "$p" 2>&1 | tee >(sed 's/\x1b\[[0-9;]*m//g' > "$SRC/docs/run_logs/part_$p.log")
      sleep 1
    done
    echo; echo "All parts done. The output of each part is saved in docs/run_logs/" ;;

  status)
    title "Are the servers running?" "Every line should say OK. If not, double-click Start_Project.cmd."
    for s in "PostgreSQL warehouse:5432" "Citus coordinator:5440" "Citus worker 1:5441" "Citus worker 2:5442"; do
      port=${s##*:}; pg_isready -h localhost -p "$port" -q && echo "  OK   ${s%%:*} (port $port)" || echo "  --   ${s%%:*} (port $port) not running"; done
    for s in "ClickHouse:8123:/ping" "Grafana:3000:/api/health" "JupyterLab:8888:/api"; do
      IFS=: read -r n port path <<<"$s"; curl -sf "http://127.0.0.1:$port$path" >/dev/null && echo "  OK   $n (port $port)" || echo "  --   $n (port $port) not running"; done
    (echo > /dev/tcp/127.0.0.1/9092) 2>/dev/null && echo "  OK   Kafka (port 9092)" || echo "  --   Kafka (port 9092) not running" ;;

  A)
    sync
    title "PART A: clean the data and explore it" "Reads the raw Chicago file, applies the cleaning rules in etl/curation.py,\nwrites data/curated/inspections_curated.csv, then draws the EDA charts."
    run "ls -lh data/raw/"
    run "python -c \"import pandas as pd; d=pd.read_csv('data/raw/food_inspections_2022_2025.csv'); print('raw rows:', len(d), '| columns:', len(d.columns)); print(d.columns.tolist())\""
    nb notebooks/01_data_curation.ipynb 45
    nb notebooks/02_eda.ipynb 25
    run "python -c \"import pandas as pd; d=pd.read_csv('data/curated/inspections_curated.csv', dtype={'zip': str}); print('curated rows:', len(d), '| completed inspections:', int(d.is_completed.sum()), '| new columns:', len(d.columns))\""
    echo "Charts: open notebooks/02_eda.ipynb in JupyterLab (http://localhost:8888). Cleaning log: docs/data_quality_report.md" ;;

  B)
    sync; need
    title "PART B (+C): build the star schema and load it" "Creates the tables (sql/01_schema.sql), loads Jan 2022-Nov 2025 (initial load),\nthen Dec 2025 (incremental load) with the procedure in sql/02_load_batch.sql, and runs the 5 checks."
    run "python etl/run_etl.py all"
    title "PART B: star vs snowflake vs fact constellation" "Builds the snowflake version too and times the same questions on both."
    run "python etl/model_comparison.py 2>&1 | head -14"
    run "$DW -c '\\dt dw.*'" ;;

  C)
    sync; need
    title "PART C: checks, business questions, indexes" "The 5 checks must all be 0. Then the 10 business questions are timed, with and without indexes."
    run "$DW -f sql/04_validation.sql"
    run "$DW -c 'SELECT batch_id, batch_label, rows_staged, rows_not_completed, rows_loaded_fact, new_facilities FROM staging.load_audit ORDER BY 1'"
    run "python etl/run_queries.py" ;;

  F)
    sync; need
    title "PART F: OLAP and the dashboard" "Runs roll-up, drill-down, slice, dice, pivot, CUBE (sql/07_olap_queries.sql) and builds the dashboard page."
    run "python etl/run_olap.py"
    run "$DW -f sql/demo_queries.sql 2>&1 | head -80"
    run "python dashboard/build_dashboard.py"
    cp dashboard/food_safety_dashboard.html "$SRC/dashboard/" && echo "Open dashboard/food_safety_dashboard.html (double-click) to see it." ;;

  mart)
    sync; need
    title "The analytics table (input of the 3 models)" "One flat table from the warehouse; each inspection also gets the previous inspection of the same place."
    run "$DW -f sql/08_analytics_mart.sql"
    run "$DW -c \"SELECT inspection_date, inspection_type, result_group, violation_count, prior_inspection_result, prior_violation_count, days_since_prior_inspection FROM mart.food_inspection_analytics_mart WHERE facility = 'JERK MAN' ORDER BY inspection_date LIMIT 6\"" ;;

  G) sync; need; title "PART G: regression" "Predicts the number of violations. Train 2022-2024, test 2025. Look for MAE and R2."; nb notebooks/07_regression.ipynb 40
     run "python -c \"import pandas as pd; print(pd.read_csv('results/regression_metrics.csv').round(3).to_string(index=False))\"" ;;
  H) sync; need; title "PART H: association rules" "Apriori and FP-Growth on 61,185 inspections. Look for the itemset count and the rules table."; nb notebooks/08_association_mining.ipynb 30
     run "python -c \"import pandas as pd; r=pd.read_csv('results/association_rules_selected.csv'); print(r[['Rule','support','confidence','lift']].head(6).round(3).to_string(index=False))\"" ;;
  I) sync; need; title "PART I: decision tree" "Predicts fail / not fail. Tuned on 2024, tested on 2025. Look for AUC, recall and the important inputs."; nb notebooks/09_decision_tree.ipynb 14
     run "python -c \"import pandas as pd; d=pd.read_csv('results/decision_tree_metrics.csv'); print(d[['Model','threshold','Accuracy','Precision','Recall','ROC-AUC']].round(3).to_string(index=False)); print(); print(pd.read_csv('results/decision_tree_importance.csv', index_col=0).head(5).round(3).to_string())\"" ;;

  D)
    sync; need
    title "PART D: distributed warehouse (Citus)" "Starts 1 coordinator + 2 workers, copies the warehouse in, splits the fact table into 32 shards,\nand times 5 queries on one server vs Citus at 61,737 to 2,000,000 rows. Takes about 5 minutes."
    run "bash scripts/setup_citus_cluster.sh"
    run "python etl/distributed_baseline.py | tail -12"
    run "python etl/distributed_citus.py | tail -30" ;;

  E)
    sync
    title "PART E: real-time warehouse (replay simulation)" "Starts ClickHouse, Kafka and the Spark job, then replays Oct-Dec 2025 as live events.\nWatch http://localhost:3000/d/food-safety-rt while it runs."
    run "bash scripts/start_realtime_stack.sh"
    curl -sf http://127.0.0.1:3000/api/health >/dev/null || run "python streaming/grafana/build_dashboard.py && bash scripts/start_grafana.sh > /dev/null"
    sleep 15
    for t in inspection_events invalid_events window_agg daily_event_time_agg; do curl -s http://127.0.0.1:8123/ --data-binary "TRUNCATE TABLE IF EXISTS food.$t" >/dev/null; done
    run "python streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 40 --bad-every 150"
    sleep 15
    "$0" clickhouse ;;

  data)
    sync
    title "SHOW: the data files" "The raw file, the cleaned file and the result tables. Nothing is changed."
    run "ls -lh data/raw/ data/curated/ 2>/dev/null"
    run "head -c 700 data/raw/food_inspections_2022_2025.csv; echo"
    run "python -c \"import pandas as pd; d=pd.read_csv('data/curated/inspections_curated.csv', dtype={'zip': str}); print(d[['inspection_id','dba_name','facility_group','risk_group','inspection_type_group','result_group','violation_count','zip']].head(8).to_string(index=False))\""
    run "ls results/" ;;

  db)
    need
    title "SHOW: the warehouse in PostgreSQL" "The same thing pgAdmin shows (server localhost:5432, user/password foodsafety)."
    run "$DW -c '\\dn'"
    run "$DW -c '\\dt+ dw.*'"
    run "$DW -c 'SELECT * FROM dw.dim_result ORDER BY 1'"
    run "$DW -c 'SELECT inspection_id, date_key, facility_key, inspection_type_key, result_key, location_key, violation_count, fail_count FROM dw.fact_inspection ORDER BY 1 LIMIT 5'"
    run "$DW -c 'SELECT facility_key, dba_name, facility_type, facility_group, risk_group FROM dw.dim_facility WHERE facility_key > 0 ORDER BY 1 LIMIT 5'" ;;

  citus)
    title "SHOW: the Citus cluster" "Same as pgAdmin on server localhost:5440, database foodsafety_citus, user postgres."
    run "$CITUS -c 'SELECT nodeid, nodename, nodeport, noderole, isactive FROM pg_dist_node ORDER BY 1'"
    run "$CITUS -c 'SELECT table_name, citus_table_type, distribution_column, shard_count FROM citus_tables ORDER BY 2, 1'"
    run "$CITUS -c \"SELECT nodeport AS worker, count(*) AS shards, pg_size_pretty(sum(shard_size)) AS data FROM citus_shards WHERE table_name = 'bench.fact_2000000_facility_key'::regclass GROUP BY 1 ORDER BY 1\"" ;;

  clickhouse)
    title "SHOW: the real-time warehouse (ClickHouse)" "Same queries you can type at http://localhost:8123/play"
    curl -sf http://127.0.0.1:8123/ping >/dev/null || { echo "ClickHouse is not running. Run Part E (menu 10) or Start_Project.cmd first."; exit 0; }
    for q in "SELECT count() AS valid_events, min(event_date) AS first_day, max(event_date) AS last_day FROM food.inspection_events" \
             "SELECT reason, count() AS events FROM food.invalid_events GROUP BY reason ORDER BY events DESC" \
             "SELECT result_group, count() AS inspections FROM food.inspection_events GROUP BY result_group ORDER BY inspections DESC"; do
      echo -e "${G}:) $q${N}"; curl -s http://127.0.0.1:8123/ --data-binary "$q FORMAT PrettyCompactMonoBlock"; echo; done ;;

  *) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
