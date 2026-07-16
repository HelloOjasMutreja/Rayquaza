# Docker Reproducibility Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anyone clone this repo, run `docker compose run --rm runner`, and reproduce the core Rayquaza experiment (LLM adversary engine finding planted timing leaks in the five Kyber512 targets) without manually installing gcc, liboqs, or Ollama, or guessing which local LLM their machine can handle.

**Architecture:** Two Docker Compose services. `ollama` (official image, models pulled at runtime into a named volume, never baked into any image) and `runner` (built from a repo-root Dockerfile that bakes in the build toolchain, a freshly-built liboqs, and the six compiled Track A target binaries). `runner`'s default command is an interactive `rich`-based wizard (`bootstrap/wizard.py`) that detects available RAM/disk, recommends a model tier, pulls it, drives the existing engine via `track-b-engine/run_focused.sh` for the chosen Kyber512 target(s), and prints a plain-language summary table.

**Tech Stack:** Docker Compose, Python 3.11, `rich` (terminal UI), `psutil` (hardware detection), `requests` (Ollama HTTP API), pytest (existing repo convention).

## Global Constraints

- Scope for this round is the core engine only: `track-a-target/`, `track-b-engine/`, `shared/`. Not the Phase B sandbox, not the pywebview visualizer, not the curated public release (see spec's Non-goals section).
- `mldsa44_leak1` is excluded from the wizard's automated target list. It needs a bespoke synthetic target file (`track-b-engine/ingestion/test_targets/mldsa44_synthetic.c`, not a generic `*_focused.c` file) and its timing signal only reproduces significantly on x86 hosts (documented in `EXPERIMENT_LOG.md`, 2026-06-17 REPS check entry: t=0.91 on macOS/arm64 vs t=116.97 on WSL2/x86). Running it automatically on an arbitrary user's machine would silently produce a non-significant result that looks like a broken setup rather than the already-published architecture finding it actually is. `docs/reproducing-mldsa.md` documents the manual path.
- LLM model weights are never baked into the Docker image. They are pulled at runtime via `ollama pull`, sized to what the detected hardware can actually handle, into a Docker-managed volume on the user's own disk.
- liboqs has no recorded version pin anywhere in this repo. The Dockerfile clones its default branch at build time and records the resolved commit SHA to `/build-info/liboqs-commit.txt`, which the wizard surfaces at startup and in its summary, so every run self-documents exactly what it built against.
- No AI/model attribution anywhere in committed files, per [[feedback-no-ai-attribution]] (applies repo-wide, not just this feature).

---

### Task 1: Fix `run_focused.sh`'s stale hardcoded path and broken hypothesis-ID detection

This script already implements the non-trivial orchestration the wizard needs (start the engine, detect which hypothesis ID it's waiting on mid-run, invoke the matching oracle binary, wait for completion). It has two real bugs found by reading it against the current engine code, not by assuming it still works: a hardcoded absolute path from one developer's machine, and a stdout-scraping pattern that no longer matches the engine's current print format (the engine used to print `waiting for feedback containing 'H001'`; it now prints `waiting for feedback file timing_H001_*.json in ... (poll every 5s)`, so the old `grep -oE "containing '[^']+'"` pattern currently matches nothing and the oracle step silently never fires).

**Files:**
- Modify: `track-b-engine/run_focused.sh`

**Interfaces:**
- Consumes: nothing new.
- Produces: `track-b-engine/run_focused.sh <focused_target.c> <oracle_target_dir>`, usable from any working directory, writing `shared/findings/loop_state_<oracle_target_dir>.json` on completion. This is what Task 7's `wizard.py` shells out to.

- [ ] **Step 1: Read the current file and confirm both bugs**

Already confirmed in this session: line `ROOT="/Users/vedanthdama/Rayquaza"` is hardcoded, and the `HYP=$(grep -oE "containing '[^']+'" ...)` line no longer matches the engine's current stdout. No test-writing step here since this is a shell script; verification is a manual regex check (Step 3) plus the end-to-end run in Task 11.

- [ ] **Step 2: Apply the fix**

Replace the full contents of `track-b-engine/run_focused.sh` with:

```bash
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
```

- [ ] **Step 3: Verify the regex fix against the engine's real current output format**

Run:
```bash
echo "    ...waiting for feedback file timing_H001_*.json in /app/shared/feedback (poll every 5s)" | grep -oE "timing_[A-Za-z0-9]+_\*\.json" | sed -E 's/^timing_//; s/_\*\.json$//'
```
Expected output: `H001`

Also run a shell syntax check:
```bash
bash -n track-b-engine/run_focused.sh
```
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add track-b-engine/run_focused.sh
git commit -m "fix: run_focused.sh hardcoded path and stale hypothesis-id detection"
```

---

### Task 2: Add `requirements-bootstrap.txt` and install it

Every later task in this plan imports `rich`, `psutil`, or `requests`. None of the three existing requirements files cover all of them (`requirements-sandbox.txt` has `requests` only). Do this first so subsequent test-writing steps can actually run.

**Files:**
- Create: `requirements-bootstrap.txt`

**Interfaces:**
- Produces: an installed environment with `rich`, `psutil`, `requests`, `pytest` available to every later task.

- [ ] **Step 1: Create the file**

```
rich>=13.0
psutil>=5.9
requests>=2.28
pytest>=8.0
```

- [ ] **Step 2: Install it and verify**

```bash
pip install -r requirements-bootstrap.txt
python -c "import rich, psutil, requests; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add requirements-bootstrap.txt
git commit -m "chore: add requirements-bootstrap.txt for the Docker reproducibility wizard"
```

---

### Task 3: `bootstrap/hardware.py` — model tier recommendation

Pure logic: given detected RAM/disk, which Ollama model pair should this machine try. No Docker, no subprocess, no I/O beyond `psutil`/`shutil` calls that are trivial to reason about.

**Files:**
- Create: `bootstrap/__init__.py` (empty)
- Create: `bootstrap/hardware.py`
- Test: `tests/bootstrap/__init__.py` (empty)
- Test: `tests/bootstrap/test_hardware.py`

**Interfaces:**
- Produces: `ModelTier` dataclass (fields: `name: str`, `models: tuple[str, ...]`, `min_ram_gb: float`, `min_disk_gb: float`, `approx_download_gb: float`, `label: str`, `faithful: bool`); `TIERS: tuple[ModelTier, ...]` ordered original-first; `detect_ram_gb() -> float`; `detect_disk_gb(path: str = "/") -> float`; `recommend_tier(ram_gb: float, disk_gb: float) -> ModelTier | None`; `tier_by_name(name: str) -> ModelTier`; `fits_disk(tier: ModelTier, disk_gb: float) -> bool`; `is_apple_silicon() -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/bootstrap/__init__.py` (empty file).

Create `tests/bootstrap/test_hardware.py`:

```python
import pytest

from bootstrap.hardware import (
    TIERS,
    detect_disk_gb,
    detect_ram_gb,
    recommend_tier,
    tier_by_name,
)


def test_recommend_tier_returns_original_when_resources_are_ample():
    tier = recommend_tier(ram_gb=32.0, disk_gb=100.0)
    assert tier is not None
    assert tier.name == "original"


def test_recommend_tier_returns_lightweight_when_original_does_not_fit():
    tier = recommend_tier(ram_gb=10.0, disk_gb=20.0)
    assert tier is not None
    assert tier.name == "lightweight"


def test_recommend_tier_returns_none_when_nothing_fits():
    tier = recommend_tier(ram_gb=2.0, disk_gb=1.0)
    assert tier is None


def test_recommend_tier_boundary_is_inclusive():
    tier = recommend_tier(ram_gb=16.0, disk_gb=12.0)
    assert tier is not None
    assert tier.name == "original"


def test_tier_by_name_returns_matching_tier():
    tier = tier_by_name("lightweight")
    assert tier.models == ("qwen2.5:3b", "phi3:mini")


def test_tier_by_name_raises_on_unknown_name():
    with pytest.raises(ValueError):
        tier_by_name("nonexistent")


def test_detect_ram_gb_returns_positive_number():
    assert detect_ram_gb() > 0


def test_detect_disk_gb_returns_positive_number():
    assert detect_disk_gb() > 0


def test_tiers_ordered_original_first():
    assert TIERS[0].name == "original"


def test_fits_disk_true_when_enough_space():
    from bootstrap.hardware import fits_disk
    tier = tier_by_name("lightweight")
    assert fits_disk(tier, disk_gb=10.0) is True


def test_fits_disk_false_when_not_enough_space():
    from bootstrap.hardware import fits_disk
    tier = tier_by_name("original")
    assert fits_disk(tier, disk_gb=5.0) is False


def test_is_apple_silicon_true_on_darwin_arm64():
    from unittest.mock import patch
    from bootstrap.hardware import is_apple_silicon
    with patch("bootstrap.hardware.platform.system", return_value="Darwin"), \
         patch("bootstrap.hardware.platform.machine", return_value="arm64"):
        assert is_apple_silicon() is True


def test_is_apple_silicon_false_on_linux():
    from unittest.mock import patch
    from bootstrap.hardware import is_apple_silicon
    with patch("bootstrap.hardware.platform.system", return_value="Linux"), \
         patch("bootstrap.hardware.platform.machine", return_value="x86_64"):
        assert is_apple_silicon() is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bootstrap/test_hardware.py -v
```
Expected: FAIL (ImportError, `bootstrap.hardware` doesn't exist yet)

- [ ] **Step 3: Write the implementation**

Create `bootstrap/__init__.py` (empty).

Create `bootstrap/hardware.py`:

```python
"""bootstrap/hardware.py -- detect available RAM/disk and recommend an
Ollama model tier.

Detection happens from wherever this runs (inside the runner container,
when used via Docker), so it reflects whatever resources are actually
available to the process, not necessarily the host's full specs -- a Docker
Desktop memory limit is respected automatically for exactly this reason.
"""
from dataclasses import dataclass

import platform
import psutil
import shutil


@dataclass(frozen=True)
class ModelTier:
    name: str
    models: tuple[str, ...]
    min_ram_gb: float
    min_disk_gb: float
    approx_download_gb: float
    label: str
    faithful: bool  # True if this tier reproduces the original paper's models


TIERS: tuple[ModelTier, ...] = (
    ModelTier(
        name="original",
        models=("codellama:7b", "qwen3:8b"),
        min_ram_gb=16.0,
        min_disk_gb=12.0,
        approx_download_gb=9.5,
        label="Original models (codellama:7b + qwen3:8b): faithful reproduction",
        faithful=True,
    ),
    ModelTier(
        name="lightweight",
        models=("qwen2.5:3b", "phi3:mini"),
        min_ram_gb=8.0,
        min_disk_gb=6.0,
        approx_download_gb=4.0,
        label="Lightweight models (qwen2.5:3b + phi3:mini): results may differ from the original paper",
        faithful=False,
    ),
)


def detect_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def detect_disk_gb(path: str = "/") -> float:
    return shutil.disk_usage(path).free / (1024 ** 3)


def recommend_tier(ram_gb: float, disk_gb: float) -> ModelTier | None:
    """Return the best-fitting tier for the given resources, preferring the
    faithful/original tier when both fit (TIERS is ordered original-first).
    Returns None if neither tier's minimums are met; the caller decides
    whether to warn and let the user proceed anyway."""
    for tier in TIERS:
        if ram_gb >= tier.min_ram_gb and disk_gb >= tier.min_disk_gb:
            return tier
    return None


def tier_by_name(name: str) -> ModelTier:
    for tier in TIERS:
        if tier.name == name:
            return tier
    raise ValueError(f"unknown tier: {name}")


def fits_disk(tier: ModelTier, disk_gb: float) -> bool:
    """Re-check a specific tier's download size against free disk right
    before pulling, separately from recommend_tier's broader thresholds
    (which include a comfort margin for running the models, not just
    downloading them)."""
    return disk_gb >= tier.approx_download_gb


def is_apple_silicon() -> bool:
    """True on macOS/arm64, where Docker has no Metal passthrough, so
    Ollama running inside a container is CPU-only regardless of what the
    host hardware could otherwise do."""
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bootstrap/test_hardware.py -v
```
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add bootstrap/__init__.py bootstrap/hardware.py tests/bootstrap/__init__.py tests/bootstrap/test_hardware.py
git commit -m "feat: add hardware detection and model tier recommendation"
```

---

### Task 4: `bootstrap/build_check.py` — verify the image build produced what the wizard needs

**Files:**
- Create: `bootstrap/build_check.py`
- Test: `tests/bootstrap/test_build_check.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `TARGET_DIRS: tuple[str, ...]` (the five Kyber target directory names); `missing_binaries(targets_root: Path, target_dirs: tuple[str, ...] = TARGET_DIRS) -> list[str]`; `read_liboqs_commit(commit_file: Path = LIBOQS_COMMIT_FILE) -> str`. Task 7 (`wizard.py`) imports `TARGET_DIRS`, `missing_binaries`, and `read_liboqs_commit` from this module.

- [ ] **Step 1: Write the failing tests**

Create `tests/bootstrap/test_build_check.py`:

```python
from pathlib import Path

from bootstrap.build_check import missing_binaries, read_liboqs_commit


def test_missing_binaries_reports_targets_without_a_binary(tmp_path):
    (tmp_path / "kyber512_leak1").mkdir()
    (tmp_path / "kyber512_leak1" / "harness_oracle").write_text("fake binary")
    (tmp_path / "kyber512_leak2").mkdir()
    # leak2 has no binary

    missing = missing_binaries(tmp_path, target_dirs=("kyber512_leak1", "kyber512_leak2"))

    assert missing == ["kyber512_leak2"]


def test_missing_binaries_empty_when_all_present(tmp_path):
    for name in ("kyber512_leak1", "kyber512_leak2"):
        d = tmp_path / name
        d.mkdir()
        (d / "harness_oracle").write_text("fake binary")

    assert missing_binaries(tmp_path, target_dirs=("kyber512_leak1", "kyber512_leak2")) == []


def test_read_liboqs_commit_returns_file_contents(tmp_path):
    commit_file = tmp_path / "liboqs-commit.txt"
    commit_file.write_text("abc1234\n")

    assert read_liboqs_commit(commit_file) == "abc1234"


def test_read_liboqs_commit_returns_placeholder_when_missing(tmp_path):
    commit_file = tmp_path / "does-not-exist.txt"

    result = read_liboqs_commit(commit_file)

    assert "unknown" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bootstrap/test_build_check.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

Create `bootstrap/build_check.py`:

```python
"""bootstrap/build_check.py -- verify the Docker image's build step actually
produced what the wizard needs before it tries to use any of it."""
from pathlib import Path

TARGET_DIRS = (
    "kyber512_leak1",
    "kyber512_leak2",
    "kyber512_leak3",
    "kyber512_leak4",
    "kyber512_leak5",
)

LIBOQS_COMMIT_FILE = Path("/build-info/liboqs-commit.txt")


def missing_binaries(targets_root: Path, target_dirs: tuple[str, ...] = TARGET_DIRS) -> list[str]:
    """Return the subset of target_dirs whose harness_oracle binary is missing."""
    missing = []
    for name in target_dirs:
        binary = targets_root / name / "harness_oracle"
        if not binary.exists():
            missing.append(name)
    return missing


def read_liboqs_commit(commit_file: Path = LIBOQS_COMMIT_FILE) -> str:
    """Return the liboqs commit SHA baked into the image, or a placeholder
    string if the file is missing (e.g. when running outside Docker)."""
    if not commit_file.exists():
        return "unknown (not running inside the built image)"
    return commit_file.read_text(encoding="utf-8").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bootstrap/test_build_check.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add bootstrap/build_check.py tests/bootstrap/test_build_check.py
git commit -m "feat: add build verification (target binaries, liboqs commit)"
```

---

### Task 5: `bootstrap/summary.py` — turn engine output into a plain results table

**Files:**
- Create: `bootstrap/summary.py`
- Test: `tests/bootstrap/test_summary.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `build_summary(findings_dir: Path, target_dirs: list[str]) -> list[dict]`, each dict shaped `{"target": str, "hypothesis_id": str | None, "verdict": str, "t_statistic": float | None}`. Task 7 (`wizard.py`) imports `build_summary` from this module and renders its return value as a `rich.Table`.

- [ ] **Step 1: Write the failing tests**

Create `tests/bootstrap/test_summary.py`:

```python
import json
from pathlib import Path

from bootstrap.summary import build_summary


def _write_snapshot(findings_dir: Path, target: str, hypotheses: list[dict]) -> None:
    findings_dir.mkdir(parents=True, exist_ok=True)
    snapshot = findings_dir / f"loop_state_{target}.json"
    snapshot.write_text(json.dumps({"hypotheses": hypotheses}), encoding="utf-8")


def test_build_summary_reads_promoted_hypothesis(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak1", [
        {"id": "H001", "status": "PROMOTED", "t_statistic": 213.4791},
    ])

    rows = build_summary(tmp_path, ["kyber512_leak1"])

    assert rows == [{
        "target": "kyber512_leak1",
        "hypothesis_id": "H001",
        "verdict": "PROMOTED",
        "t_statistic": 213.4791,
    }]


def test_build_summary_handles_missing_snapshot(tmp_path):
    rows = build_summary(tmp_path, ["kyber512_leak2"])

    assert rows == [{
        "target": "kyber512_leak2",
        "hypothesis_id": None,
        "verdict": "NO RESULT",
        "t_statistic": None,
    }]


def test_build_summary_handles_empty_hypotheses_list(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak3", [])

    rows = build_summary(tmp_path, ["kyber512_leak3"])

    assert rows == [{
        "target": "kyber512_leak3",
        "hypothesis_id": None,
        "verdict": "NO HYPOTHESES",
        "t_statistic": None,
    }]


def test_build_summary_handles_multiple_hypotheses_for_one_target(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak4", [
        {"id": "H001", "status": "DEMOTED", "t_statistic": 1.2},
        {"id": "H002", "status": "PROMOTED", "t_statistic": 88.0},
    ])

    rows = build_summary(tmp_path, ["kyber512_leak4"])

    assert len(rows) == 2
    assert rows[0]["verdict"] == "DEMOTED"
    assert rows[1]["verdict"] == "PROMOTED"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bootstrap/test_summary.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

Create `bootstrap/summary.py`:

```python
"""bootstrap/summary.py -- turn per-target loop_state snapshots (written by
run_focused.sh) into a plain summary the wizard can print, without the
caller needing to understand the full engine JSON schema."""
import json
from pathlib import Path


def build_summary(findings_dir: Path, target_dirs: list[str]) -> list[dict]:
    """For each target dir name, read shared/findings/loop_state_<name>.json
    and return one row per hypothesis found:
    {"target": str, "hypothesis_id": str | None, "verdict": str, "t_statistic": float | None}.
    A target with no snapshot file yet (run failed or hasn't finished) gets a
    single row with verdict "NO RESULT". A snapshot with no hypotheses gets
    a single row with verdict "NO HYPOTHESES"."""
    rows = []
    for name in target_dirs:
        snapshot = findings_dir / f"loop_state_{name}.json"
        if not snapshot.exists():
            rows.append({
                "target": name,
                "hypothesis_id": None,
                "verdict": "NO RESULT",
                "t_statistic": None,
            })
            continue
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        hypotheses = data.get("hypotheses", [])
        if not hypotheses:
            rows.append({
                "target": name,
                "hypothesis_id": None,
                "verdict": "NO HYPOTHESES",
                "t_statistic": None,
            })
            continue
        for hyp in hypotheses:
            rows.append({
                "target": name,
                "hypothesis_id": hyp.get("id"),
                "verdict": hyp.get("status", "UNKNOWN"),
                "t_statistic": hyp.get("t_statistic"),
            })
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bootstrap/test_summary.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add bootstrap/summary.py tests/bootstrap/test_summary.py
git commit -m "feat: add results summary builder"
```

---

### Task 6: `bootstrap/ollama_client.py` — wait-for-ready and pull-with-progress

**Files:**
- Create: `bootstrap/ollama_client.py`
- Test: `tests/bootstrap/test_ollama_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `wait_until_ready(base_url: str, timeout_s: float = 60.0, interval_s: float = 2.0) -> bool`; `pull_model(base_url: str, model: str) -> Iterator[dict]`, yielding Ollama's own progress events (dicts with at least a `"status"` key, and `"completed"`/`"total"` keys during download). Task 7 (`wizard.py`) imports both from this module.

- [ ] **Step 1: Write the failing tests**

Create `tests/bootstrap/test_ollama_client.py`:

```python
import json
from unittest.mock import Mock, patch

import requests

from bootstrap.ollama_client import pull_model, wait_until_ready


def test_wait_until_ready_returns_true_on_first_success():
    with patch("bootstrap.ollama_client.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200)
        assert wait_until_ready("http://ollama:11434", timeout_s=5, interval_s=0.01) is True


def test_wait_until_ready_returns_false_on_timeout():
    with patch(
        "bootstrap.ollama_client.requests.get",
        side_effect=requests.exceptions.ConnectionError(),
    ):
        assert wait_until_ready("http://ollama:11434", timeout_s=0.05, interval_s=0.01) is False


def test_pull_model_yields_parsed_progress_lines():
    fake_lines = [
        json.dumps({"status": "pulling manifest"}).encode(),
        json.dumps({"status": "downloading", "completed": 50, "total": 100}).encode(),
        json.dumps({"status": "success"}).encode(),
    ]
    mock_resp = Mock()
    mock_resp.iter_lines.return_value = fake_lines
    mock_resp.raise_for_status.return_value = None

    with patch("bootstrap.ollama_client.requests.post", return_value=mock_resp):
        events = list(pull_model("http://ollama:11434", "qwen2.5:3b"))

    assert events[0]["status"] == "pulling manifest"
    assert events[1]["completed"] == 50
    assert events[-1]["status"] == "success"


def test_pull_model_skips_blank_lines():
    fake_lines = [b"", json.dumps({"status": "success"}).encode(), b""]
    mock_resp = Mock()
    mock_resp.iter_lines.return_value = fake_lines
    mock_resp.raise_for_status.return_value = None

    with patch("bootstrap.ollama_client.requests.post", return_value=mock_resp):
        events = list(pull_model("http://ollama:11434", "phi3:mini"))

    assert events == [{"status": "success"}]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bootstrap/test_ollama_client.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

Create `bootstrap/ollama_client.py`:

```python
"""bootstrap/ollama_client.py -- thin wrapper around the Ollama HTTP API for
the two things the wizard needs: waiting for the service to be reachable,
and pulling a model with progress feedback."""
import json
import time
from typing import Iterator

import requests


def wait_until_ready(base_url: str, timeout_s: float = 60.0, interval_s: float = 2.0) -> bool:
    """Poll base_url until Ollama responds or timeout_s elapses. Returns
    True if it became ready, False on timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = requests.get(base_url, timeout=5)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval_s)
    return False


def pull_model(base_url: str, model: str) -> Iterator[dict]:
    """Stream progress events from Ollama's /api/pull for `model`. Yields the
    parsed JSON object from each non-blank line Ollama sends, e.g.
    {"status": "pulling manifest"} or
    {"status": "downloading", "completed": 123, "total": 456}.
    Raises requests.exceptions.HTTPError if the pull request itself fails."""
    resp = requests.post(
        f"{base_url}/api/pull",
        json={"name": model, "stream": True},
        stream=True,
        timeout=None,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        yield json.loads(line)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bootstrap/test_ollama_client.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add bootstrap/ollama_client.py tests/bootstrap/test_ollama_client.py
git commit -m "feat: add Ollama readiness check and model pull with progress"
```

---

### Task 7: `bootstrap/wizard.py` and `run_bootstrap.py` — the interactive CLI

This is the orchestration layer tying Tasks 3-6 together, plus process control (`subprocess`) and terminal interaction (`rich` prompts). It is not unit-tested the way the pure-logic modules are; it's verified by actually running it, in Task 11, matching the project's own established rule (see `references/verification-checklist.md` in the document-design-system skill: a fix isn't verified until the real output has been looked at, not just the code).

**Files:**
- Create: `bootstrap/wizard.py`
- Create: `run_bootstrap.py`

**Interfaces:**
- Consumes: `bootstrap.hardware.{TIERS, detect_ram_gb, detect_disk_gb, recommend_tier, tier_by_name, fits_disk, is_apple_silicon}`, `bootstrap.build_check.{TARGET_DIRS, missing_binaries, read_liboqs_commit}`, `bootstrap.ollama_client.{wait_until_ready, pull_model}`, `bootstrap.summary.build_summary`.
- Produces: `bootstrap.wizard.main() -> None`, the wizard's entry point, invoked by `run_bootstrap.py`.

- [ ] **Step 1: Write `bootstrap/wizard.py`**

```python
"""bootstrap/wizard.py -- the interactive CLI that runs inside the `runner`
container. Detects hardware, picks a model tier, pulls it, runs the engine
against the chosen Kyber512 target(s) via run_focused.sh, and prints a
summary.

ML-DSA-44 (mldsa44_leak1) is intentionally not part of this automated flow:
it needs a bespoke synthetic target file (not a generic "*_focused.c" file
like the five Kyber leaks) and its timing signal only reproduces on x86 (see
EXPERIMENT_LOG.md, 2026-06-17 REPS check). ARM hosts read a non-significant
t-stat that would look like a broken setup rather than a documented,
already-published architecture difference. See docs/reproducing-mldsa.md
for the manual steps.
"""
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn
from rich.prompt import IntPrompt
from rich.table import Table

from bootstrap.build_check import TARGET_DIRS, missing_binaries, read_liboqs_commit
from bootstrap.hardware import (
    TIERS,
    detect_disk_gb,
    detect_ram_gb,
    fits_disk,
    is_apple_silicon,
    recommend_tier,
    tier_by_name,
)
from bootstrap.ollama_client import pull_model, wait_until_ready
from bootstrap.summary import build_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS_ROOT = REPO_ROOT / "track-a-target" / "targets"
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"
OLLAMA_BASE_URL = os.environ.get("RAYQ_OLLAMA_BASE", "http://ollama:11434")

FOCUSED_TARGETS = {
    name: REPO_ROOT / "track-b-engine" / "ingestion" / "test_targets" / f"{name}_focused.c"
    for name in TARGET_DIRS
}

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold]RAYQUAZA[/bold] -- Post-Quantum Timing-Leak Discovery\n"
        "LLM-guided rediscovery of planted PQC side-channels",
        border_style="cyan",
    ))
    if is_apple_silicon():
        console.print(
            "[yellow]Note:[/yellow] Docker has no Metal passthrough on Apple "
            "Silicon, so Ollama will run CPU-only in this container. A native "
            "Ollama install outside Docker (pointed at with OLLAMA_HOST) would "
            "be faster on this machine if you want it. This run will still "
            "work, just more slowly.\n"
        )


def _check_build() -> str:
    missing = missing_binaries(TARGETS_ROOT, TARGET_DIRS)
    if missing:
        console.print(f"[red]Missing built targets: {', '.join(missing)}[/red]")
        console.print("The image build likely failed. Try: [bold]docker compose build --no-cache[/bold]")
        sys.exit(1)
    commit = read_liboqs_commit()
    console.print(f"[green]OK[/green] Build toolchain OK (liboqs commit {commit})")
    return commit


def _wait_for_ollama() -> None:
    console.print("Waiting for Ollama service...", end=" ")
    if not wait_until_ready(OLLAMA_BASE_URL, timeout_s=90):
        console.print("[red]unreachable[/red]")
        console.print("Check it with: [bold]docker compose logs ollama[/bold]")
        sys.exit(1)
    console.print("[green]OK[/green]")


def _choose_tier():
    ram_gb = detect_ram_gb()
    disk_gb = detect_disk_gb()
    console.print(f"RAM available:   {ram_gb:.1f} GB")
    console.print(f"Disk available: {disk_gb:.1f} GB")

    recommended = recommend_tier(ram_gb, disk_gb)
    if recommended is None:
        console.print(
            "[yellow]Neither model tier's minimums are comfortably met on this "
            "machine. You can still try the lightweight tier, but pulls or runs "
            "may be slow.[/yellow]"
        )
        recommended = tier_by_name("lightweight")

    console.print(f"\nRecommended: [bold]{recommended.label}[/bold]")
    for i, tier in enumerate(TIERS, start=1):
        marker = " (recommended)" if tier.name == recommended.name else ""
        console.print(f"  [{i}] {tier.label}{marker}")

    default_choice = next(i for i, t in enumerate(TIERS, start=1) if t.name == recommended.name)
    choice = IntPrompt.ask(
        "Which would you like?",
        default=default_choice,
        choices=[str(i) for i in range(1, len(TIERS) + 1)],
    )
    return TIERS[choice - 1]


def _pull_models(tier):
    """Pull every model in `tier`, re-checking free disk right before
    pulling (recommend_tier already checked once, but that was before the
    user's final choice, and disk can be tighter than the broader
    recommendation thresholds account for). Falls back to the lightweight
    tier once, with a clear message, rather than starting a download that
    can't finish; exits if even that doesn't fit. Returns the tier actually
    used, since a fallback means it may differ from what was passed in."""
    disk_gb = detect_disk_gb()
    if not fits_disk(tier, disk_gb):
        console.print(
            f"[yellow]Only {disk_gb:.1f} GB free, but {tier.label} needs "
            f"~{tier.approx_download_gb:.1f} GB to download.[/yellow]"
        )
        if tier.name != "lightweight":
            fallback = tier_by_name("lightweight")
            if fits_disk(fallback, disk_gb):
                console.print(f"Falling back to: [bold]{fallback.label}[/bold]")
                tier = fallback
            else:
                console.print("[red]Not enough disk space even for the lightweight tier. Free up space and try again.[/red]")
                sys.exit(1)
        else:
            console.print("[red]Not enough disk space for the lightweight tier. Free up space and try again.[/red]")
            sys.exit(1)

    for model in tier.models:
        console.print(f"Pulling {model}...")
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(model, total=None)
            for event in pull_model(OLLAMA_BASE_URL, model):
                total = event.get("total")
                completed = event.get("completed")
                if total and completed is not None:
                    progress.update(task, total=total, completed=completed)
        console.print(f"[green]OK[/green] {model} ready")
    return tier


def _choose_targets() -> list[str]:
    console.print("\nRun all 5 Kyber targets, or just one to start?")
    console.print("  [1] All 5 (full reproduction)")
    console.print("  [2] Just kyber512_leak1 (fast first taste)")
    console.print(
        "  Note: mldsa44_leak1 is not included here -- it needs an x86 host "
        "to reproduce a significant result. See docs/reproducing-mldsa.md."
    )
    choice = IntPrompt.ask("Choice", default=2, choices=["1", "2"])
    if choice == 1:
        return list(FOCUSED_TARGETS.keys())
    return ["kyber512_leak1"]


def _run_target(name: str) -> None:
    console.rule(name)
    script = REPO_ROOT / "track-b-engine" / "run_focused.sh"
    focused_file = FOCUSED_TARGETS[name]
    subprocess.run(
        ["bash", str(script), str(focused_file), name],
        cwd=REPO_ROOT,
        check=False,
    )


def _print_summary(targets: list[str], commit: str) -> None:
    rows = build_summary(FINDINGS_DIR, targets)
    table = Table(title="Summary")
    table.add_column("Target")
    table.add_column("Hypothesis")
    table.add_column("Verdict")
    table.add_column("t-stat")
    for row in rows:
        t_stat = f"{row['t_statistic']:.1f}" if row["t_statistic"] is not None else "-"
        table.add_row(row["target"], row["hypothesis_id"] or "-", row["verdict"], t_stat)
    console.print(table)
    console.print(f"liboqs commit: {commit}")
    console.print(f"Full results saved to {FINDINGS_DIR} and {REPO_ROOT / 'shared' / 'feedback'}")
    console.print("Run again any time with: docker compose run --rm runner")


def main() -> None:
    _banner()
    commit = _check_build()
    _wait_for_ollama()
    tier = _choose_tier()
    tier = _pull_models(tier)
    targets = _choose_targets()
    for name in targets:
        _run_target(name)
    _print_summary(targets, commit)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `run_bootstrap.py`**

```python
#!/usr/bin/env python3
"""run_bootstrap.py -- Rayquaza Docker reproducibility wizard entry point.

Usage (inside the runner container): python run_bootstrap.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bootstrap.wizard import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test that everything imports cleanly**

```bash
python -c "from bootstrap import wizard; print('ok')"
```
Expected: `ok` (no ImportError/SyntaxError). This does not exercise the interactive flow, only that every import resolves and the module loads. Full behavior is verified in Task 11.

- [ ] **Step 4: Commit**

```bash
git add bootstrap/wizard.py run_bootstrap.py
git commit -m "feat: add interactive reproducibility wizard"
```

---

### Task 8: `.dockerignore` and `Dockerfile`

Found while inspecting the target directories: several already have a locally-built `harness_oracle` binary sitting in the working tree (gitignored, host-built, wrong architecture for the container). Without a `.dockerignore`, a plain `COPY track-a-target/` would ship those stale host binaries into the image, where they'd either be silently unusable or, worse, silently "work" and mask a build failure. Excluding them forces every target to actually rebuild inside the container.

**Files:**
- Create: `.dockerignore`
- Create: `Dockerfile`

**Interfaces:**
- Consumes: `bootstrap/`, `run_bootstrap.py`, `requirements-bootstrap.txt`, `requirements-sandbox.txt`, `track-a-target/`, `track-b-engine/`, `shared/` (all copied into the image).
- Produces: a `runner` image with `/build-info/liboqs-commit.txt`, `/root/liboqs-install/`, five built `harness_oracle` binaries under `/app/track-a-target/targets/*/`, and `python run_bootstrap.py` as its default command.

- [ ] **Step 1: Create `.dockerignore`**

```
.git
__pycache__
*.pyc
.pytest_cache
track-a-target/targets/*/harness_oracle
track-a-target/targets/*/harness_leak5
sandbox/
sandbox/secrets.local.json
docs/
tracking/
viz/
.superpowers/
.claude/
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
# Dockerfile -- Rayquaza reproducibility wizard runner image.
# Bundles the build toolchain, liboqs, and the compiled Track A target
# binaries. Does NOT bundle any Ollama model weights -- those are pulled at
# runtime by the wizard based on detected hardware (see bootstrap/hardware.py).
FROM python:3.11-slim

ENV HOME=/root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    libssl-dev \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Build liboqs. No version pin is recorded anywhere in this repo (checked:
# EXPERIMENT_LOG.md and track-a-target/TRACK_A_PLAN.md), so this clones the
# default branch at build time and records the resolved commit, rather than
# guessing a tag that may not exist. The source tree under /root/liboqs/src
# is kept (not deleted) because kyber512_leak5/setup.sh copies reference
# files from it; only the build/ subdirectory is dropped after install.
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git /root/liboqs \
    && mkdir -p /build-info \
    && git -C /root/liboqs rev-parse HEAD > /build-info/liboqs-commit.txt \
    && cmake -S /root/liboqs -B /root/liboqs/build -GNinja \
         -DCMAKE_INSTALL_PREFIX=/root/liboqs-install \
         -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /root/liboqs/build \
    && cmake --install /root/liboqs/build \
    && rm -rf /root/liboqs/build

WORKDIR /app
COPY track-a-target/ /app/track-a-target/
COPY track-b-engine/ /app/track-b-engine/
COPY shared/ /app/shared/
COPY bootstrap/ /app/bootstrap/
COPY run_bootstrap.py requirements-bootstrap.txt requirements-sandbox.txt /app/

RUN pip install --no-cache-dir -r requirements-bootstrap.txt -r requirements-sandbox.txt

# Build every target directory: run its setup.sh first if it has one (only
# kyber512_leak5 does, to copy reference files from the liboqs source tree
# above), then make. mldsa44_leak1 is built too even though the wizard
# doesn't run it automatically, so the manual path in
# docs/reproducing-mldsa.md works without extra setup.
RUN for dir in track-a-target/targets/*/; do \
        if [ -f "$dir/setup.sh" ]; then \
            (cd "$dir" && bash setup.sh); \
        fi; \
        (cd "$dir" && make); \
    done

ENV RAYQ_OLLAMA_URL=http://ollama:11434/api/chat
ENV RAYQ_OLLAMA_BASE=http://ollama:11434

CMD ["python", "run_bootstrap.py"]
```

- [ ] **Step 3: Commit**

```bash
git add .dockerignore Dockerfile
git commit -m "feat: add runner Dockerfile (build toolchain, liboqs, target binaries)"
```

---

### Task 9: `docker-compose.yml` and the GPU override example

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.override.yml.example`

**Interfaces:**
- Consumes: `Dockerfile` (Task 8).
- Produces: the `docker compose run --rm runner` entry point referenced everywhere else in this plan and in the design spec's CLI mockup.

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped

  runner:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      - ollama
    environment:
      - RAYQ_OLLAMA_URL=http://ollama:11434/api/chat
      - RAYQ_OLLAMA_BASE=http://ollama:11434
    volumes:
      - ./shared:/app/shared
    stdin_open: true
    tty: true

volumes:
  ollama-data:
```

- [ ] **Step 2: Create `docker-compose.override.yml.example`**

```yaml
# Copy this file to docker-compose.override.yml to enable NVIDIA GPU
# passthrough for the ollama service. Requires nvidia-container-toolkit
# installed on the host (https://github.com/NVIDIA/nvidia-container-toolkit).
#
# Not applicable on Apple Silicon: Docker has no Metal passthrough on macOS,
# so Ollama runs CPU-only under Docker there regardless of this file. The
# wizard prints a one-time note about this on Apple Silicon hosts; a native
# Ollama install outside Docker is the faster option on those machines.
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

- [ ] **Step 3: Validate the compose file parses correctly**

```bash
docker compose config --quiet
```
Expected: no output, exit code 0. (Requires Docker installed; if Docker isn't available in this environment, at minimum run a YAML syntax check: `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"` expecting no exception, and treat the full `docker compose config` check as part of Task 11's end-to-end verification instead.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml docker-compose.override.yml.example
git commit -m "feat: add docker-compose.yml (ollama + runner services)"
```

---

### Task 10: README quickstart and the ML-DSA manual-reproduction doc

**Files:**
- Modify: `README.md`
- Create: `docs/reproducing-mldsa.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks; this is the last piece a real user reads. Referenced by `bootstrap/wizard.py`'s printed message (Task 7) and must exist for that reference to be real, not a placeholder.

- [ ] **Step 1: Add a quickstart section to `README.md`**

Insert after the "## Team" section and before "## How to navigate this repo":

```markdown
## Reproducing the experiment

The fastest way to see the core experiment run is Docker:

```bash
git clone <this repo's URL>
cd Rayquaza
docker compose run --rm runner
```

That single command builds the toolchain and liboqs, starts Ollama inside
Docker (no host install needed), detects how much RAM/disk your machine has
free, recommends an appropriately-sized model pair, pulls it, and runs the
LLM adversary engine against the five Kyber512 targets. The only
prerequisite is Docker itself (Docker Desktop on Mac/Windows, Docker Engine
on Linux). Nothing else needs to be installed on your machine; the model
weights are fetched into a Docker-managed volume, not baked into the image
or left on your host filesystem in any other way.

Results land in `shared/feedback/` and `shared/findings/` on your own
machine (bind-mounted, so they survive after the container exits).

Note: `mldsa44_leak1` is not part of this automated flow. See
[docs/reproducing-mldsa.md](docs/reproducing-mldsa.md) for why and how to
run it manually.
```

- [ ] **Step 2: Create `docs/reproducing-mldsa.md`**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/reproducing-mldsa.md
git commit -m "docs: add Docker quickstart and manual ML-DSA reproduction guide"
```

---

### Task 11: End-to-end verification

This is the task that actually proves the previous ten worked together, not just individually. Per this project's own established rule (used repeatedly this session, including catching a real DOCX namespace bug the same way): a build isn't verified until the real output has been looked at.

**Files:** none created or modified; this task runs what earlier tasks built and fixes any issues found, in whichever file the issue is actually in.

- [ ] **Step 1: Run the full pytest suite**

```bash
pytest tests/bootstrap/ -v
```
Expected: all tests from Tasks 3-6 pass (21 tests total: 9 hardware + 4 build_check + 4 summary + 4 ollama_client).

- [ ] **Step 2: Build the image**

```bash
docker compose build runner
```
Expected: build succeeds. Watch specifically for the liboqs cmake/ninja build step and the per-target `make` loop; if any target fails to build, read the actual compiler error rather than assuming and fix the specific target's Makefile/source issue.

- [ ] **Step 3: Run the wizard end to end against the lightweight tier, one target**

```bash
docker compose run --rm runner
```
At the prompts: choose the lightweight tier (faster to pull than the original pair), then choose "just kyber512_leak1." Let it run to completion.

Expected: the banner prints, the build-check and Ollama-wait steps both report OK, hardware numbers print, the model tier prompt appears and accepts the choice, both lightweight models pull with visible progress, `kyber512_leak1` runs and prints engine output under a `rich.rule` header, and a summary table prints at the end with a real verdict and t-stat (not `NO RESULT`).

- [ ] **Step 4: Verify results actually landed on the host**

```bash
cat shared/findings/loop_state_kyber512_leak1.json
```
Expected: valid JSON containing a `hypotheses` list with at least one entry that has a `status` and `t_statistic`. This confirms the bind mount and the `run_focused.sh` fix from Task 1 both worked, not just that the container printed something plausible.

- [ ] **Step 5: Re-run to confirm caching works**

```bash
docker compose run --rm runner
```
Expected: no image rebuild, no model re-download (Ollama reports the model already present or pulls near-instantly), confirming `ollama-data` is a persistent named volume as designed.

- [ ] **Step 6: Fix anything Steps 2-5 surfaced**

If any step failed, fix the actual root cause in the relevant file (Dockerfile, wizard.py, run_focused.sh, etc.), re-run the failing step, and only proceed once it passes for real. Do not mark this task done based on "should work now" reasoning; re-run and observe.

- [ ] **Step 7: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end Docker verification"
```
(Skip this step if Steps 2-5 all passed cleanly with no changes needed.)
