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
- [ ] Persist `findings/` out of the container (volume mount) for the 24h run.
- [ ] Capture `plot_data` for a real coverage-over-time curve (B4 analysis).

---

# PRIORITY-2: Real weakened-target baseline (Linux/WSL2)

`harness.c` (above) is the original **stub** wiring. The real, apples-to-apples
baseline lives in the files below. **These were written on the macOS/arm64 dev
box, which has no AFL++/Linux, so they have NOT been compiled here — build and
verify them on the WSL2/x86 box where Track A built liboqs and the reference.**

**Goal:** fuzz the SAME weakened reference Kyber that Track A patched, so the
control (AFL++, no LLM) is directly comparable to the LLM adversary loop's
rediscovery on LEAK-2/4/5.

## Files (real baseline)
| File | Purpose |
|------|---------|
| `harness_kyber.c` | AFL++ persistent-mode harness; real `crypto_kem_dec()` driven with the fuzz input as ciphertext (stdin fallback when not AFL-instrumented) |
| `build_weakened.sh` | Overlays Track A's patched file onto a full reference tree (`$KYBER_REF`) and builds with `afl-clang-fast -O0 -fsanitize=address -DKYBER_K=2` |
| `run_baseline_weakened.sh` | Seeds a 768B ciphertext, runs `afl-fuzz -V $FUZZ_DURATION` (24h default), summarizes |

## How to run (on WSL2)
```bash
# KYBER_REF = a full pqcrystals-kyber ref/ source tree (kem.c indcpa.c poly.c
# polyvec.c ntt.c reduce.c cbd.c verify.c fips202.c symmetric-shake.c randombytes.c)
export KYBER_REF=~/kyber/ref
cd track-b-engine/fuzzing
./build_weakened.sh leak5            # or leak2 | leak4 | clean
FUZZ_DURATION=86400 ./run_baseline_weakened.sh leak5
```

## Interpreting the comparison — important
AFL++ finds **crashes and new coverage, not timing leaks**. A non-constant-time
branch/`memcmp` is not a crash, so "did AFL find the leak" means: did
coverage-guided fuzzing **reach and exercise** the vulnerable path
(`poly_tomsg` rounding / `indcpa_dec` normalize / `crypto_kem_dec` memcmp), and
did ASan surface any memory-safety crash there? The LLM-vs-AFL claim is
**time-to-reach-vulnerable-path + crash count**, NOT "AFL detected a side
channel" (it cannot, by construction). State this explicitly in the paper.

## Open items
- [ ] Confirm with Track A that the A0 liboqs/reference build flags are still
      current (liboqs/reference was touched during LEAK-1/3 work) — see ISSUE B-005.
- [ ] Build & smoke-test `harness_kyber.c` on WSL2 (untested on macOS dev box).
- [ ] Run 24h per target (leak2/leak4/leak5 + clean), capture `plot_data`.
