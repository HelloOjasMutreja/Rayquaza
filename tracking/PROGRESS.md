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
- 2026-06-17 [B] Focused targets for LEAK-1 and LEAK-3 verified, corrected, and adversary loop run.
  kyber512_leak1_focused.c: corrected to if(b) memcpy(r,x,len) → AUTONOMOUS rediscovery (t=213.48).
  kyber512_leak3_focused.c: corrected to local a0 variable pattern → AUTONOMOUS rediscovery (t=-2421.91).
  PLACEHOLDER banners removed. UPDATED HEADLINE: 4/5 Kyber leaks autonomous (LEAK-1/2/3/4);
  1/5 hint-assisted (LEAK-5, nonconstant_comparison class). See docs/03_DECISIONS.md.
- 2026-06-17 [B] ML-DSA REPS check complete. REPS=100/1000/5000 all non-significant on macOS/arm64 (|t|<1,
  sign unstable). Root cause: -O2 on arm64 compiles 32-byte memcmp as fixed NEON sequence with no real
  early-exit saving. ML-DSA oracle confirmation must run on WSL2/x86. Harness: track-b-engine/oracle_reps_check/.
- 2026-06-18 [A] B5 oracle CLOSED: MLDSA-LEAK-1 reconfirmed on WSL2/x86. mean_A=2.482ns, mean_B=2.193ns,
  t=164.30, significant=true (n=50000). Ground truth: shared/feedback/timing_MLDSA1-ORACLE_1781763721.json.
  Track B can now cite a confirmed ML-DSA oracle. macOS/arm64 remains architecturally unsuitable.

## In Progress
- [A] Integration: LEAK-1/2/3/4/5 adversary loop complete. FINAL RESULT: 4/5 Kyber autonomous
  (LEAK-1/2/3/4 secret_dependent_branch class), 1/5 hint-assisted (LEAK-5 nonconstant_comparison).
  MLDSA-LEAK-1 oracle now CONFIRMED on WSL2/x86 (t=164.30) — see Done.
- [A→B] PRIORITY 2 — Real AFL++ 24h baseline: Track A is RUNNING it on WSL2 (was BLOCKED on B side,
  ISSUE B-005). 4 instances (leak2/leak4/leak5/clean) in tmux, AFL_AUTORESUME, -V 86400, ~1200 exec/s.
  83-min partial already shows leak5 corpus = clean corpus (timing leak invisible to coverage).
  Full results ~2026-06-19; comparison data will land in shared/findings/ for the B6 paper.

## Blocked
(none)
