#include <string.h>

// Pattern 1: secret-dependent branch
int check_key(unsigned char *key) {
    if (key[0] == 0) return 1;
    return 0;
}

// Pattern 2: variable-time memory access
int lookup(unsigned char *secret_key, int *table) {
    return table[secret_key[0]];
}

// Pattern 3: non-constant-time comparison
int compare(unsigned char *a, unsigned char *b) {
    if (memcmp(a, b, 16) == 0) return 1;
    return 0;
}
