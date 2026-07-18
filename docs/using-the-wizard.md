# Using the Docker reproducibility wizard

This is a full walkthrough of `docker compose run --rm runner`, the one-command
way to reproduce Rayquaza's core experiment: an LLM adversary engine finding
planted timing leaks in Kyber512 targets, with a real, oracle-measured timing
signal as ground truth, not a model's own claim.

For the two-line version, see the [README](../README.md#reproducing-the-experiment).
For why `mldsa44_leak1` isn't part of this flow and how to run it by hand, see
[reproducing-mldsa.md](reproducing-mldsa.md).

## Prerequisites

Docker only (Docker Desktop on Mac/Windows, Docker Engine on Linux). Nothing
else gets installed on your machine. The LLM weights are fetched at runtime
into a Docker-managed volume, never baked into the image and never left on
your host filesystem outside that volume.

If you're on Windows, WSL2 backs Docker Desktop, so a working WSL2 install is
a transitive prerequisite (Docker Desktop will offer to set this up if it's
missing).

## Quickstart

```bash
git clone <this repo's URL>
cd Rayquaza
docker compose run --rm runner
```

First run builds the `runner` image (toolchain, a freshly-cloned liboqs, and
the compiled target binaries), which takes a few minutes. Every run after
that skips straight to the wizard.

## Walking through the wizard

### 1. Build and service checks

The wizard confirms the six target binaries actually got built (if this
fails, the image build itself failed silently earlier; rebuild with
`docker compose build --no-cache` and read the real error) and waits for the
`ollama` service to come up. Both are automatic, no input needed.

### 2. Hardware detection and model tier

The wizard reads how much RAM and disk are actually available to the
container (this reflects any Docker Desktop resource limits you've set, not
necessarily your machine's full specs) and recommends one of two model
pairs:

- **Original** (`codellama:7b` + `qwen3:8b`): the pair the published results
  are based on. Recommended when you have real headroom (16GB+ RAM, 12GB+
  free disk).
- **Lightweight** (`qwen2.5:3b` + `phi3:mini`): a smaller substitute for
  constrained machines. The wizard is upfront that results may differ from
  the original paper with this pair; the mechanics are identical, but a
  smaller model can miss subtler leaks that a larger one would catch.

You can accept the recommendation or override it in either direction. If the
tier you pick doesn't actually fit on disk once you confirm, the wizard
re-checks and offers to fall back to the lightweight tier rather than
starting a download that can't finish.

Whichever models aren't already cached get pulled here, with a live progress
bar per model. Models already present in the `ollama-data` volume (from a
previous run, or because you re-ran the same tier) resolve almost instantly.

### 3. Choosing how much to run

Two options:

- **All 5** — runs `kyber512_leak1` through `kyber512_leak5` back to back,
  no further prompts, straight through to the final summary. Expect
  somewhere between 15 minutes and well over an hour depending on your
  machine and which model tier you picked.
- **Just one to start** — runs `kyber512_leak1` only, then asks
  `Continue to kyber512_leak2? [Y/n]` before moving to the next target. Say
  no at any point and the wizard jumps straight to the summary for
  whatever you've run so far. This is the faster way to see a real result
  before committing to the full run.

`mldsa44_leak1` is deliberately not offered here; see
[reproducing-mldsa.md](reproducing-mldsa.md).

### 4. Watching a target run

Each target gets its own section, headed by a divider showing which target
and how far through the batch you are (`target 2/5`). While it's running,
a spinner tracks which pipeline stage is active, colored to match:

| Stage | Color | What's happening |
|---|---|---|
| INGEST | blue | The code-analysis model reads the target source for secret-dependent branches and unsafe comparisons, and proposes a hypothesis. |
| ORACLE | green | A deterministic C program runs 50,000 timed executions to measure whether the hypothesis actually produces a timing difference. This is the ground truth: not the LLM's opinion, a real measurement. |
| REFINE | orange | The reasoning model reads the oracle's result and judges whether the hypothesis is confirmed, and writes an exploitation note if so. |

A dim, muted line under the spinner describes what's happening in more
detail, mainly so there's something to read during the oracle's 30-second
polling interval, when nothing else is printing.

Recognized output lines are colored as they scroll by: a `PROMOTED` verdict
in bold green, `DEMOTED`/`INVALIDATED` in red, warnings in bold red.

### 5. The summary

After the last target you ran (whether that's 1, 3, or all 5), a table
covers everything from that session:

| Target | Hypothesis | Verdict | t-stat |
|---|---|---|---|

followed by a short legend explaining what Verdict and t-stat actually mean
(worth reading once; t-stat in particular doesn't have a "higher/lower is
better" direction, only magnitude matters).

Full JSON results are written to `shared/feedback/` and
`shared/findings/loop_state_<target>.json` on your own machine (bind-mounted,
so they survive after the container exits with `--rm`).

## Re-running

Just run `docker compose run --rm runner` again. The image doesn't rebuild
(nothing about the toolchain/binaries changed), and any model you've already
pulled resolves near-instantly from the `ollama-data` volume instead of
re-downloading. You'll go straight from the build/service checks to picking
a tier and targets again.

To force a clean image rebuild (e.g. after pulling code changes to
`bootstrap/`, the Dockerfile, or the target sources): `docker compose build
--no-cache`.

## GPU passthrough

- **NVIDIA** (Linux, or Windows with WSL2 GPU support): install
  [nvidia-container-toolkit](https://github.com/NVIDIA/nvidia-container-toolkit),
  copy `docker-compose.override.yml.example` to `docker-compose.override.yml`,
  then run as normal.
- **Apple Silicon**: Docker has no Metal passthrough, so `ollama` runs
  CPU-only inside the container regardless of what the Mac itself could do.
  The wizard prints a one-time note about this. A native Ollama install
  outside Docker (pointed at with `OLLAMA_HOST`) would be faster on these
  machines, at the cost of not being fully containerized.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Missing built targets" at startup | The image build failed silently. Run `docker compose build --no-cache` and read the actual compiler error. |
| "Waiting for Ollama service... unreachable" | Check `docker compose logs ollama`. Often a slow first start; the wizard already retries for 90s before giving up. |
| Disk-space warning before a model pull | Free up space, or accept the lightweight-tier fallback the wizard offers. |
| A target finishes with `NO RESULT` in the summary | The engine subprocess for that target exited abnormally; scroll back in the terminal output for the actual error, since the wizard continues to remaining targets rather than aborting the whole batch. |
| Docker itself won't start / crashes with a socket error | Usually resolved by a full reboot if Docker's own process state got corrupted (e.g. after an earlier crash mid-download). Not specific to this project. |

## What's out of scope here

This wizard covers the core engine only: the five Kyber512 targets, run
through the closed-loop adversary engine. It does not include the Phase B
multi-LLM comparison sandbox or the pywebview live visualizer, both of which
live elsewhere in this repo and aren't part of the Docker path.
