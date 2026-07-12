import base64
from pathlib import Path

import pypdf

from build_pdf import build_html_document, render_pdf
from md_to_html import render_markdown_to_html

TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_build_html_document_includes_front_matter_and_body():
    front_matter = {
        "title": "Sample Report",
        "authors": "A. Uthor",
        "affiliation": "Some Org",
        "date": "July 2026",
        "classification": "Internal",
    }
    html = build_html_document(front_matter, "<h2>1. Intro</h2><p>Text.</p>")
    assert "Sample Report" in html
    assert "A. Uthor" in html
    assert "Internal" in html
    assert "<h2>1. Intro</h2><p>Text.</p>" in html
    assert "--color-paper: #F9F8F3" in html
    assert '<div class="page-break"></div>' in html


def test_build_html_document_handles_missing_front_matter_fields():
    html = build_html_document({}, "<p>Body only.</p>")
    assert "<p>Body only.</p>" in html
    assert 'class="cover-title">' in html


def test_render_pdf_produces_a_two_page_document(tmp_path):
    png_bytes = base64.b64decode(TINY_PNG_B64)
    (tmp_path / "tiny.png").write_bytes(png_bytes)
    md_path = tmp_path / "sample.md"
    md_path.write_text(
        '---\ntitle: "Sample"\nauthors: "A. Uthor"\nclassification: "Internal"\n---\n'
        '# Sample\n\n**A. Uthor**\n\n---\n\n## 1. Introduction\n\nSome text.\n',
        encoding="utf-8",
    )
    front_matter, body_html = render_markdown_to_html(md_path)
    html = build_html_document(front_matter, body_html)

    output = tmp_path / "sample.pdf"
    render_pdf(html, output, short_title="Sample", classification="Internal")

    assert output.exists()
    assert output.stat().st_size > 1000

    reader = pypdf.PdfReader(str(output))
    assert len(reader.pages) >= 2
    text = reader.pages[1].extract_text()
    assert "Introduction" in text
