CC      = gcc
CFLAGS  = -O2 -Wall -Wextra
TARGET  = harness_oracle

.PHONY: all clean

all: $(TARGET)

$(TARGET): harness_oracle.c
	$(CC) $(CFLAGS) $^ -o $@ -lm

clean:
	rm -f $(TARGET)
