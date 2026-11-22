"""Makes the output screenshots used in the report (docs/images/screens/*.png).

Two kinds:
  1. terminal shots: the REAL console output saved in docs/console_logs/*.log, drawn in a terminal window
  2. page shots: the dashboard pages, the README page, JupyterLab and Grafana, captured with headless Microsoft Edge

    python build_docs/make_screenshots.py            (Windows; needs Microsoft Edge)
"""
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "docs" / "console_logs"
OUT = ROOT / "docs" / "images" / "screens"
OUT.mkdir(parents=True, exist_ok=True)
EDGE = next((p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
             if Path(p).exists()), shutil.which("msedge"))

TERM = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#e9ecef;padding:22px;font-family:"Cascadia Mono",Consolas,monospace}
.w{background:#1e1f24;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);overflow:hidden;width:max-content;min-width:760px}
.t{background:#2b2d33;padding:9px 14px;display:flex;align-items:center;gap:7px}
.t i{width:12px;height:12px;border-radius:50%;display:inline-block}.t span{color:#9aa0a6;font:12px "Segoe UI",sans-serif;margin-left:12px}
pre{margin:0;padding:14px 18px 18px;color:#d7dae0;font-size:13px;line-height:1.45;white-space:pre}
.p{color:#7ee787}.c{color:#79c0ff}
</style></head><body><div class="w"><div class="t"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>
<span>__TITLE__</span></div><pre><span class="p">__PROMPT__</span> <span class="c">__CMD__</span>
__TEXT__</pre></div></body></html>"""


def trim(path, margin=24, keep_height=None):
    """Cut away the empty background on the right and at the bottom of a screenshot."""
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    if keep_height:
        im = im.crop((0, 0, im.width, min(im.height, keep_height)))
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 2, im.height - 2)))
    diff = ImageChops.difference(im, bg).point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    side = diff.crop((int(im.width * 0.2), 0, im.width, im.height)).getbbox()   # ignore a full-height side menu
    if box and side:
        im = im.crop((0, 0, min(im.width, box[2] + margin), min(im.height, side[3] + margin)))
    im.save(path)


def edge_shot(url, out, width, height, keep_height=None):
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1.5",
                    f"--window-size={width},{height}", "--virtual-time-budget=8000", f"--screenshot={out}", url],
                   check=True, capture_output=True, timeout=120)
    if "grafana" not in out.name and "jupyter" not in out.name:
        trim(out)
    elif keep_height:
        trim(out, keep_height=keep_height)
    print("  ", out.name)


def terminal(name, cmd, text, title="Ubuntu (WSL) - bash", prompt="root@laptop:~/eda$"):
    """Draw real console text in a terminal window and save it as a PNG."""
    lines = text.rstrip("\n").splitlines()
    page = TERM.replace("__TITLE__", title).replace("__PROMPT__", prompt).replace("__CMD__", html.escape(cmd)).replace("__TEXT__", html.escape("\n".join(lines)))
    tmp = Path(tempfile.gettempdir()) / f"fs_term_{name}.html"
    tmp.write_text(page, encoding="utf-8")
    width = min(1500, max(820, 9 * max(len(x) for x in lines + [cmd]) + 120))
    edge_shot(tmp.as_uri(), OUT / f"{name}.png", width, 110 + 19 * len(lines))


def log(name):
    return (LOGS / name).read_text(encoding="utf-8", errors="replace")


def section(text, start, end=None):
    """Lines of a log from the line containing `start` up to (not including) the line containing `end`."""
    lines = text.splitlines()
    i = next(k for k, x in enumerate(lines) if start in x)
    j = next((k for k in range(i + 1, len(lines)) if end and end in lines[k]), len(lines))
    return "\n".join(x for x in lines[i:j] if "IPKernelApp" not in x and "Kernel is running" not in x)


def main():
    run_all = log("run_all.log")
    print("terminal screenshots")
    terminal("run_all", "python run_all.py", section(run_all, "Database OK", "[4/12]") + "\n  ...")
    terminal("etl", "python etl/run_etl.py all", section(run_all, "Creating schemas", "done in"))
    terminal("model_comparison", "python etl/model_comparison.py", section(run_all, "criterion  star", "dimension bytes"))
    terminal("queries", "python etl/run_queries.py", section(run_all, "Q1a ", "done in"))
    terminal("run_all_end", "python run_all.py   (end of the run)", section(run_all, "[10/12]"))
    for f in sorted(LOGS.glob("*.log")):
        if f.stem.startswith(("psql_", "nb_", "citus", "stream")):
            first = f.read_text(encoding="utf-8", errors="replace").splitlines()[0]
            cmd, body = (first[2:], "\n".join(f.read_text(encoding="utf-8").splitlines()[1:])) if first.startswith("$ ") else ("", f.read_text(encoding="utf-8"))
            terminal(f.stem, cmd, body)

    print("page screenshots")
    dash = (ROOT / "dashboard" / "food_safety_dashboard.html").as_uri()
    for page in ["overview", "facility", "geo", "insp", "mining", "dw"]:
        edge_shot(f"{dash}#{page}", OUT / f"dashboard_{page}.png", 1440, 3400 if page in ("geo", "mining") else 1500)
    if (ROOT / "README.html").exists():
        edge_shot((ROOT / "README.html").as_uri(), OUT / "readme_page.png", 1100, 1300)
    for name, url, w, h, kh in [("jupyter_07", "http://localhost:8888/lab/tree/notebooks/07_regression.ipynb", 1440, 1000, 1240),
                                                        ("grafana_realtime", "http://localhost:3000/d/food-safety-rt?orgId=1&kiosk", 1600, 1000, None)]:
        try:
            edge_shot(url, OUT / f"{name}.png", w, h, kh)
        except Exception as exc:                                    # noqa: BLE001  (server not running)
            print("   skipped", name, exc)


if __name__ == "__main__":
    main()
