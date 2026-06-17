/*
 * harness_kyber.c — REAL AFL++ persistent-mode harness for Kyber512 decapsulation.
 *
 * PRIORITY-2 baseline: coverage-guided fuzzing with NO LLM guidance, run against
 * the SAME weakened reference Kyber that Track A patched (apples-to-apples with
 * the LLM adversary loop). Replaces the earlier stub harness.c.
 *
 * It links against the pqcrystals-kyber512 REFERENCE sources (the same ones
 * Track A injected leaks into), drives a real crypto_kem_dec() with the fuzz
 * input as the ciphertext, and lets AFL++ explore decapsulation code paths.
 *
 * BUILD / RUN: see build_weakened.sh + run_baseline_weakened.sh. Must be built
 * with afl-clang-fast on Linux (WSL2). NOTE: this file has NOT been compiled on
 * the macOS/arm64 dev box (no AFL++/Linux there) — build & verify on WSL2.
 *
 * IMPORTANT INTERPRETATION CAVEAT: AFL++ finds CRASHES and new COVERAGE, not
 * timing leaks. A non-constant-time branch/compare is not itself a crash, so
 * "did AFL find the leak" really means: did coverage-guided fuzzing REACH and
 * exercise the vulnerable code path (poly_tomsg rounding / indcpa_dec normalize
 * / crypto_kem_dec memcmp), and did it surface any memory-safety crash there?
 * The LLM-vs-AFL comparison is: time-to-reach-vulnerable-path + crashes, NOT
 * "AFL detected a timing side channel" (it cannot, by construction).
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

/* Reference Kyber API + parameters. KYBER_REF must be on the include path and
 * built for KYBER_K=2 (Kyber512). See build_weakened.sh. */
#include "kem.h"
#include "params.h"

#ifndef KYBER_SSBYTES
#define KYBER_SSBYTES 32
#endif

/*
 * AFL++ persistent mode (fast: one process, many testcases via shared memory).
 * Falls back to a single read-from-stdin pass when not built with afl-clang-fast
 * (so the harness can be smoke-tested with a plain compiler too).
 */
#ifdef __AFL_FUZZ_TESTCASE_LEN
__AFL_FUZZ_INIT();
#endif

int main(void)
{
    uint8_t pk[KYBER_PUBLICKEYBYTES];
    uint8_t sk[KYBER_SECRETKEYBYTES];
    uint8_t ss[KYBER_SSBYTES];
    uint8_t ct[KYBER_CIPHERTEXTBYTES];

    /* One fixed keypair for the whole campaign. Build randombytes.c to be
     * deterministic (seeded) so runs are reproducible across the corpus. */
    crypto_kem_keypair(pk, sk);

#ifdef __AFL_FUZZ_TESTCASE_LEN
#ifdef __AFL_HAVE_MANUAL_CONTROL
    __AFL_INIT();
#endif
    unsigned char *buf = __AFL_FUZZ_TESTCASE_BUF;   /* shared-memory testcase */

    while (__AFL_LOOP(100000)) {
        int len = __AFL_FUZZ_TESTCASE_LEN;
        memset(ct, 0, sizeof(ct));
        size_t n = (size_t)len < sizeof(ct) ? (size_t)len : sizeof(ct);
        memcpy(ct, buf, n);

        /* Decapsulate the attacker-controlled ciphertext against the fixed sk.
         * Reaches the FO re-encrypt + compare (LEAK-5), poly_tomsg (LEAK-2),
         * and indcpa_dec normalization (LEAK-4) along the way. */
        crypto_kem_dec(ss, ct, sk);
    }
    return 0;
#else
    /* Non-AFL fallback: read one ciphertext from stdin, decapsulate, exit.
     * Lets you smoke-test the build without AFL instrumentation. */
    unsigned char in[KYBER_CIPHERTEXTBYTES];
    size_t got = fread(in, 1, sizeof(in), stdin);
    memset(ct, 0, sizeof(ct));
    memcpy(ct, in, got < sizeof(ct) ? got : sizeof(ct));
    crypto_kem_dec(ss, ct, sk);
    return 0;
#endif
}
