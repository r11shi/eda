#!/usr/bin/env python3
"""Run the batch part of the project (Parts A, B, C, F, G, H, I) with one command:   python run_all.py

    python run_all.py              # everything, about 5 minutes
    python run_all.py --check      # only check the Python packages and the database connection
    python run_all.py --docker     # start the PostgreSQL container from docker-compose.yml first
    python run_all.py --skip-eda --skip-models      # leave out notebooks 02 and 07-09 (faster)

Order: data > cleaning (notebook 01) > exploration (02) > warehouse load (etl/run_etl.py) > model comparison > query timing
> OLAP > analytical mart > dashboard > regression, association rules, decision tree (notebooks 07-09).
Database settings: etl/config.py (environment variables FS_DB_* or a .env file). Parts D (Citus) and E (real-time) need extra servers: see README.md.
"""
import argparse, gzip, importlib.util, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "etl"))
PACKAGES = {"pandas": "pandas", "numpy": "numpy", "matplotlib": "matplotlib", "seaborn": "seaborn", "scipy": "scipy", "sklearn": "scikit-learn",
            "statsmodels": "statsmodels", "mlxtend": "mlxtend", "psycopg2": "psycopg2-binary", "plotly": "plotly", "nbformat": "nbformat",
            "nbclient": "nbclient", "ipykernel": "ipykernel"}
RAW = ROOT / "data" / "raw" / "food_inspections_2022_2025.csv"


def say(msg=""):
    print(msg, flush=True)


def check_packages():
    missing = [pip for mod, pip in PACKAGES.items() if importlib.util.find_spec(mod) is None]
    if missing:
        sys.exit("Missing Python packages: " + ", ".join(missing) + "\nInstall everything with:   pip install -r requirements.txt")


def db_ready():
    from config import connect
    try:
        connect(connect_timeout=3).close()
        return True, ""
    except Exception as exc:                                    # noqa: BLE001
        return False, (str(exc).strip().splitlines() or [repr(exc)])[0]


def ensure_database(use_docker):
    from config import DB
    ok, why = db_ready()
    if not ok and use_docker:
        for cmd in (["docker", "compose", "up", "-d", "db"], ["docker-compose", "up", "-d", "db"]):
            if shutil.which(cmd[0]) and subprocess.run(cmd, cwd=ROOT).returncode == 0:
                break
        say("Waiting for PostgreSQL ...")
        for _ in range(60):
            ok, why = db_ready()
            if ok:
                break
            time.sleep(1)
    if ok:
        say(f"Database OK: {DB['user']}@{DB['host']}:{DB['port']}/{DB['dbname']}")
        return
    say(f"Cannot connect to PostgreSQL ({DB['user']}@{DB['host']}:{DB['port']}/{DB['dbname']}): {why}\n")
    say("Fix it with ONE of these (details in README.md):")
    say("  1. Docker:        docker compose up -d db      (or run this script with --docker)")
    say("  2. Local server:  create the role and database described in README.md, 'Option C'")
    say("  3. Other server:  set FS_DB_HOST, FS_DB_PORT, FS_DB_NAME, FS_DB_USER, FS_DB_PASSWORD (or copy .env.example to .env)")
    sys.exit(1)


def get_data():
    gz = RAW.with_suffix(".csv.gz")
    if RAW.exists():
        say("  raw data already present")
    elif gz.exists():
        say("  unpacking the bundled data file (data/raw/*.csv.gz)")
        with gzip.open(gz, "rb") as src, open(RAW, "wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        say("  downloading the official data from the City of Chicago Data Portal")
        run_script("scripts/fetch_data.py")


def run_script(rel, *args):
    if subprocess.run([sys.executable, rel, *args], cwd=ROOT).returncode != 0:
        raise RuntimeError(f"{rel} failed")


def run_notebook(rel):
    import nbformat
    from nbclient import NotebookClient
    path = ROOT / rel
    nb = nbformat.read(path, 4)
    NotebookClient(nb, timeout=1800, resources={"metadata": {"path": str(path.parent)}}).execute()
    nbformat.write(nb, path)


def build_mart():
    from config import connect
    conn = connect(); conn.autocommit = True
    cur = conn.cursor(); cur.execute((ROOT / "sql" / "08_analytics_mart.sql").read_text())
    cur.execute("SELECT count(*) FROM mart.food_inspection_analytics_mart"); say(f"  mart rows: {cur.fetchone()[0]:,}")


def summary():
    import pandas as pd
    R = ROOT / "results"
    say("\nResults (files in results/):")
    try:
        v = pd.read_csv(R / "validation_results.csv")
        bad = v[(v["value"] != 0)]
        say(f"  warehouse checks: {v['check_name'].nunique()} checks, {len(bad)} problems")
        say("  fact rows loaded per batch (initial, incremental): " + ", ".join(str(x) for x in pd.read_csv(R / "load_audit.csv")["rows_loaded_fact"]))
        r = pd.read_csv(R / "regression_metrics.csv").set_index("Model")
        say(f"  regression: MAE {r.loc['Multiple LR: all test inspections', 'MAE']:.2f}, R2 {r.loc['Multiple LR: all test inspections', 'R2']:.2f}")
        say(f"  decision tree AUC: {pd.read_csv(R / 'decision_tree_metrics.csv').iloc[1]['ROC-AUC']:.3f}")
    except Exception as exc:                                    # noqa: BLE001
        say(f"  (could not read some result files: {exc})")
    say("  dashboard: dashboard/food_safety_dashboard.html (open it in a browser)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true"); ap.add_argument("--docker", action="store_true")
    ap.add_argument("--skip-eda", action="store_true"); ap.add_argument("--skip-models", action="store_true")
    args = ap.parse_args()
    check_packages(); ensure_database(args.docker)
    if args.check:
        say("Environment looks good. Run:  python run_all.py"); return
    steps = [("Get the data", get_data), ("Part A: profile and clean the data (notebook 01)", lambda: run_notebook("notebooks/01_data_curation.ipynb"))]
    if not args.skip_eda:
        steps.append(("Part A: exploratory analysis (notebook 02)", lambda: run_notebook("notebooks/02_eda.ipynb")))
    steps += [("Parts B, C: create the warehouse, initial load, incremental load, checks", lambda: run_script("etl/run_etl.py", "all")),
              ("Part B: compare star, snowflake and fact constellation", lambda: run_script("etl/model_comparison.py")),
              ("Part C: time the analytical queries and the indexes", lambda: run_script("etl/run_queries.py")),
              ("Part F: OLAP operations", lambda: run_script("etl/run_olap.py")),
              ("Analytical mart (input of the models)", build_mart),
              ("Part F: HTML dashboard", lambda: run_script("dashboard/build_dashboard.py"))]
    if not args.skip_models:
        steps += [("Part G: regression (notebook 07)", lambda: run_notebook("notebooks/07_regression.ipynb")),
                  ("Part H: association rules (notebook 08)", lambda: run_notebook("notebooks/08_association_mining.ipynb")),
                  ("Part I: decision tree (notebook 09)", lambda: run_notebook("notebooks/09_decision_tree.ipynb"))]
    t_all = time.time()
    for i, (name, fn) in enumerate(steps, 1):
        say(f"\n[{i}/{len(steps)}] {name}"); t0 = time.time()
        try:
            fn()
        except Exception as exc:                                # noqa: BLE001
            sys.exit(f"\nSTEP FAILED: {name}\n  {exc}\nSee 'Troubleshooting' in README.md, fix the problem and run the script again (it is safe to repeat).")
        say(f"  done in {time.time() - t0:.1f} s")
    say(f"\nAll {len(steps)} steps finished in {(time.time() - t_all) / 60:.1f} minutes.")
    summary()


if __name__ == "__main__":
    main()
