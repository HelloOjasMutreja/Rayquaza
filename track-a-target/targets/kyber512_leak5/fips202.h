#ifndef FIPS202_H
#define FIPS202_H
#include <stddef.h>
#include <stdint.h>

#define SHAKE128_RATE 168
#define SHAKE256_RATE 136
#define SHA3_256_RATE 136
#define SHA3_512_RATE  72

/*
 * Internal buffer large enough for kyber512 matrix generation:
 * 2x2 polys * ceil(512/168) = 4 blocks per seed.
 * 16 blocks = 2688 bytes gives headroom.
 */
#define _SHAKE128_BUF_BLOCKS 16

typedef struct {
    uint8_t  input[256];
    size_t   input_len;
    uint8_t  output[SHAKE128_RATE * _SHAKE128_BUF_BLOCKS];
    size_t   output_pos;
    int      squeezed;
} shake128ctx;

typedef struct {
    uint8_t  input[256];
    size_t   input_len;
    uint8_t  output[SHAKE256_RATE * _SHAKE128_BUF_BLOCKS];
    size_t   output_pos;
    int      squeezed;
} shake256ctx;

void shake128_absorb(shake128ctx *state, const uint8_t *in, size_t inlen);
void shake128_squeezeblocks(uint8_t *out, size_t nblocks, shake128ctx *state);
void shake128_ctx_release(shake128ctx *state);

void shake256_absorb(shake256ctx *state, const uint8_t *in, size_t inlen);
void shake256_squeezeblocks(uint8_t *out, size_t nblocks, shake256ctx *state);
void shake256_ctx_release(shake256ctx *state);

void shake128(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void shake256(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen);
void sha3_256(uint8_t *h, const uint8_t *in, size_t inlen);
void sha3_512(uint8_t *h, const uint8_t *in, size_t inlen);

#endif
