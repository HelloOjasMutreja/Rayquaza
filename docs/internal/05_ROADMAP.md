# Rayquaza — Roadmap & North-Star Vision

> **INTERNAL ONLY.** Excluded from public release (see `docs/internal/README.md`).
> Last refined: 2026-06-17.

The core experiment is essentially complete: six timing leaks confirmed (five Kyber +
one ML-DSA), ground truth in `shared/feedback/`. Track B is finishing B5 (ML-DSA oracle
on WSL2) and B6 (paper). Everything below runs **alongside** that remaining work, not
after it. This document is the durable shared record of where the project is going.

---

## North Star — the execution-grounded PQC side-channel benchmark

**Rayquaza becomes the first execution-grounded benchmark for AI side-channel discovery
in post-quantum cryptography** — a public leaderboard where models are scored on whether
they can find real, oracle-verified timing leaks across a large, tiered,
contamination-resistant corpus of crypto implementations.

**Why this can matter at the frontier:**

- **The oracle is the moat.** Most AI cyber benchmarks are multiple-choice, CTF
  string-match, or LLM-judge — all gameable and easy to contaminate. Rayquaza's ground
  truth is verified by measurement: a Welch t-statistic on real timing data. The leak
  reproduces on the wire or it does not.
- **Capability-eval ∩ safety-eval.** Frontier labs run cyber capability evaluations as
  part of responsible-scaling commitments. "Can the model find real vulnerabilities in
  security-critical code?" is exactly what those evals must measure.
- **PQC is the timely substrate.** NIST standardized Kyber/Dilithium in 2024; migration
  is underway; implementations are young; side-channels are the real-world break (the
  lattice math is not what gets broken — the implementation is).

**Framing (always):** defensive evaluation — using models to harden PQC implementations
and find bugs before attackers do. Targets are deliberately weakened and kept in
controlled, authorized scope.

**Gap from today to a benchmark labs cite:**

| Have now | Need |
|---|---|
| 6 planted, known-location leaks | Dozens–hundreds of targets across many primitives (Kyber, Dilithium, Falcon, SPHINCS+, plus classic AES/RSA/ECC for breadth) |
| All known to the runner | A held-out private set we administer (contamination resistance) |
| Implicit difficulty | Explicit tiers: obvious memcmp → compiler-introduced → microarchitectural ARM-only |
| Per-run t-statistic | A composite Rayquaza Score (detection rate × signal strength × cost-to-find × false-positive penalty) |
| Manual runs | A model-agnostic submission contract (point the harness at any endpoint → score) |
| — | Public leaderboard + paper with reference scores seeded day one |

**Design stance (decided):** build the visualizer and sandbox on **benchmark-shaped
foundations** from the start — a "target" is a first-class object (metadata, difficulty
tier, ground-truth record); the runner is a model-agnostic interface — even while the
visible scope is just the six leaks. Cheap to bake in now, expensive to retrofit. Apply
YAGNI to the big features (leaderboard, held-out set, large corpus) until we reach them.

---

## Delivery stack (all phases)

- **pywebview** — the app opens in its own native, chromeless OS window; the Python
  engine runs behind it and renders the diagrammatic HTML/CSS/JS interface.
- **PyInstaller** — bundles into a single `Rayquaza.exe` attached to releases;
  double-click to open, no Python or terminal required for a demo audience.
- The same code runs via `python run.py` for clone-and-run. Cross-platform builds
  (macOS `.app`, Linux binary) come from the same source later.

---

## Phased roadmap

### Phase A — Live real-time pipeline visualizer (next)

Show every engine step as it happens, with real data, diagrammatically. The per-leak
pipeline: **Ingest** (read the code) → **Vectorize** (write the C timing test) → **Wait**
(the oracle runs ~50k timings) → **Refine** (judge promote/reject) → **Save**. Wired
boxes light up the instant each real stage fires; the oracle box pulses while measuring,
then resolves green when the signal clears the significance threshold. Multiple targets
run as multiple parallel lines.

**Liveness = true real-time, built so we are never blocked on Track B.** The engine
already prints live progress to stdout; we run it as a subprocess and tap that stream for
coarse-live behavior today, with zero engine changes. To make the intermediate stages
(ingest / vectorize / refine) light precisely, we define a small **event contract** — a
one-line `emit(stage, hyp_id)` helper — and Track B adds a handful of additive one-line
calls at the stage boundaries. The visualizer is built against that contract: coarse-live
on existing output now, fully granular once the emit lines land. This handoff is logged in
`tracking/SYNC.md`; it upgrades granularity but does not gate Phase A.

### Reproducibility — woven in early (across Phase A→B, not last)

Anyone can clone and run the full experiment. Phase A already ships the basic
clone-and-run plus the `.exe`. Then: a Docker/devcontainer to remove environment drift; a
single `./run_all.sh` entry point; bundled liboqs build, model pull, all targets, and the
full loop; output as timing JSON plus a human-readable summary report. This is the same
distribution surface the benchmark submission flow will reuse.

### Phase B — Multi-LLM sandbox + comparison (the benchmark runner in embryo)

Import an LLM through the UI — local (Ollama, auto-detect the model) or via API (paste a
key/endpoint, auto-detect provider and model where possible) — name it, and run it across
the chosen leaks, driven by the Phase A live pipeline. One model at a time. When a run
finishes, send its results into a comparison view where multiple models sit side by side
and can be removed. Comparison axes: hypothesis quality, t-statistic of confirmed finds,
time/cost-to-find, false-positive rate, and the AFL++ brute-force baseline. Generate a
report from a set of comparisons. This sandbox, comparison, and report are the seed of the
benchmark submission flow and leaderboard.

### Benchmark corpus — scale-up

Grow the corpus across primitives and difficulty tiers; define the composite Rayquaza
Score; finalize the model-agnostic submission contract; stand up the held-out private set.

### Phase C — Cloud / SSH connector

Let the UI help users connect a cloud box or SSH session so runs execute remotely — for
larger models, the ARM oracle, or heavy runs. Mirrors how the LEAK-3 oracle ran on AWS
Graviton2. Depends on Phase B.

### Leaderboard + benchmark paper

A public leaderboard with reference scores for several frontier and open models seeded
from the start, and a paper positioning Rayquaza as the execution-grounded PQC
side-channel evaluation.

---

## Research outputs

- **Research paper (B6, Track B):** all data visualized — t-statistic plots, timing
  histograms, the LLM-vs-AFL++ comparison, and a multi-LLM section once Phase B exists.
- **Benchmark paper:** the north-star payoff described above.
- **Accessible analogy paper — done.** `docs/04_BANK_ANALOGY_BRIEFING.md` explains all
  five Kyber leaks in plain language and is public-safe.

---

## Release model

This repository stays private. A curated public version ships separately: the tool, the
`Rayquaza.exe`, the reproducibility bundle, and only the public-safe docs. Internal
material — this roadmap, `tracking/`, and internal specs — is excluded from the public
export. See `docs/internal/README.md`.
