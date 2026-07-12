"""
build_pdf.py -- render a Rayquaza markdown document to a styled PDF using
the design-token system in this directory.

Architecture (chosen after empirically testing Chromium's print behaviour):
  * Chromium's print-to-PDF does NOT paint the page-margin box with the
    html/body background -- any non-zero page margin renders white, causing
    a two-tone sheet. The only way to get a full-bleed paper-coloured page
    is to render with ALL margins set to zero and create the text inset with
    body padding instead.
  * With zero margins there is no room for Chromium's native running
    header/footer, so we render them as position:fixed elements in the body
    (Chromium repeats fixed elements on every printed page).
  * Chromium cannot evaluate CSS page counters, so page numbers are stamped
    onto the body pages afterwards with reportlab + pypdf.
  * The cover page must stay clean (no running header/footer), so the cover
    and body are rendered as two separate PDFs and merged -- the cover is
    page 1, the body pages are numbered starting at 2.

Run: python docs/style/build_pdf.py docs/paper/paper.md
"""
import argparse
import io
import re
from pathlib import Path

import pypdf
from reportlab.pdfgen import canvas
from playwright.sync_api import sync_playwright

from md_to_html import render_markdown_to_html

STYLE_DIR = Path(__file__).resolve().parent


def _load_css() -> tuple[str, str, str]:
    """Read tokens.css + subsystem-academic.css. Returns
    (tokens_css, subsystem_css_without_font_imports, font_link_tags).

    The Google-Fonts @import in subsystem-academic.css is positionally
    invalid once the CSS is inlined into a <style> block (CSS requires
    @import before all other rules), so it is extracted and re-emitted as
    <link> tags for the document <head>."""
    tokens_css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    subsystem_css = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    font_imports = re.findall(
        r'@import\s+url\([\'"]?(https://fonts\.googleapis\.com[^\'")\s]+)[\'"]?\)\s*;',
        subsystem_css,
    )
    subsystem_css = re.sub(
        r'@import\s+url\([\'"]?https://[^\'")\s]+[\'"]?\)\s*;', '', subsystem_css
    )
    font_links = '\n'.join(f'<link rel="stylesheet" href="{url}">' for url in font_imports)
    return tokens_css, subsystem_css, font_links


def _document_head(extra_css: str = "") -> str:
    """Shared <!doctype><head> with fonts + inlined design system CSS.
    `@page { margin: 0 }` gives the full-bleed paper sheet."""
    tokens_css, subsystem_css, font_links = _load_css()
    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{font_links}
<style>
@page {{ size: A4; margin: 0; }}
{tokens_css}
{subsystem_css}
{extra_css}
</style>
</head>'''


def build_cover_html(front_matter: dict) -> str:
    """Standalone one-page cover PDF source: full-bleed paper, a thin accent
    hairline at the top, and the document metadata. No running header/footer."""
    title = front_matter.get("title", "")
    authors = front_matter.get("authors", "")
    affiliation = front_matter.get("affiliation", "")
    date = front_matter.get("date", "")
    classification = front_matter.get("classification", "")

    extra_css = '''
    .cover { min-height: 100vh; box-sizing: border-box; padding: 0.9in 0.8in;
             display: flex; flex-direction: column; }
    .cover-rule { height: 3pt; background: var(--color-blue); width: 100%;
                  position: absolute; top: 0; left: 0; }
    .cover-eyebrow { font-family: var(--font-mono); font-size: 8pt;
                     letter-spacing: .1em; text-transform: uppercase;
                     color: var(--color-ink-soft); }
    .cover-title { font-size: 24pt; line-height: 1.25; margin-top: 2in;
                   max-width: 9in; font-weight: var(--weight-semibold); }
    .cover-authors { font-size: 12pt; margin-top: .32in;
                     font-weight: var(--weight-medium); }
    .cover-affil { font-size: 10.5pt; color: var(--color-ink-soft); margin-top: 2pt; }
    .cover-meta { margin-top: auto; display: flex; justify-content: space-between;
                  font-family: var(--font-mono); font-size: 8.5pt;
                  color: var(--color-ink-soft);
                  border-top: var(--stroke) solid var(--color-border);
                  padding-top: 8pt; }
    '''
    return f'''{_document_head(extra_css)}
<body>
  <div class="cover-rule"></div>
  <section class="cover">
    <div class="cover-eyebrow">{affiliation}</div>
    <h1 class="cover-title">{title}</h1>
    <p class="cover-authors">{authors}</p>
    <p class="cover-affil">{affiliation}</p>
    <div class="cover-meta">
      <span>{date}</span>
      <span>{classification}</span>
    </div>
  </section>
</body>
</html>'''


def build_body_html(front_matter: dict, body_html: str) -> str:
    """Body PDF source: full-bleed paper, text inset via body padding, and
    running header/footer as position:fixed elements that Chromium repeats on
    every printed page. The page number is NOT placed here -- it is stamped
    on afterwards (Chromium cannot evaluate CSS page counters)."""
    short_title = str(front_matter.get("title", ""))[:70]
    classification = str(front_matter.get("classification", ""))

    extra_css = '''
    body { padding: 0.85in 0.7in; }
    .running-header, .running-footer {
        position: fixed; left: 0; right: 0;
        font-family: var(--font-mono); font-size: 7.5pt;
        color: var(--color-ink-soft); padding: 0 0.7in;
        box-sizing: border-box; }
    .running-header { top: 0.4in; }
    .running-footer { bottom: 0.4in; }
    /* leave clear of the fixed running elements at the very top/bottom */
    article { padding-top: 2pt; }
    '''
    return f'''{_document_head(extra_css)}
<body>
  <div class="running-header">{short_title}</div>
  <div class="running-footer">{classification}</div>
  <article>
{body_html}
  </article>
</body>
</html>'''


def _render_html_to_pdf_bytes(html: str) -> bytes:
    """Render one HTML document to full-bleed A4 PDF bytes (all margins 0)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        data = page.pdf(
            format="A4",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
            prefer_css_page_size=True,
        )
        browser.close()
    return data


def _stamp_page_numbers(pdf_bytes: bytes, start_at: int = 1) -> bytes:
    """Stamp a right-aligned page number onto each page's footer band, since
    Chromium cannot evaluate CSS page counters. Uses reportlab to draw an
    overlay per page (page numbering begins at `start_at`)."""
    writer = pypdf.PdfWriter(clone_from=io.BytesIO(pdf_bytes))
    width = float(writer.pages[0].mediabox.width)
    height = float(writer.pages[0].mediabox.height)
    for i, page in enumerate(writer.pages):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(width, height))
        c.setFont("Courier", 7.5)
        c.setFillColorRGB(0.192, 0.192, 0.192)  # matches --color-ink-soft (#313131)
        c.drawRightString(width - 0.7 * 72, 0.4 * 72, str(start_at + i))
        c.save()
        buf.seek(0)
        page.merge_page(pypdf.PdfReader(buf).pages[0])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _merge_pdfs(*pdf_bytes_list: bytes) -> bytes:
    """Concatenate PDFs (given as bytes) into one, preserving order."""
    writer = pypdf.PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def render_pdf(front_matter: dict, body_html: str, output_path: Path) -> None:
    """Render the full document: a clean cover page (page 1) followed by the
    numbered body pages (starting at 2), written to output_path."""
    cover_pdf = _render_html_to_pdf_bytes(build_cover_html(front_matter))
    body_pdf = _render_html_to_pdf_bytes(build_body_html(front_matter, body_html))
    body_pdf = _stamp_page_numbers(body_pdf, start_at=2)
    final_pdf = _merge_pdfs(cover_pdf, body_pdf)
    Path(output_path).write_bytes(final_pdf)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Rayquaza markdown document to a styled PDF.")
    parser.add_argument("source", type=Path, help="Path to the source .md file")
    parser.add_argument("--output", type=Path, default=None, help="Output PDF path (default: same name, .pdf extension)")
    args = parser.parse_args()

    front_matter, body_html = render_markdown_to_html(args.source)
    output = args.output or args.source.with_suffix(".pdf")
    render_pdf(front_matter, body_html, output)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
