/*
 * harness_oracle.c — Direct timing oracle for LEAK-3 (basemul ARM branch injection)
 *
 * Standalone: no liboqs dependency.
 * Compiles: gcc -O0 -fno-inline harness_oracle.c -o harness_oracle -lm
 *   OR:     cc  -O0 -fno-inline harness_oracle.c -o harness_oracle -lm
 *
 * Background — data-dependent multiply latency on ARM:
 *   In ntt.c, basemul() multiplies secret key NTT coefficients:
 *     r[0] = fqmul(a[0], b[0]) + fqmul(fqmul(a[1], b[1]), zeta);
 *     r[1] = fqmul(a[0], b[1]) + fqmul(a[1], b[0]);
 *
 *   Here a[] are secret key polynomial coefficients in NTT domain (skpv).
 *   On x86-64: IMUL has constant latency regardless of operand magnitude.
 *   On ARM Cortex-A53/A55 (multiply-accumulate, MUL/UMULL): latency is
 *   nominally constant in the hardware datasheet, BUT branch misprediction
 *   on surrounding bounds-check code IS timing-variable. On some embedded
 *   ARM cores (Cortex-M3, M4, STM32) multiply latency IS data-dependent
 *   for small vs large operands.
 *
 *   The reference normalizes to Barrett-reduced range, but the NTT output
 *   coefficients for the secret key live in {-(q-1)/2 .. (q-1)/2} (centered).
 *   Any code that branches on the SIGN of these coefficients (e.g., a
 *   normalization step "if (a[0] < 0) a[0] += KYBER_Q") leaks whether each
 *   coefficient is positive or negative — direct information about the
 *   secret key in NTT domain.
 *
 * Injection (this file):
 *   Before the multiply, add:
 *     if (a0 < 0) a0 += KYBER_Q;   // LEAK-3: branch on secret key coefficient sign
 *
 *   This is NOT in the reference implementation. It represents a "defensive
 *   normalization" a developer might add thinking it's safe, or an optimization
 *   for unsigned-multiply-only platforms. On ARM, it produces a branch whose
 *   direction (taken/not-taken) directly encodes the sign of each secret
 *   key NTT coefficient.
 *
 * Oracle design:
 *   Condition A: a0 = +COEFF_POSITIVE (branch NOT taken — positive, no add)
 *   Condition B: a0 = -COEFF_NEGATIVE (branch TAKEN — negative, add KYBER_Q)
 *   REPS=500: ARM timer resolution typically 1-10ns; amplify to get measurable delta.
 *
 * Expected on ARM: mean_B > mean_A (Cond-B takes branch, executes extra add).
 *   The branch itself is the primary signal; the addition is secondary.
 *   On x86-64: signal may be small (|t| < 4) — this oracle is designed for ARM.
 *
 * Build note for ARM:
 *   gcc -O0 -fno-inline harness_oracle.c -o harness_oracle -lm
 *   -O0 and -fno-inline prevent the compiler from replacing the branch with a cmov.
 *   At -O2, GCC on ARM will also emit conditional instructions — use -O0.
 *
 * Theoretical background:
 *   Ravi et al. "Side-channel attacks on post-quantum signature schemes based on
 *   coding theory" (2019); Xu et al. single-trace attack on Kyber (2021).
 *   Secret key NTT coefficients can be recovered coefficient-by-coefficient if
 *   their sign is observable via timing. Each coefficient is one bit of information
 *   (positive vs negative), and with KYBER_N=256 coefficients per polynomial and
 *   KYBER_K=2 polynomials, the attack recovers 512 bits of sign information per
 *   decapsulation call.
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

#define KYBER_Q         3329
#define KYBER_N         256
#define COEFF_POSITIVE  1000   /* representative positive NTT coefficient */
#define COEFF_NEGATIVE  1000   /* abs value of representative negative coefficient */
#define REPS            500    /* calls per timing sample — ARM needs more amplification */
#define DEFAULT_WARMUP  2000
#define DEFAULT_RUNS    50000
#define TRIM_PCT        5

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
 * fqmul: Montgomery multiplication mod KYBER_Q.
 * Reference from pqcrystals-kyber_kyber512_ref/ntt.c.
 * On ARM: SMULL/SMLAL instruction used; latency nominally constant
 * but surrounding branch on sign IS data-dependent.
 */
static int32_t montgomery_reduce(int64_t a) {
    int32_t t;
    t = (int32_t)((int32_t)a * (int32_t)62209); /* QINV = -3327 mod 2^16; 62209 = 65536-3327 */
    t = (int32_t)((a - (int64_t)t * KYBER_Q) >> 16);
    return t;
}

static int16_t fqmul(int16_t a, int16_t b) {
    return (int16_t)montgomery_reduce((int32_t)a * b);
}

/*
 * patched_basemul_step: One multiply of a secret key coefficient.
 * LEAK-3 injection: branch on sign of secret coefficient before use.
 *
 * a0:   secret key NTT coefficient (secret, sign unknown to attacker)
 * b0:   ciphertext NTT coefficient (attacker-controlled in real attack)
 * zeta: precomputed NTT root of unity (public)
 */
static int16_t __attribute__((noinline))
patched_basemul_step(int16_t a0, int16_t b0, int16_t zeta) {
    /* LEAK-3: branch on secret key coefficient sign — timing-variable */
    if (a0 < 0)
        a0 = (int16_t)(a0 + KYBER_Q);   /* normalize to [0, KYBER_Q) */
    return fqmul(a0, b0);
    (void)zeta;
}

/*
 * reference_basemul_step: No branch — directly uses signed coefficient.
 * Constant-time on any platform with constant-time multiply.
 */
static int16_t __attribute__((noinline, unused))
reference_basemul_step(int16_t a0, int16_t b0, int16_t zeta) {
    return fqmul(a0, b0);
    (void)zeta;
}

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK3-ORACLE";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;

#ifdef __linux__
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);
#endif

    /* Representative NTT coefficients and zeta */
    int16_t a_pos  =  (int16_t) COEFF_POSITIVE;   /* Cond-A: positive (branch not taken) */
    int16_t a_neg  = -(int16_t) COEFF_NEGATIVE;   /* Cond-B: negative (branch taken)     */
    int16_t b_val  = (int16_t)1234;               /* ciphertext coefficient — public      */
    int16_t zeta   = (int16_t)17;                 /* NTT root of unity — public           */

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));
    if (!sa || !sb) { perror("malloc"); return 1; }

    /* Warmup — bring branch predictor and icache to steady state */
    volatile int32_t sink = 0;
    for (int i = 0; i < DEFAULT_WARMUP; i++) {
        for (int r = 0; r < REPS; r++)
            sink += patched_basemul_step(a_pos, b_val, zeta);
        for (int r = 0; r < REPS; r++)
            sink += patched_basemul_step(a_neg, b_val, zeta);
    }

    /* Interleaved measurement: REPS calls per sample */
    for (int i = 0; i < runs; i++) {
        uint64_t t0;

        /* Condition A: positive coefficient — branch not taken */
        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            sink += patched_basemul_step(a_pos, b_val, zeta);
        sa[i] = now_ns() - t0;   /* raw total for REPS calls */

        /* Condition B: negative coefficient — branch taken, add KYBER_Q */
        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            sink += patched_basemul_step(a_neg, b_val, zeta);
        sb[i] = now_ns() - t0;   /* raw total for REPS calls */
    }
    (void)sink;

    double ma, va, mb, vb;
    int na = trimmed_stats(sa, runs, &ma, &va);
    int nb = trimmed_stats(sb, runs, &mb, &vb);
    double t = welch_t(ma, va, na, mb, vb, nb);
    int sig = fabs(t) > 4.0;

    const char *note =
        "LEAK-3 basemul branch injection oracle (ARM sign-branch class). "
        "Injection: if(a0<0) a0+=KYBER_Q before fqmul(a0,b0). "
        "Cond-A: a0=+1000 (positive, branch not taken). "
        "Cond-B: a0=-1000 (negative, branch taken + KYBER_Q add). "
        "Compiled -O0 -fno-inline to prevent cmov optimization. "
        "Designed for ARM Graviton2 (t4g.micro); signal may be small on x86-64. "
        "Signal amplification: REPS=500 calls per sample.";

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

    /* Save to shared/feedback/ — path relative to target dir */
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
