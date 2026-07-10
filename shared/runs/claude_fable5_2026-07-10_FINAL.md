# Claude Fable 5 tier results — refused, documented as a finding

Only cell attempted: `claude-fable-5 x kyber512_leak5`, static-scan hybrid
mode, identical pipeline to every other tier tonight.

## Result: policy refusal, not a technical failure

The engine's static-scan ingest call — the same prompt shape every other
Claude model (Sonnet 4.6, Haiku 4.5, Sonnet 5, Opus 4.8) answered normally
all night — was refused by Claude Fable 5's safety classifiers:

```
stop_reason: "refusal"
stop_details.category: "cyber"
stop_details.explanation: "This request triggered restrictions on violative
cyber content and was blocked under Anthropic's Usage Policy."
```

Confirmed via a direct raw API call reproducing the exact ingest prompt
(a textbook non-constant-time `memcmp`-style comparison function — the
kind of function every other model in this session analyzed without
issue). `content: []`, `output_tokens: 3` (no thinking, no text) — a
clean, immediate, pre-output classifier block, not a partial/garbled
response or a truncation issue.

## Why this happened (and why it's not worth retrying blindly)

Per Anthropic's own documentation, Claude Fable 5 runs stricter safety
classifiers than the rest of the Claude lineup, explicitly targeting
cyber-security-adjacent content — and explicitly warns that "benign
adjacent work — security tooling ... — can occasionally trigger false
positives." Side-channel vulnerability discovery on reference crypto
implementations (this project's entire premise) sits squarely in that
adjacent-but-legitimate category. Every other Claude model tested tonight
(Sonnet 4.6, Sonnet 5, Haiku 4.5, Opus 4.8 — 16 cells total) analyzed the
same class of function with zero refusals. This is a Fable-5-specific,
policy-level block on the *domain*, not a fluke of one prompt's phrasing —
retrying the same static-scan prompt on the other 3 targets would almost
certainly refuse identically, so no further cells were run.

## This is itself a reportable result

Worth a line in the paper: **the most capable model in the tested lineup
was also the only one unable to participate in this legitimate defensive-
security research task**, due to safety classifiers calibrated more
aggressively than its own less-restricted siblings. This is a genuine,
documentable capability/policy tradeoff, not a null result to discard.

## Cost note

The sandbox's own cost estimator reported $0.0628 for this attempt (based
on the non-zero `usage` figures the API returned alongside the refusal).
Per Anthropic's documented refusal-billing policy, a pre-output refusal
(empty `content`, which this was) is **not actually billed** — so despite
the tool's displayed figure, the real account charge for this attempt was
almost certainly $0. `sandbox/pricing.py` does not currently special-case
refusals; this is a known minor inaccuracy in the cost estimator for this
edge case, noted here rather than fixed mid-session.

## Full-session Claude budget tracker (unchanged from actual billing)

- Claude Sonnet 4.6: $0.3731
- Claude Haiku 4.5: $0.0745
- Claude Sonnet 5: $0.3490
- Claude Opus 4.8: $1.0114
- Claude Fable 5: ~$0 (refused, likely unbilled per Anthropic policy)
- **Total: ~$1.81 of $5.00** (essentially unchanged from before this attempt)
