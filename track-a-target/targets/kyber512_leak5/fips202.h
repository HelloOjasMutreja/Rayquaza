#ifndef FIPS202_H
#define FIPS202_H
#include <stddef.h>
#include <stdint.h>

#define SHAKE128_RATE 168
#define SHAKE256_RATE 136
#define SHA3_256_RATE 136
#define SHA3_512_RATE  72

/* Keccak-1600 sponge state — 200 bytes on the stack, no heap. */
typedef struct {
    uint64_t     s[25];
    unsigned int pos;   /* absorb: bytes absorbed mod rate; squeeze: bytes output mod rate */
    int          squeezing;
} shake128incctx;

typedef shake128incctx shake128ctx;

typedef struct {
    uint64_t     s[25];
    unsigned int pos;
    int          squeezing;
} shake256incctx;

typedef shake256incctx shake256ctx;

/* --- Incremental SHAKE-128 --- */
void shake128_inc_init(shake128incctx *state);
void shake128_inc_absorb(shake128incctx *state, const uint8_t *in, size_t inlen);
void shake128_inc_finalize(shake128incctx *state);
void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128incctx *state);
void shake128_inc_ctx_release(shake128incctx *state);
void shake128_absorb_once(shake128incctx *state, const uint8_t *in, size_t inlen);
void shake128_absorb(shake128incctx *state, const uint8_t *in, size_t inlen);
void shake128_ctx_release(shake128incctx *state);

/* --- Incremental SHAKE-256 --- */
void shake256_inc_init(shake256incctx *state);
void shake256_inc_absorb(shake256incctx *state, const uint8_t *in, size_t inlen);
void shake256_inc_finalize(shake256incctx *state);
void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256incctx *state);
void shake256_inc_ctx_release(shake256incctx *state);
void shake256_absorb_once(shake256incctx *state, const uint8_t *in, size_t inlen);

/* --- One-shot --- */
void shake128(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void shake256(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void sha3_256(uint8_t *h, const uint8_t *in, size_t inlen);
void sha3_512(uint8_t *h, const uint8_t *in, size_t inlen);

#endif
