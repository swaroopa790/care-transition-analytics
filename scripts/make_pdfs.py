"""
Render the Markdown deliverables to print-ready HTML and PDF.

    python scripts/make_pdfs.py

Pipeline:  docs/*.md  --(python-markdown)-->  docs/*.html  --(headless Chrome)-->  docs/*.pdf

Chrome (or Edge) is invoked headless with --print-to-pdf; if neither browser is
available the HTML files are still produced so the documents remain printable
from any browser.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

DOCUMENTS = ["research_paper.md", "executive_summary.md"]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body {
  font-family: "Georgia", "Times New Roman", serif;
  font-size: 10.5pt; line-height: 1.55; color: #1B1B1B; margin: 0;
}
h1 { font-size: 21pt; line-height: 1.25; color: #14304A; margin: 0 0 6pt 0; }
h2 { font-size: 14pt; color: #14304A; margin: 22pt 0 8pt 0;
     border-bottom: 1.5px solid #14304A; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; color: #1F4E79; margin: 15pt 0 5pt 0; }
h4 { font-size: 10.5pt; color: #1F4E79; margin: 12pt 0 4pt 0; }
p { margin: 6pt 0; text-align: justify; }
ul, ol { margin: 6pt 0 6pt 18pt; padding-left: 6pt; }
li { margin: 3pt 0; }
strong { color: #0E2A42; }
em { color: #333; }
hr { border: none; border-top: 1px solid #D8D8D8; margin: 16pt 0; }
a { color: #1F4E79; text-decoration: none; }
blockquote {
  margin: 10pt 0; padding: 7pt 12pt; background: #F3F7FB;
  border-left: 4px solid #4C78A8; font-size: 10.5pt; color: #183B56;
}
code {
  font-family: "Consolas", "Courier New", monospace; font-size: 9pt;
  background: #F4F4F4; padding: 1px 4px; border-radius: 3px;
}
pre {
  background: #F7F9FB; border: 1px solid #DDE5EC; padding: 9pt 10pt;
  font-size: 8.6pt; line-height: 1.45; white-space: pre-wrap;
  page-break-inside: avoid;
}
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 10pt 0;
        font-size: 8.9pt; page-break-inside: avoid; }
th { background: #14304A; color: #FFFFFF; text-align: left;
     padding: 5pt 7pt; font-weight: bold; border: 1px solid #14304A; }
td { padding: 4.5pt 7pt; border: 1px solid #D5DDE5; vertical-align: top; }
tbody tr:nth-child(even) { background: #F6F9FC; }
img { max-width: 100%; max-height: 232mm; width: auto; height: auto;
      display: block; margin: 10pt auto; page-break-inside: avoid; }
figure { margin: 10pt 0; page-break-inside: avoid; }
figcaption { font-size: 8.8pt; color: #555; text-align: justify;
             margin-top: 4pt; font-style: italic; }
h1, h2, h3 { page-break-after: avoid; }
strong + table, h2 + table { page-break-before: avoid; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def find_browser() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return shutil.which("chrome") or shutil.which("msedge")


def to_html(md_path: Path) -> Path:
    source = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        source,
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.sane_lists",
            "markdown.extensions.toc",
            "markdown.extensions.codehilite",
            "markdown.extensions.attr_list",
        ],
        extension_configs={"markdown.extensions.toc": {"permalink": False}},
        output_format="html5",
    )
    title = source.splitlines()[0].lstrip("#").strip()
    html_path = md_path.with_suffix(".html")
    html_path.write_text(
        TEMPLATE.format(title=title, css=CSS, body=body), encoding="utf-8"
    )
    print(f"  html  {html_path.relative_to(ROOT)}")
    return html_path


def to_pdf(browser: str, html_path: Path) -> Path | None:
    pdf_path = html_path.with_suffix(".pdf")
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--virtual-time-budget=15000",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"  ! pdf failed for {html_path.name}: {exc}")
        return None
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        print(f"  ! pdf not written for {html_path.name}")
        return None
    print(f"  pdf   {pdf_path.relative_to(ROOT)} ({pdf_path.stat().st_size:,} bytes)")
    return pdf_path


def main() -> int:
    browser = find_browser()
    print("Browser:", browser or "none found")
    ok = True
    for name in DOCUMENTS:
        md_path = DOCS / name
        if not md_path.exists():
            print(f"  ! missing {name}")
            ok = False
            continue
        html = to_html(md_path)
        if browser:
            if to_pdf(browser, html) is None:
                ok = False
        else:
            print(f"  ! no browser available - open {html.name} and print to PDF")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
