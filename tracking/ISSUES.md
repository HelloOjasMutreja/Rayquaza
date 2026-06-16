# Issues & Open Questions

GitHub-issue style, in-repo so agents can see them. Tag [A]/[B]. 
Format: [STATUS] date [track] description.
STATUS = OPEN / IN-PROGRESS / RESOLVED.

- [RESOLVED] 2026-06-14 [A] Confirm liboqs build flags to share with Track B. → Logged in SYNC.md.
- [OPEN] 2026-06-14 [B] [B-001] GitHub#2 AFL++ harness (track-b-engine/fuzzing/harness.c) uses a STUB OQS_KEM_decaps returning 0. Replace with real liboqs. NOTE: this is NOT blocked on Track A — A0 build flags are already delivered (see SYNC.md); link -loqs -lssl -lcrypto -lpthread against ~/liboqs-install. Status: OPEN (Track B internal work).
- [OPEN] 2026-06-14 [B] [B-002] GitHub#3 Stage 3 vector generation: codellama:7b produces C that is structurally close but does NOT compile (untyped global arrays, undeclared identifiers, missing <math.h>). B3 loop mechanics verified end-to-end with mock feedback regardless; vector quality is the target of Phase B4 prompt iteration. Candidate fixes: tighten stage3_vector.txt with a full worked example, add gcc compile+auto-retry to looks_like_c() validation. Status: OPEN.

## A1 — Candidate Timing Leak Locations in Kyber512 (pqcrystals-kyber_kyber512_ref)

- [OPEN] 2026-06-16 [A] LEAK-1 GitHub#4 | verify.c:40–57 | cmov() | Category: compiler-level branch
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/verify.c, function cmov(), lines 40–57.
  The `__asm__("" : "+r"(b))` barrier prevents the compiler from branching on b within one
  translation unit, but is defeated by Clang with LTO (link-time optimization), which can see
  that b ∈ {0,1} across TU boundaries and emit a conditional branch. This turns the rejection
  selection (pre-key vs z) into a timing oracle: fail=0 (match) and fail=1 (no-match) take
  different times, breaking implicit rejection. Known as "clangover" (2024). GCC -O2 is
  generally safe; Clang -O2 -flto is not. Injection for A3: remove the asm barrier and
  compile with clang -O2 -flto, or replace the XOR-select with an explicit if/memcpy.

- [OPEN] 2026-06-16 [A] LEAK-2 GitHub#5 | poly.c:191–210 | poly_tomsg() | Category: branch on secret-derived rounding
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/poly.c, function poly_tomsg(), lines 191–210.
  Rounds each coefficient of mp = v - s^T·b (fully secret-derived) to a message bit.
  Reference uses a branchless multiply-shift (80635 * t >> 28). Naive/commented alternative
  uses integer division or an if-branch at the rounding boundary (coefficient ≈ q/4 = 832).
  Any branch here leaks whether each secret-derived coefficient rounds up or down, revealing
  mp and therefore sk. Targeted by Pessl et al. single-trace power analysis. Injection for
  A3: replace multiply-shift with `if (2*t >= KYBER_Q) bit=1; else bit=0;`.

- [OPEN] 2026-06-16 [A] LEAK-3 GitHub#6 | ntt.c:139–145 | basemul() | Category: timing on secret key coefficients
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/ntt.c, function basemul(), lines 139–145.
  Secret key coefficients (skpv) are passed directly as argument `a` and consumed via
  fqmul() → montgomery_reduce(). Reference is branchless on x86-64 (imul constant latency).
  On ARM Cortex-M and some embedded CPUs, multiply latency is data-dependent for small
  operand values, making secret key coefficient magnitudes observable. In AVX2 backend, SIMD
  behavior differs. Injection for A3: add `if (a[0] < 0) a[0] += KYBER_Q;` before use —
  branch directly on secret key coefficient sign.

- [OPEN] 2026-06-16 [A] LEAK-4 GitHub#7 | ntt.c:106–126 | invntt() via barrett_reduce | Category: branch on secret-derived NTT values
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/ntt.c, function invntt(), lines 106–126.
  Applied to mp (= s^T·b, secret-derived) via poly_invntt_tomont(). barrett_reduce() returns
  centered representatives in {-(q-1)/2,...,(q-1)/2}. Naive callers often add a conditional
  normalization (`if (x < 0) x += q`) which branches on secret-derived values. Reference
  avoids this by keeping the centered representation throughout — but it is an easy mistake
  to introduce. Injection for A3: add a normalization loop after poly_invntt_tomont() in
  indcpa_dec() that branches on mp.coeffs[i] < 0.

- [OPEN] 2026-06-16 [A] LEAK-5 GitHub#8 | kem.c:116 → verify.c:16–25 | verify() FO comparison | Category: timing oracle via non-CT compare
  File: src/kem/kyber/pqcrystals-kyber_kyber512_ref/kem.c line 116, calling verify.c:16–25.
  The FO transform compares original ct with re-encrypted cmp over 768 bytes. Reference uses
  XOR-accumulate (no early exit) — constant-time. Replacing with memcmp() or any early-exit
  comparison gives a direct decryption oracle: attacker submits ciphertexts differing in the
  last byte, measures timing, learns how many leading bytes of re-encryption match. This is
  KyberSlash1 (2023) — exploited in the Go reference implementation which used bytes.Equal.
  Highest-value injection for A3: replace `verify(ct, cmp, ...)` with `memcmp(ct, cmp, ...)`.
