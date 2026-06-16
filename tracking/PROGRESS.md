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
- 2026-06-16 [A] LEAK-1 (cmov clangover class): target kyber512_leak1/ created. Clang 18/x86-64 assessment: barrier survives LTO; compiler emits cmoveq even without barrier. Manual if-branch injection represents downstream/ARM scenario. Oracle: t=74.74, significant=true (n=50000, REPS=100).
- 2026-06-16 [A] Task 3 equivalence check (LEAK-5 in liboqs): patched both ref and AVX2 kem.c in liboqs, rebuilt, ran full OQS_KEM_decaps timing. Result: t=2.52 at n=50k, t=1.84 at n=200k — NOT significant. Full-API detection below threshold; oracle isolation required. Finding: same code modification in library, but noise floor masking prevents direct detection through the full API. liboqs reverted to clean state.

## In Progress
- [A] LEAK-3 (basemul ARM timing) — cloud ARM instance needed (user confirmed cloud ARM available). Pending setup.
- [A] Integration: run B's adversary loop against all confirmed targets (LEAK-1/2/4/5 + MLDSA-LEAK-1).
- [B] Phase B2: AFL++ fuzzing baseline — harness.c (stub OQS_KEM_decaps), Dockerfile, build/run/summarize scripts ready. Next: build container, replace stub with real liboqs, run 24h baseline.
- [B] Phase B5: ML-DSA-44 (Dilithium) extension. stage1_analysis.txt extended with 4 ML-DSA/Dilithium patterns; synthetic verify target created; harness_oracle built. Live loop run on mldsa44_synthetic.c: engine REDISCOVERED the planted leak — H006 category=nonconstant_comparison at mld_sign_verify_internal() memcmp (hypothesis-stage milestone ACHIEVED). BUT oracle on THIS hardware (macOS) gave t=0.27, significant=false (32-byte memcmp signal below timer noise floor; Track A's WSL2 measured t=116.97) → qwen3 INVALIDATED H006, loop early-stopped. Rediscovery succeeded; oracle confirmation is hardware-dependent. Next: re-run oracle on Linux/WSL2 for significance; tighten stage1 enum mapping (7B invented non-enum categories for H007-H009).

## Blocked
(none — B4 unblocked: Track A delivered A2 harness + A3/A4/A5 targets + harness_oracle; B-003 RESOLVED)
