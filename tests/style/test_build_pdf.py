import base64
from pathlib import Path

import pypdf

from build_pdf import build_cover_html, build_body_html, render_pdf
from md_to_html import render_markdown_to_html

TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_build_cover_html_includes_front_matter_and_full_bleed():
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
    # full-bleed sheet requires a zero-margin page box
    assert "@page { size: A4; margin: 0; }" in html
    assert 'class="cover-title"' in html


def test_build_cover_html_handles_missing_front_matter_fields():
    html = build_cover_html({})
    assert 'class="cover-title"' in html
    assert "@page { size: A4; margin: 0; }" in html


def test_build_body_html_has_running_elements_and_body():
    front_matter = {"title": "Sample Report", "classification": "Internal — Draft"}
    html = build_body_html(front_matter, "<h2>1. Intro</h2><p>Text.</p>")
    assert "<h2>1. Intro</h2><p>Text.</p>" in html
    assert 'class="running-header"' in html
    assert 'class="running-footer"' in html
    # running elements must be fixed so Chromium repeats them per page
    assert "position: fixed" in html
    assert "Internal — Draft" in html


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
