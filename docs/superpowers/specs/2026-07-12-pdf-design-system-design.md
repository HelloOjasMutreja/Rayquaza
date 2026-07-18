# PDF Design System — Design Spec

**Date:** 2026-07-12
**Status:** Approved by user, pending implementation plan

## 1. Problem & Scope

Rayquaza has several long-form documents (`docs/paper/paper.md`, `docs/paper/PRIMER.md`, and future specs/briefings) that currently exist only as Markdown, plus one HTML artifact rendering of the paper. There is no reusable, reproducible way to produce a properly designed PDF from these documents, and no shared visual identity across them.

This spec defines a **single design-token system** — one shared vocabulary of colors, type, and radii — used to generate PDFs (and, where relevant, the equivalent web artifact) for every long-form document in the repo going forward. Individual documents pick a **subsystem** (a curated subset of the shared tokens) rather than inventing their own look. Only one subsystem — the primary/academic register, used for `paper.md` — is fully specified in this pass. A second, warmer subsystem for comfort-reading documents (e.g. `PRIMER.md`) is named but deliberately left under-specified; it gets its own short design pass when we actually build it, using the same token vocabulary.

Rollout is incremental: build the pipeline and the primary subsystem, produce a working PDF of `paper.md`, confirm it end-to-end, and only then move on to the next document.

## 2. Token Architecture

Two layers:

1. **Primitives** (`tokens.css`) — the full raw vocabulary: every color, the type scale, the radius scale, spacing steps. Never consumed directly by content; only ever referenced by a subsystem.
2. **Subsystems** (e.g. `subsystem-academic.css`) — thin files that map primitives to semantic roles (`--body-color: var(--ink)`, `--callout-bg: var(--surface)`, etc.). A new document type gets a new subsystem file; the primitive layer never changes for that.

This guarantees every document produced by the system is recognizably part of one family, even when subsystems differ in feel.

## 3. Primary/Academic Subsystem — Full Specification

### 3.1 Color

| Token | Hex | Role |
|---|---|---|
| `paper` | `#F9F8F3` | Base page background |
| `surface` | `#E2E1DA` | Boxes, table header rows, callout fills, pill-label backgrounds when using a neutral tone |
| `border` | `#BEBEBE` | All rules, dividers, table lines, box outlines (1px only) |
| `ink-soft` | `#313131` | Secondary text, softer heading weight |
| `ink` | `#262626` | Primary text |
| `blue` | `#0099FF` | Accent |
| `green` | `#2FBB45` | Accent — semantic "good / located" |
| `orange` | `#DC762D` | Accent — semantic "partial / mislocated" |
| `red` | `#FB2C55` | Accent — semantic "bad / miss"; also the default Finding-marker pill color |

`#979797` was tested and dropped — contrast ratio against `paper` (~2.5:1) is too low for any text or meaningful UI use, kept neither as a token nor a fallback.

**Neutral vs. accent pills:** by user direction, pill-style labels (e.g. section tags, non-semantic markers) may use the neutral tones (`surface`/`border`/`ink`) instead of an accent color when a semantic color isn't actually being communicated — reserve accent-colored pills for places where the color *means* something (good/partial/bad), and use neutral pills elsewhere so accents stay meaningful rather than decorative.

### 3.2 Typography

- **Body & headings:** Public Sans. Weights restricted to Regular (400) and Medium (500)/Semibold (600) for headings — avoid Light and Bold/Black extremes.
- **Labels, meta, code, table data cells:** Roboto Mono, Regular (400) weight only — no Light, no Bold.
- No third typeface, no serif, in this subsystem.
- Section references use the `§` glyph (e.g. `§ 5.6`). A documented fallback — a small mono tag showing just the number (`5.6`) next to the title, no glyph — is available and may be swapped in later without disturbing anything else in the system.

### 3.3 Radius System

Not a fixed scale — a **rule**: `parent_radius = child_radius + padding_between_them`, applied so every nested box shares one concentric center point (matches the reference: outer panel → inner card → pill button, all concentric).

Locked chain for this subsystem: **outer 12px** (padding 6) → **mid 6px** (padding 3) → **inner 3px**. Fully circular elements (state dots, small circular markers) bypass the scale entirely.

Any new nesting depth in future components must be derived with the same formula, not picked arbitrarily — if a box needs to nest one level deeper than "inner," halve again (padding ~1.5, radius ~1.5) rather than introducing an unrelated value.

### 3.4 Borders / Strokes

All rules, dividers, table lines, and box outlines are **1px**, always `border` (`#BEBEBE`). This is a hard constraint independent of type weight — "strokes" refers only to drawn lines, not font weight.

### 3.5 Established Component Patterns

- **Data tables:** bordered container at `mid` radius; header row filled `surface`; per-row state shown via small (~6px) filled circular dots in the semantic accent color, never via colored text or colored cell backgrounds.
- **Finding / Headline callouts:** box filled `surface`, `mid` radius, **no colored border/edge strip** (explicitly rejected). Type marked by a small **solid-fill pill label** (e.g. `FINDING` in white Roboto Mono on a `red` fill, `inner` radius) placed above the callout body text.
- **Page chrome (print only):** a 1px `border`-colored hairline separates a running header (document short-name left, `§ N.N` right) from body content, and another separates body content from a footer (classification/status line left, page number right).
- **Cover page (print only):** report eyebrow line (mono, uppercase, small), large title, authors, affiliation, and a footer meta row — no colored fills beyond a single thin accent hairline at the very top of the page.

### 3.6 Page-level Print Specification

- Cover page + numbered content pages, running header/footer as above.
- Page size: A4, default for all DRDO SAG documents produced by this system (matches standard Indian institutional convention; override per-document only if a specific one explicitly requires Letter).
- Margins: 0.7in sides, 0.75in top/bottom, passed directly as the `margin` argument to Playwright's `page.pdf(...)` call. These are starting values carried over from the mockup proportions; adjust only if the first rendered `paper.md` PDF shows a concrete problem (e.g. a wide table or figure genuinely needing more width), not preemptively.

## 4. Toolchain

- **Renderer:** Python + Playwright driving headless Chromium's native print-to-PDF, consuming the same token/subsystem CSS used for on-screen rendering — no LaTeX toolchain, no manual browser print step.
  - **Why not WeasyPrint (originally planned):** WeasyPrint requires the GTK3 native runtime (Pango/cairo/GObject DLLs) which is not present on this Windows machine and requires a heavy separate system-level install to add. Verified during planning: `pip install weasyprint` succeeds but `from weasyprint import HTML` fails at import with `OSError: cannot load library 'libgobject-2.0-0'`.
  - **Why Playwright/Chromium works:** `pip install playwright && python -m playwright install chromium` is self-contained (downloads its own Chromium build, no system dependency), and Chromium's native PDF export supports page size, margins, and running header/footer templates (`page.pdf(display_header_footer=True, header_template=..., footer_template=..., margin=...)`) directly — verified working on this machine during planning.
- **Metadata:** each source `.md` declares YAML front-matter — `title`, `authors`, `date`, `classification`, `template` (subsystem selector, e.g. `paper`) — consumed by the build script, not hand-typed at build time.
- **Pipeline shape:** markdown → HTML (reusing the existing `markdown` Python package and the figure-embedding/heading-numbering/table-wrapping post-processing already built for the web artifact) → styled with `tokens.css` + the selected subsystem CSS → loaded into headless Chromium via Playwright → exported to PDF via `page.pdf(...)`, with the cover page as regular HTML content (not a Chromium header/footer template) and the running header/footer built from Chromium's native `header_template`/`footer_template` support.
- **Location:** a new `docs/style/` directory holding `tokens.css`, `subsystem-academic.css`, and the build script (e.g. `docs/style/build_pdf.py`); kept separate from `docs/paper/figures/` (which stays focused on matplotlib figure generation).

## 5. Rollout Order

1. Build the token/subsystem CSS and the markdown→PDF pipeline.
2. Produce a PDF of `docs/paper/paper.md` (the primary/academic subsystem) end-to-end; confirm it visually against this spec.
3. Only after that is confirmed working, move to the next document (`PRIMER.md` or others), which may require defining the warm subsystem's specifics as its own short follow-up design pass.

## 6. Explicitly Out of Scope for This Pass

- Full specification of the warm/"primer" subsystem (background `paper-warm`, softer `ink-warm` — values were sketched during brainstorming but not tested/confirmed; do not treat those sketch values as final).
- Any document beyond `paper.md` for the first implementation cycle.
- Non-PDF output formats beyond the existing HTML artifact pipeline.
