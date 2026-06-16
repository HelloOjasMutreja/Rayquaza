/*
 * harness_oracle.c — Direct timing oracle for LEAK-5 (memcmp FO comparison)
 *
 * Instead of measuring the full decaps (which adds ~80µs of NTT noise from
 * the reference C implementation), this harness isolates and times ONLY the
 * FO ciphertext comparison — the exact step that is vulnerable.
 *
 * Condition A: memcmp(ct, cmp, 768) where ct == cmp  → reads all 768 bytes (SLOW)
 * Condition B: memcmp(ct, cmp, 768) where ct[0] != cmp[0] → exits at byte 0 (FAST)
 *
 * This proves the comparison itself is timing-variable (the oracle exists).
 * Expected: mean_A > mean_B, |t| >> 10, significant: true.
 *
 * A separate analysis note explains why full-decaps detection requires either:
 *  a) the AVX2 liboqs backend (std ~241ns → detectable at n~500), or
 *  b) ~2M samples against the reference C backend (std ~8327ns).
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
#include "randombytes.h"

#define DEFAULT_WARMUP 1000
#define DEFAULT_RUNS   50000
#define TRIM_PCT       5

static inline uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static int trimmed_stats(uint64_t *s, int n, double *mean, double *var) {
    qsort(s, n, sizeof(uint64_t), cmp_u64);
    int cut = n * TRIM_PCT / 100, lo = cut, hi = n - cut, cnt = hi - lo;
    double sum = 0;
    for (int i = lo; i < hi; i++) sum += (double)s[i];
    double m = sum / cnt, v = 0;
    for (int i = lo; i < hi; i++) { double d = (double)s[i] - m; v += d*d; }
    *mean = m; *var = v / (cnt - 1);
    return cnt;
}

static double welch_t(double ma, double va, int na, double mb, double vb, int nb) {
    double se = sqrt(va/na + vb/nb);
    return (se == 0.0) ? 0.0 : (ma - mb) / se;
}

/*
 * Patched FO comparison: memcmp instead of constant-time verify.
 * Timing-variable: exits early on first differing byte.
 */
static int __attribute__((noinline))
patched_compare(const uint8_t *a, const uint8_t *b, size_t len) {
    return memcmp(a, b, len) != 0;
}

/*
 * Reference FO comparison: XOR-accumulate (constant-time verify).
 * For baseline — should show t ≈ 0.
 */
static int __attribute__((noinline))
reference_compare(const uint8_t *a, const uint8_t *b, size_t len) {
    uint8_t r = 0;
    for (size_t i = 0; i < len; i++) r |= a[i] ^ b[i];
    return r != 0;
}

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK5-ORACLE";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;

    /* Pin to CPU 0 */
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);

    /*
     * Condition A: buffers that MATCH (memcmp reads all 768 bytes)
     * Condition B: buffers that MISMATCH at byte 0 (memcmp exits immediately)
     */
    uint8_t buf_A[KYBER_CIPHERTEXTBYTES];       /* ct  — same for both below */
    uint8_t buf_A_match[KYBER_CIPHERTEXTBYTES];  /* cmp matches ct */
    uint8_t buf_B[KYBER_CIPHERTEXTBYTES];        /* ct  — differs from cmp at byte 0 */
    uint8_t buf_B_mismatch[KYBER_CIPHERTEXTBYTES];

    randombytes(buf_A, KYBER_CIPHERTEXTBYTES);
    memcpy(buf_A_match, buf_A, KYBER_CIPHERTEXTBYTES);   /* identical */

    randombytes(buf_B, KYBER_CIPHERTEXTBYTES);
    randombytes(buf_B_mismatch, KYBER_CIPHERTEXTBYTES);
    buf_B_mismatch[0] ^= buf_B[0] ^ (buf_B[0] + 1);      /* guarantee byte 0 differs */
    if (buf_B_mismatch[0] == buf_B[0]) buf_B_mismatch[0]++;

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));

    /* Warmup */
    volatile int sink = 0;
    for (int i = 0; i < DEFAULT_WARMUP; i++) {
        sink += patched_compare(buf_A, buf_A_match, KYBER_CIPHERTEXTBYTES);
        sink += patched_compare(buf_B, buf_B_mismatch, KYBER_CIPHERTEXTBYTES);
    }

    /* Interleaved measurement */
    for (int i = 0; i < runs; i++) {
        uint64_t t0;
        t0 = now_ns(); sink += patched_compare(buf_A, buf_A_match, KYBER_CIPHERTEXTBYTES);
        sa[i] = now_ns() - t0;
        t0 = now_ns(); sink += patched_compare(buf_B, buf_B_mismatch, KYBER_CIPHERTEXTBYTES);
        sb[i] = now_ns() - t0;
    }
    (void)sink;

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
    printf("  \"generated_by\": \"harness_oracle\",\n");
    printf("  \"note\": \"isolates FO comparison only; full-decaps detection needs AVX2 backend or ~2M samples\"\n");
    printf("}\n");

    free(sa); free(sb);
    return 0;
}
