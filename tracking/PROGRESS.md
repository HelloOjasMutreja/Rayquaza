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
- 2026-06-17 [B] PRIORITY 1 — Live adversary loop vs all three Kyber targets: 2/3 AUTONOMOUS + 1/3 HINT-ASSISTED.
  LEAK-2 ✅ autonomous (secret_dependent_branch @ poly_tomsg, oracle t=-139.91).
  LEAK-4 ✅ autonomous (secret_dependent_branch @ indcpa_dec normalization, oracle t=-901).
  LEAK-5 ⚠️  hint-assisted — LLM alone missed the nonconstant_comparison; MANDATORY FINDINGS directive from
  static scan steered it (B-004 RESOLVED). With hint: nonconstant_comparison @ crypto_kem_dec, oracle t=141.
  ABLATION documented in docs/03_DECISIONS.md and EXPERIMENT_LOG. CAVEAT: oracle is not hypothesis-specific.
  Focused targets: track-b-engine/ingestion/test_targets/kyber512_leak{2,4,5}_focused.c.
- 2026-06-17 [B] Phase B5 (prompt fix): stage1_analysis.txt ML-DSA enum adherence tightened. Patterns 6-9
  now lead with "category=<value>", each ends with "CATEGORY TO USE:", and an explicit FORBIDDEN list names
  the exact wrong strings (rejection_sampling_leaks, signature_validity_branches, nonce_reuse). B5 hypothesis
  rediscovery of MLDSA-LEAK-1 (H006, nonconstant_comparison) DONE. Oracle WSL2 confirmation pending (macOS
  arm64 architecture limitation — REPS amplification ineffective; t=0.27 on macOS vs t=116.97 on WSL2).
- 2026-06-17 [B] Focused targets for LEAK-1 and LEAK-3 verified and updated. kyber512_leak1_focused.c:
  corrected from for-loop to if(b) memcpy(r,x,len) matching harness_oracle injection. kyber512_leak3_focused.c:
  corrected from in-place a[0] modification to local a0 variable pattern matching harness_oracle injection.
  PLACEHOLDER banners removed. Oracle integration ready; adversary loop pending.
- 2026-06-17 [B] ML-DSA REPS check complete. REPS=100/1000/5000 all non-significant on macOS/arm64 (|t|<1,
  sign unstable). Root cause: -O2 on arm64 compiles 32-byte memcmp as fixed NEON sequence with no real
  early-exit saving. ML-DSA oracle confirmation must run on WSL2/x86. Harness: track-b-engine/oracle_reps_check/.

## In Progress
- [A] Integration: run B's adversary loop against LEAK-1/3 + MLDSA-LEAK-1. LEAK-2/4/5 done (2/3
  autonomous + 1/3 hint-assisted). LEAK-1 and LEAK-3 focused targets now verified against harness_oracle.c
  injections; adversary loop against LEAK-1/3 pending. MLDSA-LEAK-1 rediscovery done at hypothesis stage;
  oracle confirmation needs WSL2 (macOS arm64 limitation).
- [B] PRIORITY 2 — Real AFL++ 24h baseline: BLOCKED on WSL2 environment (ISSUE B-005). Harness
  fully prepared for all 5 leaks: track-b-engine/fuzzing/harness_kyber.c + build_weakened.sh
  (leak1|2|3|4|5|clean) + run_baseline_weakened.sh + summarize_afl.py. Run on WSL2:
    ./build_weakened.sh <leak> && ./run_baseline_weakened.sh <leak>  (for each of leak1..leak5 + clean)
- [B] Phase B5 oracle reconfirmation: ML-DSA oracle needs WSL2/x86 re-run.
    cd track-a-target/targets/mldsa44_leak1 && ./harness_oracle MLDSA1-ORACLE 50000
  Expected: t≈-103 (Track A's REPS=100 harness, significant on WSL2/x86).

## Blocked
(none)
