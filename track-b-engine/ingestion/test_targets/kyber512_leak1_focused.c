/*
 * kyber512_leak1_focused.c — focused ingestion target for Track B adversary loop.
 *
 * Contains the patched cmov() reconstructed from the ISSUES.md injection description
 * for track-a-target/targets/kyber512_leak1/ (LEAK-1: clangover / implicit-rejection
 * timing oracle). Isolated to the two functions in verify.c that are relevant.
 *
 * NOTE: kyber512_leak1/ has not yet been pushed to the shared repo. Verify and
 * replace the verbatim function body once Track A pushes verify.c there.
 *
 * Ground truth:
 *   secret_dependent_branch in cmov() — the `if(b)` branch selects between the
 *   Fujisaki-Okamoto pre-key (match) and the rejection key z (mismatch) based on
 *   the FO comparison result, which is derived from the secret key. The reference
 *   uses a constant-time XOR-select; this injection replaces it with an explicit
 *   conditional copy, creating a branch on secret-derived failure (b ∈ {0,1}).
 *
 * Oracle: track-a-target/targets/kyber512_leak1/harness_oracle
 *   Cond-A: b=0 (match, cmov skips the copy loop)
 *   Cond-B: b=1 (mismatch, cmov executes the copy loop, overwriting pre-key with z)
 *   t=74.74, significant=true (n=50000, REPS=100).
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define KYBER_N      256
#define KYBER_SYMBYTES 32

/*
 * verify() — constant-time comparison using XOR accumulation (unchanged from reference).
 * Returns 0 if a == b, non-zero otherwise. Used for the FO ciphertext check in kem.c.
 */
int verify(const uint8_t *a, const uint8_t *b, size_t len)
{
  uint64_t r = 0;
  size_t i;

  for(i=0;i<len;i++)
    r |= a[i]^b[i];

  return (-(int64_t)r) >> 63;
}

/*
 * cmov() — patched LEAK-1 version. Reference uses a constant-time XOR-select:
 *   b = -b; for(i<len) r[i] ^= b & (r[i]^x[i]);
 * This injection replaces the XOR-select with an explicit if-branch, creating a
 * timing oracle: b=0 (FO match, pre-key kept) vs b=1 (FO mismatch, z copied in).
 * In the FO transform, b is derived from verify(ct, cmp) — a secret-derived value.
 *
 * [LEAK-1] VULNERABILITY: the conditional branch `if(b)` leaks the FO comparison
 * result, allowing an attacker to distinguish valid from invalid ciphertexts by
 * timing. Analogous to clangover (2024) — that attack defeats the XOR-select via
 * Clang LTO; this manual injection makes the branch explicit.
 */
void cmov(uint8_t *r, const uint8_t *x, size_t len, uint8_t b)
{
  size_t i;

  if(b)
    for(i=0;i<len;i++)
      r[i] = x[i];
}
