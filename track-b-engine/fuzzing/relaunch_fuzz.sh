#!/usr/bin/env bash
# relaunch_fuzz.sh — relaunch all 4 AFL++ 24h baseline fuzz runs.
# Run from WSL2: bash relaunch_fuzz.sh
set -euo pipefail

export AFL_NO_UI=1
export AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
export AFL_AUTORESUME=1
export FUZZ_DURATION=86400

FUZZ_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR=/tmp/fuzz_logs
mkdir -p "$LOG_DIR"

for TARGET in leak2 leak4 leak5 clean; do
    LOG="$LOG_DIR/fuzz_${TARGET}.log"
    setsid bash -c "cd '$FUZZ_DIR' && FUZZ_DURATION=86400 AFL_NO_UI=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 ./run_baseline_weakened.sh '$TARGET' >> '$LOG' 2>&1" &
    echo "Launched $TARGET (PID=$!)"
    sleep 1
done

echo ""
echo "All 4 relaunched. Waiting 5s to confirm..."
sleep 5
COUNT=$(pgrep -c afl-fuzz 2>/dev/null || echo 0)
echo "afl-fuzz processes running: $COUNT"
echo "Tail logs: tail -f /tmp/fuzz_logs/fuzz_<target>.log"
echo "Check status: pgrep -a afl-fuzz"
