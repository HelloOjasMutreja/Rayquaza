CC     = gcc
CFLAGS = -O2 -Wall -Wextra \
         -DKYBER_K=2 \
         -I. \
         -I$(HOME)/liboqs-install/include
LDFLAGS = -L$(HOME)/liboqs-install/lib \
          -loqs -lpthread -lm \
          -Wl,-rpath,$(HOME)/liboqs-install/lib

KYBER_SRCS = kem.c indcpa.c poly.c polyvec.c ntt.c reduce.c \
             verify.c cbd.c symmetric-shake.c fips202.c randombytes.c

TARGET  = harness_leak5
TARGET2 = harness_oracle

.PHONY: all clean setup

all: $(TARGET) $(TARGET2)

$(TARGET): harness_leak5.c $(KYBER_SRCS)
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)

$(TARGET2): harness_oracle.c randombytes.c
	$(CC) $(CFLAGS) $^ -o $@ -lm

setup:
	bash setup.sh

clean:
	rm -f $(TARGET)
