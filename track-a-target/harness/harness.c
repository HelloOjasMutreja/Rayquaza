/*
 * harness.c — Kyber512 decapsulation timing harness
 * Track A, Phase A2, Rayquaza project.
 *
 * Measures decapsulation time for two conditions (A and B), computes
 * trimmed mean / variance / Welch t-statistic, and outputs JSON matching
 * the shared/feedback/ schema that Track B's adversary loop consumes.
 *
 * Condition A: valid ciphertext   (normal decaps path, ss matches)
 * Condition B: invalid ciphertext (FO reject path, ss = KDF(z, H(ct)))
 *
 * Usage:
 *   ./harness <hypothesis_id> [run_count]
 *   ./harness H001 10000
 *
 * Output: JSON to stdout. Pipe to shared/feedback/ via run.sh.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sched.h>
#include <oqs/oqs.h>

#define DEFAULT_WARMUP  500
#define DEFAULT_RUNS    10000
#define TRIM_PCT        5       /* trim top and bottom 5% as outliers */

/* ---- timing ------------------------------------------------------------ */

static inline uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* ---- statistics --------------------------------------------------------- */

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a;
    uint64_t y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

/* Compute trimmed mean and sample variance. Modifies samples (sorts in place).
 * Returns the number of samples after trimming. */
static int trimmed_stats(uint64_t *samples, int n,
                         double *out_mean, double *out_var) {
    qsort(samples, n, sizeof(uint64_t), cmp_u64);
    int cut = n * TRIM_PCT / 100;
    int lo = cut, hi = n - cut;
    int count = hi - lo;

    double sum = 0.0;
    for (int i = lo; i < hi; i++)
        sum += (double)samples[i];
    double mean = sum / count;

    double var = 0.0;
    for (int i = lo; i < hi; i++) {
        double d = (double)samples[i] - mean;
        var += d * d;
    }
    var /= (count - 1);

    *out_mean = mean;
    *out_var  = var;
    return count;
}

/* Welch's t-statistic (unequal variance). */
static double welch_t(double mean_a, double var_a, int n_a,
                      double mean_b, double var_b, int n_b) {
    double se = sqrt(var_a / n_a + var_b / n_b);
    if (se == 0.0) return 0.0;
    return (mean_a - mean_b) / se;
}

/* ---- CPU pinning (best-effort, fails silently in WSL2) ----------------- */

static void pin_to_core(int core) {
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(core, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);  /* ignore errors */
}

/* ---- main -------------------------------------------------------------- */

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "H000";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;
    int warmup          = DEFAULT_WARMUP;

    if (runs < 100) {
        fprintf(stderr, "run_count must be >= 100\n");
        return 1;
    }

    /* Pin to core 0 to reduce scheduler noise. Fails silently on WSL2. */
    pin_to_core(0);

    /* Init KEM */
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_kyber_512);
    if (!kem) { fprintf(stderr, "Failed to init Kyber512\n"); return 1; }

    uint8_t *pk         = malloc(kem->length_public_key);
    uint8_t *sk         = malloc(kem->length_secret_key);
    uint8_t *ct_valid   = malloc(kem->length_ciphertext);
    uint8_t *ct_invalid = malloc(kem->length_ciphertext);
    uint8_t *ss_enc     = malloc(kem->length_shared_secret);
    uint8_t *ss_dec     = malloc(kem->length_shared_secret);

    if (!pk || !sk || !ct_valid || !ct_invalid || !ss_enc || !ss_dec) {
        fprintf(stderr, "malloc failed\n"); return 1;
    }

    /* Keypair + valid ciphertext (condition A) */
    OQS_KEM_keypair(kem, pk, sk);
    OQS_KEM_encaps(kem, ct_valid, ss_enc, pk);

    /* Invalid ciphertext: random bytes (condition B — FO reject path) */
    OQS_randombytes(ct_invalid, kem->length_ciphertext);

    /* Allocate sample buffers */
    uint64_t *samples_a = malloc(runs * sizeof(uint64_t));
    uint64_t *samples_b = malloc(runs * sizeof(uint64_t));
    if (!samples_a || !samples_b) { fprintf(stderr, "malloc failed\n"); return 1; }

    /* Warmup — populate instruction cache and TLB */
    for (int i = 0; i < warmup; i++) {
        OQS_KEM_decaps(kem, ss_dec, ct_valid,   sk);
        OQS_KEM_decaps(kem, ss_dec, ct_invalid, sk);
    }

    /* Interleaved measurement: ABAB... reduces temporal bias */
    for (int i = 0; i < runs; i++) {
        uint64_t t0, t1;

        t0 = now_ns();
        OQS_KEM_decaps(kem, ss_dec, ct_valid, sk);
        t1 = now_ns();
        samples_a[i] = t1 - t0;

        t0 = now_ns();
        OQS_KEM_decaps(kem, ss_dec, ct_invalid, sk);
        t1 = now_ns();
        samples_b[i] = t1 - t0;
    }

    /* Statistics (sort+trim modifies samples in place) */
    double mean_a, var_a, mean_b, var_b;
    int n_a = trimmed_stats(samples_a, runs, &mean_a, &var_a);
    int n_b = trimmed_stats(samples_b, runs, &mean_b, &var_b);

    double t_stat = welch_t(mean_a, var_a, n_a, mean_b, var_b, n_b);
    /* |t| > 4 is a conservative threshold at n~9000 (p << 0.001) */
    int significant = fabs(t_stat) > 4.0;

    /* JSON output — matches shared/feedback/ schema */
    printf("{\n");
    printf("  \"hypothesis_id\": \"%s\",\n", hyp_id);
    printf("  \"run_count\": %d,\n", runs);
    printf("  \"mean_A\": %.3f,\n", mean_a);
    printf("  \"mean_B\": %.3f,\n", mean_b);
    printf("  \"variance_A\": %.3f,\n", var_a);
    printf("  \"variance_B\": %.3f,\n", var_b);
    printf("  \"t_statistic\": %.4f,\n", t_stat);
    printf("  \"significant\": %s,\n", significant ? "true" : "false");
    printf("  \"generated_by\": \"harness\"\n");
    printf("}\n");

    /* Cleanup */
    free(pk); free(sk); free(ct_valid); free(ct_invalid);
    free(ss_enc); free(ss_dec);
    free(samples_a); free(samples_b);
    OQS_KEM_free(kem);
    return 0;
}
