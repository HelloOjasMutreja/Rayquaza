#!/usr/bin/env bash
# run_a3.sh — build and run the LEAK-5 harness, save JSON to shared/feedback/
# Usage: ./run_a3.sh <hypothesis_id> [run_count]
# Example: ./run_a3.sh LEAK5-001 10000

set -euo pipefail

HYP_ID="${1:-LEAK5-001}"
RUNS="${2:-10000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
FEEDBACK_DIR="$REPO_ROOT/shared/feedback"
HARNESS="$SCRIPT_DIR/harness_leak5"

if [ ! -f "$SCRIPT_DIR/indcpa.c" ]; then
    echo "[run_a3.sh] Source files not found. Running setup.sh first..."
    bash "$SCRIPT_DIR/setup.sh"
fi

if [ ! -f "$HARNESS" ] || [ "$SCRIPT_DIR/harness_leak5.c" -nt "$HARNESS" ] || \
   [ "$SCRIPT_DIR/kem.c" -nt "$HARNESS" ]; then
    echo "[run_a3.sh] Building harness_leak5..."
    make -C "$SCRIPT_DIR" --no-print-directory
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="$FEEDBACK_DIR/timing_${HYP_ID}_${TIMESTAMP}.json"

echo "[run_a3.sh] Running LEAK-5 harness: $HYP_ID, $RUNS iterations..."
echo "[run_a3.sh] Condition A: valid ciphertext | Condition B: invalid ciphertext"
"$HARNESS" "$HYP_ID" "$RUNS" | tee "$OUTFILE"
echo ""
echo "[run_a3.sh] Saved → $OUTFILE"
