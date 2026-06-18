#!/usr/bin/env bash
# build_weakened.sh — build the AFL++ harness against a WEAKENED reference Kyber512.
#
# Apples-to-apples with the LLM adversary loop: the fuzz target is the SAME
# patched reference source Track A injected the leak into. Run on Linux (WSL2)
# with AFL++ installed. NOT runnable on the macOS/arm64 dev box.
#
# Usage:
#   KYBER_REF=/path/to/pqcrystals-kyber/ref ./build_weakened.sh <leak>
#     <leak> = leak1 | leak2 | leak3 | leak4 | leak5 | clean
#
#   KYBER_REF must point to a full Kyber REFERENCE source tree (ref/) containing
#   kem.c indcpa.c poly.c polyvec.c ntt.c reduce.c cbd.c verify.c fips202.c
#   symmetric-shake.c randombytes.c + headers, buildable for KYBER_K=2.
#
# What it does:
#   - copies the reference tree to ./build/<leak>/
#   - overlays Track A's patched file for the chosen leak (from track-a-target)
#   - compiles everything + harness_kyber.c with afl-clang-fast (+ASan)
#   - emits ./build/<leak>/kyber_fuzz
set -euo pipefail

LEAK="${1:-leak5}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"          # repo root
HERE="$ROOT/track-b-engine/fuzzing"
TARGETS="$ROOT/track-a-target/targets"

: "${KYBER_REF:?Set KYBER_REF to a full pqcrystals-kyber reference (ref/) source tree}"
command -v afl-clang-fast >/dev/null || { echo "afl-clang-fast not found — install AFL++"; exit 1; }

OUT="$HERE/build/$LEAK"
rm -rf "$OUT"; mkdir -p "$OUT"
cp "$KYBER_REF"/*.c "$KYBER_REF"/*.h "$OUT"/ 2>/dev/null || true

# Overlay Track A's patched file(s) for the chosen leak (skip for clean baseline).
case "$LEAK" in
  leak1) cp "$TARGETS/kyber512_leak1/verify.c" "$OUT/verify.c" ;;
  leak2) cp "$TARGETS/kyber512_leak2/poly.c"   "$OUT/poly.c" ;;
  leak3) cp "$TARGETS/kyber512_leak3/ntt.c"    "$OUT/ntt.c" ;;
  leak4) cp "$TARGETS/kyber512_leak4/indcpa.c" "$OUT/indcpa.c" ;;
  leak5) cp "$TARGETS/kyber512_leak5/kem.c"    "$OUT/kem.c" ;;
  clean) echo "clean baseline — no patch overlaid" ;;
  *) echo "unknown leak '$LEAK' (use leak1|leak2|leak3|leak4|leak5|clean)"; exit 1 ;;
esac

cd "$OUT"
# Kyber512 = KYBER_K 2. -O0 keeps injected branches from being turned into cmov
# (matches how Track A measured the leaks); ASan catches memory-safety crashes.
afl-clang-fast -O0 -g -fsanitize=address \
  -DKYBER_K=2 -I. \
  -o kyber_fuzz \
  *.c "$HERE/harness_kyber.c" 2>&1 | tail -20 || {
    echo "BUILD FAILED — check that KYBER_REF has the full ref/ source set."; exit 1; }

echo "Built $OUT/kyber_fuzz  (target: $LEAK)"
echo "Next: $HERE/run_baseline_weakened.sh $LEAK"
