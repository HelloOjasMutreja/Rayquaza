/*
 * kyber512_leak3_focused.c — focused ingestion target for Track B adversary loop.
 *
 * Contains the patched basemul() reconstructed from the ISSUES.md injection
 * description for track-a-target/targets/kyber512_leak3/ (LEAK-3: secret-key
 * coefficient sign branch in NTT base multiplication). Isolated to the relevant
 * functions from ntt.c; helper fqmul/montgomery_reduce included for LLM context.
 *
 * NOTE: kyber512_leak3/ has not yet been pushed to the shared repo. Verify and
 * replace the verbatim function body once Track A pushes ntt.c there.
 *
 * Ground truth:
 *   secret_dependent_branch in basemul() — the `if(a[0] < 0) a[0] += KYBER_Q`
 *   branches on the SIGN of a secret key polynomial coefficient (skpv feeds into
 *   `a` through polyvec_basemul_acc_montgomery in indcpa_dec). On ARM, multiply
 *   latency is data-dependent for small operands; the branch also leaks on x86
 *   via misprediction. Oracle confirmed on AWS Graviton2: t=-3956.26 (n=50000).
 *
 * Oracle: track-a-target/targets/kyber512_leak3/harness_oracle
 *   Cond-A: a[0] > 0 (branch not taken, no extra addition)
 *   Cond-B: a[0] < 0 (branch taken, a[0] += KYBER_Q executed)
 *   t=-3956.26, significant=true (n=50000), AWS Graviton2 arm64.
 */

#include <stdint.h>

#define KYBER_N    256
#define KYBER_Q    3329
#define QINV       3327  /* q^-1 mod 2^16 */
#define MONT       2285  /* 2^16 mod q */

/*
 * montgomery_reduce — constant-time Montgomery reduction (unchanged from reference).
 */
static int16_t montgomery_reduce(int32_t a)
{
  int16_t t;

  t = (int16_t)a*QINV;
  t = (a - (int32_t)t*KYBER_Q) >> 16;
  return t;
}

/*
 * fqmul — multiplication mod q (constant-time, unchanged from reference).
 */
static int16_t fqmul(int16_t a, int16_t b) {
  return montgomery_reduce((int32_t)a*b);
}

/*
 * basemul — base multiplication in NTT domain.
 *
 * Computes r = a * b in Z_q[X]/(X^2 - zeta). Called per polynomial-vector
 * element during polyvec_basemul_acc_montgomery(skpv, b) in indcpa_dec, where
 * `a` are secret key coefficients (skpv[i].coeffs + 2*j).
 *
 * [LEAK-3] VULNERABILITY: the injected branch `if(a[0] < 0) a[0] += KYBER_Q`
 * directly conditions on the SIGN of the secret key coefficient a[0]. On ARM
 * (Cortex-M and Graviton), integer multiply latency is data-dependent for small
 * operand magnitudes, so even without the explicit branch, coefficient size leaks.
 * The injected if-branch makes the timing leak explicit and measurement-portable.
 * Note: `const` qualifier was removed from `a` to allow the in-place update.
 */
static void basemul(int16_t r[2], int16_t a[2], const int16_t b[2], int16_t zeta)
{
  /* [LEAK-3] VULNERABILITY: branch on sign of secret key coefficient */
  if(a[0] < 0) a[0] += KYBER_Q;

  r[0]  = fqmul(a[1], b[1]);
  r[0]  = fqmul(r[0], zeta);
  r[0] += fqmul(a[0], b[0]);
  r[1]  = fqmul(a[0], b[1]);
  r[1] += fqmul(a[1], b[0]);
}
