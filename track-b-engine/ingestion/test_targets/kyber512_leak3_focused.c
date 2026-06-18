/*
 * kyber512_leak3_focused.c — focused ingestion target for Track B adversary loop.
 *
 * Contains the patched basemul() matching the injection confirmed by
 * track-a-target/targets/kyber512_leak3/harness_oracle.c (LEAK-3: secret-key
 * coefficient sign branch in NTT base multiplication). Isolated to the relevant
 * functions from ntt.c; helper fqmul/montgomery_reduce included for LLM context.
 *
 * Ground truth:
 *   secret_dependent_branch in basemul() — a local variable a0 = a[0] is introduced
 *   and the injected branch `if (a0 < 0) a0 = (int16_t)(a0 + KYBER_Q)` branches on
 *   the SIGN of the secret key coefficient. a0 feeds into polyvec_basemul_acc_montgomery
 *   (skpv feeds `a` in indcpa_dec). On ARM (Cortex-A/Graviton), the branch is
 *   timing-variable; oracle confirmed on AWS Graviton2: t=-3956.26 (n=50000, REPS=500).
 *
 * Oracle: track-a-target/targets/kyber512_leak3/harness_oracle
 *   Cond-A: a0 = +1000 (positive, branch not taken, no extra add)
 *   Cond-B: a0 = -1000 (negative, branch taken, a0 += KYBER_Q executed)
 *   t=-3956.26, significant=true (n=50000, REPS=500), AWS Graviton2 arm64.
 *
 * Injection source: harness_oracle.c patched_basemul_step():
 *   if (a0 < 0) a0 = (int16_t)(a0 + KYBER_Q);
 *   (a0 is a local variable / function parameter — not an in-place array write)
 *
 * Platform note: on x86-64 with IMUL constant latency, signal may be absent.
 * This oracle is designed for ARM; x86 |t| < 4 expected.
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
 * `a` are secret key polynomial coefficients (skpv[i].coeffs + 2*j).
 *
 * [LEAK-3] VULNERABILITY: a local copy `a0 = a[0]` is introduced, then the
 * injected branch `if (a0 < 0) a0 = (int16_t)(a0 + KYBER_Q)` directly conditions
 * on the SIGN of the secret key coefficient. On ARM (Cortex-A / Graviton),
 * branch direction is timing-variable. The injection makes the sign observable
 * via timing without modifying the `a` array itself (local variable only).
 */
static void basemul(int16_t r[2], const int16_t a[2], const int16_t b[2], int16_t zeta)
{
  /* [LEAK-3] VULNERABILITY: local copy, then branch on sign of secret key coefficient */
  int16_t a0 = a[0];
  if (a0 < 0)
    a0 = (int16_t)(a0 + KYBER_Q);

  r[0]  = fqmul(a[1], b[1]);
  r[0]  = fqmul(r[0], zeta);
  r[0] += fqmul(a0, b[0]);
  r[1]  = fqmul(a0, b[1]);
  r[1] += fqmul(a[1], b[0]);
}
