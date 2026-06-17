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

        data = state_file.load_loop_state(loop_state_path)
        state.model_label = data.get("model", "codellama:7b + qwen3:8b") + " (replay)"

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
        """Return paths to all committed loop_state_kyber512_*.json files, sorted by name."""
        return sorted(
            FINDINGS_DIR.glob("loop_state_kyber512_*.json"),
            key=lambda p: p.name,
        )
