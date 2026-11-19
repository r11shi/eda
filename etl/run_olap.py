"""Executes sql/07_olap_queries.sql and writes docs/olap_operations.md in the required format:
Business Question > Dimensions > Measure > OLAP Operation > SQL/DAX Query > Output > Interpretation."""
import re
from pathlib import Path
import pandas as pd
import psycopg2
from config import connect

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "sql" / "07_olap_queries.sql").read_text()
conn = connect(); cur = conn.cursor()


def md_table(df):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]) and (df[c].dropna() % 1 == 0).all():
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else str(int(v)))
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if (not isinstance(v, str) and pd.isna(v)) else str(v) for v in r.values) + " |")
    return "\n".join(lines)


doc = ["# Part F: OLAP Cube Operations (PostgreSQL)", "",
       "The OLAP layer is the dimensional model in schema `dw`. Hierarchies: **Time** Year > Quarter > Month > Day; **Location** Geographic Area Group / ZIP > Facility; **Facility** Facility Type > Risk Category > Establishment. "
       "Every SQL query below was executed and its output is shown. The DAX versions are given for Power BI; Power BI Desktop is not available in this environment, so **the DAX was not executed**.", "",
       "Core measures (SQL and DAX):", "",
       "| Measure | SQL | DAX |", "|---|---|---|",
       "| InspectionCount | `sum(inspection_count)` | `SUM(FactInspection[inspection_count])` |",
       "| ViolationCount | `sum(violation_count)` | `SUM(FactInspection[violation_count])` |",
       "| FailCount / PassCount / ConditionalPassCount | `sum(fail_count)` etc. | `SUM(FactInspection[fail_count])` etc. |",
       "| HighViolationFlag (count of high-violation inspections) | `sum(high_violation_flag)` | `SUM(FactInspection[high_violation_flag])` |",
       "| AverageViolations | `avg(violation_count)` | `AVERAGE(FactInspection[violation_count])` |",
       "| FailureRate | `sum(fail_count) / sum(inspection_count)` | `DIVIDE([FailCount], [InspectionCount])` |", "",
       "Note: the warehouse uses the **latest** attributes of each facility (Type-1 dimension), so group totals differ slightly from the EDA, which used the attributes recorded at each inspection (for example 43,080 against 43,057 restaurant inspections).", ""]
for b in re.split(r"^-- ##### ", text, flags=re.M)[1:]:
    lines = b.split("\n")
    head = lines[0]
    meta = {k: " ".join(l.split(": ", 1)[1] for l in lines if l.startswith(f"-- {k}:")) for k in ["question", "dimensions", "measures", "operation", "dax", "interpretation"]}
    sql = "\n".join(l for l in lines[1:] if not l.startswith("--")).strip()
    cur.execute(sql.rstrip(";")); cols = [c.name for c in cur.description]
    out = pd.DataFrame(cur.fetchall(), columns=cols)
    doc += [f"## {head}", "", f"* **Business question:** {meta['question']}", f"* **Dimensions:** {meta['dimensions']}", f"* **Measure:** {meta['measures']}",
            f"* **OLAP operation:** {meta['operation']}", "", "**SQL:**", "```sql", sql, "```", "", "**DAX:**", "```", meta["dax"], "```", "", "**Output:**", "", md_table(out), "",
            f"**Interpretation:** {meta['interpretation']}", ""]
(ROOT / "docs" / "olap_operations.md").write_text("\n".join(doc))
print("written docs/olap_operations.md with", len(re.split(r"^-- ##### ", text, flags=re.M)) - 1, "operations")
