CC     = gcc
# -O0: ensure the conditional branch in normalize_patched is not auto-vectorized
# or optimized away. At -O2, GCC may vectorize the loop with SIMD predication
# (constant-time), masking the timing difference.
CFLAGS = -O0 -fno-inline -Wall -Wextra

TARGET = harness_oracle

.PHONY: all clean

all: $(TARGET)

$(TARGET): harness_oracle.c
	$(CC) $(CFLAGS) $^ -o $@ -lm

clean:
	rm -f $(TARGET)
