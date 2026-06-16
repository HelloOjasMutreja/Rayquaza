/*
 * harness_leak5.c — A3 timing harness for LEAK-5 (memcmp FO comparison)
 *
 * Condition A: valid ciphertext   → re-encryption matches  → memcmp reads 768 bytes [SLOW]
 * Condition B: invalid ciphertext → re-encryption mismatches early → memcmp exits    [FAST]
 *
 * Expected: mean_A >> mean_B, |t| >> 10, significant: true
 *
 * Usage: ./harness_leak5 <hypothesis_id> [run_count]
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sched.h>

#include "params.h"
#include "api.h"
#include "randombytes.h"

#define DEFAULT_WARMUP 500
#define DEFAULT_RUNS   10000
#define TRIM_PCT       5

static inline uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a;
    uint64_t y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static int trimmed_stats(uint64_t *samples, int n,
                         double *out_mean, double *out_var) {
    qsort(samples, n, sizeof(uint64_t), cmp_u64);
    int cut = n * TRIM_PCT / 100;
    int lo = cut, hi = n - cut, count = hi - lo;
    double sum = 0.0;
    for (int i = lo; i < hi; i++) sum += (double)samples[i];
    double mean = sum / count;
    double var = 0.0;
    for (int i = lo; i < hi; i++) { double d = (double)samples[i] - mean; var += d*d; }
    *out_mean = mean;
    *out_var  = var / (count - 1);
    return count;
}

static double welch_t(double ma, double va, int na, double mb, double vb, int nb) {
    double se = sqrt(va/na + vb/nb);
    return (se == 0.0) ? 0.0 : (ma - mb) / se;
}

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK5-001";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;

    /* Best-effort CPU pinning */
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);

    uint8_t pk[KYBER_PUBLICKEYBYTES];
    uint8_t sk[KYBER_SECRETKEYBYTES];
    uint8_t ct_valid[KYBER_CIPHERTEXTBYTES];
    uint8_t ct_invalid[KYBER_CIPHERTEXTBYTES];
    uint8_t ss[KYBER_SSBYTES];

    crypto_kem_keypair(pk, sk);
    crypto_kem_enc(ct_valid, ss, pk);
    randombytes(ct_invalid, KYBER_CIPHERTEXTBYTES);

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));

    /* Warmup */
    for (int i = 0; i < DEFAULT_WARMUP; i++) {
        crypto_kem_dec(ss, ct_valid,   sk);
        crypto_kem_dec(ss, ct_invalid, sk);
    }

    /* Interleaved measurement */
    for (int i = 0; i < runs; i++) {
        uint64_t t0;

        t0 = now_ns(); crypto_kem_dec(ss, ct_valid,   sk); sa[i] = now_ns() - t0;
        t0 = now_ns(); crypto_kem_dec(ss, ct_invalid, sk); sb[i] = now_ns() - t0;
    }

    double ma, va, mb, vb;
    int na = trimmed_stats(sa, runs, &ma, &va);
    int nb = trimmed_stats(sb, runs, &mb, &vb);
    double t = welch_t(ma, va, na, mb, vb, nb);
    int sig = fabs(t) > 4.0;

    printf("{\n");
    printf("  \"hypothesis_id\": \"%s\",\n", hyp_id);
    printf("  \"run_count\": %d,\n", runs);
    printf("  \"mean_A\": %.3f,\n", ma);
    printf("  \"mean_B\": %.3f,\n", mb);
    printf("  \"variance_A\": %.3f,\n", va);
    printf("  \"variance_B\": %.3f,\n", vb);
    printf("  \"t_statistic\": %.4f,\n", t);
    printf("  \"significant\": %s,\n", sig ? "true" : "false");
    printf("  \"generated_by\": \"harness\"\n");
    printf("}\n");

    free(sa); free(sb);
    return 0;
}
