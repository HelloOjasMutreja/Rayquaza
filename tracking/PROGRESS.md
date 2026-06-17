# Progress

Living snapshot of project state. Update at the end of every work session. 
Tag entries [A] (Track A) or [B] (Track B). Use ISO dates.

## Done
- 2026-06-13 [A/B] Repository scaffold created.
- 2026-06-14 [A] Phase A0: WSL2 + Ubuntu 24.04, liboqs built, Kyber512 round-trip verified.
- 2026-06-14 [B] Phase B0: Repo scaffold, directory structure, AGENTS.md Ollama rules, EXPERIMENT_LOG.md, prompt library (stage1/2/3), dummy.c test target, ollama_test.py, mock_feedback.py — all created.
- 2026-06-14 [B] Phase B1: ingest.py ingestion pipeline (CodeIngester + Hypothesis dataclass) — preprocess/analyze/save working; verified on dummy.c, codellama:7b returned 2 HIGH-confidence ranked hypotheses (2/3 functions flagged; compare() has no secret-token params).
- 2026-06-16 [A] Phase A1: Kyber decapsulation code-read complete; 5 candidate leak locations logged in ISSUES.md.
- 2026-06-16 [A] Phase A2: timing harness built and verified; baseline JSON saved to shared/feedback/.
- 2026-06-16 [A] Phase A3: LEAK-5 (memcmp FO comparison) injected and confirmed. Direct oracle measurement: mean_A=28.9ns (valid CT, full compare), mean_B=25.8ns (invalid CT, early exit), t=78.9, significant=true. Ground truth in shared/feedback/. FIRST MAJOR INTEGRATION MILESTONE.
- 2026-06-16 [A] Phase A4: LEAK-2 (poly_tomsg branch) and LEAK-4 (indcpa_dec normalization) injected and confirmed. Oracles: LEAK-2 t=-139.91, LEAK-4 t=-318.58 (both n=50000, significant=true). Three weakened targets now available in track-a-target/targets/. JSON saved to shared/feedback/.
- 2026-06-16 [A] Phase A5: MLDSA-LEAK-1 (memcmp challenge comparison in ML-DSA-44 verify) injected and confirmed. Oracle: t=116.97, significant=true (n=50000). Target: track-a-target/targets/mldsa44_leak1/. Fourth target now available.
- 2026-06-16 [B] Phase B4: secondary-scan fix in ingest.py (memcmp/strcmp/strncmp + secret-branch + fixed/variable-loop re-scan of unflagged functions) verified on dummy.c (compare() now caught). Targets delivered by Track A; B-003 RESOLVED. DONE.

## In Progress
- [A] LEAK-3 (Kyber512 basemul branch) — optional extension, lower priority.
- [B] PRIORITY 1 — Live adversary loop vs all three Kyber targets: DONE 2026-06-17 (headline result).
  Method: focused targets holding the REAL patched functions verbatim (kyber512_leak{2,4,5}_focused.c),
  because codellama:7b fails on full Kyber TUs (prose/miss/timeout); full-file analysis deferred to the
  B6 multi-LLM phase (Claude/GPT-4o). Engine hardened: format:json on stage1+stage2, dict→list parser
  normalize, refine() no longer crashes on bad qwen3 JSON. RESULTS (rediscovery by category/location match):
  LEAK-2 ✅ correct (secret_dependent_branch @ poly_tomsg rounding); LEAK-4 ✅ correct (secret_dependent_branch
  @ indcpa_dec normalization, oracle t=-901 PROMOTED); LEAK-5 ❌ MISSED the memcmp (flagged sk-indexing instead;
  oracle PROMOTED it anyway since the oracle is not hypothesis-specific → false rediscovery, see B-004).
  Net: 2/3 correct rediscoveries. Snapshots: shared/findings/loop_state_kyber512_leak{2,4,5}.json.
- [B] PRIORITY 2 — Real AFL++ baseline: BLOCKED on environment (see ISSUE B-005). This macOS/arm64 host
  has no AFL++, no Docker, no ~/liboqs-install; AFL++/liboqs are Linux/WSL2. Must run on the WSL2 box.
  Nothing faked. Next: decide (a) run on WSL2, or (b) Track B prepares Linux-ready harness for execution there.
- [B] Phase B2: AFL++ fuzzing baseline — harness.c (stub OQS_KEM_decaps), Dockerfile, build/run/summarize scripts ready. Superseded by Priority 2 above (real liboqs link).
- [B] Phase B5: ML-DSA-44 (Dilithium) extension. stage1_analysis.txt extended with 4 ML-DSA/Dilithium patterns; synthetic verify target created; harness_oracle built. Live loop run on mldsa44_synthetic.c: engine REDISCOVERED the planted leak — H006 category=nonconstant_comparison at mld_sign_verify_internal() memcmp (hypothesis-stage milestone ACHIEVED). BUT oracle on THIS hardware (macOS) gave t=0.27, significant=false (32-byte memcmp signal below timer noise floor; Track A's WSL2 measured t=116.97) → qwen3 INVALIDATED H006, loop early-stopped. Rediscovery succeeded; oracle confirmation is hardware-dependent. Next: re-run oracle on Linux/WSL2 for significance; tighten stage1 enum mapping (7B invented non-enum categories for H007-H009).

## Blocked
(none — B4 unblocked: Track A delivered A2 harness + A3/A4/A5 targets + harness_oracle; B-003 RESOLVED)
