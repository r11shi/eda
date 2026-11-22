"""Saves every chart that the executed notebooks contain as docs/images/nb_<notebook>_<n>.png and writes
docs/images/notebook_charts.json (file -> notebook, section, chart titles), so Grafana can show the same charts as the report.

    python build_docs/extract_notebook_charts.py        (after run_all.py has executed the notebooks)
"""
import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
index = {}
for nb in ["02_eda", "07_regression", "08_association_mining", "09_decision_tree"]:
    cells = json.loads((ROOT / "notebooks" / f"{nb}.ipynb").read_text(encoding="utf-8"))["cells"]
    section, n = "", 0
    for c in cells:
        src = "".join(c["source"])
        if c["cell_type"] == "markdown":
            heads = [l.lstrip("# ").strip() for l in src.splitlines() if l.startswith("#")]
            section = heads[0] if heads else section
            continue
        for o in c.get("outputs", []):
            png = o.get("data", {}).get("image/png")
            if not png:
                continue
            n += 1
            name = f"nb_{nb}_{n}.png"
            (OUT / name).write_bytes(base64.b64decode(png))
            titles = re.findall(r"""(?:set_title|suptitle|title)\(\s*f?["']([^"']+)["']""", src)
            index[name] = {"notebook": nb, "section": section, "titles": titles}
            print(f"{name:40s} {section[:50]:50s} {titles[:3]}")
(OUT / "notebook_charts.json").write_text(json.dumps(index, indent=1))
print(len(index), "charts")
