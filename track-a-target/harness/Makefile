CC      = gcc
CFLAGS  = -O2 -Wall -Wextra \
           -I$(HOME)/liboqs-install/include
LDFLAGS = -L$(HOME)/liboqs-install/lib \
           -loqs -lssl -lcrypto -lpthread -lm \
           -Wl,-rpath,$(HOME)/liboqs-install/lib

TARGET  = harness

.PHONY: all clean

all: $(TARGET)

$(TARGET): harness.c
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

clean:
	rm -f $(TARGET)
