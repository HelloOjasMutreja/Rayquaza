/*
 * harness_oracle.c — Direct timing oracle for LEAK-1 (cmov branch injection)
 *
 * Standalone: no liboqs dependency.
 * Compiles: gcc/clang -O2 harness_oracle.c -o harness_oracle -lm
 *
 * Background — "clangover" class vulnerability:
 *   In kem.c, after decapsulation:
 *     fail = verify(ct, cmp, KYBER_CIPHERTEXTBYTES);   // 0 = match, 1 = mismatch
 *     cmov(kr, z, KYBER_SYMBYTES, fail);                // select real key vs decoy
 *
 *   The reference cmov() uses __asm__("" : "+r"(b)) to prevent compilers from
 *   inferring that b ∈ {0,1} and replacing the XOR-select with a branch.
 *   The comment in verify.c: "not necessary when verify.c and kem.c are separate
 *   translation units, but downstream consumers may copy/merge this code."
 *
 * Hardware/compiler assessment (Clang 18, x86-64, WSL2):
 *   - With the asm barrier present: barrier survives LTO (#APP #NO_APP in asm output);
 *     clang emits branchless SIMD XOR loop. No branch introduced.
 *   - Without the asm barrier, merged TU, clang -O2: compiler uses 'cmoveq'
 *     (conditional move instruction) — also constant-time on x86-64. No branch.
 *   - Without the asm barrier, clang -O3 single TU: fully unrolled byte XOR loop,
 *     still no branch.
 *   Conclusion: Clang 18 on x86-64 does NOT reproduce clangover for this pattern.
 *   The compiler is smart enough to emit cmov instead of jne.
 *
 * Injection (this file):
 *   Manual branch injection representing downstream consumers who rewrite cmov
 *   with a naive if-branch (the exact pattern clangover would produce on older
 *   compilers or non-cmov architectures like ARM Cortex-M):
 *
 *     if (b) memcpy(r, x, len);   // b=1: copy decoy key (timing: copy 32 bytes)
 *     // b=0: leave r unchanged   // b=0: keep real key  (timing: near-zero)
 *
 * Oracle design:
 *   Condition A: fail=0 always (branch not taken — no copy, predictor learns)
 *   Condition B: fail=1 always (branch taken — 32-byte copy, predictor learns)
 *   Signal: difference in work done (0 bytes vs 32 bytes per call).
 *   REPS=100 amplifies the small per-call signal above the timer noise floor.
 *
 * In-scope for paper: demonstrates the timing difference that would exist if a
 * compiler (or embedded platform without cmov) replaced the XOR-select with a
 * branch. This is not hypothetical: ARM Cortex-M compilers routinely produce
 * branches for this pattern when the code is copied without the asm barrier.
 *
 * Expected: mean_B > mean_A (Cond-B copies 32 bytes, Cond-A is a no-op).
 *           |t| >> 4, significant: true.
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

#define KYBER_SYMBYTES  32   /* shared secret / rejection key size */
#define REPS            100  /* calls per timing sample for signal amplification */
#define DEFAULT_WARMUP  1000
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
 * Patched cmov: explicit if-branch on fail bit.
 * Represents the "clangover" pattern — what a compiler without cmov support
 * (or a downstream consumer who rewrites this) would produce.
 * b=0: branch not taken, r unchanged (real shared secret kept)
 * b=1: branch taken, x copied into r (rejection: decoy key used)
 */
static void __attribute__((noinline))
patched_cmov(uint8_t *r, const uint8_t *x, size_t len, uint8_t b) {
    /* LEAK-1: branch on secret-derived fail bit — timing-variable */
    if (b)
        memcpy(r, x, len);
}

/*
 * Reference cmov: XOR-accumulate select with asm barrier (original design).
 * Constant-time on any compiler that respects the asm barrier.
 */
static void __attribute__((noinline, unused))
reference_cmov(uint8_t *r, const uint8_t *x, size_t len, uint8_t b) {
    __asm__("" : "+r"(b));
    b = -b;
    for (size_t i = 0; i < len; i++) r[i] ^= b & (r[i] ^ x[i]);
}

int main(int argc, char *argv[]) {
    const char *hyp_id = (argc > 1) ? argv[1] : "LEAK1-ORACLE";
    int runs            = (argc > 2) ? atoi(argv[2]) : DEFAULT_RUNS;

#ifdef __linux__
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(0, &mask);
    sched_setaffinity(0, sizeof(mask), &mask);
#endif

    /* Working buffers: r = shared secret slot, x = decoy (z in kem.c) */
    uint8_t r_A[KYBER_SYMBYTES], x_A[KYBER_SYMBYTES];
    uint8_t r_B[KYBER_SYMBYTES], x_B[KYBER_SYMBYTES];
    memset(r_A, 0xAA, KYBER_SYMBYTES);
    memset(x_A, 0xFF, KYBER_SYMBYTES);
    memset(r_B, 0xBB, KYBER_SYMBYTES);
    memset(x_B, 0xFF, KYBER_SYMBYTES);

    uint64_t *sa = malloc(runs * sizeof(uint64_t));
    uint64_t *sb = malloc(runs * sizeof(uint64_t));
    if (!sa || !sb) { perror("malloc"); return 1; }

    /* Warmup */
    volatile int sink = 0;
    uint8_t tmp[KYBER_SYMBYTES];
    for (int i = 0; i < DEFAULT_WARMUP; i++) {
        memcpy(tmp, r_A, KYBER_SYMBYTES);
        for (int r = 0; r < REPS; r++)
            patched_cmov(tmp, x_A, KYBER_SYMBYTES, 0); /* Cond-A: b=0, no copy */
        memcpy(tmp, r_B, KYBER_SYMBYTES);
        for (int r = 0; r < REPS; r++)
            patched_cmov(tmp, x_B, KYBER_SYMBYTES, 1); /* Cond-B: b=1, copy */
        sink += tmp[0];
    }

    /* Interleaved measurement: REPS calls per sample */
    for (int i = 0; i < runs; i++) {
        uint64_t t0;
        uint8_t buf[KYBER_SYMBYTES];

        memcpy(buf, r_A, KYBER_SYMBYTES);
        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            patched_cmov(buf, x_A, KYBER_SYMBYTES, 0);  /* fail=0: no copy */
        sa[i] = now_ns() - t0;   /* total for REPS calls; divide by REPS at display */
        sink += buf[0];

        memcpy(buf, r_B, KYBER_SYMBYTES);
        t0 = now_ns();
        for (int r = 0; r < REPS; r++)
            patched_cmov(buf, x_B, KYBER_SYMBYTES, 1);  /* fail=1: copy 32B */
        sb[i] = now_ns() - t0;   /* total for REPS calls; divide by REPS at display */
        sink += buf[0];
    }
    (void)sink;

    double ma, va, mb, vb;
    int na = trimmed_stats(sa, runs, &ma, &va);
    int nb = trimmed_stats(sb, runs, &mb, &vb);
    double t = welch_t(ma, va, na, mb, vb, nb);
    int sig = fabs(t) > 4.0;

    const char *note =
        "LEAK-1 cmov branch injection oracle (clangover class). "
        "Cond-A: patched_cmov(r,x,32,0) — branch not taken, r unchanged. "
        "Cond-B: patched_cmov(r,x,32,1) — branch taken, 32-byte memcpy. "
        "Clang18/x86-64 finding: barrier survives LTO; compiler emits cmoveq "
        "even without barrier — no natural clangover on this platform. "
        "Injection is manual (if-branch) representing ARM/embedded scenario. "
        "Signal amplification: REPS=100 calls per sample.";

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
