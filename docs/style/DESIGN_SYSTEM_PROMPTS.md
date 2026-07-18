# Rayquaza Design System — Reusable Prompts

Paste-ready prompt blocks for generating new diagrams, charts, or visual
assets (via an AI tool, a human designer, or yourself in six months) so they
land on-brand on the first try instead of needing a palette-and-font pass
afterward, the way `make_figures.py` and `architecture.eraser` needed this
round. Source of truth for every value below: `docs/style/tokens.css` and
`docs/superpowers/specs/2026-07-12-pdf-design-system-design.md`. If the
tokens change, update this file to match — it is a derived artifact, not an
independent spec.

---

## 1. The core brief (paste into any AI design/diagram tool)

Use this as the opening context for Eraser AI, Whimsical AI, Figma AI,
ChatGPT/Claude image generation, or any other tool being asked to produce a
diagram, chart, or graphic for this project.

```
Design system — Rayquaza (DRDO SAG technical report + companion primer):

COLOR (use exactly these hex values, nothing else):
- Paper (background): #F9F8F3
- Surface (card/tint fill, one step off paper): #E2E1DA
- Border (all rules/dividers/outlines, 1px only): #BEBEBE
- Ink (primary text/shapes): #262626
- Ink-soft (secondary text/shapes): #313131
- Blue accent: #0099FF
- Green accent: #2FBB45
- Orange accent: #DC762D
- Red accent: #FB2C55
Do not introduce any other color. Accents are used sparingly and only where
they carry real meaning (see "accent usage" below) — never as decoration.

TYPE:
- Body/labels: Public Sans (weights 400/500/600 only — no Light, no Bold/Black)
- Code/identifiers/data/mono labels: Roboto Mono (weight 400 only)
- No other typeface, no serif.

SHAPE:
- Corner radius follows a concentric rule, not a fixed scale:
  parent_radius = child_radius + padding_between_them. Locked chain:
  outer 12px (padding 6) -> mid 6px (padding 3) -> inner 3px. Fully
  circular elements (dots, small pill badges) skip the scale entirely.
- All strokes/borders/rules are 1px, always the border color (#BEBEBE).
  This applies independent of type weight.

ACCENT USAGE (this is what "sparingly and meaningfully" means in practice):
- Blue = the academic/formal register's lead accent — section numbers,
  figure/table numbers, links, primary category in a comparison.
- Green = the primer/comfortable register's lead accent (same role as blue,
  different subsystem) — OR "good / located / confirmed" in a semantic
  result context. Never use both meanings in the same diagram.
- Orange = "confirmed but wrong" / secondary category / a highlight stage
  in a pipeline (e.g. a refine/verdict step).
- Red = "wrong / miss / warning" / a feedback-loop or attention-drawing arrow.
- Neutral (ink/ink-soft/border/surface) is the default for anything that
  isn't actively carrying one of the meanings above — most boxes, most
  lines, most text. A diagram that's 80% neutral and 20% purposeful accent
  is correct; a diagram where every box is a different accent color is not.

MOOD: quiet, technical, precise — an instrument reading, not a marketing
graphic. Flat fills, no gradients, no drop shadows, no skeuomorphism, no
purple/pink/teal or any hue outside the four accents above.
```

---

## 2. Diagram-as-code / flowchart tools (Eraser, Mermaid-adjacent, Whimsical)

Append this to the core brief above when the ask is specifically a
flowchart, pipeline, or architecture diagram:

```
For this diagram specifically:
- Prefer flat rounded-rectangle nodes over cylinders/clouds/3D shapes.
- Group related nodes in a labeled container (a "subsystem" box) rather
  than scattering them — e.g. all three model providers nest inside one
  "Model Gateway" container, not as three loose boxes.
- A feedback/loop edge (if the system has one) should be dashed and red
  (#FB2C55), curving under or around the main flow rather than crossing
  through it.
- Primary forward-flow edges are solid, thin (1-1.5px), neutral ink-soft
  (#313131) or the same accent as the node they originate from.
- Label edges with short lowercase phrases describing what flows (e.g.
  "ranked hypotheses", "timing JSON"), not generic words like "data" or "next".
- Keep node label text in Public Sans; if a label is a literal
  identifier/variable/function name, set that specific token in Roboto Mono
  even inline within an otherwise-Public-Sans label.
- ALWAYS specify the layout direction explicitly (e.g. Eraser's `direction
  right` at the top of the file) for anything meant to read as a left-to-
  right or top-to-bottom pipeline. Verified the hard way: a diagram-as-code
  file with no direction hint let Eraser's auto-layout scatter the nodes
  into a zigzag (one stage top-right, the next bottom-right, the one after
  that bottom-left) — box styling was fine, but the reading order was worse
  than the plain diagram it replaced. Never assume auto-layout will find
  the flow order implied by the edges; state it.
```

**Reference files:** `docs/paper/figures/architecture.eraser` (full
pipeline + model gateway) and `docs/paper/figures/core_pipeline.eraser`
(closed loop only, no gateway — used where the gateway hasn't been
introduced yet in reading order) are working examples already following
this brief, including the `direction right` hint — reuse their structure
as a template for future pipeline diagrams rather than starting from a
blank prompt.

---

## 3. Data visualization / charts (matplotlib, or any charting tool)

Append this to the core brief when the ask is a chart, plot, or graph:

```
For this chart specifically:
- Figure/axes background is #F9F8F3 (paper), not white or transparent.
- Grid lines (if any): #BEBEBE at low-moderate alpha (~0.6), thin (~0.7pt).
- Axis spines: keep only left+bottom, drop top+right. Spine/tick color:
  #313131 for ticks, #262626 for axis titles.
- Bar/line/point color assignment should map to the "accent usage" rules in
  the core brief above — e.g. in a two-category comparison, blue vs. orange
  (not blue vs. red, which implies "correct vs. wrong" rather than "A vs B").
  In a three-way vendor/category comparison, blue/green/orange (not red,
  which should stay reserved for a genuine warning/threshold line).
  A significance threshold, error line, or "this is bad" marker is red.
- Data-point/bar text labels: Public Sans, regular or the SemiBold face for
  the specific labels meant to draw the eye (headline totals, key deltas) —
  do not bold indiscriminately.
- Any label that is a literal model name, function name, or code identifier
  (e.g. "codellama:7b", "poly_tomsg") renders in Roboto Mono, not Public Sans.
- No 3D bars, no drop shadows, no gradient fills.
```

**Reference file:** `docs/paper/figures/make_figures.py` is a working
example — it loads the actual token hex values, registers the Public
Sans/Roboto Mono TTFs from `docs/style/fonts/`, and applies all of the
above via matplotlib `rcParams`. For any new figure in this repo, add a
new function to that file rather than starting a separate script, so the
palette/font setup is defined exactly once.

---

## 4. Two registers, one system (subsystem choice)

If the asset is for the **formal technical paper** (`paper.md`), lead with
**blue** as the accent and keep the "quiet, technical, precise" mood at its
most restrained.

If the asset is for the **PRIMER companion** (`PRIMER.md`) or any future
comfort-reading/onboarding document, lead with **green** as the accent
instead, and it's acceptable to size type ~15-20% larger and add ~10-15%
more line-height/whitespace than the academic register — same palette,
warmer/roomier expression. Do not introduce a new accent color to
differentiate a subsystem; differentiate by which of the four existing
accents leads, plus type scale and spacing, exactly as `subsystem-academic.css`
and `subsystem-primer.css` already do.

---

## 5. When in doubt

Open one of the already-generated reference assets and match it rather than
re-deriving the system from this document alone:
- `docs/paper/paper.pdf` / `docs/paper/PRIMER.pdf` — the two subsystems, in full
- `docs/paper/figures/fig0_architecture.png` — the pipeline diagram, current example
- `docs/paper/figures/fig7_model_matrix.png` — a data-heavy chart, current example
