/*
 * harness_oracle.c — Direct timing oracle for LEAK-5 (memcmp FO comparison)
 *
 * Standalone: no params.h, no randombytes, no liboqs dependency.
 * Compiles on Linux and macOS: gcc -O2 harness_oracle.c -o harness_oracle -lm
 *
 * Condition A: memcmp(ct, cmp, 768) where ct == cmp  → reads all 768 bytes (SLOW)
 * Condition B: memcmp(ct, cmp, 768) where ct[0] != cmp[0] → exits at byte 0 (FAST)
 *
 * Kyber512 ciphertext is 768 bytes (KYBER_CIPHERTEXTBYTES with KYBER_K=2).
 * Expected result: mean_A > mean_B, |t| >> 10, significant: true.
 *
 * Full-decaps detection requires AVX2 backend (std ~241ns) or ~2M samples
 * against the reference C backend (std ~8327ns). Oracle approach isolates the
 * vulnerable comparison step directly.
 */

#ifdef __linux__
#define _GNU_SOURCE
#include <sched.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>

#define KYBER_CIPHERTEXTBYTES 768  /* Kyber512 with KYBER_K=2 */
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

#ifdef __linux__
    /* Pin to CPU 0 for stable timing on Linux */
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);
#endif

    /*
     * Condition A: buffers that MATCH (memcmp reads all 768 bytes)
     * Use fixed fill pattern — timing result is independent of byte values.
     */
    uint8_t buf_A[KYBER_CIPHERTEXTBYTES];
    uint8_t buf_A_match[KYBER_CIPHERTEXTBYTES];
    memset(buf_A, 0xAB, KYBER_CIPHERTEXTBYTES);
    memcpy(buf_A_match, buf_A, KYBER_CIPHERTEXTBYTES);   /* identical → full compare */

    /*
     * Condition B: buffers that MISMATCH at byte 0 (memcmp exits immediately)
     */
    uint8_t buf_B[KYBER_CIPHERTEXTBYTES];
    uint8_t buf_B_mismatch[KYBER_CIPHERTEXTBYTES];
    memset(buf_B, 0xCD, KYBER_CIPHERTEXTBYTES);
    memset(buf_B_mismatch, 0xCD, KYBER_CIPHERTEXTBYTES);
    buf_B_mismatch[0] = 0x00;                            /* byte 0 differs → early exit */

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));
    if (!sa || !sb) { perror("malloc"); return 1; }

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

    const char *note =
        "LEAK-5 memcmp FO comparison oracle. "
        "Cond-A: memcmp(ct,cmp,768) where ct==cmp (full 768-byte scan). "
        "Cond-B: memcmp(ct,cmp,768) where ct[0]!=cmp[0] (exits at byte 0). "
        "Signal: early-exit timing of non-constant-time FO comparison.";

    printf("{\n");
    printf("  \"hypothesis_id\": \"%s\",\n", hyp_id);
    printf("  \"run_count\": %d,\n", runs);
    printf("  \"mean_A\": %.3f,\n", ma);
    printf("  \"mean_B\": %.3f,\n", mb);
    printf("  \"variance_A\": %.3f,\n", va);
    printf("  \"variance_B\": %.3f,\n", vb);
    printf("  \"t_statistic\": %.4f,\n", t);
    printf("  \"significant\": %s,\n", sig ? "true" : "false");
    printf("  \"generated_by\": \"harness\",\n");
    printf("  \"note\": \"%s\"\n", note);
    printf("}\n");

    /* Save to shared/feedback/ */
    char fname[256];
    snprintf(fname, sizeof(fname),
             "../../../shared/feedback/timing_%s_%lu.json",
             hyp_id, (unsigned long)time(NULL));
    FILE *f = fopen(fname, "w");
    if (f) {
        fprintf(f, "{\n");
        fprintf(f, "  \"hypothesis_id\": \"%s\",\n", hyp_id);
        fprintf(f, "  \"run_count\": %d,\n", runs);
        fprintf(f, "  \"mean_A\": %.3f,\n", ma);
        fprintf(f, "  \"mean_B\": %.3f,\n", mb);
        fprintf(f, "  \"variance_A\": %.3f,\n", va);
        fprintf(f, "  \"variance_B\": %.3f,\n", vb);
        fprintf(f, "  \"t_statistic\": %.4f,\n", t);
        fprintf(f, "  \"significant\": %s,\n", sig ? "true" : "false");
        fprintf(f, "  \"generated_by\": \"harness\",\n");
        fprintf(f, "  \"note\": \"%s\"\n", note);
        fprintf(f, "}\n");
        fclose(f);
        fprintf(stderr, "Saved: %s\n", fname);
    }

    free(sa); free(sb);
    return 0;
}
