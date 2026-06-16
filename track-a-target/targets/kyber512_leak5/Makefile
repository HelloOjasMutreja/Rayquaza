CC     = gcc
CFLAGS = -O2 -Wall -Wextra \
         -I. \
         -I$(HOME)/liboqs-install/include \
         -I$(HOME)/liboqs/src/common/pqclean_shims
LDFLAGS = -L$(HOME)/liboqs-install/lib \
          -loqs -lssl -lcrypto -lpthread -lm \
          -Wl,-rpath,$(HOME)/liboqs-install/lib

KYBER_SRCS = kem.c indcpa.c poly.c polyvec.c ntt.c reduce.c \
             verify.c cbd.c symmetric-shake.c

TARGET = harness_leak5

.PHONY: all clean setup

all: $(TARGET)

$(TARGET): harness_leak5.c $(KYBER_SRCS)
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)

setup:
	bash setup.sh

clean:
	rm -f $(TARGET)
