#!/usr/bin/env bash
# Run the 24h AFL++ baseline fuzz of Kyber decapsulation, then summarize.
set -euo pipefail

mkdir -p corpus findings

# Seed corpus: a zeroed 768-byte Kyber512 ciphertext.
python3 -c "import sys; sys.stdout.buffer.write(b'\x00'*768)" \
  > corpus/seed_kyber512.bin

FUZZ_DURATION=${FUZZ_DURATION:-86400}

timeout "$FUZZ_DURATION" afl-fuzz \
  -i corpus/ -o findings/ \
  -V "$FUZZ_DURATION" \
  ./kyber_fuzz || true

python3 summarize_afl.py findings/ "$FUZZ_DURATION"
