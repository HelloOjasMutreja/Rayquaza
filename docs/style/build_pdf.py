"""
build_pdf.py -- render a Rayquaza markdown document to a styled PDF using
the design-token system in this directory.

Run: python docs/style/build_pdf.py docs/paper/paper.md
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from md_to_html import render_markdown_to_html

STYLE_DIR = Path(__file__).resolve().parent


def build_html_document(front_matter: dict, body_html: str) -> str:
    """Assemble the full standalone HTML document: inlined tokens.css +
    subsystem-academic.css, a cover page built from front_matter, then the
    rendered document body."""
    tokens_css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    subsystem_css = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    title = front_matter.get("title", "")
    authors = front_matter.get("authors", "")
    affiliation = front_matter.get("affiliation", "")
    date = front_matter.get("date", "")
    classification = front_matter.get("classification", "")

    cover = f'''
    <section class="cover">
      <div class="cover-eyebrow">{affiliation}</div>
      <h1 class="cover-title">{title}</h1>
      <p class="cover-authors">{authors}</p>
      <div class="cover-meta">
        <span>{date}</span>
        <span>{classification}</span>
      </div>
    </section>
    <div class="page-break"></div>
    '''

    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
{tokens_css}
{subsystem_css}
.cover {{ display:flex; flex-direction:column; height: 9.5in; }}
.cover-eyebrow {{ font-family: var(--font-mono); font-size:8pt; letter-spacing:.1em; text-transform:uppercase; color: var(--color-ink-soft); }}
.cover-title {{ font-size:22pt; margin-top:2in; max-width:9in; }}
.cover-authors {{ font-size:11pt; margin-top:.3in; font-weight: var(--weight-medium); }}
.cover-meta {{ margin-top:auto; display:flex; justify-content:space-between; font-family: var(--font-mono); font-size:8pt; color: var(--color-ink-soft); border-top: var(--stroke) solid var(--color-border); padding-top:8pt; }}
.page-break {{ break-after: page; }}
</style>
</head>
<body>
{cover}
<article>
{body_html}
</article>
</body>
</html>'''


def render_pdf(html: str, output_path: Path, short_title: str = "", classification: str = "") -> None:
    """Render html to a PDF at output_path using headless Chromium, with a
    running header (short_title) and footer (classification + page number)."""
    header_template = (
        '<div style="font-family:\'Roboto Mono\',monospace;font-size:7px;'
        'width:100%;padding:0 0.7in;color:#8a8a85;display:flex;justify-content:space-between;">'
        f'<span>{short_title}</span></div>'
    )
    footer_template = (
        '<div style="font-family:\'Roboto Mono\',monospace;font-size:7px;'
        'width:100%;padding:0 0.7in;color:#8a8a85;display:flex;justify-content:space-between;">'
        f'<span>{classification}</span><span class="pageNumber"></span></div>'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="A4",
            display_header_footer=True,
            header_template=header_template,
            footer_template=footer_template,
            margin={"top": "0.75in", "bottom": "0.75in", "left": "0.7in", "right": "0.7in"},
            print_background=True,
        )
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Rayquaza markdown document to a styled PDF.")
    parser.add_argument("source", type=Path, help="Path to the source .md file")
    parser.add_argument("--output", type=Path, default=None, help="Output PDF path (default: same name, .pdf extension)")
    args = parser.parse_args()

    front_matter, body_html = render_markdown_to_html(args.source)
    html = build_html_document(front_matter, body_html)

    output = args.output or args.source.with_suffix(".pdf")
    short_title = str(front_matter.get("title", args.source.stem))[:60]
    classification = str(front_matter.get("classification", ""))
    render_pdf(html, output, short_title=short_title, classification=classification)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
