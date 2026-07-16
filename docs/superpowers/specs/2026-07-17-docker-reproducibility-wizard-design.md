# Docker reproducibility wizard: design spec

Status: approved via conversation (design walked through interactively, user
approved the CLI mockup and said "build it"). Written up here per the
brainstorming skill's process even though the interactive spec-review gate is
being skipped for this round: the user is unavailable overnight and gave
explicit standing approval to proceed straight to implementation.

## Goal

Let a stranger clone this repo, run one command, and reproduce the core
Rayquaza experiment (the closed-loop LLM adversary engine finding planted
timing leaks in Kyber512/ML-DSA-44 targets) without manually installing gcc,
liboqs, Ollama, or hand-picking which LLM their machine can handle.

Scope for this round: the core engine only (`track-a-target/`,
`track-b-engine/`, `shared/`). Not the Phase B multi-LLM sandbox, not the
pywebview visualizer. This stays inside the private repo; it is not the
curated public release described in the public/internal separation memory
(that is a separate, later effort).

## Architecture

Two Docker Compose services:

- **`ollama`**: the official `ollama/ollama` image. A named volume
  (`ollama-data`) persists pulled models across container recreation. Ships
  with zero models baked in; everything gets pulled at runtime.
- **`runner`**: built from a repo-root `Dockerfile`. Bundles the build
  toolchain (gcc, make, cmake, git, libssl-dev), clones and builds liboqs,
  builds the six target `harness_oracle` binaries, and installs the Python
  dependencies the engine needs. All of this is small (low hundreds of MB)
  and deterministic, so it is baked into the image at build time rather than
  fetched at runtime, unlike the LLM weights.

The two services share a Docker-internal network; the runner reaches Ollama
at `http://ollama:11434` via Compose service discovery. No host networking
configuration is required from the user.

Single entry point: `docker compose run --rm runner`. This is the container's
default command, which runs the wizard (`bootstrap.py`). `--rm` means the
container is deleted after the run, so anything that must survive (results)
is bind-mounted, not written to the container's own filesystem.

## liboqs version pinning

The repo does not record which liboqs commit the original experiment was
built against (checked: no version string anywhere in `EXPERIMENT_LOG.md` or
`track-a-target/TRACK_A_PLAN.md`, and the existing per-target `setup.sh`
clones with no pin). Rather than guess a tag that may not exist, the
Dockerfile clones liboqs's default branch at build time, then a build step
resolves and writes the exact commit SHA to `/build-info/liboqs-commit.txt`
inside the image. The wizard prints this at startup and includes it in the
results summary, so every run self-documents exactly which liboqs revision
it used. Anyone who needs byte-identical rebuilds later can pin the
Dockerfile to that recorded SHA explicitly. This is called out here as an
assumption, not a decision made silently.

## The wizard (`bootstrap.py`)

Built with `rich` for interactive/pretty terminal output (panels, tables,
progress bars, prompts). Runs as the `runner` container's CMD. Steps, in
order:

1. **Banner.** A `rich.Panel` with the project name and one-line description.
2. **Environment check.** Confirm the six `harness_oracle` binaries exist
   (built at image-build time) and liboqs's shared libs are present. This is
   a sanity check, not a build step; if it fails, the image build itself
   failed silently, and the wizard says so with a `--no-cache` rebuild hint
   rather than trying to self-heal.
3. **Wait for Ollama.** Poll `http://ollama:11434` with a short retry loop
   (Compose starts both services together, so Ollama may not be up yet on
   the first check). Clear error with a `docker compose logs ollama` hint if
   it never comes up.
4. **Hardware detection.** Read RAM via `psutil.virtual_memory()` and free
   disk via `shutil.disk_usage()`, both evaluated from inside the container
   (so a Docker Desktop memory limit is respected automatically, since that's
   what's actually available to the run). Note in the panel that this
   reflects Docker's resource allocation, not raw host specs, in case the two
   differ.
5. **Model tier recommendation.** A small static table maps RAM/disk
   thresholds to a model pair:
   - **Original** (`codellama:7b` + `qwen3:8b`): the pair the paper's results
     are based on. Recommended when free RAM >= 16 GB and free disk >= 12 GB.
   - **Lightweight** (`qwen2.5:3b` + `phi3:mini`): a smaller substitute for
     constrained machines. Recommended below that threshold. Labeled clearly
     as "results may differ from the original paper" wherever it's shown,
     since it changes what's actually being measured.
   The wizard proposes the tier matching the detected hardware and lets the
   user override in either direction (accept smaller tier even with room for
   the original, or attempt the original despite a warning if resources are
   tight).
6. **Pull models.** Calls Ollama's pull API for the chosen pair, rendering
   Ollama's own progress data through a `rich.Progress` bar. Disk space is
   re-checked against the specific tier's download size before pulling, with
   a clear message (not a crash) if it won't fit.
7. **Target-count prompt.** All six targets (full reproduction, longer) or
   just `kyber512_leak1` (fast first taste). Free-form target selection
   beyond this binary choice is out of scope for this round; it can be added
   later without changing the architecture.
8. **Run the engine.** Invokes the existing `track-b-engine/main.py` per
   selected target, unchanged. The wizard wraps its stdout with a per-target
   `rich` section header (target name) rather than re-parsing or reskinning
   the engine's own output line by line, since the engine already prints
   readable per-stage progress and duplicating that logic would be a second
   place for the same information to drift out of sync.
9. **Summary.** After all selected targets finish, read the resulting JSON
   from `shared/feedback/` and `shared/findings/` and render a `rich.Table`:
   target, verdict (PROMOTED/DEMOTED/INVALIDATED/UNCHANGED), t-stat. Prints
   the liboqs commit SHA from step 2 alongside it, and the host path where
   full JSON output lives.

## Persistence

`shared/` is bind-mounted from the host into the container at the same path,
so results outlive the `--rm`'d container. `ollama-data` is a named volume
(not bind-mounted), since Ollama's own model storage format doesn't need to
be human-readable on the host, just persistent across `docker compose run`
invocations. The build toolchain, liboqs, and target binaries live inside
the image layer, not a mount, so a fresh clone always gets a known-good
build without depending on anything already present on the host.

## GPU handling

- **NVIDIA (Linux/Windows with `nvidia-container-toolkit`):** a
  `docker-compose.override.yml.example` documents the `deploy.resources`
  GPU reservation block a user can copy to `docker-compose.override.yml` to
  enable passthrough. Not auto-detected in this round; opt-in via that file,
  documented in the README.
- **Apple Silicon:** Docker has no Metal passthrough. The wizard detects
  `Darwin`/`arm64` (via `platform.system()`/`platform.machine()`, passed
  through from the host) and prints a one-time, non-blocking note in the
  banner step: Ollama will run CPU-only under Docker on this machine, and a
  native Ollama install (outside Docker, pointed at with `OLLAMA_HOST`) would
  be faster if they want it. This does not change the default flow.

## Error handling

| Failure | Behavior |
|---|---|
| Target binaries missing at wizard startup | Explain the image build likely failed; suggest `docker compose build --no-cache`. Do not attempt to build inside the running container. |
| Ollama unreachable after retries | Clear message, `docker compose logs ollama` hint, exit non-zero. |
| Chosen model tier won't fit in free disk | Reported before pulling starts, with the smaller tier offered as a fallback prompt. |
| Model pull fails mid-download (network) | Ollama's own retry/resume behavior applies; the wizard surfaces the failure and offers to retry the pull step without repeating earlier steps. |
| Engine run fails for one target | Reported in the summary table as a failure row; the wizard continues to remaining targets rather than aborting the whole batch. |

## Testing

- **Pure logic, unit-tested with pytest** (mirrors existing `tests/`
  conventions): the RAM/disk-to-model-tier recommendation function, and the
  JSON-results-to-summary-table formatter. Both take plain data in and
  return plain data out, no Docker or subprocess involved, so they're cheap
  to test thoroughly including edge cases (exactly-at-threshold RAM, missing
  or malformed result JSON).
- **Full flow, verified by actually running it**, not by reading the compose
  file: build the image, run the wizard end to end against the lightweight
  model tier (faster than the original pair) for at least one target, and
  confirm the summary table and `shared/` output are both correct. This
  follows the same rule the document-design-system skill encodes: a fix or a
  build isn't verified until the real output has been looked at.

## Non-goals for this round

- The curated public release / repo export (separate, tracked in
  [[project-public-internal-separation]]).
- The Phase B multi-LLM sandbox and the pywebview visualizer (explicitly
  excluded from scope by the user).
- Free-form target selection beyond "one" vs "all six."
- Auto-detected GPU passthrough (documented opt-in only, this round).
