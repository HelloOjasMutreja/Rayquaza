# Claude Opus 4.8 tier results (real API, real oracle) — FINAL

Same real pipeline as every other tier tonight. Priciest model tested
($5/$25 per MTok), run with a raised per-cell budget cap ($1.00 instead of
the default $0.40) since Opus's cost-per-cell was expected to approach the
default ceiling based on Sonnet-tier scaling.

| Target | claude-opus-4-8 |
|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=941.14, 198s, $0.2999) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-323.22, 134s, $0.2130) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-273.02, 124s, $0.1870) |
| mldsa44_leak1 (ML-DSA memcmp) | missed / confirmed (t=-686.57, 205s, $0.3115) |

**3/4 located+confirmed. Total real cost: $1.0114** (by far the most
expensive tier — ~2.7x Sonnet 5, ~13.6x Haiku 4.5).

## Full Claude lineup — final comparison

| Target | Sonnet 4.6 | Haiku 4.5 | Sonnet 5 | Opus 4.8 |
|---|---|---|---|---|
| kyber512_leak5 | missed | located | located | located |
| kyber512_leak4 | located | located | located | located |
| kyber512_leak2 | located | located | located | located |
| mldsa44_leak1 | missed | **located** | missed | missed |
| **Score** | 2/4 | **4/4** | 3/4 | 3/4 |
| **Cost** | $0.3731 | **$0.0745** | $0.3490 | $1.0114 |
| **Avg time/cell** | 127s | 58s | 118s | 165s |

**The headline result holds and sharpens**: `mldsa44_leak1` trips up every
single Claude model except Haiku 4.5 — including Opus 4.8, the most
expensive and most capable model in the family. Model price/tier is not
predictive of success on this specific task. Haiku 4.5 is simultaneously
the cheapest, fastest, AND most accurate Claude model tested tonight on
this vulnerability set — a genuinely counterintuitive, reproducible result
worth a dedicated callout in the paper, not just a table footnote.

## Full-session budget tracker (final)

- Claude Sonnet 4.6: $0.3731
- Claude Haiku 4.5: $0.0745
- Claude Sonnet 5: $0.3490
- Claude Opus 4.8: $1.0114
- **Total spent: $1.8080 of $5.00**
- **Remaining: $3.1920**

## Session status

This closes out the planned experiment matrix across every tier: CPU/WSL
(local, free), AWS T4 GPU (local, free), AWS A10G GPU / 32B (local, free),
and the full Claude API lineup (Sonnet 4.6, Haiku 4.5, Sonnet 5, Opus 4.8 —
$1.81 real spend). 5 open-weight model/size combinations plus 4 Claude API
models, across 4 targets, 3 hardware environments — all using the same real
gcc-compiled oracle and Welch t-test, zero mocking anywhere.
