from md_to_html import parse_front_matter


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
