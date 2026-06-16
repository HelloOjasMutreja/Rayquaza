/*
 * fips202.c — SHAKE128/256 and SHA3-256/512 via OpenSSL 3 EVP.
 *
 * Provides the incremental _inc_ API that this liboqs kyber ref uses,
 * plus one-shot wrappers. No dependency on liboqs internal headers.
 */
#include <string.h>
#include <openssl/evp.h>
#include "fips202.h"

/* ====================================================================
 * SHAKE-128 incremental
 * ==================================================================== */

void shake128_inc_init(shake128incctx *ctx) {
    ctx->evp_ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex((EVP_MD_CTX *)ctx->evp_ctx, EVP_shake128(), NULL);
    ctx->pos      = 0;
    ctx->squeezed = 0;
}

void shake128_inc_absorb(shake128incctx *ctx, const uint8_t *in, size_t inlen) {
    EVP_DigestUpdate((EVP_MD_CTX *)ctx->evp_ctx, in, inlen);
}

void shake128_inc_finalize(shake128incctx *ctx) {
    /* Actual XOF finalization is deferred to the first squeezeblocks call
     * so we can still call EVP_DigestFinalXOF with the full desired length. */
    (void)ctx;
}

void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128incctx *ctx) {
    if (!ctx->squeezed) {
        EVP_DigestFinalXOF((EVP_MD_CTX *)ctx->evp_ctx,
                           ctx->buf, sizeof(ctx->buf));
        EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
        ctx->evp_ctx  = NULL;
        ctx->squeezed = 1;
    }
    size_t len = nblocks * SHAKE128_RATE;
    memcpy(out, ctx->buf + ctx->pos, len);
    ctx->pos += len;
}

void shake128_inc_ctx_release(shake128incctx *ctx) {
    if (ctx->evp_ctx) {
        EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
        ctx->evp_ctx = NULL;
    }
}

/* One-shot absorb. Frees any ctx left by a prior inc_init (the kyber matrix-gen
 * path calls xof_init -> shake128_inc_init then xof_absorb -> shake128_absorb_once,
 * so a context may already be allocated) before re-initializing. */
void shake128_absorb_once(shake128incctx *ctx, const uint8_t *in, size_t inlen) {
    if (ctx->evp_ctx) EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
    ctx->evp_ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex((EVP_MD_CTX *)ctx->evp_ctx, EVP_shake128(), NULL);
    EVP_DigestUpdate((EVP_MD_CTX *)ctx->evp_ctx, in, inlen);
    ctx->pos      = 0;
    ctx->squeezed = 0;
}

/* Non-incremental wrappers */
void shake128_absorb(shake128incctx *ctx, const uint8_t *in, size_t inlen) {
    shake128_absorb_once(ctx, in, inlen);
}

void shake128_ctx_release(shake128incctx *ctx) {
    shake128_inc_ctx_release(ctx);
}

/* ====================================================================
 * SHAKE-256 incremental
 * ==================================================================== */

void shake256_inc_init(shake256incctx *ctx) {
    ctx->evp_ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex((EVP_MD_CTX *)ctx->evp_ctx, EVP_shake256(), NULL);
    ctx->pos      = 0;
    ctx->squeezed = 0;
}

void shake256_inc_absorb(shake256incctx *ctx, const uint8_t *in, size_t inlen) {
    EVP_DigestUpdate((EVP_MD_CTX *)ctx->evp_ctx, in, inlen);
}

void shake256_inc_finalize(shake256incctx *ctx) {
    (void)ctx;
}

void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256incctx *ctx) {
    if (!ctx->squeezed) {
        EVP_DigestFinalXOF((EVP_MD_CTX *)ctx->evp_ctx,
                           ctx->buf, sizeof(ctx->buf));
        EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
        ctx->evp_ctx  = NULL;
        ctx->squeezed = 1;
    }
    size_t len = nblocks * SHAKE256_RATE;
    memcpy(out, ctx->buf + ctx->pos, len);
    ctx->pos += len;
}

void shake256_inc_ctx_release(shake256incctx *ctx) {
    if (ctx->evp_ctx) {
        EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
        ctx->evp_ctx = NULL;
    }
}

void shake256_absorb_once(shake256incctx *ctx, const uint8_t *in, size_t inlen) {
    if (ctx->evp_ctx) EVP_MD_CTX_free((EVP_MD_CTX *)ctx->evp_ctx);
    ctx->evp_ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex((EVP_MD_CTX *)ctx->evp_ctx, EVP_shake256(), NULL);
    EVP_DigestUpdate((EVP_MD_CTX *)ctx->evp_ctx, in, inlen);
    ctx->pos      = 0;
    ctx->squeezed = 0;
}

/* ====================================================================
 * One-shot XOF
 * ==================================================================== */

void shake128(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_shake128(), NULL);
    EVP_DigestUpdate(ctx, in, inlen);
    EVP_DigestFinalXOF(ctx, out, outlen);
    EVP_MD_CTX_free(ctx);
}

void shake256(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_shake256(), NULL);
    EVP_DigestUpdate(ctx, in, inlen);
    EVP_DigestFinalXOF(ctx, out, outlen);
    EVP_MD_CTX_free(ctx);
}

/* ====================================================================
 * One-shot SHA3
 * ==================================================================== */

void sha3_256(uint8_t *h, const uint8_t *in, size_t inlen) {
    unsigned int len = 32;
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha3_256(), NULL);
    EVP_DigestUpdate(ctx, in, inlen);
    EVP_DigestFinal_ex(ctx, h, &len);
    EVP_MD_CTX_free(ctx);
}

void sha3_512(uint8_t *h, const uint8_t *in, size_t inlen) {
    unsigned int len = 64;
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha3_512(), NULL);
    EVP_DigestUpdate(ctx, in, inlen);
    EVP_DigestFinal_ex(ctx, h, &len);
    EVP_MD_CTX_free(ctx);
}
