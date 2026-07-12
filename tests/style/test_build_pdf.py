import base64
from pathlib import Path

import pypdf
import pypdfium2 as pdfium

from build_pdf import (
    build_cover_html,
    build_body_html,
    render_pdf,
    PAPER_RGB,
    BODY_MARGIN_TOP_IN,
    BODY_MARGIN_BOTTOM_IN,
)
from md_to_html import render_markdown_to_html

TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_build_cover_html_includes_front_matter_and_paints_own_background():
    front_matter = {
        "title": "Sample Report",
        "authors": "A. Uthor",
        "affiliation": "Some Org",
        "date": "July 2026",
        "classification": "Internal",
    }
    html = build_cover_html(front_matter)
    assert "Sample Report" in html
    assert "A. Uthor" in html
    assert "Internal" in html
    assert "--color-paper: #F9F8F3" in html
    # cover paints its own full-bleed background (rendered with margin=0,
    # so unlike the body it can safely self-paint)
    assert "html, body { background: var(--color-paper); }" in html
    assert 'class="cover-title"' in html


def test_build_cover_html_handles_missing_front_matter_fields():
    html = build_cover_html({})
    assert 'class="cover-title"' in html


def test_build_body_html_has_no_background_and_no_fixed_elements():
    front_matter = {"title": "Sample Report", "classification": "Internal — Draft"}
    html = build_body_html(front_matter, "<h2>1. Intro</h2><p>Text.</p>")
    assert "<h2>1. Intro</h2><p>Text.</p>" in html
    # body must be transparent -- the paper background, running
    # header/footer, and page number are all painted by _paint_body_pages
    # afterwards, not by the HTML/CSS itself
    assert "html, body { background: transparent; }" in html
    # no running header/footer in the HTML: position:fixed does not reserve
    # flow space per page in Chromium and was found to overlap body text
    assert "running-header" not in html
    assert "running-footer" not in html
    assert "position: fixed" not in html


def test_render_pdf_produces_a_numbered_multipage_document(tmp_path):
    png_bytes = base64.b64decode(TINY_PNG_B64)
    (tmp_path / "tiny.png").write_bytes(png_bytes)
    md_path = tmp_path / "sample.md"
    md_path.write_text(
        '---\ntitle: "Sample"\nauthors: "A. Uthor"\nclassification: "Internal"\n---\n'
        '# Sample\n\n**A. Uthor**\n\n---\n\n## 1. Introduction\n\nSome text.\n',
        encoding="utf-8",
    )
    front_matter, body_html = render_markdown_to_html(md_path)

    output = tmp_path / "sample.pdf"
    render_pdf(front_matter, body_html, output)

    assert output.exists()
    assert output.stat().st_size > 1000

    reader = pypdf.PdfReader(str(output))
    # cover page (1) + at least one body page (2)
    assert len(reader.pages) >= 2
    body_text = reader.pages[1].extract_text()
    assert "Introduction" in body_text
    # the body page carries a stamped page number ("2")
    assert "2" in body_text


def test_render_pdf_every_page_is_paper_coloured_at_all_four_corners(tmp_path):
    """Regression test for the two-tone background bug: every page's four
    corners (not just the content area) must be the paper colour."""
    md_path = tmp_path / "sample.md"
    md_path.write_text(
        '---\ntitle: "Sample"\nclassification: "Internal"\n---\n'
        '# Sample\n\n**A. Uthor**\n\n---\n\n## 1. Introduction\n\n'
        + "<p>Some text.</p>\n" * 5,
        encoding="utf-8",
    )
    front_matter, body_html = render_markdown_to_html(md_path)
    output = tmp_path / "sample.pdf"
    render_pdf(front_matter, body_html, output)

    expected = tuple(round(c * 255) for c in PAPER_RGB)
    doc = pdfium.PdfDocument(str(output))
    for i in range(len(doc)):
        img = doc[i].render(scale=1.0).to_pil().convert("RGB")
        w, h = img.size
        # page 0 (cover) has a deliberate 3pt blue accent hairline across the
        # very top edge -- sample its top corners a few px lower, clear of it
        top_y = 8 if i == 0 else 2
        corners = {
            "top-left": img.getpixel((2, top_y)),
            "top-right": img.getpixel((w - 3, top_y)),
            "bottom-left": img.getpixel((2, h - 3)),
            "bottom-right": img.getpixel((w - 3, h - 3)),
        }
        for name, px in corners.items():
            # allow a small tolerance for anti-aliasing/rounding
            assert all(abs(a - b) <= 2 for a, b in zip(px, expected)), (
                f"page {i} {name} corner is {px}, expected ~{expected}"
            )


def test_render_pdf_running_header_does_not_overlap_body_text(tmp_path):
    """Regression test for the header/footer overlap bug: on a densely-filled
    body page, the running header/footer text must land inside the reserved
    margin band, never inside the content area where body text also lands."""
    md_path = tmp_path / "sample.md"
    dense_paragraphs = "\n\n".join(
        "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 10
        for _ in range(60)
    )
    md_path.write_text(
        '---\ntitle: "Sample Report Title"\nclassification: "Internal"\n---\n'
        f'# Sample\n\n**A. Uthor**\n\n---\n\n## 1. Introduction\n\n{dense_paragraphs}\n',
        encoding="utf-8",
    )
    front_matter, body_html = render_markdown_to_html(md_path)
    output = tmp_path / "sample.pdf"
    render_pdf(front_matter, body_html, output)

    reader = pypdf.PdfReader(str(output))
    assert len(reader.pages) >= 3, "test fixture must produce multiple body pages"

    top_margin_pt = BODY_MARGIN_TOP_IN * 72
    bottom_margin_pt = BODY_MARGIN_BOTTOM_IN * 72

    for i, page in enumerate(reader.pages[1:], start=1):
        height = float(page.mediabox.height)
        positions_by_text = {}

        def _visitor(text, cm, tm, font_dict, font_size):
            if text.strip():
                positions_by_text.setdefault(text.strip(), tm[5])

        page.extract_text(visitor_text=_visitor)

        title_ys = [y for t, y in positions_by_text.items() if "Sample Report Title" in t]
        body_ys = [y for t, y in positions_by_text.items() if "Lorem ipsum" in t]

        for title_y in title_ys:
            # the running header text must sit above the content area
            # (i.e. within the top margin band, not lower than it)
            assert title_y > height - top_margin_pt, (
                f"page {i}: running header at y={title_y} overlaps the "
                f"content area (top margin band starts at y={height - top_margin_pt})"
            )
        for body_y in body_ys:
            # body text must never render inside the reserved bottom margin
            assert body_y > bottom_margin_pt, (
                f"page {i}: body text at y={body_y} overlaps the bottom "
                f"margin band (band ends at y={bottom_margin_pt})"
            )
