#!/usr/bin/env bash
# build_oracles.sh — build the harness_oracle binaries for the Kyber targets
# that the Phase B sandbox can run. Run in WSL: bash build_oracles.sh
set -u
ROOT=/mnt/d/Code/Rayquaza/track-a-target/targets
for t in leak2 leak4 leak5; do
    d="$ROOT/kyber512_$t"
    echo "=== kyber512_$t ==="
    if [ ! -d "$d" ]; then echo "  missing dir"; continue; fi
    ( cd "$d" && make >/tmp/oracle_build_$t.log 2>&1 )
    if [ -x "$d/harness_oracle" ]; then
        echo "  built: harness_oracle"
    else
        echo "  BUILD FAILED — log:"; tail -5 "/tmp/oracle_build_$t.log"
    fi
done