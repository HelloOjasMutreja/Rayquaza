#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>

// Define the input classes
class class_A {
    uint8_t sk[KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES+i];
};

class class_B {
    uint8_t sk[KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES+i];
};

// Define the test function
void test() {
    // Declare arrays to store the timestamps for each class
    long double mean_A = 0;
    long double mean_B = 0;
    long double variance_A = 0;
    long double variance_B = 0;
    long double stderr_A = 0;
    long double stderr_B = 0;
    long double pooled_stderr = 0;
    long double t_statistic = 0;
    int significant = 0;

    // Loop over each class
    for (int i = 0; i < 2; i++) {
        // Initialize the arrays to store the timestamps
        long double timestamps_A[10000];
        long double timestamps_B[10000];

        // Run each class exactly 10000 times
        for (int j = 0; j < 10000; j++) {
            // Craft inputs to trigger the hypothesis
            if (i == 0) {
                class_A input;
                input.sk[KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES+i] = j % 256;
                crypto_kem_dec(NULL, NULL, (const uint8_t *)&input);
            } else {
                class_B input;
                input.sk[KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES+i] = j % 256;
                crypto_kem_dec(NULL, NULL, (const uint8_t *)&input);
            }

            // Measure the timing of each run
            struct timespec start, end;
            clock_gettime(CLOCK_MONOTONIC, &start);
            crypto_kem_dec(NULL, NULL, (const uint8_t *)&input);
            clock_gettime(CLOCK_MONOTONIC, &end);

            // Store the timing in the appropriate array
            if (i == 0) {
                timestamps_A[j] = (long double)(end.tv_sec - start.tv_sec) + (long double)(end.tv_nsec - start.tv_nsec) / 1000000000;
            } else {
                timestamps_B[j] = (long double)(end.tv_sec - start.tv_sec) + (long double)(end.tv_nsec - start.tv_nsec) / 1000000000;
            }
        }

        // Compute the mean and variance for each class
        mean_A += timestamps_A[0];
        mean_B += timestamps_B[0];
        for (int j = 1; j < 10000; j++) {
            mean_A += timestamps_A[j];
            mean_B += timestamps_B[j];
        }
        mean_A /= 10000;
        mean_B /= 10000;
        for (int j = 0; j < 10000; j++) {
            variance_A += pow((timestamps_A[j] - mean_A), 2);
            variance_B += pow((timestamps_B[j] - mean_B), 2);
        }
        variance_A /= 10000;
        variance_B /= 10000;

        // Compute the standard error for each class
        stderr_A = sqrt(variance_A);
        stderr_B = sqrt(variance_B);

        // Compute the pooled standard error
        pooled_stderr = sqrt((stderr_A*stderr_A + stderr_B*stderr_B) / 2);

        // Compute the t-statistic
        t_statistic = (mean_A - mean_B) / pooled_stderr;

        // Determine if the difference is statistically significant
        if (fabs(t_statistic) > 2.0) {
            significant = 1;
        } else {
            significant = 0;
        }
    }

    // Print the results in JSON format
    printf("{\"hypothesis_id\":\"H001\",\"mean_A\":%.2Lf,\"mean_B\":%.2Lf,\"variance_A\":%.2Lf,\"variance_B\":%.2Lf,\"t_statistic\":%.2Lf,\"significant\":%d}", mean_A, mean_B, variance_A, variance_B, t_statistic, significant);
}

int main() {
    test();
    return 0;
}