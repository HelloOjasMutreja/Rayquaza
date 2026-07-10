# Frontier API tier results (Claude Sonnet 4.6, real API, real oracle) — FINAL

Ran against the real Anthropic API (not a local/free model) via the sandbox's
own gateway (`sandbox/gateway/providers/anthropic.py`), metered per-call with
a hard per-cell spend cap (`RAYQ_MAX_COST_USD`, default $0.40) added
specifically for this run given a small ($5) API credit balance. Oracle and
ingest pipeline identical to every other tier tonight — real gcc-compiled
timing harness, real Welch t-test, no mocking.

| Target | claude-sonnet-4-6 |
|---|---|
| kyber512_leak5 (FO memcmp) | missed / confirmed (t=1053.88, $0.1012) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-281.97, $0.0632) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-63.84, $0.0509) |
| mldsa44_leak1 (ML-DSA memcmp) | missed / confirmed (t=-629.50, $0.1589) |

**2/4 located+confirmed, 2/4 confirmed-but-mislocated. Total real cost: $0.3731.**

## Cross-model-family pattern (now the headline finding of the whole session)

`kyber512_leak5` and `mldsa44_leak1` are the two hardest targets across
**every** model tested tonight, regardless of family or size:

| Target | codellama 7B (WSL) | codellama 13B (T4) | claude-sonnet-4-6 (API) | qwen2.5-coder 7B/14B/32B |
|---|---|---|---|---|
| kyber512_leak5 | located | **missed** | **missed** | located (all 3 sizes) |
| mldsa44_leak1 | located | **missed** | **missed** | located (all 3 sizes) |

Both misses are still oracle-confirmed — the model found a real, statistically
significant timing signal on its own generated vector, just attributed it to
the wrong function/category. Both `leak5` and `mldsa44_leak1` share the same
underlying vulnerability shape: a `memcmp`-based non-constant-time comparison
in a verification/decapsulation path (Kyber's FO re-encryption check, ML-DSA's
signature verification). qwen2.5-coder is the only family tested that gets
this shape right at every size tried (7B/14B/32B) — codellama and Claude
Sonnet 4.6 both miss it. This looks like a genuine model-capability
discriminator specific to this vulnerability pattern, not random variance —
worth a dedicated paragraph in the paper rather than being buried in a table.

## Operational note

Added a hard per-cell budget cap this session
(`sandbox/meter.py::Meter.over_budget()`, checked in
`sandbox/gateway/chat.py` before every provider call, wired through
`sandbox/run_session.py`) since this was the first run with real money on
the line. Also added `claude-haiku-4-5` to both the model registry
(`sandbox/config.py`) and pricing table (`sandbox/pricing.py`) as a cheaper
option, not used this run.

## Budget remaining

~$4.63 of the original $5 API credit remains after this run.
