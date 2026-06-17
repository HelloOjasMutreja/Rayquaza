/*
 * kyber512_leak4_focused.c — focused ingestion target for Track B Phase B4/B6.
 *
 * Contains the REAL patched indcpa_dec() copied VERBATIM from
 * track-a-target/targets/kyber512_leak4/indcpa.c (the LEAK-4 weakened target).
 * Isolated to a single function (the full 338-line indcpa.c timed out the 7B
 * model). Ground truth: secret_dependent_branch / variable_loop at the
 * `if(mp.coeffs[k] < 0) mp.coeffs[k] += KYBER_Q` normalization loop.
 * Oracle: kyber512_leak4/harness_oracle.
 */

#include <stdint.h>

#define KYBER_N 256
#define KYBER_Q 3329
#define KYBER_INDCPA_MSGBYTES (KYBER_N / 8)
#define KYBER_INDCPA_BYTES 768
#define KYBER_INDCPA_SECRETKEYBYTES 768

typedef struct { int16_t coeffs[KYBER_N]; } poly;
typedef struct { poly vec[2]; } polyvec;

/*************************************************
* Name:        indcpa_dec
*
* Description: Decryption function of the CPA-secure
*              public-key encryption scheme underlying Kyber.
*
* Arguments:   - uint8_t *m: pointer to output decrypted message
*              - const uint8_t *c: pointer to input ciphertext
*              - const uint8_t *sk: pointer to input secret key
**************************************************/
void indcpa_dec(uint8_t m[KYBER_INDCPA_MSGBYTES],
                const uint8_t c[KYBER_INDCPA_BYTES],
                const uint8_t sk[KYBER_INDCPA_SECRETKEYBYTES])
{
  polyvec b, skpv;
  poly v, mp;

  unpack_ciphertext(&b, &v, c);
  unpack_sk(&skpv, sk);

  polyvec_ntt(&b);
  polyvec_basemul_acc_montgomery(&mp, &skpv, &b);
  poly_invntt_tomont(&mp);

  /* LEAK-4: non-constant-time normalization on secret-derived NTT coefficients.
   * barrett_reduce returns centered reps in {-(q-1)/2,...,(q-1)/2}.
   * This conditional += KYBER_Q branches on the SIGN of each secret-derived
   * coefficient of mp = s^T*b, leaking information about the secret key. */
  for(unsigned int k = 0; k < KYBER_N; k++)
    if(mp.coeffs[k] < 0) mp.coeffs[k] += KYBER_Q;

  poly_sub(&mp, &v, &mp);
  poly_reduce(&mp);

  poly_tomsg(m, &mp);
}
