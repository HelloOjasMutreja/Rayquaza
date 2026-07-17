# Reproducing the ML-DSA-44 result manually

`mldsa44_leak1` is intentionally not part of the automated Docker wizard
(`docker compose run --rm runner`). Two reasons, both found by reading the
actual experiment history rather than assuming the target fits the same
pattern as the five Kyber512 leaks:

1. **No generic focused-target file.** Each Kyber512 leak has a matching
   `track-b-engine/ingestion/test_targets/kyber512_leakN_focused.c` file the
   wizard points the engine at directly. ML-DSA-44 instead used a
   purpose-built synthetic target,
   `track-b-engine/ingestion/test_targets/mldsa44_synthetic.c`, created
   during the original experiment (see `EXPERIMENT_LOG.md`, 2026-06-16
   entry). There is no drop-in equivalent to automate the same way.

2. **The timing signal is architecture-sensitive.** Per
   `EXPERIMENT_LOG.md`'s 2026-06-17 REPS-amplification check: the planted
   32-byte `memcmp` leak is significant on WSL2/x86 (t=116.97) but is
   **not** significant on macOS/arm64 at any REPS level tested (t=0.91,
   -0.81, 0.75 across REPS=100/1000/5000, sign unstable). This is a real,
   already-published finding about compiler codegen differences, not a bug.
   Running this target automatically on an arbitrary user's machine (most
   likely Apple Silicon, given how common it is) would silently produce a
   non-significant result that looks exactly like a broken setup.

## Manual steps (requires an x86 host, e.g. WSL2 on Windows or a Linux x86
machine; will not show a significant t-stat on Apple Silicon)

```bash
# From the repo root, inside the runner container or an x86 Linux/WSL2 shell
# with liboqs already built (see Dockerfile for the exact build steps):
track-b-engine/run_focused.sh \
  track-b-engine/ingestion/test_targets/mldsa44_synthetic.c \
  mldsa44_leak1
```

This follows the same `run_focused.sh` orchestration the automated wizard
uses for the Kyber512 targets: it starts the engine, detects the hypothesis
ID it's waiting on, runs `track-a-target/targets/mldsa44_leak1/harness_oracle`
against it, and snapshots the result to
`shared/findings/loop_state_mldsa44_leak1.json`.

If you want the REPS-amplified oracle variant used in the 2026-06-17 check
instead of the standard one, see
`track-b-engine/oracle_reps_check/harness_oracle_reps.c`.
