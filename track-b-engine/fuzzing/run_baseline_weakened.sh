#!/usr/bin/env bash
# run_baseline_weakened.sh — 24h AFL++ baseline against a weakened Kyber target.
# Run on Linux (WSL2) after build_weakened.sh. Usage: run_baseline_weakened.sh <leak>
set -euo pipefail

LEAK="${1:-leak5}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/track-b-engine/fuzzing"
OUT="$HERE/build/$LEAK"
BIN="$OUT/kyber_fuzz"

[ -x "$BIN" ] || { echo "missing $BIN — run build_weakened.sh $LEAK first"; exit 1; }

# AFL++ findings go to WSL ext4 home (not /mnt/d NTFS) to avoid severe I/O slowdown.
# After the run, summarize_afl.py copies the summary JSON back to shared/findings/.
FUZZ_HOME="${HOME}/fuzz"
CORPUS="$FUZZ_HOME/$LEAK/corpus"
FINDINGS="$FUZZ_HOME/$LEAK/findings"
mkdir -p "$CORPUS" "$FINDINGS"

# Seed: a zeroed 768-byte Kyber512 ciphertext (valid length, invalid content —
# exercises the FO-failure / rejection path that reaches the planted leaks).
python3 -c "import sys; sys.stdout.buffer.write(b'\x00'*768)" > "$CORPUS/seed_ct.bin"

FUZZ_DURATION="${FUZZ_DURATION:-86400}"   # 24h default
export AFL_NO_UI=1

# -V <secs>: stop after the time budget. ASAN_OPTIONS keeps AFL happy with ASan.
ASAN_OPTIONS=abort_on_error=1:symbolize=0 \
timeout "$FUZZ_DURATION" afl-fuzz \
  -i "$CORPUS" -o "$FINDINGS" \
  -V "$FUZZ_DURATION" \
  -- "$BIN" || true

python3 "$HERE/summarize_afl.py" "$FINDINGS" "$FUZZ_DURATION"
echo "Done ($LEAK). Compare unique_paths / time-to-first-path / crashes against the"
echo "LLM rediscovery for this target (shared/findings/loop_state_kyber512_${LEAK}.json)."
