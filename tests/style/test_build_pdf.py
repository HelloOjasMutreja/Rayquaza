from build_pdf import build_html_document


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
