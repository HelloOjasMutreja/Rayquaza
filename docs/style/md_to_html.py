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
