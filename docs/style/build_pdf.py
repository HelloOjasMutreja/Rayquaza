"""
build_pdf.py -- render a Rayquaza markdown document to a styled PDF using
the design-token system in this directory.

Architecture (chosen after empirically testing Chromium's real print
behaviour, twice -- see git history for the two failed attempts):

  1. Chromium's print-to-PDF never paints the page-*margin* box with the
     page's own background, no matter what CSS is set on html/body -- only
     the printable content area gets it. With a non-zero margin, the margin
     band is always a plain white strip. The only way to get a true
     full-bleed paper page from Chromium alone is margin = 0.

  2. But margin = 0 leaves no room for a *repeating* header/footer:
     `position: fixed` elements in Chromium's paged output repeat on every
     page (as documented), but they do NOT reserve space in the surrounding
     content flow -- normal content just flows continuously underneath them,
     so dense text collides with the fixed band on every page after the
     first. (Verified directly: rendered a 4-page dense-text document with
     a margin:0 + position:fixed header/footer and the header/footer text
     visibly overlapped body paragraphs on pages 2-4.)

  3. Chromium's own header_template/footer_template mechanism (used with a
     non-zero page margin) DOES give correct, non-overlapping pagination --
     the margin is real reserved space, guaranteed by the browser's page box
     model. But the template's rendered content does not reliably fill the
     full margin band edge-to-edge (verified: even with an explicit pixel
     height equal to the margin, a white sliver remained at the true page
     edge), so it cannot be used to paint the margin the paper colour.

  4. The approach that is actually correct on all three fronts (real
     pagination, full-bleed colour, no overlap) is to let Chromium paginate
     the body with a real, non-zero margin and a **transparent** background
     (so nothing is painted over the margin OR the content area by Chromium),
     then post-process every rendered page ourselves: paint a full-page
     paper-coloured rectangle as the base layer, draw the running
     header/footer text and page number directly onto it with reportlab, and
     merge Chromium's (background-less) page content on top. This has been
     verified to give clean paper corners on every page and zero overlap
     between the running header/footer and body text.

  The cover page is simpler -- it is one page, has no running header/footer,
  and needs no post-processing: it is rendered directly with margin = 0 and
  paints its own full-bleed background via CSS (case 1 above, which is
  correct when there's no repeating header/footer to fight over the margin).

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

# Body page margins (inches). Real @page-equivalent margins so Chromium
# reserves this space on every page -- guaranteed no overlap with the
# running header/footer, which is painted into exactly this band afterwards.
BODY_MARGIN_TOP_IN = 0.75
BODY_MARGIN_BOTTOM_IN = 0.75
BODY_MARGIN_LEFT_IN = 0.62
BODY_MARGIN_RIGHT_IN = 0.62

PAPER_RGB = (249 / 255, 248 / 255, 243 / 255)   # --color-paper #F9F8F3
INK_SOFT_RGB = (0x31 / 255, 0x31 / 255, 0x31 / 255)  # --color-ink-soft #313131


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
    """Shared <!doctype><head> with fonts + inlined design system CSS."""
    tokens_css, subsystem_css, font_links = _load_css()
    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{font_links}
<style>
{tokens_css}
{subsystem_css}
{extra_css}
</style>
</head>'''


def build_cover_html(front_matter: dict) -> str:
    """Standalone one-page cover PDF source: full-bleed paper (rendered with
    margin=0, no repeating header/footer to fight over the margin band), a
    thin accent hairline at the top, and the document metadata."""
    title = front_matter.get("title", "")
    authors = front_matter.get("authors", "")
    affiliation = front_matter.get("affiliation", "")
    date = front_matter.get("date", "")
    classification = front_matter.get("classification", "")

    extra_css = '''
    html, body { background: var(--color-paper); }
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
    """Body PDF source: html/body deliberately left transparent (no
    background), since Chromium's real page margin is used for pagination
    and the paper background + running header/footer + page number are all
    painted afterwards as a per-page reportlab underlay (see module
    docstring for why)."""
    # No horizontal body padding: the left/right text inset comes entirely
    # from Chromium's page margin (BODY_MARGIN_LEFT/RIGHT_IN), so body text
    # aligns exactly with the reportlab-painted running header/footer, which
    # are drawn at the same margin offset.
    extra_css = '''
    html, body { background: transparent; }
    body { padding: 0; }
    '''
    return f'''{_document_head(extra_css)}
<body>
<article>
{body_html}
</article>
</body>
</html>'''


def _render_cover_pdf_bytes(html: str) -> bytes:
    """Render the (self-painted, full-bleed) cover page: margin = 0."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        data = page.pdf(
            format="A4",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
        )
        browser.close()
    return data


def _render_body_pdf_bytes(html: str) -> bytes:
    """Render the (transparent-background) body pages with a real page
    margin, so Chromium reserves that space on every page -- this is what
    guarantees no overlap with the running header/footer/page-number that
    gets painted into that band afterwards."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        data = page.pdf(
            format="A4",
            margin={
                "top": f"{BODY_MARGIN_TOP_IN}in",
                "bottom": f"{BODY_MARGIN_BOTTOM_IN}in",
                "left": f"{BODY_MARGIN_LEFT_IN}in",
                "right": f"{BODY_MARGIN_RIGHT_IN}in",
            },
            print_background=True,
        )
        browser.close()
    return data


def _paint_body_pages(pdf_bytes: bytes, short_title: str, classification: str, start_at: int) -> bytes:
    """For every page of the (transparent) body PDF: paint a full-page paper
    rectangle, draw the running header/footer text and page number into the
    reserved margin band, then merge the Chromium page content on top. Page
    numbering begins at `start_at` (the cover page occupies page 1).

    Builds a fresh writer rather than mutating the cloned one in place --
    each source page is merged onto its own reportlab-drawn underlay page,
    and only the merged result is added to the output."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    width = float(reader.pages[0].mediabox.width)
    height = float(reader.pages[0].mediabox.height)
    left_pt = BODY_MARGIN_LEFT_IN * 72
    right_pt = BODY_MARGIN_RIGHT_IN * 72
    top_pt = BODY_MARGIN_TOP_IN * 72
    bottom_pt = BODY_MARGIN_BOTTOM_IN * 72

    writer = pypdf.PdfWriter()
    for i, chromium_page in enumerate(reader.pages):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(width, height))
        c.setFillColorRGB(*PAPER_RGB)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFont("Helvetica", 7.5)
        c.setFillColorRGB(*INK_SOFT_RGB)
        c.drawString(left_pt, height - top_pt + 10, short_title)
        c.drawString(left_pt, bottom_pt - 18, classification)
        c.drawRightString(width - right_pt, bottom_pt - 18, str(start_at + i))
        c.save()
        buf.seek(0)
        underlay = pypdf.PdfReader(buf).pages[0]
        # attach to the writer before merging -- merging onto a page that
        # isn't yet assigned to a writer is deprecated in pypdf
        attached = writer.add_page(underlay)
        attached.merge_page(chromium_page)
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
    short_title = str(front_matter.get("title", ""))[:70]
    classification = str(front_matter.get("classification", ""))

    cover_pdf = _render_cover_pdf_bytes(build_cover_html(front_matter))
    body_pdf = _render_body_pdf_bytes(build_body_html(front_matter, body_html))
    body_pdf = _paint_body_pages(body_pdf, short_title, classification, start_at=2)
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
