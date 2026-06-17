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
- 2026-06-16 [A] Phase A6: LEAK-3 (basemul ARM branch on secret NTT coefficient sign) confirmed. Oracle on AWS t4g.micro Graviton2: mean_A=13.202ns, mean_B=15.341ns, t=-3956.26, significant=true (n=50000). Target: track-a-target/targets/kyber512_leak3/. All five Kyber leaks now confirmed.
- 2026-06-17 [B] Phase B — Live adversary loop vs all three Kyber targets: 3/3 correct rediscoveries (HEADLINE RESULT).
  Method: focused targets embedding Track A's real patched functions verbatim (kyber512_leak{2,4,5}_focused.c);
  codellama:7b fails on full Kyber TUs so full-file analysis deferred to B6 multi-LLM phase.
  Engine hardened: format:json on stage1+stage2, dict→list parser, refine() robust to bad qwen3 JSON.
  LEAK-2 ✅ secret_dependent_branch @ poly_tomsg rounding. LEAK-4 ✅ secret_dependent_branch @ indcpa_dec
  normalization (oracle t=-901 PROMOTED). LEAK-5 ✅ nonconstant_comparison @ crypto_kem_dec memcmp
  (oracle t=141 PROMOTED) after B-004 prompt fix: mandatory-findings directive from static scan steers
  model onto the memcmp. Snapshots: shared/findings/loop_state_kyber512_leak{2,4,5}.json.
  CAVEAT for paper: oracle is not hypothesis-specific; judge rediscovery by category/location vs ground truth.
- 2026-06-17 [B] ML-DSA REPS check complete. REPS=100/1000/5000 all non-significant on macOS/arm64 (|t|<1,
  sign unstable). Root cause: -O2 on arm64 compiles 32-byte memcmp as fixed NEON sequence with no real
  early-exit saving. ML-DSA oracle confirmation must run on WSL2/x86. Harness: track-b-engine/oracle_reps_check/.

## In Progress
- [B] AFL++ baseline — Linux-ready harness prepared (track-b-engine/fuzzing/harness_kyber.c +
  build_weakened.sh + run_baseline_weakened.sh). Fuzzes weakened reference Kyber per target.
  Not yet run: macOS/arm64 host has no AFL++/Docker/liboqs (ISSUE B-005). Build+run on WSL2.
- [B] Phase B5: ML-DSA-44 (Dilithium) extension. Engine rediscovered MLDSA-LEAK-1 (H006,
  nonconstant_comparison at mld_sign_verify_internal() memcmp). Oracle non-significant on macOS/arm64
  regardless of REPS — architecture limitation, not amplification issue. Rerun on WSL2/x86 required.
  Also: tighten stage1 enum mapping (7B invented non-enum categories for H007-H009).

## Blocked
(none)