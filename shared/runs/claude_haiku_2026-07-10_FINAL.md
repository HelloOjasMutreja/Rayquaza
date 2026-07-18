# Claude Haiku 4.5 tier results (real API, real oracle) — FINAL

Same real pipeline as every other tier tonight — real gcc-compiled oracle,
real Welch t-test, no mocking. Ran against the real Anthropic API, budget-
capped at $0.40/cell (never came close to hitting it).

| Target | claude-haiku-4-5 |
|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=573.41, 44s, $0.0146) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-302.19, 46s, $0.0158) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-112.33, 50s, $0.0147) |
| mldsa44_leak1 (ML-DSA memcmp) | located / confirmed (t=-703.18, 94s, $0.0294) |

**4/4 located+confirmed. Total real cost: $0.0745.** Also the fastest and
cheapest API tier by far — 44-94s per cell vs Claude Sonnet 4.6's 67-223s.

## This revises the earlier cross-model finding

`claude_api_2026-07-10_FINAL.md` (Claude Sonnet 4.6) noted that
`kyber512_leak5` and `mldsa44_leak1` looked like universally hard targets,
missed by every model tried at that point (codellama 7B/13B, Claude Sonnet
4.6) except qwen2.5-coder. **Haiku 4.5 breaks that pattern** — it locates
both of those targets cleanly. So the discriminator isn't "Claude family
struggles with this vulnerability shape" — it's specific to which Claude
model. Smaller/faster Haiku 4.5 outperforming larger Sonnet 4.6 on this
exact task is itself the more interesting finding: for this narrow static-
scan-plus-refine task, model size/tier within a family doesn't predict
success the way it might for general capability. Worth flagging in the
paper as a caution against assuming "bigger/pricier model = better bug-
finder" without task-specific validation.

## Budget tracker

- Claude Sonnet 4.6: $0.3731
- Claude Haiku 4.5: $0.0745
- **Running total: $0.4476 of $5.00**
- Remaining: ~$4.55

Next up (pending): Claude Sonnet 5 (intro-priced $2/$10 per MTok, cheaper
*and* more capable than 4.6), then Claude Opus 4.8 if budget allows.
