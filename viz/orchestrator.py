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
        state.model_label = data.get("model", "unknown model") + " (replay)"

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

    def all_replay_paths(self) -> list[Path]:
        """Return paths to all committed loop_state_kyber512_*.json files, sorted by name."""
        return sorted(
            FINDINGS_DIR.glob("loop_state_kyber512_*.json"),
            key=lambda p: p.name,
        )

    def start_live(self, target_id: str) -> None:
        """Start a live run against the real engine subprocess."""
        import json
        targets = json.loads((REPO_ROOT / "viz" / "targets.json").read_text(encoding="utf-8"))
        meta = next((t for t in targets if t["id"] == target_id), None)
        if not meta or not meta.get("focused_target"):
            return

        from .sources.live import LiveSource

        target_c = REPO_ROOT / meta["focused_target"]
        state = RunState(run_id="live")
        state.model_label = "codellama:7b + qwen3:8b (live)"

        def on_wait(hyp_id: str):
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

        On Windows: invokes via wsl.exe. On Linux: runs the binary natively.
        """
        import platform
        import subprocess as _sp
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
                _sp.run(cmd, timeout=700, check=False)
            except Exception:
                pass

        threading.Thread(target=_invoke, daemon=True).start()
