#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>

// Define the input classes
class_A = {
    c: 0x1234567890abcdef,
    c2: 0x1234567890abcdee
};
class_B = {
    c: 0x1234567890abcdef,
    c2: 0x1234567890abcdf0
};

// Define the function signature to test
int mld_sign_verify_internal(const uint8_t *sig, size_t siglen, const uint8_t *m, size_t mlen, const uint8_t *ctx, size_t ctxlen, const uint8_t *pk) {
    // Stub function to test
    return 0;
}

// Measurement loop
for (i = 0; i < 10000; i++) {
    // Run class A
    start = clock_gettime(CLOCK_MONOTONIC);
    mld_sign_verify_internal(class_A.sig, class_A.siglen, class_A.m, class_A.mlen, class_A.ctx, class_A.ctxlen, class_A.pk);
    end = clock_gettime(CLOCK_MONOTONIC);
    delta[i] = (end - start) * 1000000000; // Convert to nanoseconds

    // Run class B
    start = clock_gettime(CLOCK_MONOTONIC);
    mld_sign_verify_internal(class_B.sig, class_B.siglen, class_B.m, class_B.mlen, class_B.ctx, class_B.ctxlen, class_B.pk);
    end = clock_gettime(CLOCK_MONOTONIC);
    delta[i + 1] = (end - start) * 1000000000; // Convert to nanoseconds
}

// Compute statistics
mean_A = 0;
for (i = 0; i < 10000; i++) {
    mean_A += delta[i];
}
mean_A /= 10000;

mean_B = 0;
for (i = 10000; i < 20000; i++) {
    mean_B += delta[i];
}
mean_B /= 10000;

variance_A = 0;
for (i = 0; i < 10000; i++) {
    variance_A += pow((delta[i] - mean_A), 2);
}
variance_A /= 9999;

variance_B = 0;
for (i = 10000; i < 20000; i++) {
    variance_B += pow((delta[i] - mean_B), 2);
}
variance_B /= 9999;

stderr_A = sqrt(variance_A / 10000);
stderr_B = sqrt(variance_B / 10000);

pooled_stderr = sqrt(stderr_A*stderr_A + stderr_B*stderr_B) / 2;

t_statistic = (mean_A - mean_B) / pooled_stderr;

significant = 1;
if (fabs(t_statistic) > 2.0) {
    significant = true;
} else {
    significant = false;
}

// Print output
printf("{\"hypothesis_id\":\"H006\",\"mean_A\":%.1f,\"mean_B\":%.1f,\"variance_A\":%.1f,\"variance_B\":%.1f,\"t_statistic\":%.1f,\"significant\":%s}", mean_A, mean_B, variance_A, variance_B, t_statistic, significant ? "true" : "false");