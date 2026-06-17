#!/usr/bin/env bash
# start_fuzz_all.sh — launch 24h AFL++ baseline fuzz runs for all four targets.
# Run from WSL2: bash start_fuzz_all.sh
# Requires: build_weakened.sh already run for all four targets.

FUZZ_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/tmp/fuzz_logs"
mkdir -p "$LOG_DIR"

export AFL_NO_UI=1
export AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
export FUZZ_DURATION=86400

for TARGET in leak2 leak4 leak5 clean; do
    setsid bash -c "cd '$FUZZ_DIR' && ./run_baseline_weakened.sh '$TARGET' >> '$LOG_DIR/fuzz_$TARGET.log' 2>&1" &
    PID=$!
    echo "Launched fuzz_$TARGET — PID=$PID"
    sleep 1
done

echo "All 4 fuzz runs launched. PIDs logged above."
echo "Tail logs with: tail -f /tmp/fuzz_logs/fuzz_<target>.log"
echo "Check running: pgrep -a afl-fuzz"
