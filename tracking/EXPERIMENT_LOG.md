# Experiment Log

Append-only. One entry per experiment/run. Never edit past entries.
Format:
## YYYY-MM-DD HH:MM [A/B] <short title>
- What: <what was run>
- Settings: <key parameters>
- Result: <what happened>
- Takeaway: <one-line conclusion / next step>

---

## 2026-06-16 [A] A6 — LEAK-3 basemul ARM oracle confirmed (AWS t4g.micro Graviton2)
- What: Built and ran LEAK-3 oracle on AWS t4g.micro (ARM Graviton2, aarch64, Ubuntu 24.04).
  Injection: `if (a0 < 0) a0 += KYBER_Q;` before fqmul(a0, b0) in basemul() step.
  Condition A: a0=+1000 (positive NTT coeff, branch not taken — no addition).
  Condition B: a0=-1000 (negative NTT coeff, branch taken — add KYBER_Q=3329).
  Compiled -O0 -fno-inline to preserve branch. REPS=500 per timing sample.
- Settings: n=50000, 5% trim, Welch t-test, CLOCK_MONOTONIC_RAW, CPU pinned core 0.
  Hardware: AWS t4g.micro, ARM Graviton2 (A72-class), 2 vCPUs, ap-southeast-2.
  SSH from local, SCP harness, compiled natively on ARM64.
- Result: mean_A=13.202ns, mean_B=15.341ns, variance_A=1442, variance_B=1844,
  t=-3956.26, significant=true. Delta: 2.14ns/call, extremely high |t| due to low
  per-sample variance relative to large sample count. JSON: shared/feedback/timing_LEAK3-ARM-GRAVITON2_*.json.
- Takeaway: LEAK-3 CONFIRMED on ARM Graviton2. Branch on sign of secret NTT coefficient
  is timing-observable on real ARM hardware. x86-64 is immune (IMUL constant latency,
  compiler emits cmov). Hardware boundary clearly demonstrated: ARM = vulnerable,
  x86-64 = not vulnerable. All five Kyber512 timing leaks now confirmed across
  three hardware/compiler categories.

## 2026-06-16 [A] LEAK-1 — cmov clangover class assessment and oracle
- What: Assessed whether Clang 18 + LTO defeats the asm barrier in cmov() (verify.c:40).
  Compiled with LTO (gold linker), examined IR bitcode and final assembly.
  Also tested without barrier (merged TU, clang -O2 and -O3).
- Settings: clang-18 -O2 -flto, gold plugin linker; WSL2/Ubuntu 24.04, x86-64.
  Test: two-TU simulation (verify_ct + cmov_ct) to match real kem.c + verify.c layout.
- Result: Barrier survives LTO — #APP/#NO_APP visible in IR and asm output.
  Without barrier, clang -O2 emits 'cmoveq' (conditional move instruction, constant-time).
  Without barrier, clang -O3: fully unrolled byte XOR loop, also no branch.
  Conclusion: clangover does NOT reproduce on Clang 18/x86-64 for this cmov pattern.
  Manual injection (explicit if/memcpy branch): oracle t=74.74, significant=true (n=50k, REPS=100).
  Target: track-a-target/targets/kyber512_leak1/harness_oracle.c
- Takeaway: Clang 18/x86-64 is not vulnerable to clangover for this implementation.
  The risk exists on ARM Cortex-M and older compilers lacking cmov. Oracle demonstrates
  what the timing leak would look like if a branch were introduced.

## 2026-06-16 [A] Task 3 — LEAK-5 equivalence check in liboqs (full API)
- What: Patched both ref and AVX2 kyber512 kem.c in ~/liboqs source with memcmp injection
  (same as LEAK-5). Rebuilt liboqs with ninja, installed, ran OQS_KEM_decaps timing.
  Condition A: valid ciphertext; Condition B: invalid ciphertext.
- Settings: n=50k and n=200k, full OQS_KEM_decaps() call path, gcc -O2 harness.
  Patched: pqcrystals-kyber_kyber512_ref/kem.c AND pqcrystals-kyber_kyber512_avx2/kem.c.
  liboqs selects AVX2 backend at runtime (CPU has AVX2). Reverted after experiment.
- Result:
  n=50k:  mean_A=8122ns, mean_B=8110ns, std≈728ns, t=2.52, significant=false.
  n=200k: mean_A=7052ns, mean_B=7050ns, std≈389ns, t=1.84, significant=false.
  The ~3ns memcmp signal is below the full-decaps noise floor even with AVX2 backend.
- Takeaway: Same code modification exists in the library, but oracle isolation is required
  to reliably confirm the vulnerability. Full-API detection would need impractically large
  n (est. n>600k) or a dedicated microarchitectural measurement setup. This validates the
  oracle hypothesis generation methodology — the LLM identifies the code pattern, the
  oracle isolates the signal. liboqs reverted to clean state after experiment.

## 2026-06-14 [A] liboqs build + Kyber512 round-trip
- What: Built liboqs from source on WSL2/Ubuntu 24.04; ran minimal C test for Kyber512 keygen -> encaps -> decaps.
- Settings: gcc 13.3, cmake 3.28, OpenSSL 3.0.13, ninja 1.11.1. Flags: BUILD_SHARED_LIBS=ON, OQS_BUILD_ONLY_LIB=ON, OQS_DIST_BUILD=ON, KEM_KYBER=ON, SIG_DILITHIUM=ON.
- Result: All four steps passed (keygen OK, encaps OK, decaps OK, shared secret match OK).
- Takeaway: A0 complete. Toolchain confirmed. Build flags handed to Track B via SYNC.md. Next: A1 — map secret flow in Decaps.

## 2026-06-16 [A] A1 — Kyber512 decapsulation source code analysis
- What: Read all key source files in pqcrystals-kyber_kyber512_ref: kem.c, indcpa.c, poly.c, ntt.c, reduce.c, verify.c.
- Settings: liboqs depth-1 clone, ref implementation (not AVX2). Analysis only — no execution.
- Result: Mapped full decapsulation call chain; established sk layout; identified 5 candidate
  timing leak locations across compiler/branch/microarch categories. All are in pqcrystals
  ref C source. Confirmed: montgomery_reduce and barrett_reduce are branchless; poly_tomsg
  uses safe multiply-shift; verify uses XOR-accumulate; cmov uses asm barrier. Reference is
  CT by inspection but has known real-world failures at compiler and microarch layers.
- Takeaway: A1 complete. LEAK-5 (memcmp/FO compare) is highest-value A3 injection target.
  LEAK-1 (cmov/clangover) is easiest to trigger. Next: A2 — timing harness.

## 2026-06-16 [A] A2 — Timing harness baseline run (ref implementation)
- What: Built harness.c and ran 10000 interleaved decaps measurements on pqcrystals ref build.
  Condition A: valid ciphertext. Condition B: random (invalid) ciphertext.
- Settings: CLOCK_MONOTONIC_RAW, 500 warmup runs, 5% trim, Welch t-test, WSL2/Ubuntu 24.04,
  gcc -O2, liboqs depth-1 main. CPU affinity attempted (pin core 0, WSL2 best-effort).
- Result: mean_A=5869.8ns, mean_B=5881.7ns, var_A=58368, var_B=59169, t=-3.29, significant=false.
- Takeaway: A2 complete. Ref implementation is constant-time as expected (|t|<4). Noise floor
  ~241ns std dev in WSL2. Need >~500ns mean diff for clear detection in A3. JSON saved to
  shared/feedback/. Harness schema confirmed compatible with Track B mock format.

## 2026-06-16 [A] A4 — LEAK-2 and LEAK-4 timing oracles confirmed
- What: Injected two additional weakened Kyber512 targets and ran oracle harnesses.
  LEAK-2: patched poly_tomsg() in poly.c to replace branchless multiply-shift with
    `if (2*t >= KYBER_Q) t=1; else t=0;` — branches on secret-derived rounding decision.
  LEAK-4: added conditional normalization loop in indcpa_dec() after poly_invntt_tomont(&mp):
    `for(k<N) if(mp.coeffs[k]<0) mp.coeffs[k]+=KYBER_Q` — 256 branches on sign of secret NTT poly.
- Settings: Both oracle harnesses compiled with -O0 -fno-inline (prevent cmov optimization).
  LEAK-2 oracle: misprediction design — Cond-A: all coeffs=2500 (predictor learns, 0 mispredicts);
    Cond-B: random-per-call LCG mix (predictor can't learn, ~128 mispredicts). n=50000.
  LEAK-4 oracle: direct normalization timing — Cond-A: all_positive (0 additions);
    Cond-B: all_negative (256 additions of KYBER_Q=3329). n=50000.
- Result:
  LEAK-2: mean_A=760.4ns, mean_B=816.8ns, t=-139.91, significant=true.
  LEAK-4: mean_A=291.9ns, mean_B=534.1ns, t=-318.58, significant=true.
  Note: LEAK-2 direction oracle alone (both predictable) gives t=-0.64 (not significant).
    The leak requires unpredictable branch patterns — compiler at -O2 also eliminates it (cmov).
- Takeaway: A4 complete. All three standalone timing oracles confirmed (LEAK-2/4/5). Track B
  now has three targets for adversary loop integration. JSON saved to shared/feedback/.

## 2026-06-16 [A] A5 — MLDSA-LEAK-1 timing oracle confirmed (ML-DSA-44 memcmp challenge comparison)
- What: Injected MLDSA-LEAK-1 into ML-DSA-44 verify path (sign.c line 1197): replaced
  constant-time mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES) with memcmp(c, c2, 32).
  Built standalone oracle harness (no liboqs dependency, compiles -O2 on any Unix).
- Settings: harness_oracle, n=50000, 5% trim, Welch t-test, CLOCK_MONOTONIC_RAW, CPU pinned.
  Condition A: memcmp(c, c2, 32) where c == c2 (matching challenge hash, reads all 32 bytes).
  Condition B: memcmp(c, c2, 32) where c[0] != c2[0] (differing at byte 0, early exit).
  Algorithm: ML-DSA-44 (FIPS 204, parameter set 2, MLDSA_CTILDEBYTES=32).
- Result: mean_A=16.195ns, mean_B=15.790ns, t=116.97, significant=true.
  Absolute difference: 0.405ns over 32 bytes. Very low variance → high |t| despite small delta.
- Takeaway: A5 complete. MLDSA-LEAK-1 oracle CONFIRMED. First ML-DSA weakened target operational.
  Category: nonconstant_comparison — directly analogous to LEAK-5 (Kyber FO comparison).
  Target available for Track B B5 multi-algorithm experiments. JSON saved to shared/feedback/.

## 2026-06-17 [B] B-LEAK1 — Adversary loop vs LEAK-1 (cmov if-branch): AUTONOMOUS rediscovery
- What: Ran run_focused.sh against kyber512_leak1_focused.c (corrected from PLACEHOLDER:
  if(b) memcpy(r,x,len) matching harness_oracle injection). Live loop, 3 cycles.
  Stage1: codellama:7b full-source analysis (keyword scanner found no memcmp/strcmp matches).
  Stage2: qwen3:8b refiner (returned non-object JSON — shape error, revision skipped again).
  Oracle: harness_oracle compiled cc -O2 on macOS arm64 (REPS=100, 32-byte memcpy signal).
  Note: first two runs contaminated by stale timing_H001_*.json from prior LEAK-5 session;
  fixed by renaming stale file to ARCHIVED_LEAK5_stale_* (removing H001 from filename).
- Settings: main.py --cycles 3, live mode. codellama:7b stage1/3, qwen3:8b stage2 (partial).
  Oracle: n=50000, Cond-A b=0 (branch not taken, r unchanged), Cond-B b=1 (branch taken, 32-byte memcpy).
  Harness: cc -O2 from kyber512_leak1/harness_oracle.c. REPS=100 signal amplification.
- Result: H001 → PROMOTED.
  category: secret_dependent_branch ✅ (matches ground truth).
  location: cmov() line 9 ✅ (correct function — the if(b) branch on FO comparison result).
  Oracle: t=213.4791, significant=true. mean_A=2.042ns (b=0, no copy), mean_B=1.603ns (b=1, copy).
  Mode: AUTONOMOUS — no keyword scanner match; full-source analysis; no MANDATORY hint fired.
  Loop state snapshot: shared/findings/loop_state_kyber512_leak1.json.
  Note: macOS arm64 with cc -O2 detects the signal (t=213.48 vs WSL2 clang-18 t=74.74 from A6).
  The if(b) branch survives -O2 compilation due to noinline + memcpy being a library call.
  qwen3 refiner JSON shape error (same as LEAK-3): confidence MEDIUM from oracle, not refiner.
- Takeaway: LEAK-1 AUTONOMOUS rediscovery confirmed. UPDATED HEADLINE: 4/5 Kyber leaks
  autonomously rediscovered (LEAK-1/2/3/4 = secret_dependent_branch class). LEAK-5 alone
  required a static-scanner hint (nonconstant_comparison class — different pattern family).
  Stale-feedback bug documented: poll_feedback matches by hypothesis_id substring in filename;
  archived files must have the hypothesis_id substring removed from their name.

## 2026-06-17 [B] B-LEAK3 — Adversary loop vs LEAK-3 (basemul sign-branch): AUTONOMOUS rediscovery
- What: Ran run_focused.sh against kyber512_leak3_focused.c (corrected from PLACEHOLDER:
  local a0 variable pattern matching harness_oracle injection). Engine ran 3-cycle live loop.
  Stage1: codellama:7b full-source analysis (keyword scanner found no memcmp/strcmp matches).
  Stage2: qwen3:8b refiner (returned non-object JSON — shape error noted, revision skipped).
  Oracle: harness_oracle compiled gcc -O0 -fno-inline on macOS arm64 (M-series, REPS=500).
- Settings: main.py --cycles 3, live mode. codellama:7b stage1/3, qwen3:8b stage2 (partial).
  Oracle: n=50000, Cond-A a0=+1000 (positive, no branch), Cond-B a0=-1000 (negative, branch+add).
  Hypothesis counter started at H003 (continuing from prior session state).
- Result: H003 → PROMOTED.
  category: secret_dependent_branch ✅ (matches ground truth).
  location: basemul() line 25 ✅ (correct function).
  Oracle: t=-2421.9069, significant=true. mean_A=5.219ns, mean_B=5.851ns (REPS=500 amplified).
  Mode: AUTONOMOUS — no keyword scanner match; full-source analysis; no MANDATORY hint fired.
  Loop state snapshot: shared/findings/loop_state_kyber512_leak3.json.
  Note: macOS arm64 CAN detect this signal (unlike ML-DSA memcmp NEON case) because the
  leak is a genuine conditional branch (if a0<0) that survives -O0 compilation, not a
  NEON-optimized memcmp. t=-2421 vs Graviton2 t=-3956 — both highly significant.
  qwen3 refiner JSON shape error: confidence downgraded to MEDIUM at refine stage, but
  oracle promotion is definitive. Noted for B6 (multi-LLM): fix qwen3 output parsing.
- Takeaway: LEAK-3 AUTONOMOUS rediscovery confirmed. Updated headline: 3/4 Kyber targets
  run → 3 autonomous (LEAK-2/3/4), 1 hint-assisted (LEAK-5). LEAK-1 pending.

## 2026-06-16 [A] A3 — LEAK-5 timing oracle confirmed (memcmp FO comparison)
- What: Injected LEAK-5 into Kyber512 FO transform (kem.c line 116): replaced constant-time
  verify() with memcmp(). Built standalone harness from pqcrystals ref C source with custom
  fips202 (pure keccak, no external deps). Two harness variants:
  (1) harness_leak5: full decaps timing — not significant (ref C std 8327ns >> 3ns signal).
  (2) harness_oracle: isolates FO comparison only — measures memcmp timing directly.
- Settings: harness_oracle, n=50000, 5% trim, Welch t-test, CLOCK_MONOTONIC_RAW, CPU pinned.
  Condition A: memcmp(ct, cmp, 768) where ct == cmp (valid CT, reads all 768 bytes).
  Condition B: memcmp(ct, cmp, 768) where ct[0] != cmp[0] (invalid CT, exits at byte 0).
- Result: mean_A=28.9ns, mean_B=25.8ns, t=78.93, significant=true.
  Full-decaps timing: mean≈80000ns, std≈8327ns, t=0.08, significant=false.
  (Full-decaps detection requires AVX2 backend ~241ns std, est t~35 at n=500.)
- Takeaway: A3 complete. LEAK-5 oracle CONFIRMED with t=78.93. FIRST MAJOR INTEGRATION MILESTONE.
  Ground truth JSON in shared/feedback/timing_LEAK5-ORACLE_*.json. Track B (B3) can now use
  harness_oracle to close the real feedback loop (drop --use-mock). Next: A4 — additional
  targets (LEAK-2/3/4) and full B-engine integration run.
