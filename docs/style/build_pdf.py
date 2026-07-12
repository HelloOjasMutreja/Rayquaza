"""
build_pdf.py -- render a Rayquaza markdown document to a styled PDF using
the design-token system in this directory.

Run: python docs/style/build_pdf.py docs/paper/paper.md
"""
import argparse
from pathlib import Path

from md_to_html import render_markdown_to_html

STYLE_DIR = Path(__file__).resolve().parent


def build_html_document(front_matter: dict, body_html: str) -> str:
    """Assemble the full standalone HTML document: inlined tokens.css +
    subsystem-academic.css, a cover page built from front_matter, then the
    rendered document body."""
    tokens_css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    subsystem_css = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    title = front_matter.get("title", "")
    authors = front_matter.get("authors", "")
    affiliation = front_matter.get("affiliation", "")
    date = front_matter.get("date", "")
    classification = front_matter.get("classification", "")

    cover = f'''
    <section class="cover">
      <div class="cover-eyebrow">{affiliation}</div>
      <h1 class="cover-title">{title}</h1>
      <p class="cover-authors">{authors}</p>
      <div class="cover-meta">
        <span>{date}</span>
        <span>{classification}</span>
      </div>
    </section>
    <div class="page-break"></div>
    '''

    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
{tokens_css}
{subsystem_css}
.cover {{ display:flex; flex-direction:column; height: 9.5in; }}
.cover-eyebrow {{ font-family: var(--font-mono); font-size:8pt; letter-spacing:.1em; text-transform:uppercase; color: var(--color-ink-soft); }}
.cover-title {{ font-size:22pt; margin-top:2in; max-width:9in; }}
.cover-authors {{ font-size:11pt; margin-top:.3in; font-weight: var(--weight-medium); }}
.cover-meta {{ margin-top:auto; display:flex; justify-content:space-between; font-family: var(--font-mono); font-size:8pt; color: var(--color-ink-soft); border-top: var(--stroke) solid var(--color-border); padding-top:8pt; }}
.page-break {{ break-after: page; }}
</style>
</head>
<body>
{cover}
<article>
{body_html}
</article>
</body>
</html>'''
