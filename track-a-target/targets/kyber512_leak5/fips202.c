/*
 * fips202.c — SHAKE128, SHAKE256, SHA3-256, SHA3-512 via OpenSSL 3 EVP.
 * No dependency on liboqs internal headers.
 */
#include <string.h>
#include <openssl/evp.h>
#include "fips202.h"

/* ---- streaming SHAKE128 ---- */

void shake128_absorb(shake128ctx *s, const uint8_t *in, size_t inlen) {
    memcpy(s->input, in, inlen);
    s->input_len  = inlen;
    s->output_pos = 0;
    s->squeezed   = 0;
}

static void shake128_do_squeeze(shake128ctx *s) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_shake128(), NULL);
    EVP_DigestUpdate(ctx, s->input, s->input_len);
    EVP_DigestFinalXOF(ctx, s->output, sizeof(s->output));
    EVP_MD_CTX_free(ctx);
    s->squeezed = 1;
}

void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128ctx *s) {
    if (!s->squeezed) shake128_do_squeeze(s);
    size_t len = nblocks * SHAKE128_RATE;
    memcpy(out, s->output + s->output_pos, len);
    s->output_pos += len;
}

void shake128_ctx_release(shake128ctx *s) {
    (void)s;
}

/* ---- streaming SHAKE256 ---- */

void shake256_absorb(shake256ctx *s, const uint8_t *in, size_t inlen) {
    memcpy(s->input, in, inlen);
    s->input_len  = inlen;
    s->output_pos = 0;
    s->squeezed   = 0;
}

static void shake256_do_squeeze(shake256ctx *s) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_shake256(), NULL);
    EVP_DigestUpdate(ctx, s->input, s->input_len);
    EVP_DigestFinalXOF(ctx, s->output, sizeof(s->output));
    EVP_MD_CTX_free(ctx);
    s->squeezed = 1;
}

void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256ctx *s) {
    if (!s->squeezed) shake256_do_squeeze(s);
    size_t len = nblocks * SHAKE256_RATE;
    memcpy(out, s->output + s->output_pos, len);
    s->output_pos += len;
}

void shake256_ctx_release(shake256ctx *s) {
    (void)s;
}

/* ---- one-shot XOF ---- */

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

/* ---- one-shot SHA3 ---- */

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
