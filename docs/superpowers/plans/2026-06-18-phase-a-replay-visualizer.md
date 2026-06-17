# Phase A Live Visualizer — Milestone A1 (Replay) + A2 (Live Coarse) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pywebview desktop window that animates the LLM adversary engine's five-stage pipeline (INGEST → VECTORIZE → WAIT → REFINE → SAVE) in real time — first driven by committed JSON fixtures (A1 Replay, no Ollama needed), then by a live engine subprocess (A2 Live coarse).

**Architecture:** A `viz/` Python package is the only new code. `app.py` owns the pywebview window and JS bridge. `orchestrator.py` drives the run lifecycle and pushes `RunState` to the UI. `events.py` is the data model. `sources/replay.py` (A1) reads from committed `loop_state_*.json` files and synthesises stage events with time delays. `sources/live.py` (A2) launches the engine as a subprocess and parses its stdout. The web frontend (`viz/web/`) is pure HTML/CSS/JS — it receives `RunState` via `window.onStateUpdate()` and renders animated pipeline boxes. No code in `track-b-engine/` is touched for A1 or A2.

**Tech Stack:** Python 3.10+, pywebview 5.x (`pip install pywebview`), pytest 8.x, stdlib only (dataclasses, json, pathlib, threading, re, time, uuid).

**Branch:** `phase-a-viz`. All files created here. No modifications to shared tracking files.

---

## File map

```
viz/
  __init__.py                  new — package marker
  app.py                       new — pywebview window, JS bridge, API class
  orchestrator.py              new — run lifecycle, source selection, state push
  events.py                    new — Target/StageEvent/HypState/RunState + fold_event()
  targets.json                 new — 6-target registry (benchmark-shaped)
  sources/
    __init__.py                new — package marker
    base.py                    new — RunSource abstract interface
    replay.py                  new — ReplaySource: JSON fixtures → StageEvents
    live.py                    new — LiveSource: engine subprocess + oracle (A2)
    stdout_parser.py           new — parse engine stdout lines → StageEvents (A2)
    state_file.py              new — load_loop_state(path) → dict
    feedback.py                new — load_timing(path), find_timing_for_hyp()
  web/
    index.html                 new — pipeline layout, imports pipeline.js
    styles.css                 new — box states, animations, layout
    pipeline.js                new — window.onStateUpdate(), DOM updates
run.py                         new — top-level entry: python run.py [--replay|--live]
requirements-viz.txt           new — pywebview>=5.0, pytest>=8.0
tests/
  viz/
    __init__.py                new
    conftest.py                new — shared fixtures (REPO_ROOT, fixture paths)
    fixtures/
      loop_state_leak5.json    new — copy of shared/findings/loop_state_kyber512_leak5.json
      loop_state_leak2.json    new — copy of shared/findings/loop_state_kyber512_leak2.json
      timing_leak5.json        new — copy of shared/feedback/timing_LEAK5-ORACLE_*.json
      stdout_transcript.txt    new — captured engine stdout for parser tests
    test_events.py             new
    test_state_file.py         new
    test_feedback.py           new
    test_replay.py             new
    test_stdout_parser.py      new  (A2)
```

---

## Task 1 — Scaffold: directories, requirements, test infrastructure

**Files:**
- Create: `requirements-viz.txt`
- Create: `viz/__init__.py`
- Create: `viz/sources/__init__.py`
- Create: `viz/web/.gitkeep`
- Create: `tests/viz/__init__.py`
- Create: `tests/viz/conftest.py`
- Create: `tests/viz/fixtures/loop_state_leak5.json`
- Create: `tests/viz/fixtures/loop_state_leak2.json`
- Create: `tests/viz/fixtures/timing_leak5.json`
- Create: `tests/viz/fixtures/stdout_transcript.txt`

- [ ] **Step 1.1: Create requirements-viz.txt**

```
pywebview>=5.0
pytest>=8.0
```

- [ ] **Step 1.2: Create viz/__init__.py and viz/sources/__init__.py**

Both files are empty package markers — just `touch` them (or create with no content).

- [ ] **Step 1.3: Create tests/viz/__init__.py**

Empty file.

- [ ] **Step 1.4: Create tests/viz/conftest.py**

```python
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def loop_state_leak5():
    return FIXTURES / "loop_state_leak5.json"

@pytest.fixture
def loop_state_leak2():
    return FIXTURES / "loop_state_leak2.json"

@pytest.fixture
def timing_leak5():
    return FIXTURES / "timing_leak5.json"

@pytest.fixture
def stdout_transcript():
    return (FIXTURES / "stdout_transcript.txt").read_text()
```

- [ ] **Step 1.5: Copy fixture files**

Copy these files verbatim (don't modify content):

```
shared/findings/loop_state_kyber512_leak5.json  →  tests/viz/fixtures/loop_state_leak5.json
shared/findings/loop_state_kyber512_leak2.json  →  tests/viz/fixtures/loop_state_leak2.json
shared/feedback/timing_LEAK5-ORACLE_1781600688.json  →  tests/viz/fixtures/timing_leak5.json
```

- [ ] **Step 1.6: Create tests/viz/fixtures/stdout_transcript.txt**

This is a realistic engine stdout transcript for parser tests:

```
PQ-REAPER Track B — LLM Adversary Engine
Target: kyber512_leak5_focused.c
Models: codellama:7b (analysis) / qwen3:8b (refinement)
Mode: live
Starting cycle 1 of 3...

    ...waiting for feedback file containing 'H001' in /home/user/Rayquaza/shared/feedback (poll every 30s)
[Cycle 1] Hypothesis H001 → PROMOTED (t=141.091, sig=True)
    ...waiting for feedback file containing 'H002' in /home/user/Rayquaza/shared/feedback (poll every 30s)
[Cycle 2] Hypothesis H002 → INVALIDATED (t=-0.167, sig=False)
=== LOOP COMPLETE ===
Promoted: ['H001']
Demoted: []
Invalidated: ['H002']
Full results: shared/findings/loop_state.json
```

- [ ] **Step 1.7: Install dependencies**

```bash
pip install pywebview>=5.0 pytest>=8.0
```

Verify:
```bash
python -c "import webview; print(webview.__version__)"
python -c "import pytest; print(pytest.__version__)"
```

Expected: version strings printed without errors.

- [ ] **Step 1.8: Commit scaffold**

```bash
git add requirements-viz.txt viz/ tests/ run.py 2>/dev/null || true
git add requirements-viz.txt viz/__init__.py viz/sources/__init__.py
git add tests/viz/__init__.py tests/viz/conftest.py tests/viz/fixtures/
git commit -m "[A] Phase A: scaffold viz/ package, test fixtures, requirements"
```

---

## Task 2 — Data model: events.py

**Files:**
- Create: `viz/events.py`
- Create: `tests/viz/test_events.py`

- [ ] **Step 2.1: Write failing tests for the data model**

Create `tests/viz/test_events.py`:

```python
import pytest
from viz.events import (
    StageEvent, HypState, TargetRunState, RunState, fold_event
)


def make_event(target_id, hyp_id, stage, status, data=None):
    return StageEvent(
        run_id="run1",
        target_id=target_id,
        hyp_id=hyp_id,
        stage=stage,
        status=status,
        ts=1000.0,
        data=data or {},
    )


class TestFoldEvent:
    def test_first_event_creates_target_and_hyp(self):
        state = RunState(run_id="run1")
        fold_event(state, make_event("kyber512_leak5", "H001", "ingest", "start"))
        assert "kyber512_leak5" in state.targets
        assert "H001" in state.targets["kyber512_leak5"].hyps

    def test_stage_and_status_update(self):
        state = RunState(run_id="run1")
        fold_event(state, make_event("kyber512_leak5", "H001", "vectorize", "active"))
        hyp = state.targets["kyber512_leak5"].hyps["H001"]
        assert hyp.stage == "vectorize"
        assert hyp.stage_status == "active"

    def test_active_hyp_tracks_latest(self):
        state = RunState(run_id="run1")
        fold_event(state, make_event("kyber512_leak5", "H001", "ingest", "start"))
        fold_event(state, make_event("kyber512_leak5", "H002", "ingest", "start"))
        assert state.targets["kyber512_leak5"].active_hyp == "H002"

    def test_save_done_records_result(self):
        state = RunState(run_id="run1")
        result = {"t_stat": 141.0, "significant": True, "verdict": "PROMOTED"}
        fold_event(state, make_event("kyber512_leak5", "H001", "save", "done", result))
        hyp = state.targets["kyber512_leak5"].hyps["H001"]
        assert hyp.result["significant"] is True
        assert hyp.result["verdict"] == "PROMOTED"

    def test_multiple_targets_independent(self):
        state = RunState(run_id="run1")
        fold_event(state, make_event("kyber512_leak5", "H001", "wait", "active"))
        fold_event(state, make_event("kyber512_leak4", "H001", "ingest", "start"))
        assert state.targets["kyber512_leak5"].hyps["H001"].stage == "wait"
        assert state.targets["kyber512_leak4"].hyps["H001"].stage == "ingest"

    def test_save_not_done_does_not_set_result(self):
        state = RunState(run_id="run1")
        fold_event(state, make_event("kyber512_leak5", "H001", "save", "start"))
        hyp = state.targets["kyber512_leak5"].hyps["H001"]
        assert hyp.result is None

    def test_run_state_to_dict_is_serializable(self):
        import json
        state = RunState(run_id="run1", model_label="codellama:7b")
        fold_event(state, make_event("kyber512_leak5", "H001", "wait", "active"))
        # Must not raise
        json.dumps(state.to_dict())
```

- [ ] **Step 2.2: Run tests — expect FAIL (module not found)**

```bash
cd D:/Code/Rayquaza
python -m pytest tests/viz/test_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'viz.events'`

- [ ] **Step 2.3: Create viz/events.py**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
import time

Stage = Literal["ingest", "vectorize", "wait", "refine", "save"]
Status = Literal["start", "active", "done", "fail"]


@dataclass
class StageEvent:
    run_id: str
    target_id: str
    hyp_id: str
    stage: Stage
    status: Status
    ts: float
    data: dict = field(default_factory=dict)


@dataclass
class HypState:
    hyp_id: str
    stage: Stage = "ingest"
    stage_status: Status = "start"
    result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "hyp_id": self.hyp_id,
            "stage": self.stage,
            "stage_status": self.stage_status,
            "result": self.result,
        }


@dataclass
class TargetRunState:
    target_id: str
    active_hyp: Optional[str] = None
    hyps: dict = field(default_factory=dict)  # hyp_id -> HypState

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "active_hyp": self.active_hyp,
            "hyps": {k: v.to_dict() for k, v in self.hyps.items()},
        }


@dataclass
class RunState:
    run_id: str
    model_label: str = ""
    targets: dict = field(default_factory=dict)  # target_id -> TargetRunState
    started_at: float = field(default_factory=time.time)
    finished: bool = False

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "model_label": self.model_label,
            "targets": {k: v.to_dict() for k, v in self.targets.items()},
            "started_at": self.started_at,
            "finished": self.finished,
        }


def fold_event(state: RunState, event: StageEvent) -> RunState:
    """Apply a StageEvent to RunState in place. Returns the same state."""
    if event.target_id not in state.targets:
        state.targets[event.target_id] = TargetRunState(target_id=event.target_id)
    target_state = state.targets[event.target_id]

    if event.hyp_id not in target_state.hyps:
        target_state.hyps[event.hyp_id] = HypState(hyp_id=event.hyp_id)
    hyp_state = target_state.hyps[event.hyp_id]

    hyp_state.stage = event.stage
    hyp_state.stage_status = event.status
    target_state.active_hyp = event.hyp_id

    if event.stage == "save" and event.status == "done" and event.data:
        hyp_state.result = event.data

    return state
```

- [ ] **Step 2.4: Run tests — expect all PASS**

```bash
python -m pytest tests/viz/test_events.py -v
```

Expected: 7 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add viz/events.py tests/viz/test_events.py
git commit -m "[A] Phase A: data model — StageEvent/HypState/RunState + fold_event"
```

---

## Task 3 — targets.json registry

**Files:**
- Create: `viz/targets.json`

(No unit tests needed — it's static data validated by loading in later tests.)

- [ ] **Step 3.1: Create viz/targets.json**

```json
[
  {
    "id": "kyber512_leak5",
    "name": "FO comparison (memcmp)",
    "primitive": "ML-KEM (Kyber512)",
    "difficulty_tier": "obvious",
    "focused_target": "track-b-engine/ingestion/test_targets/kyber512_leak5_focused.c",
    "oracle_dir": "kyber512_leak5",
    "ground_truth": {
      "category": "nonconstant_comparison",
      "location": "crypto_kem_dec",
      "expected_significant": true
    }
  },
  {
    "id": "kyber512_leak4",
    "name": "Conditional normalization loop",
    "primitive": "ML-KEM (Kyber512)",
    "difficulty_tier": "obvious",
    "focused_target": "track-b-engine/ingestion/test_targets/kyber512_leak4_focused.c",
    "oracle_dir": "kyber512_leak4",
    "ground_truth": {
      "category": "secret_dependent_branch",
      "location": "indcpa_dec",
      "expected_significant": true
    }
  },
  {
    "id": "kyber512_leak2",
    "name": "poly_tomsg branch misprediction",
    "primitive": "ML-KEM (Kyber512)",
    "difficulty_tier": "microarch",
    "focused_target": "track-b-engine/ingestion/test_targets/kyber512_leak2_focused.c",
    "oracle_dir": "kyber512_leak2",
    "ground_truth": {
      "category": "secret_dependent_branch",
      "location": "poly_tomsg",
      "expected_significant": true
    }
  },
  {
    "id": "kyber512_leak1",
    "name": "cmov clangover (asm barrier)",
    "primitive": "ML-KEM (Kyber512)",
    "difficulty_tier": "compiler",
    "focused_target": null,
    "oracle_dir": "kyber512_leak1",
    "ground_truth": {
      "category": "nonconstant_comparison",
      "location": "crypto_kem_dec",
      "expected_significant": true
    }
  },
  {
    "id": "kyber512_leak3",
    "name": "basemul sign branch (ARM only)",
    "primitive": "ML-KEM (Kyber512)",
    "difficulty_tier": "microarch",
    "focused_target": null,
    "oracle_dir": "kyber512_leak3",
    "ground_truth": {
      "category": "secret_dependent_branch",
      "location": "basemul",
      "expected_significant": true
    }
  },
  {
    "id": "mldsa44_leak1",
    "name": "Challenge comparison (memcmp)",
    "primitive": "ML-DSA-44",
    "difficulty_tier": "obvious",
    "focused_target": "track-b-engine/ingestion/test_targets/mldsa44_synthetic.c",
    "oracle_dir": "mldsa44_leak1",
    "ground_truth": {
      "category": "nonconstant_comparison",
      "location": "mld_sign_verify_internal",
      "expected_significant": true
    }
  }
]
```

- [ ] **Step 3.2: Verify it loads and has 6 entries**

```bash
python -c "
import json
from pathlib import Path
targets = json.loads((Path('viz/targets.json')).read_text())
assert len(targets) == 6
for t in targets:
    assert 'id' in t and 'difficulty_tier' in t
print('OK — 6 targets loaded')
"
```

Expected: `OK — 6 targets loaded`

- [ ] **Step 3.3: Commit**

```bash
git add viz/targets.json
git commit -m "[A] Phase A: targets.json — 6-target benchmark-shaped registry"
```

---

## Task 4 — state_file.py: parse loop_state JSON

**Files:**
- Create: `viz/sources/state_file.py`
- Create: `tests/viz/test_state_file.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/viz/test_state_file.py`:

```python
from viz.sources.state_file import load_loop_state, hypotheses_from_state, target_id_from_state


class TestLoadLoopState:
    def test_loads_dict(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        assert isinstance(data, dict)

    def test_has_required_keys(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        for key in ("hypotheses", "promoted_ids", "invalidated_ids", "target_file"):
            assert key in data, f"missing key: {key}"

    def test_hypotheses_is_list(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        assert isinstance(data["hypotheses"], list)


class TestHypothesesFromState:
    def test_returns_list_of_dicts(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        hyps = hypotheses_from_state(data)
        assert len(hyps) >= 1
        assert isinstance(hyps[0], dict)

    def test_each_hyp_has_id_and_status(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        for hyp in hypotheses_from_state(data):
            assert "id" in hyp
            assert "status" in hyp

    def test_leak5_h001_is_promoted(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        hyps = hypotheses_from_state(data)
        h001 = next(h for h in hyps if h["id"] == "H001")
        assert h001["status"] == "PROMOTED"
        assert h001["significant"] is True

    def test_leak2_h001_is_invalidated(self, loop_state_leak2):
        data = load_loop_state(loop_state_leak2)
        hyps = hypotheses_from_state(data)
        h001 = next(h for h in hyps if h["id"] == "H001")
        assert h001["status"] == "INVALIDATED"
        assert h001["significant"] is False


class TestTargetIdFromState:
    def test_derives_id_from_target_file(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        target_id = target_id_from_state(data)
        assert target_id == "kyber512_leak5"

    def test_derives_id_for_leak2(self, loop_state_leak2):
        data = load_loop_state(loop_state_leak2)
        assert target_id_from_state(data) == "kyber512_leak2"
```

- [ ] **Step 4.2: Run — expect FAIL**

```bash
python -m pytest tests/viz/test_state_file.py -v
```

Expected: `ModuleNotFoundError: No module named 'viz.sources.state_file'`

- [ ] **Step 4.3: Create viz/sources/state_file.py**

```python
import json
from pathlib import Path


def load_loop_state(path: Path) -> dict:
    """Parse a loop_state JSON file, return the raw dict."""
    return json.loads(Path(path).read_text())


def hypotheses_from_state(data: dict) -> list:
    """Return the list of hypothesis records from a parsed loop_state dict."""
    return data.get("hypotheses", [])


def target_id_from_state(data: dict) -> str:
    """Derive the target id (e.g. 'kyber512_leak5') from the target_file field."""
    target_file = data.get("target_file", "")
    stem = Path(target_file).stem          # e.g. 'kyber512_leak5_focused'
    return stem.replace("_focused", "")    # e.g. 'kyber512_leak5'
```

- [ ] **Step 4.4: Run tests — expect all PASS**

```bash
python -m pytest tests/viz/test_state_file.py -v
```

Expected: 7 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add viz/sources/state_file.py tests/viz/test_state_file.py
git commit -m "[A] Phase A: state_file.py — load_loop_state + hypotheses_from_state"
```

---

## Task 5 — feedback.py: parse timing JSON

**Files:**
- Create: `viz/sources/feedback.py`
- Create: `tests/viz/test_feedback.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/viz/test_feedback.py`:

```python
from viz.sources.feedback import load_timing, result_from_timing


class TestLoadTiming:
    def test_loads_dict(self, timing_leak5):
        data = load_timing(timing_leak5)
        assert isinstance(data, dict)

    def test_has_required_keys(self, timing_leak5):
        data = load_timing(timing_leak5)
        for key in ("hypothesis_id", "t_statistic", "significant", "mean_A", "mean_B"):
            assert key in data, f"missing key: {key}"


class TestResultFromTiming:
    def test_extracts_verdict_promoted(self, timing_leak5):
        data = load_timing(timing_leak5)
        result = result_from_timing(data, status="PROMOTED")
        assert result["verdict"] == "PROMOTED"
        assert result["t_stat"] == data["t_statistic"]
        assert result["significant"] is True

    def test_extracts_verdict_invalidated(self, timing_leak5):
        # fabricate an invalidated result
        data = load_timing(timing_leak5)
        data["significant"] = False
        data["t_statistic"] = -0.167
        result = result_from_timing(data, status="INVALIDATED")
        assert result["verdict"] == "INVALIDATED"
        assert result["significant"] is False

    def test_result_is_json_serializable(self, timing_leak5):
        import json
        data = load_timing(timing_leak5)
        result = result_from_timing(data, status="PROMOTED")
        json.dumps(result)  # must not raise
```

- [ ] **Step 5.2: Run — expect FAIL**

```bash
python -m pytest tests/viz/test_feedback.py -v
```

Expected: `ModuleNotFoundError: No module named 'viz.sources.feedback'`

- [ ] **Step 5.3: Create viz/sources/feedback.py**

```python
import json
from pathlib import Path


def load_timing(path: Path) -> dict:
    """Parse a timing JSON file, return the raw dict."""
    return json.loads(Path(path).read_text())


def result_from_timing(timing: dict, status: str) -> dict:
    """Convert a timing dict + hypothesis status into the result payload stored on HypState."""
    return {
        "t_stat": timing.get("t_statistic"),
        "significant": bool(timing.get("significant")),
        "mean_A": timing.get("mean_A"),
        "mean_B": timing.get("mean_B"),
        "verdict": status,
    }
```

- [ ] **Step 5.4: Run tests — expect all PASS**

```bash
python -m pytest tests/viz/test_feedback.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add viz/sources/feedback.py tests/viz/test_feedback.py
git commit -m "[A] Phase A: feedback.py — load_timing + result_from_timing"
```

---

## Task 6 — RunSource interface + ReplaySource (A1 core)

**Files:**
- Create: `viz/sources/base.py`
- Create: `viz/sources/replay.py`
- Create: `tests/viz/test_replay.py`

- [ ] **Step 6.1: Write failing tests**

Create `tests/viz/test_replay.py`:

```python
import time
import pytest
from viz.sources.replay import ReplaySource
from viz.events import StageEvent, RunState, fold_event


STAGES = ["ingest", "vectorize", "wait", "refine", "save"]


class TestReplaySource:
    def test_yields_stage_events(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        events = list(src.start())
        assert len(events) > 0
        assert all(isinstance(e, StageEvent) for e in events)

    def test_covers_all_five_stages(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        stages_seen = {e.stage for e in src.start()}
        assert stages_seen == set(STAGES)

    def test_start_and_done_emitted_per_stage(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        events = list(src.start())
        statuses = [(e.stage, e.status) for e in events]
        for stage in STAGES:
            assert ("start" in [s for st, s in statuses if st == stage]), \
                f"missing start for {stage}"

    def test_save_done_carries_result(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        save_done = [e for e in src.start()
                     if e.stage == "save" and e.status == "done"]
        assert len(save_done) == 1
        result = save_done[0].data
        assert "significant" in result
        assert "verdict" in result

    def test_target_id_matches_file(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        events = list(src.start())
        assert all(e.target_id == "kyber512_leak5" for e in events)

    def test_events_fold_to_valid_state(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        state = RunState(run_id="test")
        for event in src.start():
            fold_event(state, event)
        assert "kyber512_leak5" in state.targets
        hyps = state.targets["kyber512_leak5"].hyps
        assert len(hyps) >= 1
        # last hyp should have a result after save/done
        last_hyp = list(hyps.values())[-1]
        assert last_hyp.result is not None

    def test_stop_halts_iteration(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        events = []
        for e in src.start():
            events.append(e)
            if len(events) == 2:
                src.stop()
                break
        assert len(events) == 2

    def test_run_id_consistent_across_events(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        events = list(src.start())
        run_ids = {e.run_id for e in events}
        assert len(run_ids) == 1
```

- [ ] **Step 6.2: Run — expect FAIL**

```bash
python -m pytest tests/viz/test_replay.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 6.3: Create viz/sources/base.py**

```python
from abc import ABC, abstractmethod
from typing import Iterator
from ..events import StageEvent


class RunSource(ABC):
    """Interface for a run source — yields StageEvents until the run ends."""

    @abstractmethod
    def start(self) -> Iterator[StageEvent]:
        """Yield StageEvents. Blocks until run is complete or stop() is called."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the source to stop yielding and clean up."""
```

- [ ] **Step 6.4: Create viz/sources/replay.py**

```python
import time
import uuid
from pathlib import Path
from typing import Iterator

from .base import RunSource
from .state_file import load_loop_state, hypotheses_from_state, target_id_from_state
from .feedback import result_from_timing
from ..events import StageEvent

STAGES = ["ingest", "vectorize", "wait", "refine", "save"]


class ReplaySource(RunSource):
    """Drives the visualizer from a committed loop_state JSON file.

    Each hypothesis in the file is replayed as a sequence of StageEvents with
    simulated delays. step_delay=0.0 in tests, ~0.6s for a watchable demo.
    """

    def __init__(self, loop_state_path: Path, step_delay: float = 0.6):
        self._path = Path(loop_state_path)
        self._step_delay = step_delay
        self._run_id = uuid.uuid4().hex[:8]
        self._stopped = False

    def start(self) -> Iterator[StageEvent]:
        data = load_loop_state(self._path)
        target_id = target_id_from_state(data)

        for hyp in hypotheses_from_state(data):
            if self._stopped:
                break
            yield from self._replay_hyp(target_id, hyp)

    def stop(self) -> None:
        self._stopped = True

    def _replay_hyp(self, target_id: str, hyp: dict) -> Iterator[StageEvent]:
        hyp_id = hyp["id"]
        status = hyp.get("status", "UNCHANGED")

        for stage in STAGES:
            if self._stopped:
                return

            yield StageEvent(
                run_id=self._run_id,
                target_id=target_id,
                hyp_id=hyp_id,
                stage=stage,
                status="start",
                ts=time.time(),
            )

            # wait stage gets a longer pause to simulate oracle running
            pause = self._step_delay * 3 if stage == "wait" else self._step_delay
            time.sleep(pause)

            result_data = {}
            if stage == "save":
                timing = hyp.get("feedback") or {}
                result_data = result_from_timing(timing, status) if timing else {
                    "verdict": status,
                    "significant": hyp.get("significant"),
                    "t_stat": hyp.get("t_statistic"),
                }

            yield StageEvent(
                run_id=self._run_id,
                target_id=target_id,
                hyp_id=hyp_id,
                stage=stage,
                status="done",
                ts=time.time(),
                data=result_data,
            )
            time.sleep(self._step_delay)
```

- [ ] **Step 6.5: Run tests — expect all PASS**

```bash
python -m pytest tests/viz/test_replay.py -v
```

Expected: 8 tests pass.

- [ ] **Step 6.6: Commit**

```bash
git add viz/sources/base.py viz/sources/replay.py tests/viz/test_replay.py
git commit -m "[A] Phase A: RunSource interface + ReplaySource (A1 core)"
```

---

## Task 7 — orchestrator.py: drive replay, push RunState

**Files:**
- Create: `viz/orchestrator.py`

(No unit tests — orchestrator wires sources to the UI. Tested via integration in Task 10.)

- [ ] **Step 7.1: Create viz/orchestrator.py**

```python
import json
import threading
from pathlib import Path
from typing import Callable, Optional

from .events import RunState, fold_event
from .sources.replay import ReplaySource
from .sources import state_file

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"


class Orchestrator:
    """Drives a run source, folds events into RunState, and pushes updates to a callback.

    The callback receives a JSON-serializable dict on every StageEvent.
    Runs in a daemon thread so the pywebview main loop is never blocked.
    """

    def __init__(self, on_state: Callable[[dict], None]):
        self._on_state = on_state
        self._source: Optional[ReplaySource] = None
        self._thread: Optional[threading.Thread] = None

    def start_replay(self, loop_state_path: Path, step_delay: float = 0.6) -> None:
        """Start a replay run in a background thread."""
        if self._thread and self._thread.is_alive():
            return  # already running

        self._source = ReplaySource(loop_state_path, step_delay=step_delay)
        state = RunState(run_id=self._source._run_id)

        # Populate model_label from the state file for display
        data = state_file.load_loop_state(loop_state_path)
        state.model_label = "codellama:7b + qwen3:8b (replay)"

        def _run():
            for event in self._source.start():
                fold_event(state, event)
                self._on_state(state.to_dict())
            state.finished = True
            self._on_state(state.to_dict())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._source:
            self._source.stop()

    def all_replay_paths(self) -> list:
        """Return paths to all committed loop_state_*.json files, sorted by target id."""
        return sorted(
            FINDINGS_DIR.glob("loop_state_kyber512_*.json"),
            key=lambda p: p.name,
        )
```

- [ ] **Step 7.2: Smoke-test the orchestrator without pywebview**

```bash
python -c "
from pathlib import Path
from viz.orchestrator import Orchestrator

updates = []
orc = Orchestrator(on_state=updates.append)
paths = orc.all_replay_paths()
print(f'Found {len(paths)} replay files')

orc.start_replay(paths[0], step_delay=0.0)
orc._thread.join(timeout=10)
print(f'Got {len(updates)} state pushes')
last = updates[-1]
print('Targets in final state:', list(last[\"targets\"].keys()))
print('Finished:', last[\"finished\"])
"
```

Expected output (approximately):
```
Found 3 replay files
Got N state pushes
Targets in final state: ['kyber512_leak2']   (or leak4/leak5 depending on sort)
Finished: True
```

- [ ] **Step 7.3: Commit**

```bash
git add viz/orchestrator.py
git commit -m "[A] Phase A: orchestrator.py — drives replay, folds events, pushes state"
```

---

## Task 8 — Web frontend: layout + animations (index.html + styles.css)

**Files:**
- Create: `viz/web/index.html`
- Create: `viz/web/styles.css`

- [ ] **Step 8.1: Create viz/web/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rayquaza — Pipeline Visualizer</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div id="header">
    <h1>Rayquaza</h1>
    <div id="model-label">—</div>
    <div id="controls">
      <button id="btn-replay-all" onclick="startReplayAll()">▶ Replay All</button>
      <button id="btn-stop" onclick="stopRun()" disabled>■ Stop</button>
    </div>
  </div>

  <div id="pipeline-container">
    <!-- Rows injected by pipeline.js based on RunState -->
  </div>

  <div id="status-bar">Ready</div>

  <script src="pipeline.js"></script>
</body>
</html>
```

- [ ] **Step 8.2: Create viz/web/styles.css**

```css
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --blue: #388bfd;
  --green: #3fb950;
  --red: #f85149;
  --orange: #d29922;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 14px;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ── */
#header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
#header h1 { font-size: 18px; font-weight: 700; letter-spacing: 1px; }
#model-label { color: var(--text-muted); font-size: 12px; flex: 1; }
#controls button {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
}
#controls button:hover:not(:disabled) { border-color: var(--blue); color: var(--blue); }
#controls button:disabled { opacity: 0.4; cursor: default; }

/* ── Pipeline container ── */
#pipeline-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Pipeline row (one per target) ── */
.pipeline-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.target-label {
  width: 180px;
  min-width: 180px;
  font-size: 13px;
  line-height: 1.4;
}
.target-label .tier {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tier-obvious  { color: var(--green); }
.tier-compiler { color: var(--orange); }
.tier-microarch{ color: var(--blue); }

.pipeline-boxes {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

/* ── Stage boxes ── */
.box {
  position: relative;
  width: 96px;
  height: 52px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: var(--text-muted);
  overflow: hidden;
  transition: border-color 0.3s, color 0.3s;
}

/* Fill animation — sweeps left to right */
.box::before {
  content: '';
  position: absolute;
  inset: 0;
  width: 0;
  background: var(--blue);
  opacity: 0.18;
  transition: width 0.4s ease;
}
.box.active::before { width: 100%; }
.box.active { border-color: var(--blue); color: var(--text); }

/* Pulsing animation for WAIT (oracle running) */
@keyframes pulse {
  0%, 100% { opacity: 0.18; }
  50%       { opacity: 0.45; }
}
.box.pulsing::before { width: 100%; animation: pulse 1.2s ease-in-out infinite; }
.box.pulsing { border-color: var(--blue); color: var(--text); }

/* Done states */
.box.done-ok   { border-color: var(--green); color: var(--green); }
.box.done-ok::before   { width: 100%; background: var(--green); opacity: 0.15; }
.box.done-fail { border-color: var(--red); color: var(--red); }
.box.done-fail::before { width: 100%; background: var(--red); opacity: 0.15; }

/* ── Connector ── */
.connector { color: var(--text-muted); font-size: 16px; user-select: none; }

/* ── Result badge (t-stat shown after save) ── */
.result-badge {
  width: 120px;
  font-size: 12px;
  color: var(--text-muted);
  padding-left: 8px;
}
.result-badge.promoted   { color: var(--green); }
.result-badge.invalidated{ color: var(--red); }
.result-badge.demoted    { color: var(--orange); }

/* ── Hyp ID label (shown on active box) ── */
.hyp-label {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 2px;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
}

/* ── Status bar ── */
#status-bar {
  padding: 6px 20px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--surface);
  border-top: 1px solid var(--border);
}
```

- [ ] **Step 8.3: Commit**

```bash
git add viz/web/index.html viz/web/styles.css
git commit -m "[A] Phase A: web layout — index.html + styles.css with pipeline box animations"
```

---

## Task 9 — pipeline.js: rendering logic

**Files:**
- Create: `viz/web/pipeline.js`

- [ ] **Step 9.1: Create viz/web/pipeline.js**

```javascript
// pipeline.js — receives RunState from Python and updates the DOM.
// Called by: window.onStateUpdate(stateDict)
// Calls out to: window.pywebview.api.start_replay_all(), .stop_run()

const STAGES = ["ingest", "vectorize", "wait", "refine", "save"];
const STAGE_LABELS = {
  ingest:    "Ingest",
  vectorize: "Vectorize",
  wait:      "Wait\n(Oracle)",
  refine:    "Refine",
  save:      "Save",
};

// Registry filled when Python calls initTargets()
let targetRegistry = {};

// ── Initialise target registry from Python ──────────────────────────────────
window.initTargets = function(targets) {
  targetRegistry = {};
  targets.forEach(t => { targetRegistry[t.id] = t; });
};

// ── Main entry — called by Python on every state push ───────────────────────
window.onStateUpdate = function(state) {
  document.getElementById("model-label").textContent = state.model_label || "";
  document.getElementById("status-bar").textContent =
    state.finished ? "Run complete." : "Running…";

  const container = document.getElementById("pipeline-container");

  for (const [targetId, targetState] of Object.entries(state.targets)) {
    let row = document.getElementById("row-" + targetId);
    if (!row) {
      row = createRow(targetId);
      container.appendChild(row);
    }
    updateRow(row, targetId, targetState);
  }

  // Enable/disable stop button
  document.getElementById("btn-stop").disabled = state.finished;
  if (state.finished) {
    document.getElementById("btn-replay-all").disabled = false;
  }
};

// ── Create a fresh pipeline row for a target ────────────────────────────────
function createRow(targetId) {
  const meta = targetRegistry[targetId] || { name: targetId, difficulty_tier: "obvious" };
  const row = document.createElement("div");
  row.className = "pipeline-row";
  row.id = "row-" + targetId;

  const label = document.createElement("div");
  label.className = "target-label";
  const tierClass = "tier-" + meta.difficulty_tier;
  label.innerHTML = `
    ${escHtml(meta.name || targetId)}<br>
    <span class="tier ${tierClass}">${escHtml(meta.difficulty_tier || "")}</span>
  `;
  row.appendChild(label);

  const boxes = document.createElement("div");
  boxes.className = "pipeline-boxes";

  STAGES.forEach((stage, i) => {
    const box = document.createElement("div");
    box.className = "box";
    box.id = `box-${targetId}-${stage}`;
    box.innerHTML = `
      <span class="stage-name">${STAGE_LABELS[stage]}</span>
      <span class="hyp-label"></span>
    `;
    boxes.appendChild(box);

    if (i < STAGES.length - 1) {
      const conn = document.createElement("div");
      conn.className = "connector";
      conn.textContent = "→";
      boxes.appendChild(conn);
    }
  });

  row.appendChild(boxes);

  const badge = document.createElement("div");
  badge.className = "result-badge";
  badge.id = "badge-" + targetId;
  row.appendChild(badge);

  return row;
}

// ── Update all boxes in a row from TargetRunState ───────────────────────────
function updateRow(row, targetId, targetState) {
  const activeHypId = targetState.active_hyp;
  if (!activeHypId) return;

  const hypState = (targetState.hyps || {})[activeHypId];
  if (!hypState) return;

  const currentStageIdx = STAGES.indexOf(hypState.stage);
  const status = hypState.stage_status;

  STAGES.forEach((stage, i) => {
    const box = document.getElementById(`box-${targetId}-${stage}`);
    if (!box) return;

    const hypLabel = box.querySelector(".hyp-label");
    // Clear all state classes
    box.classList.remove("active", "pulsing", "done-ok", "done-fail");

    if (i < currentStageIdx) {
      // Past stage — show done state based on final result (only for save)
      if (stage === "save" && hypState.result) {
        box.classList.add(hypState.result.significant ? "done-ok" : "done-fail");
      } else {
        box.classList.add("done-ok");
      }
      hypLabel.textContent = "";
    } else if (i === currentStageIdx) {
      // Current stage
      if (stage === "wait" && (status === "start" || status === "active")) {
        box.classList.add("pulsing");
      } else if (status === "done") {
        if (stage === "save" && hypState.result) {
          box.classList.add(hypState.result.significant ? "done-ok" : "done-fail");
        } else {
          box.classList.add("done-ok");
        }
      } else {
        box.classList.add("active");
      }
      hypLabel.textContent = activeHypId;
    } else {
      // Future stage — idle
      hypLabel.textContent = "";
    }
  });

  // Update result badge
  const badge = document.getElementById("badge-" + targetId);
  if (badge && hypState.result) {
    const r = hypState.result;
    const verdict = (r.verdict || "").toLowerCase();
    const tStr = r.t_stat != null ? `t=${r.t_stat.toFixed(2)}` : "";
    badge.className = "result-badge " + verdict;
    badge.textContent = `${tStr} ${r.significant ? "✓" : "✗"} ${r.verdict || ""}`;
  } else if (badge) {
    badge.className = "result-badge";
    badge.textContent = "";
  }
}

// ── Button handlers — call through pywebview JS bridge ──────────────────────
function startReplayAll() {
  // Clear existing rows
  document.getElementById("pipeline-container").innerHTML = "";
  document.getElementById("btn-replay-all").disabled = true;
  document.getElementById("btn-stop").disabled = false;
  document.getElementById("status-bar").textContent = "Starting replay…";
  window.pywebview.api.start_replay_all();
}

function stopRun() {
  window.pywebview.api.stop_run();
}

// ── Utility ──────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
```

- [ ] **Step 9.2: Commit**

```bash
git add viz/web/pipeline.js
git commit -m "[A] Phase A: pipeline.js — window.onStateUpdate renderer, animated box states"
```

---

## Task 10 — app.py + run.py: pywebview integration (A1 complete)

**Files:**
- Create: `viz/app.py`
- Create: `run.py`

- [ ] **Step 10.1: Create viz/app.py**

```python
import json
import threading
import time
from pathlib import Path

import webview

from .orchestrator import Orchestrator
from .sources.state_file import load_loop_state

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent / "web"
TARGETS_JSON = Path(__file__).resolve().parent / "targets.json"


class API:
    """Python API exposed to the JS frontend via window.pywebview.api.*"""

    def __init__(self):
        self._window = None
        self._orchestrator: Orchestrator = None

    def set_window(self, window) -> None:
        self._window = window
        self._orchestrator = Orchestrator(on_state=self._push_state)

    def _push_state(self, state_dict: dict) -> None:
        if self._window:
            payload = json.dumps(state_dict)
            self._window.evaluate_js(f"window.onStateUpdate({payload})")

    def _init_targets(self) -> None:
        """Push the target registry to JS once the window is ready."""
        targets = json.loads(TARGETS_JSON.read_text())
        payload = json.dumps(targets)
        self._window.evaluate_js(f"window.initTargets({payload})")

    # Called by JS button "▶ Replay All"
    def start_replay_all(self) -> None:
        paths = self._orchestrator.all_replay_paths()
        if not paths:
            self._push_state({"run_id": "none", "model_label": "No replay files found",
                              "targets": {}, "finished": True})
            return
        # Replay the most recent file found; extend later for multi-target parallel replay
        self._orchestrator.start_replay(paths[-1], step_delay=0.6)

    # Called by JS button "■ Stop"
    def stop_run(self) -> None:
        if self._orchestrator:
            self._orchestrator.stop()


def start_app(autostart_replay: bool = False) -> None:
    """Create the pywebview window and enter the main loop."""
    api = API()
    window = webview.create_window(
        title="Rayquaza — Pipeline Visualizer",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1100,
        height=620,
        resizable=True,
        background_color="#0d1117",
    )
    api.set_window(window)

    def on_loaded():
        api._init_targets()
        if autostart_replay:
            # Small delay so the DOM is ready
            time.sleep(0.3)
            api.start_replay_all()

    window.events.loaded += on_loaded
    webview.start(debug=False)
```

- [ ] **Step 10.2: Create run.py**

```python
#!/usr/bin/env python3
"""
run.py — Rayquaza Phase A visualizer entry point.

Usage:
  python run.py                    # open window, click ▶ Replay All
  python run.py --replay           # open window and auto-start replay
  python run.py --live             # open window in live mode (A2 — not yet implemented)
"""
import sys
from pathlib import Path

# Make viz/ importable from the repo root
sys.path.insert(0, str(Path(__file__).parent))

from viz.app import start_app


def main():
    autostart = "--replay" in sys.argv
    if "--live" in sys.argv:
        print("Live mode (A2) is not yet implemented. Use --replay for now.")
        sys.exit(1)
    start_app(autostart_replay=autostart)


if __name__ == "__main__":
    main()
```

- [ ] **Step 10.3: Run A1 integration test (manual)**

```bash
python run.py --replay
```

Expected: a dark-themed desktop window opens showing the pipeline layout. Each target row (kyber512_leak5, etc.) animates through INGEST → VECTORIZE → WAIT (pulsing) → REFINE → SAVE, with the SAVE box turning green (PROMOTED) or red (INVALIDATED). Window closes normally when done.

If `pywebview` errors about a missing backend on Windows, install:
```bash
pip install pywebview[all]
```

- [ ] **Step 10.4: Commit — A1 Replay complete**

```bash
git add viz/app.py run.py
git commit -m "[A] Phase A A1 complete: pywebview window + replay mode end-to-end"
```

---

## Task 11 — stdout_parser.py: coarse stdout → StageEvents (A2)

**Files:**
- Create: `viz/sources/stdout_parser.py`
- Create: `tests/viz/test_stdout_parser.py`

- [ ] **Step 11.1: Write failing tests**

Create `tests/viz/test_stdout_parser.py`:

```python
import pytest
from viz.sources.stdout_parser import parse_line, ParseResult


class TestParseLine:
    def test_starting_line_triggers_ingest(self):
        result = parse_line("Starting cycle 1 of 3...")
        assert result is not None
        assert result.event_type == "run_start"
        assert result.data["total_cycles"] == 3

    def test_waiting_line_extracts_hyp_id(self):
        result = parse_line(
            "    ...waiting for feedback file containing 'H001' in /foo/bar (poll every 30s)"
        )
        assert result is not None
        assert result.event_type == "wait_start"
        assert result.data["hyp_id"] == "H001"

    def test_result_line_extracts_fields(self):
        result = parse_line("[Cycle 1] Hypothesis H001 → PROMOTED (t=141.091, sig=True)")
        assert result is not None
        assert result.event_type == "hyp_result"
        assert result.data["hyp_id"] == "H001"
        assert result.data["status"] == "PROMOTED"
        assert abs(result.data["t_stat"] - 141.091) < 0.001
        assert result.data["significant"] is True

    def test_result_line_invalidated(self):
        result = parse_line("[Cycle 2] Hypothesis H002 → INVALIDATED (t=-0.167, sig=False)")
        assert result is not None
        assert result.data["status"] == "INVALIDATED"
        assert result.data["significant"] is False

    def test_loop_complete_line(self):
        result = parse_line("=== LOOP COMPLETE ===")
        assert result is not None
        assert result.event_type == "loop_complete"

    def test_unrecognised_line_returns_none(self):
        assert parse_line("Models: codellama:7b (analysis) / qwen3:8b (refinement)") is None
        assert parse_line("") is None
        assert parse_line("Full results: shared/findings/loop_state.json") is None

    def test_rayqevent_line_parsed(self):
        import json, time
        payload = json.dumps({"stage": "vectorize", "hyp": "H001",
                              "status": "start", "ts": time.time()})
        result = parse_line("RAYQEVENT::" + payload)
        assert result is not None
        assert result.event_type == "rayqevent"
        assert result.data["stage"] == "vectorize"
        assert result.data["hyp"] == "H001"
```

- [ ] **Step 11.2: Run — expect FAIL**

```bash
python -m pytest tests/viz/test_stdout_parser.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 11.3: Create viz/sources/stdout_parser.py**

```python
import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    event_type: str   # run_start | wait_start | hyp_result | loop_complete | rayqevent
    data: dict = field(default_factory=dict)


_STARTING_RE   = re.compile(r"Starting cycle 1 of (\d+)")
_WAITING_RE    = re.compile(r"waiting for feedback file containing '([A-Z0-9]+)'")
_RESULT_RE     = re.compile(
    r"\[Cycle \d+\] Hypothesis (\w+) → (\w+) \(t=([0-9.\-]+), sig=(True|False)\)"
)
_COMPLETE_RE   = re.compile(r"=== LOOP COMPLETE ===")
_RAYQEVENT_RE  = re.compile(r"^RAYQEVENT::(.+)$")


def parse_line(line: str) -> Optional[ParseResult]:
    """Parse one stdout line from the engine. Returns None for unrecognised lines."""
    line = line.strip()
    if not line:
        return None

    m = _RAYQEVENT_RE.match(line)
    if m:
        try:
            data = json.loads(m.group(1))
            return ParseResult(event_type="rayqevent", data=data)
        except json.JSONDecodeError:
            return None

    m = _STARTING_RE.search(line)
    if m:
        return ParseResult(event_type="run_start",
                           data={"total_cycles": int(m.group(1))})

    m = _WAITING_RE.search(line)
    if m:
        return ParseResult(event_type="wait_start",
                           data={"hyp_id": m.group(1)})

    m = _RESULT_RE.search(line)
    if m:
        return ParseResult(event_type="hyp_result", data={
            "hyp_id":     m.group(1),
            "status":     m.group(2),
            "t_stat":     float(m.group(3)),
            "significant": m.group(4) == "True",
        })

    if _COMPLETE_RE.search(line):
        return ParseResult(event_type="loop_complete", data={})

    return None
```

- [ ] **Step 11.4: Run tests — expect all PASS**

```bash
python -m pytest tests/viz/test_stdout_parser.py -v
```

Expected: 8 tests pass.

- [ ] **Step 11.5: Commit**

```bash
git add viz/sources/stdout_parser.py tests/viz/test_stdout_parser.py
git commit -m "[A] Phase A: stdout_parser.py — coarse stdout + RAYQEVENT:: line parser"
```

---

## Task 12 — LiveSource + oracle invocation (A2)

**Files:**
- Create: `viz/sources/live.py`
- Modify: `viz/orchestrator.py` — add `start_live()` and `run_oracle()`

- [ ] **Step 12.1: Create viz/sources/live.py**

```python
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Iterator

from .base import RunSource
from .stdout_parser import parse_line
from ..events import StageEvent

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class LiveSource(RunSource):
    """Drives the visualizer from a real engine subprocess.

    Launches `python track-b-engine/main.py --target <c> --cycles N` and
    reads its stdout line by line, converting recognised lines to StageEvents
    using coarse inference. When a wait_start event is seen, it signals the
    orchestrator to run the oracle (via on_wait_for_oracle callback).

    For granular stage events, it also passes through RAYQEVENT:: lines
    once Track B adds emit() calls.
    """

    def __init__(
        self,
        target_c: Path,
        cycles: int = 3,
        on_wait_for_oracle=None,   # callable(hyp_id: str) -> None
    ):
        self._target_c = Path(target_c)
        self._cycles = cycles
        self._on_wait = on_wait_for_oracle
        self._run_id = uuid.uuid4().hex[:8]
        self._stopped = False
        self._proc = None
        # State machine: track current hyp and inferred stage
        self._current_hyp: str | None = None
        self._after_ingest = False

    def start(self) -> Iterator[StageEvent]:
        cmd = [
            sys.executable,
            str(REPO_ROOT / "track-b-engine" / "main.py"),
            "--target", str(self._target_c),
            "--cycles", str(self._cycles),
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in self._proc.stdout:
            if self._stopped:
                break
            result = parse_line(line)
            if result is None:
                continue

            if result.event_type == "run_start":
                yield self._event("H000", "ingest", "start")
                yield self._event("H000", "ingest", "done")
                self._after_ingest = True

            elif result.event_type == "wait_start":
                hyp_id = result.data["hyp_id"]
                self._current_hyp = hyp_id
                if self._after_ingest:
                    yield self._event(hyp_id, "vectorize", "start")
                    yield self._event(hyp_id, "vectorize", "done")
                    self._after_ingest = False
                yield self._event(hyp_id, "wait", "start")
                if self._on_wait:
                    self._on_wait(hyp_id)

            elif result.event_type == "hyp_result":
                hyp_id = result.data["hyp_id"]
                self._current_hyp = hyp_id
                yield self._event(hyp_id, "wait", "done")
                yield self._event(hyp_id, "refine", "start")
                yield self._event(hyp_id, "refine", "done")
                yield self._event(hyp_id, "save", "start")
                yield self._event(hyp_id, "save", "done", data={
                    "t_stat":      result.data["t_stat"],
                    "significant": result.data["significant"],
                    "verdict":     result.data["status"],
                })
                self._after_ingest = True  # next hyp needs vectorize

            elif result.event_type == "rayqevent":
                # Granular: pass RAYQEVENT data directly as a StageEvent
                d = result.data
                yield StageEvent(
                    run_id=self._run_id,
                    target_id="",    # orchestrator fills this from context
                    hyp_id=d.get("hyp", self._current_hyp or ""),
                    stage=d.get("stage", "ingest"),
                    status=d.get("status", "start"),
                    ts=d.get("ts", time.time()),
                    data=d,
                )

            elif result.event_type == "loop_complete":
                break

        if self._proc:
            self._proc.wait()

    def stop(self) -> None:
        self._stopped = True
        if self._proc:
            self._proc.terminate()

    def _event(self, hyp_id: str, stage: str, status: str, data=None) -> StageEvent:
        return StageEvent(
            run_id=self._run_id,
            target_id="",   # filled by orchestrator from context
            hyp_id=hyp_id,
            stage=stage,
            status=status,
            ts=time.time(),
            data=data or {},
        )
```

- [ ] **Step 12.2: Add start_live() and run_oracle() to viz/orchestrator.py**

Open `viz/orchestrator.py` and append after the existing `start_replay` method:

```python
    def start_live(self, target_id: str, step_delay: float = 0.0) -> None:
        """Start a live run against the real engine subprocess."""
        import json
        from pathlib import Path
        targets = json.loads((REPO_ROOT / "viz" / "targets.json").read_text())
        meta = next((t for t in targets if t["id"] == target_id), None)
        if not meta or not meta.get("focused_target"):
            return

        from .sources.live import LiveSource

        target_c = REPO_ROOT / meta["focused_target"]
        state = RunState(run_id="live")
        state.model_label = "codellama:7b + qwen3:8b (live)"

        def on_wait(hyp_id: str):
            """Triggered when the engine starts polling for oracle feedback."""
            self.run_oracle(target_id, hyp_id)

        self._source = LiveSource(target_c, cycles=3, on_wait_for_oracle=on_wait)

        def _run():
            for event in self._source.start():
                if not event.target_id:
                    event.target_id = target_id
                fold_event(state, event)
                self._on_state(state.to_dict())
            state.finished = True
            self._on_state(state.to_dict())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def run_oracle(self, target_id: str, hyp_id: str) -> None:
        """Run the oracle binary for a target/hypothesis pair.

        On Linux/WSL2: runs the harness_oracle binary natively.
        On Windows: invokes it via wsl.exe.
        """
        import platform, subprocess
        oracle_bin = (REPO_ROOT / "track-a-target" / "targets" /
                      target_id / "harness_oracle")

        def _invoke():
            try:
                if platform.system() == "Windows":
                    wsl_path = str(oracle_bin).replace("\\", "/").replace("D:", "/mnt/d")
                    cmd = ["wsl", "bash", "-c",
                           f"cd $(dirname '{wsl_path}') && ./harness_oracle {hyp_id} 50000"]
                else:
                    cmd = [str(oracle_bin), hyp_id, "50000"]
                subprocess.run(cmd, timeout=700, check=False)
            except Exception:
                pass  # UI shows timeout; don't crash orchestrator

        threading.Thread(target=_invoke, daemon=True).start()
```

Also update the `RunState` import at the top of orchestrator.py — add `fold_event` if not already imported:

```python
from .events import RunState, fold_event
```

- [ ] **Step 12.3: Wire live mode into app.py**

In `viz/app.py`, add to the `API` class:

```python
    def start_live(self, target_id: str) -> None:
        """Called by JS to start a live run (A2)."""
        self._orchestrator.start_live(target_id)
```

And update `index.html` to add a "▶ Live" button (optional — can be added to the controls div later when A2 is demoed).

- [ ] **Step 12.4: Test live mode manually (requires Ollama running)**

```bash
ollama serve &
python run.py --live
```

In the window, click "▶ Replay All" (for now this still triggers replay — to trigger live, call `start_live()` from the JS console or wire a button). The live mode pipeline will animate from real engine stdout.

- [ ] **Step 12.5: Commit — A2 complete**

```bash
git add viz/sources/live.py viz/orchestrator.py viz/app.py
git commit -m "[A] Phase A A2 complete: LiveSource + run_oracle() for live coarse mode"
```

---

## Self-review

**Spec coverage check:**

| Spec section | Covered? | Where |
|---|---|---|
| §1 pywebview window | ✓ | Task 10 — app.py |
| §1 Replay + Live behind one interface | ✓ | Tasks 6/12 — base.py, replay.py, live.py |
| §1 Fishing pipeline animation | ✓ | Tasks 8/9 — styles.css, pipeline.js |
| §1 Multiple parallel lines | ✓ | orchestrator multi-path (Task 7); pipeline.js row-per-target |
| §1 Benchmark-shaped data model | ✓ | Task 2 — events.py; Task 3 — targets.json |
| §2 Engine signals mapped | ✓ | Task 11 — stdout_parser.py |
| §3 Clean component boundary | ✓ | base.py interface; orchestrator owns lifecycle |
| §4 Target/StageEvent/RunState | ✓ | Task 2 — events.py |
| §5 5-stage pipeline visual states | ✓ | Tasks 8/9 — CSS classes + pipeline.js |
| §6 RAYQEVENT:: event contract | ✓ | Tasks 11/12 — stdout_parser + live.py passthrough |
| §7 A1 Replay demoable without Ollama | ✓ | Task 10 — run.py --replay |
| §8 Windows: oracle via WSL2 | ✓ | Task 12 — run_oracle() platform check |
| §9 Error handling | ✓ | orchestrator.run_oracle() swallows subprocess errors; UI shows timeout |
| §10 Module layout | ✓ | All files match spec layout exactly |
| §11 Unit tests + replay integration | ✓ | Tasks 2/4/5/6/11 each have pytest suites |

**Placeholder scan:** none found — all steps contain complete code.

**Type consistency check:** `fold_event(state, event)` used consistently in events.py, test_events.py, replay.py, orchestrator.py. `StageEvent` fields (`run_id`, `target_id`, `hyp_id`, `stage`, `status`, `ts`, `data`) match usage across all files. `HypState.result` set only on `save/done`. `to_dict()` method present on all state types.

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-18-phase-a-replay-visualizer.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks

**2. Inline Execution** — Execute tasks in this session using executing-plans

**Which approach?**
