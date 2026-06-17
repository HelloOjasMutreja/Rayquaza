# Internal docs — NOT for public release

Everything under `docs/internal/` is **internal-only**. It is tracked in this private
repository but **must be excluded from any public release or export**.

When we publish the public version of Rayquaza (the tool, the `Rayquaza.exe`, the
clone-and-run reproducibility bundle, and the public-safe docs such as the bank-analogy
briefing), the release/export process **must drop**:

- `docs/internal/` (this entire tree — roadmap, strategy, north-star benchmark plan)
- `tracking/` (internal coordination boards)
- any internal design specs

The public gets a fully working, reproducible tool and benchmark runner — not the
roadmap or strategic positioning.
