# PDF Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable markdown-to-PDF pipeline for Rayquaza's long-form documents, fully specifying and implementing the primary/academic subsystem, then produce the first real PDF from `docs/paper/paper.md`.

**Architecture:** A two-layer CSS token system (`docs/style/tokens.css` primitives + `docs/style/subsystem-academic.css` semantic mapping) consumed by a markdown→HTML pipeline (`docs/style/md_to_html.py`, built as small composable regex/string transforms, each independently tested) which feeds a Playwright/Chromium PDF exporter (`docs/style/build_pdf.py`). Every source document declares its metadata as YAML front-matter.

**Tech Stack:** Python 3.14, `markdown` (Python-Markdown), `pyyaml`, `playwright` (headless Chromium), `pypdf` (test verification only), `pytest`.

## Global Constraints

- Colors (exact hex, from spec §3.1): `paper` #F9F8F3, `surface` #E2E1DA, `border` #BEBEBE, `ink-soft` #313131, `ink` #262626, `blue` #0099FF, `green` #2FBB45, `orange` #DC762D, `red` #FB2C55. `#979797` is explicitly excluded from every file in this system.
- Typography: Public Sans for body/headings (weights 400/500/600 only — no Light, no Bold/Black). Roboto Mono for labels/meta/code/table data (weight 400 only — no Light, no Bold).
- Radius: concentric chain only — outer 12px (padding 6), mid 6px (padding 3), inner 3px. No arbitrary radius values outside this chain.
- Strokes: all rules/borders/dividers are 1px, always the `border` color token. This is independent of font weight.
- Section references use `§` (e.g. `§ 5.6`).
- Finding/Headline callouts use a neutral box (`surface` fill, no colored border/edge) with a small solid-fill pill label — per user direction, the pill uses the neutral `ink`/`paper` pair (dark fill, light text) rather than an accent color, since accent colors are reserved for places where they carry real semantic meaning.
- Page size: A4. Margins: 0.75in top/bottom, 0.7in left/right.
- Renderer: Playwright + headless Chromium (already verified working on this machine — `pip install playwright && python -m playwright install chromium`). WeasyPrint is not used (blocked by a missing GTK3 native runtime on this machine).
- Spec source of truth: `docs/superpowers/specs/2026-07-12-pdf-design-system-design.md`.

---

## File Structure

**Create:**
- `docs/style/tokens.css` — primitive design tokens (color/type/radius/spacing)
- `docs/style/subsystem-academic.css` — semantic mapping for the paper.md subsystem
- `docs/style/md_to_html.py` — markdown → styled HTML pipeline, composed of small tested transforms
- `docs/style/build_pdf.py` — HTML page assembly (cover page) + Playwright PDF export + CLI
- `requirements-style.txt` — `markdown`, `pyyaml`, `playwright`, `pypdf`, `pytest`
- `tests/style/conftest.py` — puts `docs/style/` on `sys.path` for the other test files
- `tests/style/test_tokens_css.py`
- `tests/style/test_md_to_html.py`
- `tests/style/test_build_pdf.py`

**Modify:**
- `docs/paper/paper.md` — add a YAML front-matter block at the very top (title/authors/affiliation/date/classification/template); existing manual title block (`# Rayquaza: ...` / authors paragraph / `---`) is left in place for plain-markdown readers and is stripped automatically by the render pipeline.

---

### Task 1: Scaffold — tokens.css, subsystem-academic.css, requirements, CSS sanity tests

**Files:**
- Create: `docs/style/tokens.css`
- Create: `docs/style/subsystem-academic.css`
- Create: `requirements-style.txt`
- Create: `tests/style/conftest.py`
- Create: `tests/style/test_tokens_css.py`

**Interfaces:**
- Produces: two CSS files consumed by every later task via file-read (no Python API — CSS custom properties are consumed directly by the browser at render time).

- [ ] **Step 1: Create the requirements file**

`requirements-style.txt`:
```
markdown>=3.10
pyyaml>=6.0
playwright>=1.61
pypdf>=6.14
pytest>=8.0
```

- [ ] **Step 2: Install dependencies and the Chromium browser**

```bash
pip install -r requirements-style.txt
python -m playwright install chromium
```

Expected: both commands complete without error. (Both were already verified working on this machine during planning — if `playwright install chromium` fails here, stop and diagnose before continuing; nothing downstream will work without it.)

- [ ] **Step 3: Create `docs/style/tokens.css`**

```css
/* Rayquaza PDF design system -- primitive tokens.
   Never consumed directly by content; only ever referenced by a subsystem
   file (e.g. subsystem-academic.css). See
   docs/superpowers/specs/2026-07-12-pdf-design-system-design.md */

:root {
  /* color primitives */
  --color-paper: #F9F8F3;
  --color-surface: #E2E1DA;
  --color-border: #BEBEBE;
  --color-ink-soft: #313131;
  --color-ink: #262626;
  --color-blue: #0099FF;
  --color-green: #2FBB45;
  --color-orange: #DC762D;
  --color-red: #FB2C55;

  /* type primitives */
  --font-sans: "Public Sans", sans-serif;
  --font-mono: "Roboto Mono", monospace;
  --weight-regular: 400;
  --weight-medium: 500;
  --weight-semibold: 600;

  /* radius primitives -- concentric chain, outer 12 / mid 6 / inner 3 */
  --radius-outer: 12px;
  --radius-mid: 6px;
  --radius-inner: 3px;
  --radius-pad-outer: 6px;
  --radius-pad-mid: 3px;

  /* spacing primitives */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  /* stroke width -- all rules/borders use this, never a different width */
  --stroke: 1px;
}
```

- [ ] **Step 4: Create `docs/style/subsystem-academic.css`**

```css
/* Rayquaza PDF design system -- "academic" subsystem.
   Maps tokens.css primitives to semantic roles for paper.md-style reports.
   Every value here must trace back to a var(--...) in tokens.css --
   no new hex colors, no new radius values outside the concentric chain. */

@import url('tokens.css');
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Roboto+Mono:wght@400&display=swap');

body {
  background: var(--color-paper);
  color: var(--color-ink);
  font-family: var(--font-sans);
  font-weight: var(--weight-regular);
  font-size: 11.5pt;
  line-height: 1.6;
  margin: 0;
}

h1, h2, h3 { font-weight: var(--weight-semibold); line-height: 1.3; }
h2 { font-size: 15pt; margin: 20pt 0 8pt; }
h3 { font-size: 12.5pt; margin: 14pt 0 6pt; }

.secnum {
  font-weight: var(--weight-semibold);
  margin-right: 0.4em;
  color: var(--color-ink);
}

code {
  font-family: var(--font-mono);
  font-weight: var(--weight-regular);
  background: var(--color-surface);
  border-radius: var(--radius-inner);
  padding: 1px 4px;
  font-size: 0.85em;
}

figure { margin: 12pt 0; }
figure img {
  width: 100%;
  border: var(--stroke) solid var(--color-border);
  border-radius: var(--radius-mid);
}
figcaption {
  font-family: var(--font-mono);
  font-size: 8.5pt;
  color: var(--color-ink-soft);
  margin-top: 5pt;
}
figcaption .fignum { font-weight: var(--weight-medium); color: var(--color-ink); }

.table-caption {
  font-family: var(--font-mono);
  font-size: 8.5pt;
  color: var(--color-ink-soft);
  margin: 4pt 0 10pt;
}
.table-caption .fignum { font-weight: var(--weight-medium); color: var(--color-ink); }

.table-wrap {
  border: var(--stroke) solid var(--color-border);
  border-radius: var(--radius-mid);
  overflow: hidden;
  margin: 10pt 0;
}
table { width: 100%; border-collapse: collapse; font-size: 9pt; }
thead th {
  background: var(--color-surface);
  text-align: left;
  font-weight: var(--weight-medium);
  padding: 6pt 8pt;
}
tbody td {
  padding: 5pt 8pt;
  border-top: var(--stroke) solid var(--color-border);
  font-variant-numeric: tabular-nums;
}

.callout {
  background: var(--color-surface);
  border-radius: var(--radius-mid);
  padding: 10pt 12pt;
  margin: 12pt 0;
}
.callout .pill {
  display: inline-block;
  background: var(--color-ink);
  color: var(--color-paper);
  font-family: var(--font-mono);
  font-weight: var(--weight-medium);
  font-size: 7.5pt;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2pt 6pt;
  border-radius: var(--radius-inner);
  margin-right: 6pt;
}

.reftag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 8pt;
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
  background: var(--color-surface);
  padding: 1pt 5pt;
  border-radius: var(--radius-inner);
  margin-right: 6pt;
}

hr { border: none; border-top: var(--stroke) solid var(--color-border); margin: 16pt 0; }
a { color: var(--color-blue); }
```

- [ ] **Step 5: Create `tests/style/conftest.py`**

```python
from pathlib import Path
import sys

STYLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "style"
sys.path.insert(0, str(STYLE_DIR))
```

- [ ] **Step 6: Write the CSS sanity test**

`tests/style/test_tokens_css.py`:
```python
from pathlib import Path

STYLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "style"


def test_tokens_css_defines_required_primitives():
    css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    for var in [
        "--color-paper", "--color-surface", "--color-border",
        "--color-ink-soft", "--color-ink",
        "--color-blue", "--color-green", "--color-orange", "--color-red",
        "--font-sans", "--font-mono",
        "--radius-outer", "--radius-mid", "--radius-inner",
        "--stroke",
    ]:
        assert var in css, f"tokens.css missing {var}"


def test_tokens_css_hex_values_match_spec():
    css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    for hex_value in [
        "#F9F8F3", "#E2E1DA", "#BEBEBE", "#313131", "#262626",
        "#0099FF", "#2FBB45", "#DC762D", "#FB2C55",
    ]:
        assert hex_value in css, f"tokens.css missing {hex_value}"
    assert "#979797" not in css, "grey 2 (#979797) must not appear -- explicitly dropped"


def test_subsystem_academic_consumes_tokens_not_hardcoded_hex():
    css = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    assert "@import" in css and "tokens.css" in css
    assert ".callout" in css
    assert ".pill" in css
    assert "var(--radius-mid)" in css
    assert "var(--radius-inner)" in css
    # subsystem file should not invent its own hex colors
    import re
    hex_literals = re.findall(r"#[0-9A-Fa-f]{6}\b", css)
    assert hex_literals == [], f"subsystem-academic.css must only use var(--color-*), found: {hex_literals}"
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/style/test_tokens_css.py -v`
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add requirements-style.txt docs/style/tokens.css docs/style/subsystem-academic.css tests/style/
git commit -m "feat: PDF design system tokens + academic subsystem CSS"
```

---

### Task 2: `md_to_html.py` — `parse_front_matter`

**Files:**
- Create: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py` (created this task)

**Interfaces:**
- Produces: `parse_front_matter(text: str) -> tuple[dict, str]`

- [ ] **Step 1: Write the failing test**

`tests/style/test_md_to_html.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'md_to_html'`

- [ ] **Step 3: Write the minimal implementation**

`docs/style/md_to_html.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.parse_front_matter"
```

---

### Task 3: `md_to_html.py` — `embed_images`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: `embed_images(md_text: str, base_dir: Path) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
import base64
from pathlib import Path

from md_to_html import embed_images

TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'embed_images'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py` (after `parse_front_matter`):
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.embed_images"
```

---

### Task 4: `md_to_html.py` — `strip_title_block`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `strip_title_block(html: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import strip_title_block


def test_strip_title_block_removes_leading_h1_author_hr():
    html = (
        "<h1>Title</h1>\n"
        "<p><strong>Authors</strong><br>Affiliation</p>\n"
        "<hr />\n"
        "<h2>Abstract</h2>\n<p>Body.</p>"
    )
    result = strip_title_block(html)
    assert result == "<h2>Abstract</h2>\n<p>Body.</p>"


def test_strip_title_block_noop_if_no_leading_h1():
    html = "<h2>Abstract</h2>\n<p>Body.</p>"
    assert strip_title_block(html) == html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'strip_title_block'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
def strip_title_block(html: str) -> str:
    """Remove a leading <h1>...</h1><p>...</p><hr/> block (the document's
    manual title/author block), since front-matter supplies the same data
    for the cover page. No-op if the document doesn't start with an <h1>."""
    pattern = re.compile(r"^\s*<h1>.*?</h1>\s*<p>.*?</p>\s*<hr\s*/?>\s*", re.S)
    return pattern.sub("", html, count=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.strip_title_block"
```

---

### Task 5: `md_to_html.py` — `number_and_id_headings`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `number_and_id_headings(html: str) -> str`, and a private `_slugify(text: str) -> str` helper

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import number_and_id_headings


def test_number_and_id_headings_top_level_numbered_heading():
    html = "<h2>5. Multi-Model Comparison</h2>"
    result = number_and_id_headings(html)
    assert result == (
        '<h2 id="5-multi-model-comparison">'
        '<span class="secnum">5.</span> Multi-Model Comparison</h2>'
    )


def test_number_and_id_headings_subsection_numbered_heading():
    html = "<h3>5.6 Autonomous vs. Hybrid</h3>"
    result = number_and_id_headings(html)
    assert result == (
        '<h3 id="56-autonomous-vs-hybrid">'
        '<span class="secnum">5.6</span> Autonomous vs. Hybrid</h3>'
    )


def test_number_and_id_headings_unnumbered_heading_gets_id_only():
    html = "<h2>Abstract</h2>"
    result = number_and_id_headings(html)
    assert result == '<h2 id="abstract">Abstract</h2>'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'number_and_id_headings'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.number_and_id_headings"
```

---

### Task 6: `md_to_html.py` — `wrap_figures`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `wrap_figures(html: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import wrap_figures


def test_wrap_figures_merges_image_and_caption_paragraph():
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
    html = '<p><img alt="x" src="data:image/png;base64,AAAA" /></p>\n<p>Unrelated text.</p>'
    assert wrap_figures(html) == html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'wrap_figures'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.wrap_figures"
```

---

### Task 7: `md_to_html.py` — `wrap_tables`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `wrap_tables(html: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import wrap_tables


def test_wrap_tables_styles_caption_paragraph():
    html = '<p><strong>Table 1: Planted leaks.</strong></p>'
    result = wrap_tables(html)
    assert result == '<p class="table-caption"><span class="fignum">Table 1: Planted leaks.</span> </p>'


def test_wrap_tables_wraps_table_element():
    html = '<table><tr><td>x</td></tr></table>'
    result = wrap_tables(html)
    assert result == '<div class="table-wrap"><table><tr><td>x</td></tr></table></div>'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'wrap_tables'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.wrap_tables"
```

---

### Task 8: `md_to_html.py` — `wrap_callouts`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `wrap_callouts(html: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import wrap_callouts


def test_wrap_callouts_headline():
    html = '<p><strong>Headline</strong>: codellama:7b found 4/5 leaks.</p>'
    result = wrap_callouts(html)
    assert result == '<div class="callout"><span class="pill">HEADLINE</span>codellama:7b found 4/5 leaks.</div>'


def test_wrap_callouts_finding():
    html = '<p><strong>Finding</strong>: portability is not guaranteed.</p>'
    result = wrap_callouts(html)
    assert result == '<div class="callout"><span class="pill">FINDING</span>portability is not guaranteed.</div>'


def test_wrap_callouts_leaves_other_bold_paragraphs_untouched():
    html = '<p><strong>Note</strong>: something else.</p>'
    assert wrap_callouts(html) == html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'wrap_callouts'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
def wrap_callouts(html: str) -> str:
    """Convert '<p><strong>Headline</strong>: text</p>' or
    '<p><strong>Finding</strong>: text</p>' paragraphs into a neutral
    callout box with a solid ink-on-paper pill label -- no colored
    border/edge strip (explicitly rejected during design review)."""
    pattern = re.compile(r'<p><strong>(Headline|Finding)</strong>:?\s*(.*?)</p>', re.S)
    def _repl(match: re.Match) -> str:
        label, body = match.groups()
        return f'<div class="callout"><span class="pill">{label.upper()}</span>{body}</div>'
    return pattern.sub(_repl, html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.wrap_callouts"
```

---

### Task 9: `md_to_html.py` — `wrap_reftags`

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Produces: `wrap_reftags(html: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import wrap_reftags


def test_wrap_reftags_styles_bracket_tag():
    html = '<li>[REF-KYBERSLASH] M. J. Kannwischer et al.</li>'
    result = wrap_reftags(html)
    assert result == '<li><span class="reftag">REF-KYBERSLASH</span> M. J. Kannwischer et al.</li>'


def test_wrap_reftags_leaves_normal_list_items_untouched():
    html = '<li>Not a reference.</li>'
    assert wrap_reftags(html) == html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'wrap_reftags'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
def wrap_reftags(html: str) -> str:
    """Style '[REF-FOO]' bracket tags at the start of a References <li>
    as a small mono pill."""
    return re.sub(
        r'<li>\[(REF-[A-Z0-9-]+)\]\s*',
        lambda m: f'<li><span class="reftag">{m.group(1)}</span> ',
        html,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 18 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.wrap_reftags"
```

---

### Task 10: `md_to_html.py` — `render_markdown_to_html` orchestrator

**Files:**
- Modify: `docs/style/md_to_html.py`
- Modify: `tests/style/test_md_to_html.py`

**Interfaces:**
- Consumes: every function from Tasks 2-9 (`parse_front_matter`, `embed_images`, `strip_title_block`, `number_and_id_headings`, `wrap_figures`, `wrap_tables`, `wrap_callouts`, `wrap_reftags`)
- Produces: `render_markdown_to_html(md_path: Path) -> tuple[dict, str]` -- this is the function `build_pdf.py` (Tasks 11-12) calls.

- [ ] **Step 1: Write the failing test**

Append to `tests/style/test_md_to_html.py`:
```python
from md_to_html import render_markdown_to_html

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


def test_render_markdown_to_html_full_pipeline(tmp_path):
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
    assert '<div class="callout"><span class="pill">FINDING</span>' in html
    assert '<span class="reftag">REF-FOO</span>' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_markdown_to_html'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/md_to_html.py`:
```python
def render_markdown_to_html(md_path: Path) -> tuple[dict, str]:
    """Full pipeline: read md_path, split front matter, render the
    remaining markdown to HTML, strip the manual title block, then apply
    every wrap_*/number_and_id_headings transform in order. Returns
    (front_matter, body_html)."""
    raw = md_path.read_text(encoding="utf-8")
    front_matter, body_md = parse_front_matter(raw)
    body_md = embed_images(body_md, md_path.parent)
    converter = _markdown.Markdown(extensions=["tables", "sane_lists", "footnotes", "smarty"])
    html = converter.convert(body_md)
    html = strip_title_block(html)
    html = number_and_id_headings(html)
    html = wrap_figures(html)
    html = wrap_tables(html)
    html = wrap_callouts(html)
    html = wrap_reftags(html)
    return front_matter, html
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_md_to_html.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/md_to_html.py tests/style/test_md_to_html.py
git commit -m "feat: md_to_html.render_markdown_to_html orchestrator"
```

---

### Task 11: `build_pdf.py` — `build_html_document` (cover page + page assembly)

**Files:**
- Create: `docs/style/build_pdf.py`
- Create: `tests/style/test_build_pdf.py`

**Interfaces:**
- Consumes: `docs/style/tokens.css`, `docs/style/subsystem-academic.css` (read as text)
- Produces: `build_html_document(front_matter: dict, body_html: str) -> str`

- [ ] **Step 1: Write the failing test**

`tests/style/test_build_pdf.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_build_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_pdf'`

- [ ] **Step 3: Write the minimal implementation**

`docs/style/build_pdf.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_build_pdf.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add docs/style/build_pdf.py tests/style/test_build_pdf.py
git commit -m "feat: build_pdf.build_html_document"
```

---

### Task 12: `build_pdf.py` — `render_pdf` (Playwright export) + CLI

**Files:**
- Modify: `docs/style/build_pdf.py`
- Modify: `tests/style/test_build_pdf.py`

**Interfaces:**
- Consumes: `build_html_document` (Task 11), `render_markdown_to_html` (Task 10)
- Produces: `render_pdf(html: str, output_path: Path, short_title: str = "", classification: str = "") -> None`, and a CLI entrypoint (`main()` / `if __name__ == "__main__"`)

- [ ] **Step 1: Write the failing test**

Replace the top of `tests/style/test_build_pdf.py` (the existing `from build_pdf import build_html_document` line from Task 11) so the file now reads, in full:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/style/test_build_pdf.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_pdf'`

- [ ] **Step 3: Write the minimal implementation**

Add to `docs/style/build_pdf.py` (after `build_html_document`, replacing the file's ending):
```python
from playwright.sync_api import sync_playwright


def render_pdf(html: str, output_path: Path, short_title: str = "", classification: str = "") -> None:
    """Render html to a PDF at output_path using headless Chromium, with a
    running header (short_title) and footer (classification + page number)."""
    header_template = (
        '<div style="font-family:\'Roboto Mono\',monospace;font-size:7px;'
        'width:100%;padding:0 0.7in;color:#8a8a85;display:flex;justify-content:space-between;">'
        f'<span>{short_title}</span></div>'
    )
    footer_template = (
        '<div style="font-family:\'Roboto Mono\',monospace;font-size:7px;'
        'width:100%;padding:0 0.7in;color:#8a8a85;display:flex;justify-content:space-between;">'
        f'<span>{classification}</span><span class="pageNumber"></span></div>'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="A4",
            display_header_footer=True,
            header_template=header_template,
            footer_template=footer_template,
            margin={"top": "0.75in", "bottom": "0.75in", "left": "0.7in", "right": "0.7in"},
            print_background=True,
        )
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Rayquaza markdown document to a styled PDF.")
    parser.add_argument("source", type=Path, help="Path to the source .md file")
    parser.add_argument("--output", type=Path, default=None, help="Output PDF path (default: same name, .pdf extension)")
    args = parser.parse_args()

    front_matter, body_html = render_markdown_to_html(args.source)
    html = build_html_document(front_matter, body_html)

    output = args.output or args.source.with_suffix(".pdf")
    short_title = str(front_matter.get("title", args.source.stem))[:60]
    classification = str(front_matter.get("classification", ""))
    render_pdf(html, output, short_title=short_title, classification=classification)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/style/test_build_pdf.py -v`
Expected: 3 passed (this test spins up headless Chromium, so it will take a few seconds longer than the others -- that's expected)

- [ ] **Step 5: Run the full test suite for this feature**

Run: `pytest tests/style/ -v`
Expected: 25 passed (3 from test_tokens_css.py + 19 from test_md_to_html.py + 3 from test_build_pdf.py)

- [ ] **Step 6: Commit**

```bash
git add docs/style/build_pdf.py tests/style/test_build_pdf.py
git commit -m "feat: build_pdf.render_pdf + CLI entrypoint"
```

---

### Task 13: Add front-matter to `paper.md` and generate the first real PDF

**Files:**
- Modify: `docs/paper/paper.md`
- Create: `docs/paper/paper.pdf` (generated output, committed like the existing figure PNGs)

**Interfaces:**
- Consumes: `docs/style/build_pdf.py`'s CLI (`main()`, Task 12)

- [ ] **Step 1: Add YAML front-matter to the top of `docs/paper/paper.md`**

Open `docs/paper/paper.md` and insert this block as the very first lines of the file, before the existing `# Rayquaza: ...` heading (the existing heading/authors/`---` block stays exactly as-is below it -- the pipeline strips it automatically at render time):

```yaml
---
title: "Rayquaza: LLM-Guided Timing Side-Channel Rediscovery in Post-Quantum Cryptography Implementations"
authors: "Vedanth Dama, Ojas Mutroja"
affiliation: "Defence Research and Development Organisation — Scientific Analysis Group (DRDO SAG)"
date: "July 2026"
classification: "Internal — B7 Draft"
template: paper
---
```

- [ ] **Step 2: Generate the PDF**

Run: `python docs/style/build_pdf.py docs/paper/paper.md`
Expected output: `wrote docs\paper\paper.pdf` (or `docs/paper/paper.pdf` depending on shell), with no exceptions.

- [ ] **Step 3: Verify the generated PDF programmatically**

```bash
python - <<'EOF'
import pypdf
reader = pypdf.PdfReader("docs/paper/paper.pdf")
print("page count:", len(reader.pages))
print("first content page text sample:")
print(reader.pages[1].extract_text()[:300])
EOF
```

Expected: page count is a reasonable multi-page number (paper.md is long -- expect well over 10 pages), and the printed text sample contains recognizable text from the Abstract section (e.g. "Post-quantum cryptographic").

- [ ] **Step 4: Manual visual check**

Open `docs/paper/paper.pdf` in a PDF viewer. Confirm against the spec (`docs/superpowers/specs/2026-07-12-pdf-design-system-design.md`):
- Cover page shows title, authors, affiliation, date, classification
- Running header shows the paper's short title; running footer shows the classification line and page number
- Section headings show the `§`-free numbered style established in `number_and_id_headings` (e.g. "5.6 Autonomous vs. Hybrid" with "5.6" set apart)
- All 9 figures render (not broken image icons)
- Tables are bordered, header row tinted, radius consistent
- Headline/Finding paragraphs render as neutral callout boxes with a solid dark pill label, no colored edge strip
- No `#979797` grey, no font besides Public Sans/Roboto Mono, no border thicker than 1px anywhere

If anything is visibly wrong, fix the relevant CSS in `docs/style/subsystem-academic.css` or the relevant transform in `docs/style/md_to_html.py`, rerun Step 2, and re-check -- do not proceed to commit until this looks right.

- [ ] **Step 5: Commit**

```bash
git add docs/paper/paper.md docs/paper/paper.pdf
git commit -m "feat: first Rayquaza PDF via the new design system (paper.md)"
```

---

## Self-Review Notes

- **Spec coverage:** §3.1 (color) -> Task 1 + tests. §3.2 (type) -> Task 1's CSS. §3.3 (radius) -> Task 1's CSS. §3.4 (strokes) -> Task 1's CSS. §3.5 (component patterns: tables, callouts, page chrome, cover page) -> Tasks 1, 7, 8, 11, 12. §3.6 (page spec: A4, margins) -> Task 12. §4 (toolchain: Playwright, front-matter, pipeline shape, file location) -> Tasks 1-13 throughout. §5 (rollout order: build pipeline, then paper.md, stop there) -> Task 13 is the last task in this plan; PRIMER.md and the warm subsystem are explicitly out of scope (§6) and are not tasks here.
- **Placeholder scan:** no TBD/TODO strings; every step has complete, runnable code.
- **Type consistency:** `render_markdown_to_html` (Task 10) returns `tuple[dict, str]`, matching what `build_pdf.py`'s `main()` (Task 12) destructures as `front_matter, body_html`. `build_html_document` (Task 11) takes `(front_matter: dict, body_html: str)` matching that same pair. `render_pdf` (Task 12) takes the `html: str` produced by `build_html_document` and an `output_path: Path`, matching how `main()` calls it.
