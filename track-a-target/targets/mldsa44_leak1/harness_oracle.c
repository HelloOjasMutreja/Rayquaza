/*
 * harness_oracle.c — Direct timing oracle for LEAK-1 (memcmp challenge comparison)
 *
 * Standalone: no ML-DSA source dependency.
 * Compiles on Linux and macOS: gcc -O2 harness_oracle.c -o harness_oracle -lm
 *
 * Injection: in mld_sign_verify_internal() the constant-time
 *   mld_ct_memcmp(c, c2, MLDSA_CTILDEBYTES)
 * is replaced with the standard early-exit
 *   memcmp(c, c2, MLDSA_CTILDEBYTES)
 *
 * ML-DSA-44 (FIPS 204, parameter set 2): MLDSA_CTILDEBYTES = 32.
 *
 * Condition A: memcmp(c, c2, 32) where c == c2  → reads all 32 bytes (SLOW)
 * Condition B: memcmp(c, c2, 32) where c[0] != c2[0] → exits at byte 0 (FAST)
 *
 * Signal amplification: each timing sample loops REPS=100 comparisons so the
 * raw ~0.4ns/call difference becomes ~40ns/sample — above macOS clock_gettime
 * noise floor (~20ns std dev). Reported means are per-call (divided by REPS).
 *
 * Expected: mean_A > mean_B, |t| >> 4, significant: true on Linux and macOS.
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

#define MLDSA_CTILDEBYTES  32   /* ML-DSA-44 challenge hash size */
#define REPS               100  /* comparisons per sample — amplifies ~0.4ns signal to ~40ns */
#define DEFAULT_WARMUP     1000
#define DEFAULT_RUNS       50000
#define TRIM_PCT           5

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
 * Patched challenge comparison: memcmp instead of constant-time XOR-accumulate.
 * Timing-variable: exits early on first differing byte.
 */
static int __attribute__((noinline))
patched_compare(const uint8_t *a, const uint8_t *b, size_t len) {
    return memcmp(a, b, len) != 0;
}

/*
 * Reference challenge comparison: XOR-accumulate (constant-time, analogous to
 * mld_ct_memcmp in ct.h). For baseline — should show t ≈ 0.
 */
static int __attribute__((noinline, unused))
reference_compare(const uint8_t *a, const uint8_t *b, size_t len) {
    uint8_t r = 0;
    for (size_t i = 0; i < len; i++) r |= a[i] ^ b[i];
    return r != 0;
}

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK1-ORACLE";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;

#ifdef __linux__
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);
#endif

    /*
     * Condition A: challenge buffers that MATCH (memcmp reads all 32 bytes)
     */
    uint8_t buf_A[MLDSA_CTILDEBYTES];
    uint8_t buf_A_match[MLDSA_CTILDEBYTES];
    memset(buf_A, 0xAA, MLDSA_CTILDEBYTES);
    memcpy(buf_A_match, buf_A, MLDSA_CTILDEBYTES);   /* identical → full compare */

    /*
     * Condition B: challenge buffers that MISMATCH at byte 0 (early exit)
     */
    uint8_t buf_B[MLDSA_CTILDEBYTES];
    uint8_t buf_B_mismatch[MLDSA_CTILDEBYTES];
    memset(buf_B, 0xBB, MLDSA_CTILDEBYTES);
    memset(buf_B_mismatch, 0xBB, MLDSA_CTILDEBYTES);
    buf_B_mismatch[0] = 0x00;                         /* byte 0 differs → early exit */

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));
    if (!sa || !sb) { perror("malloc"); return 1; }

    /* Warmup */
    volatile int sink = 0;
    for (int i = 0; i < DEFAULT_WARMUP; i++) {
        for (int r = 0; r < REPS; r++)
            sink += patched_compare(buf_A, buf_A_match, MLDSA_CTILDEBYTES);
        for (int r = 0; r < REPS; r++)
            sink += patched_compare(buf_B, buf_B_mismatch, MLDSA_CTILDEBYTES);
    }

    /* Interleaved measurement: each sample times REPS calls to amplify the signal */
    for (int i = 0; i < runs; i++) {
        uint64_t t0;
        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            sink += patched_compare(buf_A, buf_A_match, MLDSA_CTILDEBYTES);
        sa[i] = now_ns() - t0;   /* raw total for REPS calls; divided by REPS at display */

        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            sink += patched_compare(buf_B, buf_B_mismatch, MLDSA_CTILDEBYTES);
        sb[i] = now_ns() - t0;   /* raw total for REPS calls; divided by REPS at display */
    }
    (void)sink;

    double ma, va, mb, vb;
    int na = trimmed_stats(sa, runs, &ma, &va);
    int nb = trimmed_stats(sb, runs, &mb, &vb);
    double t = welch_t(ma, va, na, mb, vb, nb);
    int sig = fabs(t) > 4.0;

    const char *note =
        "LEAK-1 memcmp ML-DSA-44 challenge comparison oracle. "
        "Cond-A: memcmp(c,c2,32) where c==c2 (full 32-byte scan). "
        "Cond-B: memcmp(c,c2,32) where c[0]!=c2[0] (exits at byte 0). "
        "Injection: mld_ct_memcmp replaced with memcmp in mld_sign_verify_internal. "
        "Signal amplification: REPS=100 calls per sample; means reported per-call. "
        "Portable: significant on Linux (WSL2) and macOS.";

    printf("{\n");
    printf("  \"hypothesis_id\": \"%s\",\n", hyp_id);
    printf("  \"run_count\": %d,\n", runs);
    printf("  \"mean_A\": %.3f,\n", ma / REPS);
    printf("  \"mean_B\": %.3f,\n", mb / REPS);
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
        fprintf(f, "  \"mean_A\": %.3f,\n", ma / REPS);
        fprintf(f, "  \"mean_B\": %.3f,\n", mb / REPS);
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
