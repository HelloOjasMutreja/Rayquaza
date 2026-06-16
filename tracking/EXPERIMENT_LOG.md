# Experiment Log

Append-only. One entry per experiment/run. Never edit past entries.
Format:
## YYYY-MM-DD HH:MM [A/B] <short title>
- What: <what was run>
- Settings: <key parameters>
- Result: <what happened>
- Takeaway: <one-line conclusion / next step>

---

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
