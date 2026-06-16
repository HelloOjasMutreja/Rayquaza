/*
 * harness_oracle.c — LEAK-4 timing oracle
 *
 * Measures the conditional normalization loop injected into indcpa_dec()
 * after poly_invntt_tomont(&mp):
 *
 *   for (k = 0; k < KYBER_N; k++)
 *     if (mp.coeffs[k] < 0) mp.coeffs[k] += KYBER_Q;
 *
 * Two crafted inputs isolate the timing difference:
 *   Cond-A: all coefficients =  100 (positive) → branch not taken, 0 additions
 *   Cond-B: all coefficients = -100 (negative) → branch taken,   256 additions of KYBER_Q
 *
 * The 256 extra additions (3329 each) in Cond-B produce a measurable time
 * difference proportional to the number of negative coefficients in mp.
 * Since mp = s^T*b (fully secret-derived), negative-coefficient count leaks
 * information about the secret key sk.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <stdlib.h>

#define KYBER_Q 3329
#define KYBER_N 256

/* LEAK-4: conditional normalization loop on secret-derived polynomial */
static __attribute__((noinline))
void normalize_patched(int16_t *coeffs)
{
    for (unsigned int k = 0; k < KYBER_N; k++)
        if (coeffs[k] < 0) coeffs[k] += KYBER_Q;
}

/* Reference: no normalization (keep centered representation) */
static __attribute__((noinline))
void normalize_ref(int16_t *coeffs)
{
    (void)coeffs;  /* constant-time: do nothing */
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
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK4-ORACLE";
    int N = (argc > 2) ? atoi(argv[2]) : 50000;

    /* Condition A: all positive coefficients → branch not taken, no additions */
    int16_t mp_pos[KYBER_N];
    for (int i = 0; i < KYBER_N; i++) mp_pos[i] =  100;

    /* Condition B: all negative coefficients → branch always taken, 256 additions */
    int16_t mp_neg[KYBER_N];
    for (int i = 0; i < KYBER_N; i++) mp_neg[i] = -100;

    double *ta = malloc(N * sizeof(double));
    double *tb = malloc(N * sizeof(double));
    if (!ta || !tb) { perror("malloc"); return 1; }

    /* Warmup */
    for (int i = 0; i < 1000; i++) {
        int16_t tmp[KYBER_N];
        memcpy(tmp, mp_pos, sizeof(tmp)); normalize_patched(tmp);
        memcpy(tmp, mp_neg, sizeof(tmp)); normalize_patched(tmp);
    }

    /* Interleaved measurement */
    for (int i = 0; i < N; i++) {
        uint64_t t0, t1;
        int16_t tmp_a[KYBER_N], tmp_b[KYBER_N];

        memcpy(tmp_a, mp_pos, sizeof(tmp_a));
        t0 = now_ns();
        normalize_patched(tmp_a);
        t1 = now_ns();
        ta[i] = (double)(t1 - t0);

        memcpy(tmp_b, mp_neg, sizeof(tmp_b));
        t0 = now_ns();
        normalize_patched(tmp_b);
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
        "LEAK-4 indcpa_dec normalization oracle. "
        "Cond-A: all coeffs=+100 (positive, branch not-taken, 0 additions). "
        "Cond-B: all coeffs=-100 (negative, branch taken, 256 x +=KYBER_Q). "
        "Signal: 256 conditional additions on secret-derived NTT polynomial mp=s^T*b.";

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
