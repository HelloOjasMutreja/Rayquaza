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
