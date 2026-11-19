"""Builds Presenter_Guide.pdf and Theory_Study_Guide.pdf from their .md files (markdown -> HTML -> headless Chromium)."""
import markdown, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
D = HERE.parent / "docs" / "guides"
css = """<style>:root{--navy:#12355b;--teal:#1b998b;--line:#d9e1ea;--soft:#f4f7fb} body{font-family:'Segoe UI',Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#1f2933;margin:0}
h1{font-size:27px;color:#fff;background:linear-gradient(120deg,#12355b,#1b6f8a 60%,#1b998b);border-radius:12px;padding:16px 22px;margin:0 0 10px}
h2{font-size:20px;color:var(--navy);border-left:6px solid var(--teal);border-bottom:1px solid var(--line);padding:2px 0 3px 12px;margin-top:22px} h3{font-size:16px;color:var(--teal)}
table{border-collapse:separate;border-spacing:0;width:100%;margin:8px 0;font-size:12px;border:1px solid var(--line);border-radius:8px;overflow:hidden} th{background:var(--navy);color:#fff;padding:5px 8px;text-align:left} td{padding:4px 8px;vertical-align:top;border-top:1px solid var(--line)} tbody tr:nth-child(even) td{background:var(--soft)}
code{background:#eaf1f8;color:#0f4c75;padding:0 3px;border-radius:4px;font-size:12.5px} pre{background:#f4f7fb;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:11.5px;white-space:pre-wrap} blockquote{border-left:5px solid var(--teal);margin:8px 0;padding:4px 12px;background:#eafaf6;border-radius:0 8px 8px 0} h2,h3{page-break-after:avoid} tr{page-break-inside:avoid}</style>"""
for name in ["Presenter_Guide", "Theory_Study_Guide", "Project_Quick_Guide", "Guide_1_Regression", "Guide_2_Association_Rules", "Guide_3_Decision_Tree", "Guide_4_Probable_Questions", "Project_Source_of_Truth", "How_To_Run"]:
    h = D / "tmp_guide.html"
    h.write_text("<!doctype html><html><head><meta charset='utf-8'>" + css + "</head><body>" + markdown.markdown((D / f"{name}.md").read_text(), extensions=["tables", "fenced_code"]) + "</body></html>")
    import os
    foot = "Rushikesh Maddewad | PRN 202502040037 | Roll 353 | " + name.replace("_", " ")
    env = {**os.environ, "NODE_PATH": subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()}
    subprocess.run(["node", str(HERE / "html_to_pdf.js"), str(h), str(D / (name + ".pdf")), foot], check=True, env=env)
    h.unlink()
