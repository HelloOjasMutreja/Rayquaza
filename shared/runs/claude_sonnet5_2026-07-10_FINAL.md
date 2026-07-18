# Claude Sonnet 5 tier results (real API, real oracle) — FINAL

Same real pipeline as every other tier tonight. Intro-priced at $2/$10 per
MTok (through 2026-08-31) — cheaper than Sonnet 4.6's $3/$15 despite being
the newer, more capable model.

| Target | claude-sonnet-5 |
|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=129.22, 133s, $0.0939) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-306.69, 64s, $0.0509) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-38.00, 61s, $0.0432) |
| mldsa44_leak1 (ML-DSA memcmp) | missed / confirmed (t=-680.51, 215s, $0.1610) |

**3/4 located+confirmed. Total real cost: $0.3490.**

## Comparison across the Claude lineup tested tonight

| Target | Sonnet 4.6 | Haiku 4.5 | Sonnet 5 |
|---|---|---|---|
| kyber512_leak5 | missed | **located** | **located** |
| kyber512_leak4 | located | located | located |
| kyber512_leak2 | located | located | located |
| mldsa44_leak1 | missed | **located** | missed |
| **Score** | 2/4 | **4/4** | 3/4 |
| **Cost** | $0.3731 | **$0.0745** | $0.3490 |

Sonnet 5 improves on Sonnet 4.6 (correctly locates `leak5` this time), but
still misses `mldsa44_leak1` — the one target that seems to trip up every
Claude Sonnet variant regardless of generation. Haiku 4.5 remains the
standout: cheapest, fastest, and the only Claude model to go 4/4. This
continues to argue against a naive "bigger/newer = better bug-finder"
assumption for this specific static-scan-plus-refine task — worth
highlighting in the paper as a genuine, reproducible surprise rather than
noise (Haiku's 4/4 held up across a full independent 4-target run, not a
single lucky cell).

## Budget tracker

- Claude Sonnet 4.6: $0.3731
- Claude Haiku 4.5: $0.0745
- Claude Sonnet 5: $0.3490
- **Running total: $0.7966 of $5.00**
- Remaining: ~$4.20

Next up (pending user go-ahead): Claude Opus 4.8 ($5/$25 per MTok — the
priciest tier tried tonight; a full 4-target run would likely cost
$0.60-0.80 based on Sonnet-tier scaling, well within remaining budget but
worth confirming before spending).
