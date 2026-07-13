import base64
from pathlib import Path

from md_to_html import parse_front_matter, embed_images

TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_parse_front_matter_extracts_yaml_block():
    text = "---\ntitle: Foo\nauthors: Bar\n---\n\nBody text here."
    front_matter, body = parse_front_matter(text)
    assert front_matter == {"title": "Foo", "authors": "Bar"}
    assert body == "Body text here."


def test_parse_front_matter_no_block_returns_empty_dict():
    text = "# Just a heading\n\nBody."
    front_matter, body = parse_front_matter(text)
    assert front_matter == {}
    assert body == text


def test_embed_images_converts_relative_png_to_data_uri(tmp_path):
    png_bytes = base64.b64decode(TINY_PNG_B64)
    (tmp_path / "tiny.png").write_bytes(png_bytes)
    md = "![alt text](tiny.png)"
    result = embed_images(md, tmp_path)
    expected_b64 = base64.b64encode(png_bytes).decode("ascii")
    assert result == f"![alt text](data:image/png;base64,{expected_b64})"


def test_embed_images_leaves_non_png_and_urls_untouched():
    md = "![a](http://example.com/x.png) and ![b](fig.svg)"
    result = embed_images(md, Path("."))
    assert result == md


def test_strip_title_block_removes_leading_h1_author_hr():
    from md_to_html import strip_title_block
    html = (
        "<h1>Title</h1>\n"
        "<p><strong>Authors</strong><br>Affiliation</p>\n"
        "<hr />\n"
        "<h2>Abstract</h2>\n<p>Body.</p>"
    )
    result = strip_title_block(html)
    assert result == "<h2>Abstract</h2>\n<p>Body.</p>"


def test_strip_title_block_noop_if_no_leading_h1():
    from md_to_html import strip_title_block
    html = "<h2>Abstract</h2>\n<p>Body.</p>"
    assert strip_title_block(html) == html


def test_number_and_id_headings_top_level_numbered_heading():
    from md_to_html import number_and_id_headings
    html = "<h2>5. Multi-Model Comparison</h2>"
    result = number_and_id_headings(html)
    assert result == (
        '<h2 id="5-multi-model-comparison">'
        '<span class="secnum">5.</span> Multi-Model Comparison</h2>'
    )


def test_number_and_id_headings_subsection_numbered_heading():
    from md_to_html import number_and_id_headings
    html = "<h3>5.6 Autonomous vs. Hybrid</h3>"
    result = number_and_id_headings(html)
    assert result == (
        '<h3 id="56-autonomous-vs-hybrid">'
        '<span class="secnum">5.6</span> Autonomous vs. Hybrid</h3>'
    )


def test_number_and_id_headings_unnumbered_heading_gets_id_only():
    from md_to_html import number_and_id_headings
    html = "<h2>Abstract</h2>"
    result = number_and_id_headings(html)
    assert result == '<h2 id="abstract">Abstract</h2>'


def test_number_and_id_headings_part_style_heading():
    from md_to_html import number_and_id_headings
    html = "<h2>Part 1 — Why this research exists</h2>"
    result = number_and_id_headings(html)
    assert result == (
        '<h2 id="part-1-why-this-research-exists">'
        '<span class="secnum">Part 1</span> Why this research exists</h2>'
    )


def test_number_and_id_headings_part_style_heading_with_decimal():
    from md_to_html import number_and_id_headings
    html = "<h2>Part 4.5 — Then we asked something</h2>"
    result = number_and_id_headings(html)
    assert result == (
        '<h2 id="part-45-then-we-asked-something">'
        '<span class="secnum">Part 4.5</span> Then we asked something</h2>'
    )


def test_wrap_figures_merges_image_and_caption_paragraph():
    from md_to_html import wrap_figures
    html = (
        '<p><img alt="Figure 0" src="data:image/png;base64,AAAA" /></p>\n'
        '<p><strong>Figure 0.</strong> The pipeline diagram.</p>'
    )
    result = wrap_figures(html)
    assert result == (
        '<figure><img alt="Figure 0" src="data:image/png;base64,AAAA">'
        '<figcaption><span class="fignum">Figure 0.</span> The pipeline diagram.</figcaption></figure>'
    )


def test_wrap_figures_leaves_unpaired_image_untouched():
    from md_to_html import wrap_figures
    html = '<p><img alt="x" src="data:image/png;base64,AAAA" /></p>\n<p>Unrelated text.</p>'
    assert wrap_figures(html) == html


def test_wrap_tables_styles_caption_paragraph():
    from md_to_html import wrap_tables
    html = '<p><strong>Table 1: Planted leaks.</strong></p>'
    result = wrap_tables(html)
    assert result == '<p class="table-caption"><span class="fignum">Table 1: Planted leaks.</span> </p>'


def test_wrap_tables_wraps_table_element():
    from md_to_html import wrap_tables
    html = '<table><tr><td>x</td></tr></table>'
    result = wrap_tables(html)
    assert result == '<div class="table-wrap"><table><tr><td>x</td></tr></table></div>'


def test_wrap_callouts_headline():
    from md_to_html import wrap_callouts
    html = '<p><strong>Headline</strong>: codellama:7b found 4/5 leaks.</p>'
    result = wrap_callouts(html)
    assert result == '<div class="callout callout--headline"><span class="pill">HEADLINE</span>codellama:7b found 4/5 leaks.</div>'


def test_wrap_callouts_finding():
    from md_to_html import wrap_callouts
    html = '<p><strong>Finding</strong>: portability is not guaranteed.</p>'
    result = wrap_callouts(html)
    assert result == '<div class="callout callout--finding"><span class="pill">FINDING</span>portability is not guaranteed.</div>'


def test_wrap_callouts_leaves_other_bold_paragraphs_untouched():
    from md_to_html import wrap_callouts
    html = '<p><strong>Note</strong>: something else.</p>'
    assert wrap_callouts(html) == html


def test_wrap_reftags_styles_bracket_tag():
    from md_to_html import wrap_reftags
    html = '<li>[REF-KYBERSLASH] M. J. Kannwischer et al.</li>'
    result = wrap_reftags(html)
    assert result == '<li><span class="reftag">REF-KYBERSLASH</span> M. J. Kannwischer et al.</li>'


def test_wrap_reftags_leaves_normal_list_items_untouched():
    from md_to_html import wrap_reftags
    html = '<li>Not a reference.</li>'
    assert wrap_reftags(html) == html


FIXTURE_MD = '''---
title: "Sample Report"
authors: "A. Uthor"
template: paper
---
# Sample Report

**A. Uthor**
Some Affiliation

---

## 1. Introduction

Some intro text.

![Figure 0](tiny.png)

**Figure 0.** A tiny test figure.

**Table 1: A small table.**

| A | B |
|---|---|
| 1 | 2 |

**Finding**: something notable happened.

## References

- [REF-FOO] Some Author, "A Paper," 2020.
'''


def test_render_markdown_to_html_preserves_fenced_code_block_layout(tmp_path):
    """Regression test: triple-backtick fenced blocks (e.g. ASCII diagrams)
    must render as a real <pre><code> block with line breaks preserved, not
    reflow as wrapped prose. This requires the 'fenced_code' markdown
    extension -- without it, ``` blocks silently fall through as an inline
    <code> span inside a <p>, and the whitespace/line-break structure of an
    ASCII diagram is lost."""
    from md_to_html import render_markdown_to_html

    md_path = tmp_path / "sample.md"
    md_path.write_text(
        "# Sample\n\n**A. Uthor**\n\n---\n\n## 1. Diagram\n\n"
        "```\n"
        "+------+     +------+\n"
        "| A    | --> | B    |\n"
        "+------+     +------+\n"
        "```\n",
        encoding="utf-8",
    )
    front_matter, html = render_markdown_to_html(md_path)

    assert "<pre>" in html and "<code>" in html
    # exact line structure of the diagram must survive, not be collapsed
    # into a single wrapped paragraph ('-->' is correctly HTML-escaped
    # to '--&gt;' inside the code block, so match that)
    assert "+------+     +------+" in html
    assert "| A    | --&gt; | B    |" in html


def test_render_markdown_to_html_full_pipeline(tmp_path):
    from md_to_html import render_markdown_to_html

    png_bytes = base64.b64decode(TINY_PNG_B64)
    (tmp_path / "tiny.png").write_bytes(png_bytes)
    md_path = tmp_path / "sample.md"
    md_path.write_text(FIXTURE_MD, encoding="utf-8")

    front_matter, html = render_markdown_to_html(md_path)

    assert front_matter == {"title": "Sample Report", "authors": "A. Uthor", "template": "paper"}
    assert not html.strip().startswith("<h1>")
    assert '<span class="secnum">1.</span> Introduction' in html
    assert "<figure>" in html and "data:image/png;base64," in html
    assert '<div class="table-wrap">' in html
    assert '<p class="table-caption">' in html
    assert '<div class="callout callout--finding"><span class="pill">FINDING</span>' in html
    assert '<span class="reftag">REF-FOO</span>' in html
