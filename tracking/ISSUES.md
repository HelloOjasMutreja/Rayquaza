# Issues & Open Questions

GitHub-issue style, in-repo so agents can see them. Tag [A]/[B]. 
Format: [STATUS] date [track] description.
STATUS = OPEN / IN-PROGRESS / RESOLVED.

- [RESOLVED] 2026-06-14 [A] Confirm liboqs build flags to share with Track B. → Logged in SYNC.md.
- [OPEN] 2026-06-14 [B] [B-001] GitHub#2 AFL++ harness (track-b-engine/fuzzing/harness.c) uses a STUB OQS_KEM_decaps returning 0. Replace with real liboqs. NOTE: this is NOT blocked on Track A — A0 build flags are already delivered (see SYNC.md); link -loqs -lssl -lcrypto -lpthread against ~/liboqs-install. Status: OPEN (Track B internal work).
- [DEFERRED] 2026-06-14→2026-06-16 [B] [B-002] GitHub#3 Stage 3 vector generation: codellama:7b produces C that is structurally close but does NOT compile (untyped global arrays, undeclared identifiers, missing <math.h>). DEFERRED for B4: generated C vectors are documentation artifacts only; real timing measurement runs through Track A's harness_oracle, not by compiling/running these vectors. Candidate fixes: tighten stage3_vector.txt with a full worked example, add gcc compile+auto-retry to looks_like_c() validation. Not blocking B4.
- [RESOLVED] 2026-06-16 [B] [B-003] B4 real-oracle runs previously blocked: targets assumed for B4 were absent on 2026-06-16. RESOLVED: Track A delivered A2 (timing harness) + A3/A4 (LEAK-2, LEAK-4, LEAK-5 targets + harness_oracle) on 2026-06-16 — see SYNC.md. B4 real runs can now proceed.

## A1 — Candidate Timing Leak Locations in Kyber512 (pqcrystals-kyber_kyber512_ref)

- [RESOLVED] 2026-06-16 [A] LEAK-1 GitHub#4 | verify.c:40–57 | cmov() | Category: compiler-level branch | Oracle: t=74.74, significant=true (n=50000, REPS=100). Target: track-a-target/targets/kyber512_leak1/.
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/verify.c, function cmov(), lines 40–57.
  Assessment (Clang 18, x86-64, WSL2): The asm barrier __asm__("" : "+r"(b)) survives LTO —
  confirmed by inspecting LLVM IR bitcode. Without the barrier (merged TU), Clang 18 emits
  'cmoveq' (conditional-move instruction, constant-time on x86-64) rather than jne/branch.
  Clangover does NOT reproduce on Clang 18/x86-64 for this pattern. Risk exists on ARM
  Cortex-M and older compilers lacking cmov instructions.
  Injection: manual if-branch (if(b) memcpy(r,x,len)) representing downstream/ARM scenario.
  Oracle: Cond-A=b=0 (no copy), Cond-B=b=1 (32-byte copy), REPS=100 amplification.
  Result: mean_A=1.692ns, mean_B=1.508ns, t=74.74, significant=true, n=50000.

- [RESOLVED] 2026-06-16 [A] LEAK-2 GitHub#5 | poly.c:191–210 | poly_tomsg() | Category: branch on secret-derived rounding | Confirmed: t=-139.91, significant=true (misprediction oracle, n=50000). Target: track-a-target/targets/kyber512_leak2/.
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/poly.c, function poly_tomsg(), lines 191–210.
  Rounds each coefficient of mp = v - s^T·b (fully secret-derived) to a message bit.
  Reference uses a branchless multiply-shift (80635 * t >> 28). Naive/commented alternative
  uses integer division or an if-branch at the rounding boundary (coefficient ≈ q/4 = 832).
  Any branch here leaks whether each secret-derived coefficient rounds up or down, revealing
  mp and therefore sk. Targeted by Pessl et al. single-trace power analysis. Injection for
  A3: replace multiply-shift with `if (2*t >= KYBER_Q) bit=1; else bit=0;`.
  Oracle note: branch direction alone (both predictable) is not significant (t=-0.64). Signal
  emerges from misprediction overhead when pattern is unpredictable (random-per-call Cond-B,
  t=-139.91). Compiled with -O0; at -O2 GCC emits cmov, eliminating the leak (research finding).

- [RESOLVED] 2026-06-16 [A] LEAK-3 GitHub#6 | ntt.c:139–145 | basemul() | Category: branch on secret NTT coefficient sign | Confirmed: t=-3956.26, significant=true (ARM oracle, n=50000). Target: track-a-target/targets/kyber512_leak3/.
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/ntt.c, function basemul(), lines 139–145.
  Secret key NTT coefficients (skpv) are Barrett-reduced into centered range {-(q-1)/2...(q-1)/2}.
  Injection: `if (a0 < 0) a0 += KYBER_Q;` before fqmul — branches on sign of each secret coeff.
  Hardware: AWS t4g.micro (ARM Graviton2), Ubuntu 24.04 arm64, ap-southeast-2.
  Oracle: Cond-A=a0=+1000 (positive, branch not taken), Cond-B=a0=-1000 (negative, branch taken).
  Result: mean_A=13.202ns, mean_B=15.341ns, t=-3956.26, significant=true, n=50000.
  Note: difference 2.14ns/call × REPS=500 → very high |t| due to low variance at this sample size.
  x86-64 finding: signal absent (IMUL constant latency; compiler emits cmov even at -O0 for this
  pattern — confirmed Clang 18). ARM Graviton2: branch is real and timing-observable.
  Research significance: secret key NTT coefficient signs (512 bits across KYBER_K=2 polys,
  KYBER_N=256 coeffs each) are recoverable one-by-one per decapsulation call.

- [RESOLVED] 2026-06-16 [A] LEAK-4 GitHub#7 | indcpa.c:325 | indcpa_dec() normalization | Category: branch on secret-derived NTT values | Confirmed: t=-318.58, significant=true (normalization loop oracle, n=50000). Target: track-a-target/targets/kyber512_leak4/.
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/indcpa.c, function indcpa_dec().
  After poly_invntt_tomont(&mp), added: for(k<KYBER_N) if(mp.coeffs[k]<0) mp.coeffs[k]+=KYBER_Q.
  barrett_reduce() returns centered reps in {-(q-1)/2,...,(q-1)/2}. This conditional +=KYBER_Q
  branches on the SIGN of each secret-derived coefficient of mp = s^T*b (fully secret), and
  executes up to 256 extra integer additions. Signal: mean_A=291.9ns (0 additions, all positive),
  mean_B=534.1ns (256 additions, all negative) → 242ns difference, t=-318.58.

- [RESOLVED] 2026-06-16 [A] LEAK-5 GitHub#8 | kem.c:116 → verify.c:16–25 | verify() FO comparison | Category: timing oracle via non-CT compare | Confirmed: t=78.93, significant=true (oracle harness, n=50000). Target: track-a-target/targets/kyber512_leak5/.

## A5 — ML-DSA-44 (FIPS 204) Weakened Target

- [RESOLVED] 2026-06-16 [A] MLDSA-LEAK-1 | sign.c:1197 | mld_sign_verify_internal() challenge comparison | Category: nonconstant_comparison | Confirmed: t=116.97, significant=true (oracle harness, n=50000). Target: track-a-target/targets/mldsa44_leak1/.
  File: mldsa-native_ml-dsa-44_ref/mldsa/src/sign.c, function mld_sign_verify_internal(), line 1197.
  Injection: replace mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES) with memcmp(c, c2, MLDSA_CTILDEBYTES).
  mld_ct_memcmp is XOR-accumulate (constant-time, analogous to Kyber's verify()). memcmp exits
  early on first differing byte, creating a timing oracle on the 32-byte challenge hash comparison.
  In the real ML-DSA verify path, c is derived from the signature and c2 is recomputed from the
  message — a forgery or invalid signature differs in challenge bytes, leaking WHERE it first
  differs and potentially reconstructing the expected challenge. Analogous to KyberSlash1 (LEAK-5).
  Oracle: mean_A=16.195ns (c==c2, full 32-byte scan), mean_B=15.790ns (c[0]!=c2[0], early exit),
    t=116.97, significant=true, n=50000. Small absolute difference (0.4ns) but |t|=116 due to
    very low variance — the 32-byte memcmp is a tight, repeatable operation with minimal noise.
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/kem.c line 116, calling verify.c:16–25.
  The FO transform compares original ct with re-encrypted cmp over 768 bytes. Reference uses
  XOR-accumulate (no early exit) — constant-time. Replacing with memcmp() or any early-exit
  comparison gives a direct decryption oracle: attacker submits ciphertexts differing in the
  last byte, measures timing, learns how many leading bytes of re-encryption match. This is
  KyberSlash1 (2023) — exploited in the Go reference implementation which used bytes.Equal.
  Highest-value injection for A3: replace `verify(ct, cmp, ...)` with `memcmp(ct, cmp, ...)`.
