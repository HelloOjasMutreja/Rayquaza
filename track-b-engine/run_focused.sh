#!/usr/bin/env bash
# run_focused.sh — drive one focused target end-to-end through the live loop.
# Starts main.py (unbuffered), detects the hypothesis id it waits on, runs the
# matching Track A harness_oracle to drop real timing into shared/feedback/,
# waits for completion, and snapshots loop_state.json per target.
#
# Usage: run_focused.sh <focused_target.c> <oracle_target_dir>
#   e.g. run_focused.sh track-b-engine/ingestion/test_targets/kyber512_leak2_focused.c kyber512_leak2
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
FOCUSED="$1"
ORACLE_DIR="$2"
OUT=$(mktemp)

python3 -u track-b-engine/main.py --target "$FOCUSED" --cycles 3 > "$OUT" 2>&1 &
LPID=$!

# Learn the hypothesis id from the engine's own feedback-file glob pattern
# (timing_H001_*.json), which is more stable than matching free-text wording.
HYP=""
for _ in $(seq 1 120); do
  HYP=$(grep -oE "timing_[A-Za-z0-9]+_\*\.json" "$OUT" 2>/dev/null | head -1 | sed -E 's/^timing_//; s/_\*\.json$//')
  [ -n "$HYP" ] && break
  kill -0 $LPID 2>/dev/null || break
  sleep 5
done

if [ -n "$HYP" ]; then
  echo ">>> detected hypothesis id: $HYP — running oracle from $ORACLE_DIR"
  ( cd "track-a-target/targets/$ORACLE_DIR" && ./harness_oracle "$HYP" 50000 >/dev/null 2>&1 )
else
  echo ">>> WARNING: no hypothesis id detected (loop produced no hypotheses?)"
fi

wait $LPID
echo "================ LOOP OUTPUT ($ORACLE_DIR) ================"
cat "$OUT"
if [ -f shared/findings/loop_state.json ]; then
  cp shared/findings/loop_state.json "shared/findings/loop_state_${ORACLE_DIR}.json"
  echo ">>> snapshot: shared/findings/loop_state_${ORACLE_DIR}.json"
fi
rm -f "$OUT"
