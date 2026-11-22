"""Renders README.md as one self-contained, shareable web page (all diagrams and charts embedded, no internet needed except the font).

Writes two files:
    README.html                         a normal HTML document (double-click to open, send to friends)
    deliverables/Project_Guide.html     the same page without the <html>/<head> wrapper, for publishing as a shared page

    python build_docs/build_readme_html.py          (needs: pip install mistune pillow)
"""
import base64
import html
import io
import re
from pathlib import Path

import mistune
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
md = (ROOT / "README.md").read_text(encoding="utf-8")
body = mistune.create_markdown(plugins=["table"], escape=False)(md)


def slug(text):
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).lower()
    return re.sub(r"[^a-z0-9 -]", "", text).replace(" ", "-")


def embed(src, alt):
    """An image from the repository, embedded in the page: SVG diagrams inline (they follow the theme), PNG charts as data URIs."""
    path = ROOT / src
    if not path.exists():
        return f'<p><em>(missing image: {src})</em></p>'
    if path.suffix == ".svg":
        return path.read_text(encoding="utf-8")
    im = Image.open(path).convert("RGB")
    im.thumbnail((1400, 2400))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=82, optimize=True)
    return f'<img alt="{alt}" loading="lazy" src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'


body = re.sub(r"<h([1-3])>(.*?)</h\1>", lambda m: f'<h{m.group(1)} id="{slug(m.group(2))}">{m.group(2)}</h{m.group(1)}>', body)
# image + the "What it shows / Why we made it" note under it -> one <figure>
body = re.sub(r'<p><img src="([^"]+)" alt="([^"]*)"\s*/?></p>\s*<blockquote>\s*(.*?)\s*</blockquote>',
              lambda m: f'<figure><div class="fig">{embed(m.group(1), m.group(2))}</div><figcaption><b class="ft">{m.group(2)}</b>{m.group(3)}</figcaption></figure>',
              body, flags=re.S)
body = re.sub(r'<p><img src="([^"]+)" alt="([^"]*)"\s*/?></p>', lambda m: f'<figure><div class="fig">{embed(m.group(1), m.group(2))}</div></figure>', body)
body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
body = body.replace("<pre><code", '<div class="cw"><pre><code').replace("</code></pre>", "</code></pre></div>")

STYLE = """
/* Layout: one narrow reading column; figures may run a little wider. */
:root{--bg:#fdfdfc;--ink:#21201c;--mute:#63635e;--line:#e9e8e4;--code:#f6f6f4;--card:#ffffff;
 --d-ink:#21201c;--d-mute:#63635e;--d-box:#ffffff;--d-line:#c9c8c2;--d-acc:#2f5bd3;--d-acc2:#1f8a5b;--d-warm:#c2542d;--d-tint:#eaf0fd;--d-tint2:#e6f4ec;--d-tint3:#fbeae4;
 --sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"JetBrains Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111110;--ink:#eeeeec;--mute:#a1a09a;--line:#2a2a28;--code:#191918;--card:#191918;
 --d-ink:#eeeeec;--d-mute:#a1a09a;--d-box:#1c1c1b;--d-line:#3a3a37;--d-acc:#7d9bf0;--d-acc2:#5cc28f;--d-warm:#ec8a63;--d-tint:#1c2540;--d-tint2:#16291f;--d-tint3:#33201a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#111110;--ink:#eeeeec;--mute:#a1a09a;--line:#2a2a28;--code:#191918;--card:#191918;
 --d-ink:#eeeeec;--d-mute:#a1a09a;--d-box:#1c1c1b;--d-line:#3a3a37;--d-acc:#7d9bf0;--d-acc2:#5cc28f;--d-warm:#ec8a63;--d-tint:#1c2540;--d-tint2:#16291f;--d-tint3:#33201a;color-scheme:dark}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 var(--sans);-webkit-font-smoothing:antialiased}
main{max-width:720px;margin:0 auto;padding-block:64px 120px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main>*{min-width:0}
h1,h2,h3{text-wrap:balance;letter-spacing:-.01em}
h1{font-size:22px;font-weight:600;margin:0 0 6px}h1+p{color:var(--mute);margin-top:4px}
h2{font-size:17px;font-weight:600;margin:64px 0 12px;padding-top:20px;border-top:1px solid var(--line);scroll-margin-top:24px}
h3{font-size:14.5px;font-weight:600;margin:28px 0 8px}
p{margin:0 0 16px}strong{font-weight:600}
a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}a:hover{text-decoration-color:var(--mute)}
a:focus-visible{outline:2px solid var(--d-acc);outline-offset:2px;border-radius:3px}
ul,ol{padding-left:20px;margin:0 0 16px}li{margin:4px 0}
hr{border:0;margin:0}
blockquote{margin:0 0 16px;padding-left:14px;border-left:2px solid var(--line);color:var(--mute)}
code{font:13px/1.6 var(--mono);background:var(--code);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
.cw{overflow-x:auto;margin:0 0 20px;border:1px solid var(--line);border-radius:10px;background:var(--code)}
pre{margin:0;padding:14px 16px}pre code{background:none;border:0;padding:0;font-size:12.5px;line-height:1.65;white-space:pre}
.tw{overflow-x:auto;margin:0 0 20px;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}th{font-weight:500;color:var(--mute);background:var(--code)}
figure{margin:24px 0 28px}
.fig{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:12px;overflow-x:auto}
.fig svg{display:block;width:100%;height:auto;min-width:520px}
.fig img{display:block;width:100%;height:auto;border-radius:6px;background:#fff}
figcaption{font-size:13.5px;line-height:1.6;color:var(--mute);margin-top:10px}
figcaption .ft{display:block;color:var(--ink);font-weight:600;margin-bottom:2px}
figcaption p{margin:0 0 2px}figcaption strong{color:var(--ink);font-weight:600}
.top{color:var(--mute);font-size:13px;margin-bottom:40px}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">')
CONTENT = f'<main><div class="top">Project guide · Data Analytics (MDM) · Department of Computer Engineering</div>{body}</main>'

full = (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Food Safety Analytics Guide</title>{FONTS}<style>{STYLE}</style></head><body>{CONTENT}</body></html>\n')
(ROOT / "README.html").write_text(full, encoding="utf-8")
fragment = (f'<title>Food Safety Analytics Guide</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n{FONTS}\n<style>{STYLE}</style>\n{CONTENT}\n')
(ROOT / "deliverables").mkdir(exist_ok=True)
(ROOT / "deliverables" / "Project_Guide.html").write_text(fragment, encoding="utf-8")
print("written README.html and deliverables/Project_Guide.html", f"{len(full) / 1e6:.1f} MB")
