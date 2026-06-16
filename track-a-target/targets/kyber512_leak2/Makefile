CC     = gcc
# -O0: prevent compiler from optimizing if-branch to conditional move (cmov).
# The LEAK-2 vulnerability requires a real branch instruction — at -O2 GCC
# typically emits 'setge'/'cmov' which is constant-time, eliminating the leak.
CFLAGS = -O0 -fno-inline -Wall -Wextra

TARGET = harness_oracle

.PHONY: all clean

all: $(TARGET)

$(TARGET): harness_oracle.c
	$(CC) $(CFLAGS) $^ -o $@ -lm

clean:
	rm -f $(TARGET)
