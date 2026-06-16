#!/usr/bin/env bash
# run.sh — build harness and save output to shared/feedback/
# Usage: ./run.sh <hypothesis_id> [run_count]
# Example: ./run.sh H001 10000

set -euo pipefail

HYP_ID="${1:-H000}"
RUNS="${2:-10000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FEEDBACK_DIR="$REPO_ROOT/shared/feedback"
HARNESS="$SCRIPT_DIR/harness"

# Build if needed
if [ ! -f "$HARNESS" ] || [ "$SCRIPT_DIR/harness.c" -nt "$HARNESS" ]; then
    echo "[run.sh] Building harness..."
    make -C "$SCRIPT_DIR" --no-print-directory
fi

# Output filename: timing_<hyp_id>_<timestamp>.json
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="$FEEDBACK_DIR/timing_${HYP_ID}_${TIMESTAMP}.json"

echo "[run.sh] Running: $HYP_ID, $RUNS iterations..."
"$HARNESS" "$HYP_ID" "$RUNS" | tee "$OUTFILE"
echo ""
echo "[run.sh] Saved → $OUTFILE"
