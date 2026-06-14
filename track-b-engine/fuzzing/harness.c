/*
 * harness.c — AFL++ persistent-mode fuzz harness for Kyber decapsulation.
 *
 * This is the B2 fuzzing BASELINE: coverage-guided fuzzing with NO LLM
 * guidance. Its findings (unique paths, crashes) are the control condition
 * the Track B LLM adversary engine is later compared against.
 *
 * Right now OQS_KEM_decaps is a STUB that returns 0. The fuzz input is fed
 * in as the `ciphertext` parameter so the harness wiring is exercised.
 *
 * TODO: replace stub with real liboqs once Track A delivers build flags
 *       (see tracking/SYNC.md — A0 flags are DELIVERED; link with
 *        -loqs -lssl -lcrypto -lpthread against ~/liboqs-install).
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Kyber512 sizes (bytes). */
#define KYBER512_CIPHERTEXT_BYTES 768
#define KYBER512_SECRETKEY_BYTES  1632
#define KYBER512_SHAREDSECRET_BYTES 32

/*
 * STUB for liboqs decapsulation. Returns 0 (OQS_SUCCESS).
 * TODO: replace stub with real liboqs once Track A delivers build flags
 *       (see tracking/SYNC.md).
 */
int OQS_KEM_decaps(void *kem, uint8_t *shared_secret,
                   const uint8_t *ciphertext, const uint8_t *sk) {
    (void)kem;
    (void)ciphertext;
    (void)sk;
    if (shared_secret) {
        memset(shared_secret, 0, KYBER512_SHAREDSECRET_BYTES);
    }
    return 0;
}

/*
 * AFL++ LLVMFuzzerTestOneInput entry point. AFL++ (afl-clang-fast) provides
 * the persistent-mode driver and calls this once per input.
 */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    /* Build a fixed-size ciphertext buffer from the fuzz input. */
    uint8_t ciphertext[KYBER512_CIPHERTEXT_BYTES];
    uint8_t sk[KYBER512_SECRETKEY_BYTES];
    uint8_t shared_secret[KYBER512_SHAREDSECRET_BYTES];

    memset(ciphertext, 0, sizeof(ciphertext));
    memset(sk, 0xAB, sizeof(sk)); /* fixed dummy secret key */

    /* Feed fuzz input as the ciphertext parameter (clamped to buffer size). */
    size_t n = size < sizeof(ciphertext) ? size : sizeof(ciphertext);
    memcpy(ciphertext, data, n);

    OQS_KEM_decaps(NULL, shared_secret, ciphertext, sk);
    return 0;
}
