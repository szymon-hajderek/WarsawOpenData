"""Builds the frequent-places pages: shared head + body from templates/, screenshots from img/ inlined.

Run from the repo root: python artifacts/frequent-places/build.py
"""
import base64
import re
from pathlib import Path

HERE = Path(__file__).parent

HEAD = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one reading column; screenshots in a two-column grid. Same family as artifacts/delays/. Warsaw red accent. */
:root {
  --bg: #f6f4f4; --surface: #ffffff; --code-bg: #f0ecec; --ink: #17130f; --ink-2: #4f4846; --muted: #7a716e;
  --grid: #e3dcdb; --accent: #b8102e; --pass: #0c8f2e; --fail: #c8322b; --skip: #9a6a00;
  --f-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --f-body: "Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif;
  --f-mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #141112; --surface: #1d191a; --code-bg: #262022; --ink: #f3eeee; --ink-2: #c4bbba; --muted: #978d8b;
  --grid: #332c2d; --accent: #f5c400; --pass: #3cc160; --fail: #ef5a52; --skip: #f0b429; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #141112; --surface: #1d191a; --code-bg: #262022; --ink: #f3eeee; --ink-2: #c4bbba; --muted: #978d8b;
  --grid: #332c2d; --accent: #f5c400; --pass: #3cc160; --fail: #ef5a52; --skip: #f0b429; color-scheme: dark }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.6 var(--f-body); }
.wrap { max-width: 920px; margin: 0 auto; padding-block: 40px 72px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 44px; }
h1, h2, h3 { font-family: var(--f-display); text-wrap: balance; margin: 0; line-height: 1.15; }
h1 { font-size: clamp(30px, 5vw, 44px); }
h2 { font-size: 23px; }
p, li { max-width: 72ch; }
p { margin: 0; }
b { color: var(--ink); }
ul, ol { margin: 0; padding-left: 22px; display: grid; gap: 6px; }
section { display: grid; gap: 12px; min-width: 0; }
.eyebrow { font: 500 12px/1 var(--f-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
header { display: grid; gap: 14px; }
.lead { color: var(--ink-2); font-size: 18px; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 18px; font: 13px/1.4 var(--f-mono); color: var(--ink-2); }
.meta b { font-weight: 500; }
.note { color: var(--ink-2); font-size: 15px; }
code { font: 0.88em var(--f-mono); background: var(--code-bg); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }
.facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 15px; background: var(--surface); border: 1px solid var(--grid); border-radius: 8px; padding: 14px 16px; margin: 0; }
.facts dt { color: var(--muted); font: 500 12px/1.9 var(--f-mono); text-transform: uppercase; letter-spacing: .04em; }
.facts dd { margin: 0; min-width: 0; }
@media (max-width: 520px) { .facts { grid-template-columns: 1fr; } .facts dd { margin-bottom: 6px; } }
.tbl { overflow-x: auto; background: var(--surface); border: 1px solid var(--grid); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 8px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--grid); }
th { font: 500 12px var(--f-mono); letter-spacing: .04em; text-transform: uppercase; color: var(--muted); white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
.r { font: 500 12px/1 var(--f-mono); padding: 4px 8px; border-radius: 999px; border: 1px solid currentColor; white-space: nowrap; display: inline-block; margin: 1px 0; }
.r.pass { color: var(--pass); } .r.fail { color: var(--fail); } .r.skip { color: var(--skip); }
.shots { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 16px; }
figure { margin: 0; display: grid; gap: 6px; min-width: 0; }
figure img { width: 100%; max-width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--grid); display: block; }
figcaption { font-size: 14px; color: var(--ink-2); }
</style>
</head>
<body>
"""


def inline(match: re.Match) -> str:
    data = base64.b64encode((HERE / match.group(1)).read_bytes()).decode()
    return f'src="data:image/jpeg;base64,{data}"'


def build(name: str, out: Path) -> None:
    body = (HERE / "templates" / name).read_text(encoding="utf-8")
    title = re.match(r"<!--title:(.*?)-->", body).group(1)
    body = re.sub(r'src="(img/[^"]+\.jpg)"', inline, body)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEAD.replace("__TITLE__", title) + body + "</body>\n</html>\n", encoding="utf-8")
    print("wrote", out.relative_to(HERE))


build("frequent-places-docs.html", HERE / "frequent-places-docs.html")
build("frequent-places-tests.html", HERE / "tests" / "frequent-places-tests.html")
