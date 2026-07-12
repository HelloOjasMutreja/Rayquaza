"""
md_to_html.py -- markdown -> styled HTML pipeline for the Rayquaza PDF
design system. Each transform below is a small, independently-tested
function; render_markdown_to_html() (added last) composes them in order.
"""
import base64
import re
from pathlib import Path

import markdown as _markdown
import yaml


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a leading '---\\n...\\n---' YAML block off the top of text.
    Returns (front_matter_dict, remaining_text). If there is no front-matter
    block, returns ({}, text) unchanged."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            fm_text = text[4:end]
            body = text[end + 4:]
            body = body.lstrip("\n")
            front_matter = yaml.safe_load(fm_text) or {}
            return front_matter, body
    return {}, text


def embed_images(md_text: str, base_dir: Path) -> str:
    """In markdown source text, replace ![alt](relative/path.png) references
    with ![alt](data:image/png;base64,...) data URIs, resolved relative to
    base_dir. References to non-.png images, absolute URLs, or already-data
    URIs are left unchanged."""
    def _embed(match: re.Match) -> str:
        alt, src = match.group(1), match.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)
        if not src.lower().endswith(".png"):
            return match.group(0)
        image_path = base_dir / src
        image_bytes = image_path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return f"![{alt}](data:image/png;base64,{b64})"
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _embed, md_text)


def strip_title_block(html: str) -> str:
    """Remove a leading <h1>...</h1><p>...</p><hr/> block (the document's
    manual title/author block), since front-matter supplies the same data
    for the cover page. No-op if the document doesn't start with an <h1>."""
    pattern = re.compile(r"^\s*<h1>.*?</h1>\s*<p>.*?</p>\s*<hr\s*/?>\s*", re.S)
    return pattern.sub("", html, count=1)


def _slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def number_and_id_headings(html: str) -> str:
    """For every <h2>/<h3>, inject a slugified id attribute. If the heading
    text starts with a section number (e.g. '5.' or '5.6'), wrap that
    numbering token in <span class="secnum">...</span>, exactly as it
    appears in the source (with or without a trailing period)."""
    def _repl(match: re.Match) -> str:
        level, inner = match.group(1), match.group(2)
        slug = _slugify(inner)
        numbering = re.match(r"^(\d+(?:\.\d+)*\.?)\s+(.*)$", inner)
        if numbering:
            rendered = f'<span class="secnum">{numbering.group(1)}</span> {numbering.group(2)}'
        else:
            rendered = inner
        return f'<h{level} id="{slug}">{rendered}</h{level}>'
    return re.sub(r"<h([23])>(.*?)</h\1>", _repl, html)


def wrap_figures(html: str) -> str:
    """Merge a '<p><img ...></p>' immediately followed by a
    '<p><strong>Figure N.</strong> caption</p>' into one <figure> block.
    Pairs not matching this exact shape are left untouched."""
    pattern = re.compile(
        r'<p><img alt="([^"]*)" src="([^"]+)"\s*/?></p>\s*'
        r'<p><strong>(Figure \d+\.)</strong>\s*(.*?)</p>',
        re.S,
    )
    def _repl(match: re.Match) -> str:
        alt, src, fignum, caption = match.groups()
        return (
            f'<figure><img alt="{alt}" src="{src}">'
            f'<figcaption><span class="fignum">{fignum}</span> {caption}</figcaption></figure>'
        )
    return pattern.sub(_repl, html)


def wrap_tables(html: str) -> str:
    """Style '<p><strong>Table N...</strong> rest</p>' caption paragraphs,
    and wrap every <table> in a <div class="table-wrap">."""
    html = re.sub(
        r'<p><strong>(Table \d+[^<]*)</strong>\s*(.*?)</p>',
        lambda m: f'<p class="table-caption"><span class="fignum">{m.group(1)}</span> {m.group(2)}</p>',
        html, flags=re.S,
    )
    html = html.replace("<table>", '<div class="table-wrap"><table>')
    html = html.replace("</table>", "</table></div>")
    return html


def wrap_callouts(html: str) -> str:
    """Convert '<p><strong>Headline</strong>: text</p>' or
    '<p><strong>Finding</strong>: text</p>' paragraphs into a callout
    box with a solid pill label. A modifier class (callout--headline /
    callout--finding) is emitted so CSS can apply semantic accent colours
    per label type."""
    pattern = re.compile(r'<p><strong>(Headline|Finding)</strong>:?\s*(.*?)</p>', re.S)
    def _repl(match: re.Match) -> str:
        label, body = match.groups()
        modifier = label.lower()
        return f'<div class="callout callout--{modifier}"><span class="pill">{label.upper()}</span>{body}</div>'
    return pattern.sub(_repl, html)


def wrap_reftags(html: str) -> str:
    """Style '[REF-FOO]' bracket tags at the start of a References <li>
    as a small mono pill."""
    return re.sub(
        r'<li>\[(REF-[A-Z0-9-]+)\]\s*',
        lambda m: f'<li><span class="reftag">{m.group(1)}</span> ',
        html,
    )


def render_markdown_to_html(md_path: Path) -> tuple[dict, str]:
    """Full pipeline: read md_path, split front matter, render the
    remaining markdown to HTML, strip the manual title block, then apply
    every wrap_*/number_and_id_headings transform in order. Returns
    (front_matter, body_html)."""
    raw = md_path.read_text(encoding="utf-8")
    front_matter, body_md = parse_front_matter(raw)
    body_md = embed_images(body_md, md_path.parent)
    converter = _markdown.Markdown(extensions=["tables", "sane_lists", "footnotes", "smarty", "fenced_code"])
    html = converter.convert(body_md)
    html = strip_title_block(html)
    html = number_and_id_headings(html)
    html = wrap_figures(html)
    html = wrap_tables(html)
    html = wrap_callouts(html)
    html = wrap_reftags(html)
    return front_matter, html
