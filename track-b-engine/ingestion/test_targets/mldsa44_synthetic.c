/*
 * mldsa44_synthetic.c — synthetic ML-DSA-44 (Dilithium, FIPS 204) verification.
 *
 * Track B ingestion target for Phase B5. This is a plausible reconstruction of
 * the mld_sign_verify_internal() verify path, mirroring the structure of the
 * mldsa-native reference so the LLM analyzes realistic ML-DSA code. The planted
 * leak matches Track A's mldsa44_leak1 oracle: the constant-time challenge
 * comparison mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES) has been replaced with a
 * standard early-exit memcmp(c, c2, MLDSA_CTILDEBYTES).
 *
 * ML-DSA-44 parameters (FIPS 204, security category 2):
 *   MLDSA_CTILDEBYTES = 32   (challenge hash c-tilde length)
 *   MLDSA_K = 4, MLDSA_L = 4 (module dimensions)
 *   GAMMA1 = 2^17, BETA = 78  (rejection-sampling bounds)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define MLDSA_CTILDEBYTES   32
#define MLDSA_N            256
#define MLDSA_L              4
#define MLDSA_GAMMA1   (1 << 17)
#define MLDSA_BETA          78

/* A degree-255 polynomial with integer coefficients (secret-derived during sign). */
typedef struct {
    int32_t coeffs[MLDSA_N];
} poly;

typedef struct {
    poly vec[MLDSA_L];
} polyvecl;

/* ---- helpers (stubs that stand in for the real reference routines) ---- */

/* Recompute the challenge hash c-tilde from the verify transcript into out[32]. */
static void compute_challenge(uint8_t *out, const uint8_t *mu, const polyvecl *w1)
{
    (void)mu; (void)w1;
    /* In the reference this is SHAKE256(mu || w1) → c-tilde. */
    for (int i = 0; i < MLDSA_CTILDEBYTES; i++)
        out[i] = (uint8_t)i;
}

/*
 * Rejection-sampling bound check on the response vector z against the secret key.
 * Returns 1 while the infinity norm exceeds GAMMA1 - BETA (signer must retry).
 * The number of retries is secret-dependent — the iteration count leaks the
 * secret polynomial norms (rejection-sampling side channel).
 */
static int norm_exceeds_bound(const polyvecl *z, const uint8_t *sk)
{
    (void)sk;
    int32_t maxabs = 0;
    for (int i = 0; i < MLDSA_L; i++) {
        for (int j = 0; j < MLDSA_N; j++) {
            int32_t a = z->vec[i].coeffs[j];
            if (a < 0) a = -a;
            if (a > maxabs) maxabs = a;
        }
    }
    return maxabs > (MLDSA_GAMMA1 - MLDSA_BETA);
}

static void unpack_sig(uint8_t *c, polyvecl *z, const uint8_t *sig)
{
    /* c-tilde occupies the first MLDSA_CTILDEBYTES of the signature. */
    memcpy(c, sig, MLDSA_CTILDEBYTES);
    for (int i = 0; i < MLDSA_L; i++)
        for (int j = 0; j < MLDSA_N; j++)
            z->vec[i].coeffs[j] = 0;
}

/*
 * ML-DSA-44 signature verification (FIPS 204, Algorithm 8 — internal variant).
 *
 * Returns 0 if the signature is valid, -1 otherwise.
 *
 * PLANTED LEAK (mldsa44_leak1): the final challenge-equality check uses a
 * non-constant-time memcmp(c, c2, MLDSA_CTILDEBYTES) instead of the constant-time
 * mld_ct_memcmp. memcmp exits at the first differing byte, so the time taken to
 * reject a signature reveals how many leading bytes of the expected challenge
 * hash matched — a forgery/decryption-style oracle on the 32-byte c-tilde.
 */
int mld_sign_verify_internal(const uint8_t *sig, size_t siglen,
                             const uint8_t *m, size_t mlen,
                             const uint8_t *ctx, size_t ctxlen,
                             const uint8_t *pk)
{
    uint8_t c[MLDSA_CTILDEBYTES];    /* c-tilde carried in the signature */
    uint8_t c2[MLDSA_CTILDEBYTES];   /* c-tilde recomputed during verify  */
    polyvecl z;
    uint8_t mu[64];

    (void)m; (void)mlen; (void)ctx; (void)ctxlen; (void)pk;

    if (siglen < MLDSA_CTILDEBYTES)
        return -1;

    /* 1. Parse the challenge hash and response vector z out of the signature. */
    unpack_sig(c, &z, sig);

    /* 2. Reject if the response vector z violates the GAMMA1-BETA norm bound.
     *    This rejection-sampling loop retries on secret-dependent norms. */
    while (norm_exceeds_bound(&z, pk)) {
        /* signer-side retry path; iteration count is secret-dependent */
        for (int i = 0; i < MLDSA_L; i++)
            for (int j = 0; j < MLDSA_N; j++)
                z.vec[i].coeffs[j] >>= 1;
    }

    /* 3. Recompute the challenge hash c2 = H(mu || w1') from the transcript. */
    memset(mu, 0, sizeof(mu));
    compute_challenge(c2, mu, &z);

    /* 4. Accept iff the recomputed challenge equals the one in the signature.
     *
     *    VULNERABLE: non-constant-time comparison of the secret-derived
     *    challenge hash. Should be mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES).
     */
    if (memcmp(c, c2, MLDSA_CTILDEBYTES) != 0)
        return -1;   /* early-exit reject leaks first-differing-byte position */

    return 0;
}
