/*
 * fips202.c — self-contained Keccak-1600 / SHAKE / SHA3.
 * No external dependencies. Implements the incremental _inc_ API used by
 * this liboqs kyber ref. ~3x faster than the previous OpenSSL EVP wrapper
 * because there are no heap allocations; state lives on the stack.
 */
#include <string.h>
#include "fips202.h"

/* ====================================================================
 * Keccak-1600 permutation
 * ==================================================================== */

static const uint64_t RC[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808AULL,
    0x8000000080008000ULL, 0x000000000000808BULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008AULL,
    0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000AULL,
    0x000000008000808BULL, 0x800000000000008BULL, 0x8000000000008089ULL,
    0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800AULL, 0x800000008000000AULL, 0x8000000080008081ULL,
    0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL
};

static const int RHO[24] = {
     1,  3,  6, 10, 15, 21, 28, 36, 45, 55,  2, 14,
    27, 41, 56,  8, 25, 43, 62, 18, 39, 61, 20, 44
};

static const int PI[24] = {
    10,  7, 11, 17, 18,  3,  5, 16,  8, 21, 24,  4,
    15, 23, 19, 13, 12,  2, 20, 14, 22,  9,  6,  1
};

#define ROL64(x, n) (((x) << (n)) | ((x) >> (64 - (n))))

static void keccak_f1600(uint64_t a[25]) {
    uint64_t c[5], d, t, tmp;
    int i, x, r;

    for (r = 0; r < 24; r++) {
        /* Theta */
        for (x = 0; x < 5; x++)
            c[x] = a[x] ^ a[x+5] ^ a[x+10] ^ a[x+15] ^ a[x+20];
        for (x = 0; x < 5; x++) {
            d = c[(x+4)%5] ^ ROL64(c[(x+1)%5], 1);
            for (i = x; i < 25; i += 5) a[i] ^= d;
        }
        /* Rho + Pi */
        t = a[1];
        for (i = 0; i < 24; i++) {
            tmp    = a[PI[i]];
            a[PI[i]] = ROL64(t, RHO[i]);
            t      = tmp;
        }
        /* Chi */
        for (i = 0; i < 25; i += 5) {
            uint64_t b[5];
            for (x = 0; x < 5; x++) b[x] = a[i+x];
            for (x = 0; x < 5; x++)
                a[i+x] = b[x] ^ (~b[(x+1)%5] & b[(x+2)%5]);
        }
        /* Iota */
        a[0] ^= RC[r];
    }
}

/* ====================================================================
 * Sponge helpers
 * ==================================================================== */

/* XOR a byte into the little-endian lane at position pos */
static inline void sponge_xor_byte(uint64_t s[25], unsigned int pos, uint8_t b) {
    s[pos / 8] ^= (uint64_t)b << (8 * (pos % 8));
}

/* Read a byte from lane at position pos */
static inline uint8_t sponge_get_byte(const uint64_t s[25], unsigned int pos) {
    return (uint8_t)(s[pos / 8] >> (8 * (pos % 8)));
}

static void absorb_bytes(uint64_t s[25], unsigned int *pos,
                         unsigned int rate,
                         const uint8_t *in, size_t inlen) {
    size_t i;
    for (i = 0; i < inlen; i++) {
        sponge_xor_byte(s, *pos, in[i]);
        if (++(*pos) == rate) {
            keccak_f1600(s);
            *pos = 0;
        }
    }
}

static void pad_and_switch(uint64_t s[25], unsigned int pos,
                           unsigned int rate, uint8_t domain) {
    /* SHAKE padding: domain || 0* || 1 */
    sponge_xor_byte(s, pos, domain);
    sponge_xor_byte(s, rate - 1, 0x80);
    keccak_f1600(s);
}

static void squeeze_blocks(uint8_t *out, size_t nblocks,
                           uint64_t s[25], unsigned int rate) {
    size_t b, i;
    for (b = 0; b < nblocks; b++) {
        for (i = 0; i < rate; i++)
            out[b * rate + i] = sponge_get_byte(s, i);
        keccak_f1600(s);
    }
}

/* ====================================================================
 * SHAKE-128 incremental
 * ==================================================================== */

void shake128_inc_init(shake128incctx *ctx) {
    memset(ctx->s, 0, sizeof(ctx->s));
    ctx->pos = 0;
    ctx->squeezing = 0;
}

void shake128_inc_absorb(shake128incctx *ctx,
                         const uint8_t *in, size_t inlen) {
    absorb_bytes(ctx->s, &ctx->pos, SHAKE128_RATE, in, inlen);
}

void shake128_inc_finalize(shake128incctx *ctx) {
    pad_and_switch(ctx->s, ctx->pos, SHAKE128_RATE, 0x1f);
    ctx->pos = 0;
    ctx->squeezing = 1;
}

void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128incctx *ctx) {
    squeeze_blocks(out, nblocks, ctx->s, SHAKE128_RATE);
}

void shake128_inc_ctx_release(shake128incctx *ctx) {
    (void)ctx; /* stack-allocated; nothing to free */
}

void shake128_absorb_once(shake128incctx *ctx, const uint8_t *in, size_t inlen) {
    memset(ctx->s, 0, sizeof(ctx->s));
    ctx->pos = 0;
    ctx->squeezing = 0;
    absorb_bytes(ctx->s, &ctx->pos, SHAKE128_RATE, in, inlen);
    pad_and_switch(ctx->s, ctx->pos, SHAKE128_RATE, 0x1f);
    ctx->pos = 0;
    ctx->squeezing = 1;
}

void shake128_absorb(shake128incctx *ctx, const uint8_t *in, size_t inlen) {
    shake128_absorb_once(ctx, in, inlen);
}

void shake128_ctx_release(shake128incctx *ctx) {
    (void)ctx;
}

/* ====================================================================
 * SHAKE-256 incremental
 * ==================================================================== */

void shake256_inc_init(shake256incctx *ctx) {
    memset(ctx->s, 0, sizeof(ctx->s));
    ctx->pos = 0;
    ctx->squeezing = 0;
}

void shake256_inc_absorb(shake256incctx *ctx,
                         const uint8_t *in, size_t inlen) {
    absorb_bytes(ctx->s, &ctx->pos, SHAKE256_RATE, in, inlen);
}

void shake256_inc_finalize(shake256incctx *ctx) {
    pad_and_switch(ctx->s, ctx->pos, SHAKE256_RATE, 0x1f);
    ctx->pos = 0;
    ctx->squeezing = 1;
}

void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256incctx *ctx) {
    squeeze_blocks(out, nblocks, ctx->s, SHAKE256_RATE);
}

void shake256_inc_ctx_release(shake256incctx *ctx) {
    (void)ctx;
}

void shake256_absorb_once(shake256incctx *ctx, const uint8_t *in, size_t inlen) {
    memset(ctx->s, 0, sizeof(ctx->s));
    ctx->pos = 0;
    absorb_bytes(ctx->s, &ctx->pos, SHAKE256_RATE, in, inlen);
    pad_and_switch(ctx->s, ctx->pos, SHAKE256_RATE, 0x1f);
    ctx->pos = 0;
    ctx->squeezing = 1;
}

/* ====================================================================
 * One-shot XOF
 * ==================================================================== */

void shake128(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen) {
    shake128incctx ctx;
    shake128_absorb_once(&ctx, in, inlen);
    /* squeeze byte-by-byte for arbitrary outlen */
    size_t i;
    for (i = 0; i < outlen; i++) {
        if (i % SHAKE128_RATE == 0 && i != 0)
            keccak_f1600(ctx.s);
        out[i] = sponge_get_byte(ctx.s, i % SHAKE128_RATE);
    }
}

void shake256(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen) {
    shake256incctx ctx;
    shake256_absorb_once(&ctx, in, inlen);
    size_t i;
    for (i = 0; i < outlen; i++) {
        if (i % SHAKE256_RATE == 0 && i != 0)
            keccak_f1600(ctx.s);
        out[i] = sponge_get_byte(ctx.s, i % SHAKE256_RATE);
    }
}

/* ====================================================================
 * One-shot SHA3 (domain = 0x06, fixed output length)
 * ==================================================================== */

static void sha3_hash(uint8_t *out, size_t outlen,
                      const uint8_t *in, size_t inlen, unsigned int rate) {
    uint64_t s[25] = {0};
    unsigned int pos = 0;
    absorb_bytes(s, &pos, rate, in, inlen);
    pad_and_switch(s, pos, rate, 0x06); /* SHA3 domain, not SHAKE */
    size_t i;
    for (i = 0; i < outlen; i++)
        out[i] = sponge_get_byte(s, i);
}

void sha3_256(uint8_t *h, const uint8_t *in, size_t inlen) {
    sha3_hash(h, 32, in, inlen, SHA3_256_RATE);
}

void sha3_512(uint8_t *h, const uint8_t *in, size_t inlen) {
    sha3_hash(h, 64, in, inlen, SHA3_512_RATE);
}
