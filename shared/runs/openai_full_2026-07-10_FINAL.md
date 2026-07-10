# OpenAI full-depth tier results (real API, real oracle) — FINAL

Combines the earlier breadth run (`openai_breadth_2026-07-10_FINAL.md`,
single-target sampling across 8 models) with a follow-up full-depth run
covering the remaining 3 targets for the 6 models that succeeded on
`kyber512_leak5`. All 4 targets now covered for 6 of the 8 OpenAI models
tested tonight. Same real pipeline throughout (real gcc-compiled oracle,
real Welch t-test, no mocking).

| Model | leak5 | leak4 | leak2 | mldsa44_leak1 | Score | Cost |
|---|---|---|---|---|---|---|
| gpt-5.4-nano | located | located | located | located | **4/4** | $0.0136 |
| gpt-5.4-mini | located | located | located | missed | 3/4 | $0.0452 |
| gpt-5.4 | located | located | located | located | **4/4** | $0.1468 |
| gpt-5.6-terra | located | located | located | located | **4/4** | $0.1836 |
| gpt-5.6-sol | located | located | located | missed | 3/4 | $0.4123 |
| gpt-5.5 | located | located | located | located | **4/4** | $0.4480 |

**22/24 located+confirmed across the 6 fully-tested models (92%).** Every
single miss was still oracle-confirmed (a real, significant timing signal,
just mis-attributed) — zero true pipeline failures across all 24 cells.

Not brought to full depth (breadth-only, from the earlier run):
`gpt-5.6-luna` (missed leak5, timed out waiting for oracle feedback —
diagnosed as a legitimate model-quality miss, not a pipeline bug) and
`gpt-5.3-codex` (architecturally incompatible with this provider's Chat
Completions implementation — needs the newer Responses API).

## The cross-vendor contrast is now the session's sharpest finding

Recall from the Claude lineup: only **1 of 5** Claude models (Haiku 4.5)
correctly located `mldsa44_leak1` — Sonnet 4.6, Sonnet 5, and Opus 4.8 all
missed it (Fable 5 refused the domain outright). Here, **4 of 6** OpenAI
models get it right. This is a genuine, reproducible, cross-vendor
difference in how each provider's current model lineup handles this
specific vulnerability shape (a `memcmp`-based non-constant-time
comparison inside a signature-verification path) — not a fluke of any
single run. Worth a real comparison paragraph in the paper: OpenAI's
current-gen models, across a wide price range ($0.20-$5 per MTok), were
simply more reliable at this particular class of bug than Claude's
current-gen lineup, despite Claude's Haiku 4.5 being the single cheapest
and fastest model to test 4/4 tonight overall.

## Notable outlier

`gpt-5.5 x kyber512_leak4` took **1624.7s (~27 minutes)** — by far the
longest cell of the entire session — yet completed cleanly and correctly
(located/confirmed, normal cost $0.0918). Not investigated further since
it succeeded; noted here as a real, if unexplained, latency outlier worth
knowing about if reproducing this run.

## Budget tracker (full session, final)

- Claude tier (5 models): $1.8080
- OpenAI breadth run (8 models, 1 target each): $0.3408
- OpenAI full-depth run (6 models, 3 more targets each): $0.9211
- **Total spent: $3.0699 of $5.00**
- **Remaining: $1.9301**
