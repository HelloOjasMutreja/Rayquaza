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
