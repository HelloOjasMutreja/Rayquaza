# Track B — AFL++ Fuzzing Baseline (Phase B2)

**What:** A 24-hour AFL++ coverage-guided fuzz of Kyber decapsulation
(`OQS_KEM_decaps`), run inside a reproducible Ubuntu 22.04 container.

**Why:** This establishes the **control baseline** for the research question —
how many unique code paths and crashes does *classical* coverage-guided fuzzing
find in a fixed time budget, *without* any LLM guidance? The Track B LLM
adversary engine's findings (timing hypotheses confirmed, paths reached) are
measured against this baseline to test whether LLM augmentation helps an
attacker find weaknesses faster.

**Current status:** The harness links against a **stub** `OQS_KEM_decaps` that
returns 0. This exercises the full fuzzing pipeline (build → seed → fuzz →
summarize) end-to-end. The stub is replaced with real liboqs once it is built
into the image. liboqs build flags from Track A are already delivered — see
`tracking/SYNC.md` (A0). Link with `-loqs -lssl -lcrypto -lpthread` against
`~/liboqs-install`.

## Files
| File | Purpose |
|------|---------|
| `Dockerfile` | Ubuntu 22.04 + afl++ toolchain; builds harness at image-build time |
| `harness.c` | AFL++ `LLVMFuzzerTestOneInput` harness; feeds input as ciphertext |
| `build.sh` | `afl-clang-fast` build with ASan |
| `run_baseline.sh` | Seeds corpus, runs `afl-fuzz` for `$FUZZ_DURATION`, summarizes |
| `summarize_afl.py` | Parses AFL++ output → `shared/findings/afl_baseline_<date>.json` |

## How to run
```bash
cd track-b-engine/fuzzing
docker build -t kyber-fuzz .
docker run kyber-fuzz
```
To run a shorter smoke test, override the duration (seconds):
```bash
docker run -e FUZZ_DURATION=60 kyber-fuzz
```

## Output
`shared/findings/afl_baseline_<date>.json` with:
`total_execs`, `unique_crashes`, `unique_paths`, `duration_seconds`,
`start_time`, `end_time`, `coverage_estimate`.

## TODO
- [ ] Replace stub `OQS_KEM_decaps` with real liboqs build inside the image.
- [ ] Persist `findings/` out of the container (volume mount) for the 24h run.
- [ ] Capture `plot_data` for a real coverage-over-time curve (B4 analysis).
