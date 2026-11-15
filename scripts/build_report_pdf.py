"""Generates publication-quality PDF report from docs/REPORT.md using Playwright Chromium."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pypdf
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
REPORT_MD = ROOT / "docs" / "REPORT.md"
HTML_OUT = ROOT / "docs" / "report.html"
PDF_OUT = ROOT / "docs" / "REPORT.pdf"

CSS = """
@page {
    size: A4;
    margin: 14mm 14mm 14mm 14mm;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
}
h1 {
    font-size: 18pt;
    margin-top: 0;
    margin-bottom: 6px;
    color: #0f172a;
    border-bottom: 2px solid #0f172a;
    padding-bottom: 4px;
}
h2 {
    font-size: 12.5pt;
    margin-top: 14px;
    margin-bottom: 6px;
    color: #1e293b;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 2px;
    page-break-after: avoid;
}
h3 {
    font-size: 10.5pt;
    margin-top: 10px;
    margin-bottom: 4px;
    color: #334155;
    page-break-after: avoid;
}
p {
    margin-top: 0;
    margin-bottom: 6px;
    text-align: justify;
}
ul, ol {
    margin-top: 0;
    margin-bottom: 6px;
    padding-left: 18px;
}
li {
    margin-bottom: 3px;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    margin-bottom: 8px;
    font-size: 8pt;
    page-break-inside: avoid;
}
th, td {
    border: 1px solid #cbd5e1;
    padding: 4px 6px;
    text-align: left;
}
th {
    background-color: #f1f5f9;
    font-weight: 600;
    color: #0f172a;
}
tr:nth-child(even) td {
    background-color: #f8fafc;
}
code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 8pt;
    background-color: #f1f5f9;
    padding: 1px 3px;
    border-radius: 3px;
}
pre {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 6px 8px;
    font-size: 7.5pt;
    border-radius: 4px;
    overflow-x: auto;
    margin: 6px 0;
    page-break-inside: avoid;
}
pre code {
    background-color: transparent;
    padding: 0;
}
blockquote {
    border-left: 3px solid #3b82f6;
    margin: 6px 0;
    padding-left: 10px;
    color: #475569;
    font-style: italic;
    background-color: #f8fafc;
    padding: 4px 10px;
}
img {
    max-width: 95%;
    height: auto;
    display: block;
    margin: 8px auto;
    max-height: 200px;
    page-break-inside: avoid;
}
.appendix-page {
    page-break-before: always;
}
hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 10px 0;
}
"""

def generate_pdf() -> None:
    md_content = REPORT_MD.read_text(encoding="utf-8")
    
    # Split appendices to ensure page break
    if "## Appendix:" in md_content:
        parts = md_content.split("## Appendix:")
        main_part = parts[0]
        appendix_part = "## Appendix:" + parts[1]
    else:
        main_part = md_content
        appendix_part = ""

    md = MarkdownIt().enable("table")
    html_main = md.render(main_part)
    html_appendix = md.render(appendix_part) if appendix_part else ""

    # Replace relative image path with absolute file URI for reliable Playwright loading
    img_path = (ROOT / "docs" / "images" / "bid_graph.png").as_uri()
    html_main = html_main.replace('src="images/bid_graph.png"', f'src="{img_path}"')

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{html_main}
<div class="appendix-page">
{html_appendix}
</div>
</body>
</html>"""

    HTML_OUT.write_text(full_html, encoding="utf-8")
    print(f"[build_pdf] Wrote HTML to {HTML_OUT}")

    # Use Node.js Playwright in apps/web to render PDF
    node_script = f"""
const {{ chromium }} = require('{ROOT.as_posix()}/apps/web/node_modules/@playwright/test');
(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('{HTML_OUT.as_uri()}', {{ waitUntil: 'networkidle' }});
    await page.pdf({{
        path: '{PDF_OUT.as_posix()}',
        format: 'A4',
        printBackground: true,
        margin: {{
            top: '12mm',
            bottom: '12mm',
            left: '12mm',
            right: '12mm'
        }}
    }});
    await browser.close();
    console.log('[build_pdf] Rendered PDF successfully');
}})();
"""
    node_runner = ROOT / "docs" / "render_runner.js"
    node_runner.write_text(node_script, encoding="utf-8")

    try:
        proc = subprocess.run(
            ["node", str(node_runner)],
            cwd=str(ROOT / "apps" / "web"),
            capture_output=True,
            text=True,
            check=True,
        )
        print(proc.stdout)
    finally:
        if node_runner.exists():
            node_runner.unlink()

    if PDF_OUT.is_file():
        reader = pypdf.PdfReader(str(PDF_OUT))
        total_pages = len(reader.pages)
        print(f"[build_pdf] Successfully generated {PDF_OUT} ({total_pages} total pages)")

if __name__ == "__main__":
    generate_pdf()
