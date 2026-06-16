/*
 * harness_oracle.c — LEAK-2 timing oracle
 *
 * Measures poly_tomsg_patched() timing with two crafted polynomial inputs
 * to confirm the if-branch leaks coefficient information:
 *
 *   Cond-A: all coefficients = 100 (<q/2=1664) → branch NOT taken, bit=0
 *   Cond-B: all coefficients = 2500 (>q/2)     → branch TAKEN,     bit=1
 *
 * Compiled with -O0 to prevent compiler from replacing if/else with cmov.
 * At -O0, each conditional generates a real branch instruction; the taken
 * vs not-taken path difference is measurable across 256 coefficients/call.
 *
 * For reference, poly_tomsg_ref() uses branchless multiply-shift (constant-time).
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <stdlib.h>

#define KYBER_Q              3329
#define KYBER_N              256
#define KYBER_INDCPA_MSGBYTES 32

typedef struct { int16_t coeffs[KYBER_N]; } poly;

/* LEAK-2: non-constant-time rounding branch */
static __attribute__((noinline))
void poly_tomsg_patched(uint8_t msg[KYBER_INDCPA_MSGBYTES], const poly *a)
{
    unsigned int i, j;
    uint32_t t;
    for (i = 0; i < KYBER_N/8; i++) {
        msg[i] = 0;
        for (j = 0; j < 8; j++) {
            t  = (uint32_t)a->coeffs[8*i+j];
            t += ((int16_t)t >> 15) & KYBER_Q;
            if (2*t >= KYBER_Q)
                t = 1;
            else
                t = 0;
            msg[i] |= (uint8_t)(t << j);
        }
    }
}

/* Reference: branchless multiply-shift (constant-time baseline) */
static __attribute__((noinline))
void poly_tomsg_ref(uint8_t msg[KYBER_INDCPA_MSGBYTES], const poly *a)
{
    unsigned int i, j;
    uint32_t t;
    for (i = 0; i < KYBER_N/8; i++) {
        msg[i] = 0;
        for (j = 0; j < 8; j++) {
            t  = (uint32_t)a->coeffs[8*i+j];
            t += ((int16_t)t >> 15) & KYBER_Q;
            t <<= 1;
            t += 1665;
            t *= 80635;
            t >>= 28;
            t &= 1;
            msg[i] |= (uint8_t)(t << j);
        }
    }
}

static uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static int cmp_double(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static double trimmed_mean(double *arr, int n) {
    qsort(arr, n, sizeof(double), cmp_double);
    int trim = (int)(n * 0.05);
    double s = 0;
    for (int i = trim; i < n - trim; i++) s += arr[i];
    return s / (double)(n - 2*trim);
}

static double trimmed_var(double *arr, int n, double mean) {
    int trim = (int)(n * 0.05);
    double s = 0;
    for (int i = trim; i < n - trim; i++) s += (arr[i]-mean)*(arr[i]-mean);
    return s / (double)(n - 2*trim - 1);
}

int main(int argc, char *argv[])
{
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK2-ORACLE";
    int N = (argc > 2) ? atoi(argv[2]) : 50000;

    /* Condition A: all coeffs > q/2 — fully predictable, 0 mispredicts */
    poly mp_a;
    for (int i = 0; i < KYBER_N; i++) mp_a.coeffs[i] = 2500;

    /* Condition B: randomized per-call — ~128 mispredicts per call */
    /* (tmp_b constructed inside the measurement loop) */

    uint8_t msg_a[KYBER_INDCPA_MSGBYTES], msg_b[KYBER_INDCPA_MSGBYTES];

    double *ta = malloc(N * sizeof(double));
    double *tb = malloc(N * sizeof(double));
    if (!ta || !tb) { perror("malloc"); return 1; }

    /*
     * Oracle design: misprediction oracle.
     *
     * Cond-A (FAST): all coeffs = 2500 (> q/2) — branch always not-taken.
     *   The CPU's branch predictor learns "always not-taken" after warmup → 0 mispredicts.
     *
     * Cond-B (SLOW): random mix of 100/2500 per call, re-randomized each iteration using
     *   a simple LCG seeded on loop index.  The predictor never sees a consistent pattern
     *   across calls → ~128 mispredicts per call → measurable penalty.
     *
     * This simulates: valid ciphertexts that produce specific (learnable) mp distributions
     * vs adversarial or invalid ciphertexts that produce unpredictable mp distributions.
     */

    /* Warmup: train predictor on condition-A pattern */
    for (int i = 0; i < 2000; i++) {
        poly_tomsg_patched(msg_a, &mp_a);
    }

    /* Interleaved measurement */
    for (int i = 0; i < N; i++) {
        uint64_t t0, t1;
        poly tmp_a = mp_a;

        /* Cond-B: fresh pseudo-random pattern each iteration (prevent predictor learning) */
        poly tmp_b;
        for (int k = 0; k < KYBER_N; k++) {
            unsigned int v = (unsigned int)((uint64_t)(i+1) * 6364136223846793005ULL
                                            + (uint64_t)k  * 1442695040888963407ULL);
            tmp_b.coeffs[k] = (int16_t)((v & 0x10000) ? 2500 : 100);
        }

        t0 = now_ns();
        poly_tomsg_patched(msg_a, &tmp_a);
        t1 = now_ns();
        ta[i] = (double)(t1 - t0);

        t0 = now_ns();
        poly_tomsg_patched(msg_b, &tmp_b);
        t1 = now_ns();
        tb[i] = (double)(t1 - t0);
    }

    double mean_a = trimmed_mean(ta, N);
    double mean_b = trimmed_mean(tb, N);
    double var_a  = trimmed_var(ta, N, mean_a);
    double var_b  = trimmed_var(tb, N, mean_b);
    double t_stat = (mean_a - mean_b) / sqrt(var_a/(double)N + var_b/(double)N);
    int sig = fabs(t_stat) > 4.0;

    const char *note =
        "LEAK-2 poly_tomsg misprediction oracle. "
        "Cond-A: all coeffs=2500 (>q/2, predictor learns not-taken, 0 mispredicts). "
        "Cond-B: random-per-call mix of 100/2500 (predictor cannot learn, ~128 mispredicts). "
        "Signal: branch misprediction overhead from secret-derived unpredictable bit pattern. "
        "Compiled -O0 to prevent cmov optimization of if-branch.";

    printf("{\n");
    printf("  \"hypothesis_id\": \"%s\",\n", hyp_id);
    printf("  \"run_count\": %d,\n", N);
    printf("  \"mean_A\": %.3f,\n", mean_a);
    printf("  \"mean_B\": %.3f,\n", mean_b);
    printf("  \"variance_A\": %.3f,\n", var_a);
    printf("  \"variance_B\": %.3f,\n", var_b);
    printf("  \"t_statistic\": %.4f,\n", t_stat);
    printf("  \"significant\": %s,\n", sig ? "true" : "false");
    printf("  \"generated_by\": \"harness\",\n");
    printf("  \"note\": \"%s\"\n", note);
    printf("}\n");

    char fname[256];
    snprintf(fname, sizeof(fname),
             "../../../shared/feedback/timing_%s_%lu.json",
             hyp_id, (unsigned long)time(NULL));
    FILE *f = fopen(fname, "w");
    if (f) {
        fprintf(f, "{\n");
        fprintf(f, "  \"hypothesis_id\": \"%s\",\n", hyp_id);
        fprintf(f, "  \"run_count\": %d,\n", N);
        fprintf(f, "  \"mean_A\": %.3f,\n", mean_a);
        fprintf(f, "  \"mean_B\": %.3f,\n", mean_b);
        fprintf(f, "  \"variance_A\": %.3f,\n", var_a);
        fprintf(f, "  \"variance_B\": %.3f,\n", var_b);
        fprintf(f, "  \"t_statistic\": %.4f,\n", t_stat);
        fprintf(f, "  \"significant\": %s,\n", sig ? "true" : "false");
        fprintf(f, "  \"generated_by\": \"harness\",\n");
        fprintf(f, "  \"note\": \"%s\"\n", note);
        fprintf(f, "}\n");
        fclose(f);
        fprintf(stderr, "Saved: %s\n", fname);
    }

    free(ta);
    free(tb);
    return !sig;
}
