# Decision Log

Record every significant decision: what we chose, the alternatives, and why. 
Format: date, decision, rationale.

- YYYY-MM-DD: Project named Rayquaza. Rationale: distinctive, maps to the work.
- YYYY-MM-DD: Target library = liboqs. Rationale: maintained reference PQC implementations.
- YYYY-MM-DD: Classical baseline = AFL++. Rationale: state-of-the-art coverage-guided fuzzer.

---

## 2026-06-17: LEAK-5 rediscovery must be reported as hint-assisted, not autonomous

**Decision:** The final Kyber rediscovery headline is **4/5 autonomous LLM + 1/5 hint-assisted**.

**UPDATED 2026-06-17 (after LEAK-1/3 loop runs):** Original entry said 2/3; expanded to all 5 leaks.
LEAK-1 and LEAK-3 adversary loops ran and both produced autonomous rediscoveries:
- LEAK-1 (cmov if-branch): secret_dependent_branch @ cmov() line 9, oracle t=213.48, AUTONOMOUS.
- LEAK-3 (basemul sign-branch): secret_dependent_branch @ basemul() line 25, oracle t=-2421.91, AUTONOMOUS.
All four `secret_dependent_branch` targets (LEAK-1/2/3/4) were found without hints. Only LEAK-5
(`nonconstant_comparison` class) required the static-scanner directive.

**Background:** LEAK-5 (crypto_kem_dec memcmp / KyberSlash1) requires non-constant-time comparison
detection — the `nonconstant_comparison` category. Without any steering, codellama:7b (the stage1
model) consistently missed it: on the full kem.c it fixated on the keypair generation; on the focused
kyber512_leak5_focused.c it fixated on the `sk[...]` copy branch and never emitted a finding for the
`memcmp(ct, cmp, KYBER_CIPHERTEXTBYTES)` call even with a passive "; also contains:
nonconstant_comparison" comment in the prompt.

The fix — the MANDATORY FINDINGS directive prepended to the prompt — works by injecting the static
scanner's categorical conclusion directly into the LLM's instruction. The model complies and emits the
correct finding. But the *discovery* of the vulnerability class came from the static secondary scan
(regex match on `memcmp(` in the function body), not from the LLM's reasoning.

**Alternatives considered:**
- Claim 5/5 because all PROMOTED outcomes were correct — rejected: PROMOTED uses an oracle that isn't
  hypothesis-specific; even wrong-location hypotheses get PROMOTED on leaky targets.
- Discard the hint-on run entirely — rejected: it's a real result; the engine with static-scan
  integration does find LEAK-5, which is useful for the ablation.
- Claim 4/5 and leave LEAK-5 as a plain miss — rejected: we have both runs and should report both.

**Paper framing:**
- LEAK-1, LEAK-2, LEAK-3, LEAK-4: **autonomous** — LLM correctly categorized and located the leak
  from source alone. All are in the `secret_dependent_branch` family (if-branch on secret-derived value).
- LEAK-5: **scanner-directed** — static regex matched `memcmp`; MANDATORY directive told the LLM what
  category to emit; LLM produced the correct finding text and the oracle confirmed significance. Credit
  belongs to the static scan; the LLM added hypothesis text and location detail.
- Headline stat: "codellama:7b autonomously rediscovered 4/5 planted Kyber leaks; the fifth (LEAK-5,
  nonconstant_comparison class) required static-analysis guidance."
- Ablation table (for paper §Results): run the engine in two modes — (a) stage1 only, no static hint;
  (b) stage1 + static secondary scan + MANDATORY directive — and report per-leak rediscovery rate for
  each mode. This isolates the LLM's autonomous coverage from the hybrid approach.
- The nonconstant_comparison miss is consistent with 7B limitations: the model reliably catches
  if-branch / loop leaks (secret_dependent_branch) but struggles with CT-vs-non-CT API substitution
  (`memcmp` vs `verify()`/`ct_memcmp`) without explicit prompting. Larger models (B6 phase:
  Claude API, GPT-4o) should be tested on LEAK-5 without the MANDATORY directive to see if this is
  model-size-dependent.

**Implementation note:** the MANDATORY directive remains in ingest.py — it's the right production
behavior for the hybrid engine. The paper just must report which mode each result came from.

## 2026-06-17: Focused targets instead of full Kyber TUs for codellama:7b

**Decision:** Run stage1 analysis on single-function focused files, not the full Kyber source
translation units, for the 7B model.

**Rationale:** codellama:7b fails on full Kyber TUs — poly.c (361 lines) returns prose instead of
JSON; indcpa.c (338 lines) hits the 180s Ollama timeout; kem.c (92 lines) causes the model to fixate
on `crypto_kem_keypair` and miss `crypto_kem_dec` entirely. Full-file analysis works with larger
context models (B6: Claude API / GPT-4o) — deferred.

**Paper note:** the methodology section must state that focused targets were used for the 7B-model
arm of the experiment. The B6 full-source runs will test whether larger models close the gap.

## 2026-06-17: macOS/arm64 cannot confirm ML-DSA-44 oracle; WSL2/x86 required

**Decision:** Do not claim ML-DSA oracle confirmation from macOS timing results. Log as
hardware-environment finding.

**Rationale:** ML-DSA-44 MLDSA-LEAK-1 oracle measures a 32-byte memcmp early-exit signal (~0.4ns
delta). On macOS/arm64 at -O2, the 32-byte memcmp compiles to fixed NEON compare instructions with
no real early-exit path, so the timing signal doesn't exist at the ISA level. REPS amplification
(100×/1000×/5000× inner loop) confirmed non-significant and sign-unstable (t ≈ 0.9, -0.8, 0.75).
Track A's WSL2/x86 measured t=116.97 because x86 memcmp is a byte loop with real early exit.

**Paper implication:** report the ML-DSA oracle result with the environment (WSL2/x86, gcc -O2).
Note that the same oracle is non-detectable on macOS/arm64 and explain the ISA-level reason — this is
itself a finding about timing-oracle portability, useful context for practitioners.
