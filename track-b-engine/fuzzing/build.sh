#!/usr/bin/env bash
# Build the AFL++ Kyber fuzz harness.
set -euo pipefail

afl-clang-fast -fsanitize=address -O0 -g \
  -o kyber_fuzz harness.c

echo "Build complete. Run: afl-fuzz -i corpus/ -o findings/ ./kyber_fuzz"
