# Sync & Handoffs

Cross-track coordination board. Log here when one track delivers something the other needs, 
or needs something from the other. This is how the two halves stay coupled.

## Track A -> Track B (deliverables B depends on)
- [DELIVERED] 2026-06-14 A0: liboqs build flags (for B2 fuzzing baseline).
  liboqs commit: depth-1 clone of open-quantum-safe/liboqs main.
  cmake -G Ninja .. \
    -DCMAKE_INSTALL_PREFIX="$HOME/liboqs-install" \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_BUILD_ONLY_LIB=ON \
    -DOQS_DIST_BUILD=ON \
    -DOQS_ENABLE_KEM_KYBER=ON \
    -DOQS_ENABLE_SIG_DILITHIUM=ON
  Installs to ~/liboqs-install/{include,lib}. Link with -loqs -lssl -lcrypto -lpthread.
  Tested on Ubuntu 24.04, gcc 13.3, cmake 3.28, OpenSSL 3.0.13.
- [DELIVERED] 2026-06-16 A2: timing harness ready. Location: track-a-target/harness/.
  Build: cd track-a-target/harness && make
  Run:   ./run.sh <hypothesis_id> [run_count]  →  saves JSON to shared/feedback/
  Schema: confirmed matches mock_timing format (hypothesis_id, run_count, mean_A/B ns,
    variance_A/B, t_statistic, significant, generated_by:"harness").
  Baseline (ref build, 10000 runs, WSL2): mean≈5870ns, std≈241ns, t=-3.29 (not significant).
  Noise floor: ~241ns std dev in WSL2. Injected vulnerabilities should produce >500ns
  mean difference to be clearly detectable above noise.
- [DELIVERED] 2026-06-16 A3: LEAK-5 weakened target (memcmp FO oracle) confirmed significant.
  Target: track-a-target/targets/kyber512_leak5/ (patched kem.c with memcmp instead of verify).
  Measurement approach: direct oracle harness (harness_oracle) isolates FO comparison step.
  Result: mean_A=28.9ns (valid CT, full 768-byte compare), mean_B=25.8ns (invalid CT, early exit),
    t=78.93, significant=true, n=50000. JSON saved to shared/feedback/timing_LEAK5-ORACLE_*.json.
  Note: full-decaps detection via ref C requires ~2M samples (std 8327ns >> signal 3ns).
    With AVX2 backend (std ~241ns) the oracle is detectable at n~500. Use oracle harness for B3.
  B3 integration: run ./harness_oracle <hypothesis_id> 50000 from kyber512_leak5/ and the
    JSON lands in shared/feedback/ with significant:true confirming the hypothesis.
- [DELIVERED] 2026-06-16 A4: two additional weakened Kyber512 targets confirmed significant.
  LEAK-2 | track-a-target/targets/kyber512_leak2/ | poly_tomsg() misprediction oracle
    Patch: poly.c poly_tomsg() — replace branchless multiply-shift with `if (2*t >= KYBER_Q)`.
    Oracle: harness_oracle [hypothesis_id] [n]. Cond-A: all_predictable (0 mispredicts).
    Cond-B: random-per-call LCG mix (~128 mispredicts). Compiled -O0 (cmov at -O2 eliminates leak).
    Result: mean_A=760.4ns, mean_B=816.8ns, t=-139.91, significant=true, n=50000.
    Research note: branch direction alone is not significant (t=-0.64). Signal requires
    unpredictable mp distribution (adversarial or invalid CT scenario).
  LEAK-4 | track-a-target/targets/kyber512_leak4/ | indcpa_dec normalization oracle
    Patch: indcpa.c after poly_invntt_tomont(&mp) — add `for(k<N) if(mp.coeffs[k]<0) mp.coeffs[k]+=KYBER_Q`.
    Oracle: harness_oracle [hypothesis_id] [n]. Cond-A: all_positive (0 additions).
    Cond-B: all_negative (256 additions of KYBER_Q=3329).
    Result: mean_A=291.9ns, mean_B=534.1ns, t=-318.58, significant=true, n=50000.
    Note: signal is the number of negative coefficients in mp (proportional to Hamming weight
    pattern). Full-decaps noise floor still too high for detection in ref C; oracle isolates loop.
  B3 integration: three confirmed Kyber512 targets now available. Run harness_oracle from each target dir.
    kyber512_leak5/  → harness_oracle LEAK5-ORACLE 50000   (t=78.93)
    kyber512_leak2/  → harness_oracle LEAK2-ORACLE 50000   (t=-139.91)
    kyber512_leak4/  → harness_oracle LEAK4-ORACLE 50000   (t=-318.58)
  All save JSON to shared/feedback/ in standard schema.
- [DELIVERED] 2026-06-16 A5: ML-DSA-44 (Dilithium) weakened target confirmed significant.
  MLDSA-LEAK-1 | track-a-target/targets/mldsa44_leak1/ | challenge comparison (memcmp vs ct_memcmp)
    Algorithm: ML-DSA-44 (FIPS 204, 128-bit security level).
    Patch: sign.c mld_sign_verify_internal() — replace mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES)
      with memcmp(c, c2, MLDSA_CTILDEBYTES). MLDSA_CTILDEBYTES=32 for ML-DSA-44.
    Oracle: standalone harness_oracle (no liboqs dependency), compiled -O2.
      Cond-A: memcmp(c, c2, 32) where c==c2 (full 32-byte scan, SLOW).
      Cond-B: memcmp(c, c2, 32) where c[0]!=c2[0] (exits at byte 0, FAST).
    Result: mean_A=16.195ns, mean_B=15.790ns, t=116.97, significant=true, n=50000.
    B3 integration: run harness_oracle <hypothesis_id> 50000 from mldsa44_leak1/.
      mldsa44_leak1/ → harness_oracle MLDSA1-ORACLE 50000  (t=116.97)
    Category: nonconstant_comparison. Analogous to LEAK-5 but in ML-DSA verify path.
    Note: challenge hash is 32 bytes vs 768 for Kyber FO — smaller window but still detectable.
  [INTEGRATED by B, 2026-06-16] B5 integration wired: harness_oracle rebuilt (gcc -O2), the
    live adversary loop consumed its real JSON from shared/feedback/. The engine REDISCOVERED
    the leak (H006 nonconstant_comparison at the memcmp). HOWEVER on Track B's hardware (macOS)
    the oracle gave t=0.27, significant=FALSE at n=50000 — NOT reproducing Track A's WSL2 t=116.97.
    See Open coordination questions. B5 hypothesis-stage rediscovery complete; oracle confirmation
    pending a higher-resolution timing environment.

## Track B -> Track A (deliverables A depends on)
- [DELIVERED] 2026-06-14 B0: Mock feedback format defined. Track A harness (A2) must output
  JSON matching the schema in shared/feedback/mock_timing_<timestamp>.json (generated by
  track-b-engine/engine/mock_feedback.py). Required fields:
    hypothesis_id (string), run_count (int), mean_A (float ns), mean_B (float ns),
    variance_A (float), variance_B (float), t_statistic (float), significant (bool),
    generated_by (string — use "harness" for real runs, "mock" for synthetic).
  See shared/feedback/ for an example output file.
- [READY] 2026-06-14 B3: LLM adversary loop is ready for integration. Track A: drop timing
  JSON files into shared/feedback/ with the filename containing the hypothesis_id
  (e.g. timing_H001_<timestamp>.json). Format: see shared/feedback/mock_timing_*.json for
  the schema. Once real files land there, drop the --use-mock flag to close the loop
  (the loop polls shared/feedback/ every 30s, 600s timeout per hypothesis).
- [PENDING] B3: test-vector format spec (so A harness can consume them).
- [RESOLVED] 2026-06-17 B→A: kyber512_leak1/ and kyber512_leak3/ target directories confirmed
  present on main (harness_oracle.c verified readable in both). Track B focused targets updated:
  kyber512_leak1_focused.c corrected to if(b) memcpy(r,x,len); kyber512_leak3_focused.c corrected
  to local a0 variable pattern. PLACEHOLDER banners removed. Adversary loop against LEAK-1/3 in
  progress (LEAK-3 DONE: autonomous rediscovery confirmed; LEAK-1 in progress).

## Open coordination questions
- 2026-06-16→17 [B→A / A→B] mldsa44_leak1 oracle portability — RESOLVED with hardware caveat.
  Original problem (B→A 2026-06-16): macOS clock_gettime noise floor (~24ns std dev) swamped the
  32-byte memcmp signal (t=0.27, single-call). B asked A for the WSL2 timing source.
  Track A fix (A→B 2026-06-16): REPS=100 signal amplification (commit 1c7fb88 on main); integer-
  division quantization fix added. WSL2 reconfirm: t=-226.85, significant=true, n=50000.
  B empirical check (B→A 2026-06-17): REPS=100/1000/5000 tested on macOS/arm64 using
  track-b-engine/oracle_reps_check/harness_oracle_reps.c. ALL NON-SIGNIFICANT (t≈0, sign unstable).
  Root cause: at -O2 on arm64, 32-byte memcmp compiles to fixed NEON instructions — no real
  early-exit path, so the WSL2/x86 byte-loop early-exit signal doesn't exist here regardless of REPS.
  NOTE: Track B's "no REPS loop" report was from a stale checkout; the fix was already on main.
  Track B's REPS test was against a local harness (harness_oracle_reps.c) built from scratch —
  the macOS arm64 non-significance is a genuine hardware-ISA finding, not a stale-code issue.
  CONCLUSION: ML-DSA oracle significant on WSL2/x86 (t=-226.85); non-significant on macOS/arm64.
  Oracle confirmation requires WSL2/x86. macOS arm64 is architecturally unsuitable for this oracle.
- 2026-06-17 [B integration] PRIORITY-1 done: ran the live adversary loop against Kyber targets.
  As-of status: LEAK-2/4/5 done (2/3 AUTONOMOUS + 1/3 HINT-ASSISTED per ablation in docs/03_DECISIONS.md).
  LEAK-3 done: ✅ AUTONOMOUS (secret_dependent_branch @ basemul(), oracle t=-2421.91 on macOS arm64).
  LEAK-1: in progress (adversary loop running, LEAK-1 harness compiled cc -O2 on macOS).
  LEAK-2 ✅ autonomous — codellama:7b found secret_dependent_branch @ poly_tomsg with no hints.
  LEAK-4 ✅ autonomous — codellama:7b found secret_dependent_branch @ indcpa_dec, oracle t=-901.
  LEAK-5 ⚠️  scanner-directed — model missed the memcmp; MANDATORY FINDINGS directive from static
    scan steered it (ablation result — see docs/03_DECISIONS.md).
  LEAK-3 ✅ autonomous — codellama:7b found secret_dependent_branch @ basemul() line 25, oracle
    t=-2421.91 significant (macOS arm64 with gcc -O0 -fno-inline; confirms signal visible on M-series).
  CAVEAT: standalone oracle not hypothesis-specific — PROMOTED ≠ correct; judge by category/location.
- 2026-06-17 [B→A] ML-DSA REPS harness — NOT working on macOS/arm64 (architecture limitation).
  REPS=100 -> t=0.91, REPS=1000 -> t=-0.81, REPS=5000 -> t=0.75; ALL non-significant, sign unstable.
  Root cause confirmed independently by Track B harness: -O2 arm64 memcmp is a fixed NEON sequence,
  no early-exit saving exists. Signal Track A sees on WSL2/x86 (byte-loop memcmp) is absent here.
  CONCLUSION: ML-DSA oracle confirmation must run on WSL2/x86. REPS harness: oracle_reps_check/.
- 2026-06-17 [A→B] ROOT CAUSE for three "missing/unchanged" reports from prior session:
  Track B's fork was behind main. Specifics now confirmed on both sides:
  1. mldsa44_leak1/harness_oracle.c REPS=100 fix was on main (commit 1c7fb88) before Track B checked.
     Track B's "no REPS loop" report was from a stale checkout. Track B's macOS/arm64 non-significance
     result stands independently (tested via local harness_oracle_reps.c, not the stale file).
     Track A additionally fixed integer-division quantization → reconfirmed WSL2 t=-226.85.
  2. kyber512_leak1/ and kyber512_leak3/ were already on main (harness_oracle.c + Makefile).
     Ground truth in shared/feedback/: LEAK1-CMOV t=74.74, LEAK3-ARM-GRAVITON2 t=-3956.26.
     Injection is in standalone harness_oracle.c (not a separate patched kem.c/ntt.c).
  3. DamsDen/ was NEVER committed — purely local to Track B machine. Not staged, not an issue.
  Track B response: focused targets now corrected to match harness injections (not discarded —
  they are valid adversary-loop inputs). LEAK-3 adversary loop complete (autonomous). LEAK-1 running.
- 2026-06-17 [B→A] HOUSEKEEPING: DamsDen/ RESOLVED — never committed, not staged by Track B.
