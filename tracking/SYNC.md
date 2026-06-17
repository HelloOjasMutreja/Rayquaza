## Open coordination questions
- 2026-06-16→17 [B→A] mldsa44_leak1 oracle portability — RESOLVED with hardware caveat.
  Problem: macOS clock_gettime noise floor swamps the 32-byte memcmp signal (t=0.27 on macOS).
  Track A fix (WSL2/x86): REPS=100 loop → t=-103.26, significant=true.
  Track B finding: REPS=100/1000/5000 all non-significant on macOS/arm64 (|t|<1, sign unstable).
  Root cause: -O2 on arm64 compiles 32-byte memcmp as fixed NEON sequence — no early-exit saving exists.
  CONCLUSION: REPS amplification works on x86; ML-DSA oracle confirmation requires WSL2/x86, not macOS.
- 2026-06-17 [B→A] Integration complete: live adversary loop ran against all three Kyber targets.
  3/3 correct rediscoveries (LEAK-2, LEAK-4, LEAK-5). On macOS: LEAK-4 oracle strong/stable (t=-901);
  LEAK-2 misprediction oracle significant ~4/5 runs (t -6 to -31, occasional noisy outliers);
  LEAK-5 oracle strong (t=+141..+235). CAVEAT: standalone oracle is not hypothesis-specific —
  PROMOTED ≠ confirmed correct; paper must judge by category/location match vs ground truth.
- 2026-06-17 [B→A] Housekeeping: track-a-target/targets/mldsa44_leak1/ confirmed clean on Track A side
  (only Makefile + harness_oracle.c + harness_oracle binary). If a DamsDen/ Next.js directory appears
  locally on Track B's machine, it was never committed — do not stage it.

- 2026-06-17 [A→B] ROOT CAUSE for three "missing/unchanged" reports: **Track B's fork is behind main.**
  ACTION: `git fetch origin && git merge origin/main` (or rebase) before further work. Specifics:
  1. mldsa44_leak1/harness_oracle.c REPS=100 fix IS present + committed (1c7fb88 on main). The
     "no REPS loop" report was a stale checkout. Track A additionally fixed the integer-division
     quantization (raw total now divided at display) → reconfirmed WSL2/x86 t=-226.85, significant.
  2. kyber512_leak1/ and kyber512_leak3/ ARE on main (harness_oracle.c + Makefile each) with ground
     truth in shared/feedback/ (LEAK1-CMOV t=74.74; LEAK3-ARM-GRAVITON2 t=-3956.26). Note: for
     leak1/leak3 the injection is embedded in the standalone harness_oracle.c, not a separate kem.c.
  3. DamsDen/ was NEVER committed and is not in git history — purely local to Track B; delete locally.
  Once pulled, the leak1/leak3 reconstruction placeholders Track B's agent made can be discarded.