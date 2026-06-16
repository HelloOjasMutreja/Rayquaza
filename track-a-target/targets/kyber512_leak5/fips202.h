#ifndef FIPS202_H
#define FIPS202_H
#include <stddef.h>
#include <stdint.h>

#define SHAKE128_RATE 168
#define SHAKE256_RATE 136
#define SHA3_256_RATE 136
#define SHA3_512_RATE  72

/*
 * Pre-squeezed output buffer. Kyber512 matrix generation needs at most
 * 4 blocks (672 bytes) per polynomial; 16 blocks gives comfortable headroom.
 */
#define _FIPS202_BUF_BLOCKS 32

/* Incremental SHAKE-128 context (what this liboqs version calls shake128incctx) */
typedef struct {
    void    *evp_ctx;   /* EVP_MD_CTX* during absorb; NULL after first squeeze */
    uint8_t  buf[SHAKE128_RATE * _FIPS202_BUF_BLOCKS];
    size_t   pos;
    int      squeezed;
} shake128incctx;

/* Alias so any code using the old shake128ctx name still compiles */
typedef shake128incctx shake128ctx;

/* Incremental SHAKE-256 context */
typedef struct {
    void    *evp_ctx;
    uint8_t  buf[SHAKE256_RATE * _FIPS202_BUF_BLOCKS];
    size_t   pos;
    int      squeezed;
} shake256incctx;

typedef shake256incctx shake256ctx;

/* --- Incremental SHAKE-128 (used by symmetric.h / indcpa.c) --- */
void shake128_inc_init(shake128incctx *state);
void shake128_inc_absorb(shake128incctx *state, const uint8_t *in, size_t inlen);
void shake128_inc_finalize(shake128incctx *state);
void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128incctx *state);
void shake128_inc_ctx_release(shake128incctx *state);

/* One-shot absorb into an (optionally pre-inited) incremental context.
 * Used by kyber_shake128_absorb in symmetric-shake.c. */
void shake128_absorb_once(shake128incctx *state, const uint8_t *in, size_t inlen);

/* Non-incremental wrappers (one-shot absorb) */
void shake128_absorb(shake128incctx *state, const uint8_t *in, size_t inlen);
void shake128_ctx_release(shake128incctx *state);

/* --- Incremental SHAKE-256 --- */
void shake256_inc_init(shake256incctx *state);
void shake256_inc_absorb(shake256incctx *state, const uint8_t *in, size_t inlen);
void shake256_inc_finalize(shake256incctx *state);
void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256incctx *state);
void shake256_inc_ctx_release(shake256incctx *state);
void shake256_absorb_once(shake256incctx *state, const uint8_t *in, size_t inlen);

/* --- One-shot XOF / hash --- */
void shake128(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void shake256(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void sha3_256(uint8_t *h, const uint8_t *in, size_t inlen);
void sha3_512(uint8_t *h, const uint8_t *in, size_t inlen);

#endif
