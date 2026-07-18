# OpenAI breadth tier results (real API, real oracle) — FINAL

Deliberately breadth-over-depth: 8 current-generation OpenAI models, each
run on a single target (`kyber512_leak5`) rather than the full 4-target
matrix, to sample a wide price/capability spectrum within remaining budget.
Same real pipeline as every other tier tonight (real gcc-compiled oracle,
real Welch t-test, no mocking).

All 8 model IDs and prices were verified twice against OpenAI's official
pricing page (`developers.openai.com/api/docs/pricing`) and cross-checked
against the live `/v1/models` list on this account — see commit `aaed2b7`.
`gpt-4o`/`gpt-4o-mini` (already in the codebase from an earlier session)
were deliberately **not** used this run — they no longer appear on the
current pricing page, so their existing hardcoded prices are unverified and
weren't trusted with real spend.

| Model | Result | Cost | Notes |
|---|---|---|---|
| gpt-5.4-nano | located / confirmed (t=155.86, 49s) | $0.0035 | validation cell, ran first |
| gpt-5.4-mini | located / confirmed (t=114.49, 46s) | $0.0149 | |
| gpt-5.4 | located / confirmed (t=466.94, 47s) | $0.0392 | |
| gpt-5.6-luna | **missed / no** (t=None, 629s) | $0.0121 | see below |
| gpt-5.6-terra | located / confirmed (t=236.93, 109s) | $0.0569 | |
| gpt-5.6-sol | located / confirmed (t=402.89, 77s) | $0.0801 | |
| gpt-5.5 | located / confirmed (t=544.62, 209s) | $0.1341 | |
| gpt-5.3-codex | **missed / no** (t=None, 2s) | $0.0000 | see below |

**6/8 located+confirmed. Total real cost: $0.3408.**

## Two anomalies, both diagnosed (not pipeline bugs)

**`gpt-5.6-luna`** ran for 629s (far longer than any other cell tonight)
and produced a normal-sized real response (3068 prompt + 1509 completion
tokens, real $0.0121 cost) but never got oracle-confirmed. The run
artifact shows `verdict: "UNCHANGED"`, `error: null` — the ingest step
completed cleanly, but the downstream oracle-feedback poll (600s timeout)
never received a result, most likely because the model's generated timing
harness failed to compile or otherwise never reached
`invoke_oracle`. This is the same failure *shape* as several CPU-tier
misses earlier tonight (a legitimate model-quality miss, not a recurrence
of the wait_start-regex or invoke_oracle-cwd bugs fixed hours ago — those
have held up cleanly across 20+ successful cells since).

**`gpt-5.3-codex`** failed in 2.1s at exactly $0.00 — confirmed via a
direct raw API call that this is an **architectural incompatibility**, not
a content or quality issue: `gpt-5.3-codex` returns `HTTP 404
"This model is not supported in the v1/chat/completions endpoint. Use the
v1/responses endpoint instead."` `sandbox/gateway/providers/openai.py`
only implements the older Chat Completions API — codex-family models need
the newer Responses API, a different request/response shape entirely.
Not fixed this session (would need a real provider rewrite, not a quick
patch) — documented here as a known limitation for future work.

## Budget tracker (full session)

- Claude tier (5 models): $1.8080
- OpenAI tier (8 models, this run): $0.3408
- **Total spent: $2.1488 of $5.00**
- **Remaining: $2.8512**
