#define _GNU_SOURCE
#include <sys/random.h>
#include "randombytes.h"

void randombytes(unsigned char *x, size_t xlen) {
    size_t done = 0;
    while (done < xlen) {
        ssize_t r = getrandom(x + done, xlen - done, 0);
        if (r > 0) done += (size_t)r;
    }
}
