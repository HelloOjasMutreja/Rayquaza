#!/usr/bin/env bash
# setup.sh — copies unmodified ref source files from the liboqs clone.
# Run once before building. Requires liboqs cloned at ~/liboqs.
# Our patched kem.c is already in this directory — do NOT overwrite it.

set -euo pipefail

REF="$HOME/liboqs/src/kem/kyber/pqcrystals-kyber_kyber512_ref"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$REF" ]; then
    echo "ERROR: liboqs not found at $REF"
    echo "Clone it with: git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git ~/liboqs"
    exit 1
fi

for f in \
    indcpa.c indcpa.h \
    poly.c poly.h \
    polyvec.c polyvec.h \
    ntt.c ntt.h \
    reduce.c reduce.h \
    verify.c verify.h \
    cbd.c cbd.h \
    symmetric-shake.c symmetric.h \
    params.h api.h kem.h; do
    cp "$REF/$f" "$DIR/"
    echo "  copied $f"
done

echo ""
echo "Setup complete. Patched kem.c is already in place — do not overwrite it."
echo "Run 'make' to build."
