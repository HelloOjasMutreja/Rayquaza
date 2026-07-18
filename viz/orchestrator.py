import threading
from pathlib import Path
from typing import Callable, Optional

from .events import RunState, fold_event
from .sources.base import RunSource
from .sources.replay import ReplaySource
from .sources import state_file

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"


class Orchestrator:
    """Drives run sources, folds events into RunState, and pushes updates to a callback.

    The callback receives a JSON-serializable dict on every StageEvent.
    All sources run in daemon threads so the pywebview main loop is never blocked.
    """

    def __init__(self, on_state: Callable[[dict], None]):
        self._on_state = on_state
        self._lock = threading.Lock()
        # Parallel replay (list of sources + threads)
        self._replay_sources: list[RunSource] = []
        self._replay_threads: list[threading.Thread] = []
        # Live (single source)
        self._source: Optional[RunSource] = None
        self._thread: Optional[threading.Thread] = None

    def start_replay_all(self, paths: list[Path], step_delay: float = 0.6) -> None:
        """Start parallel replay runs for every path, all animating simultaneously."""
        if self._replay_threads and any(t.is_alive() for t in self._replay_threads):
            return

        self._replay_sources = []
        self._replay_threads = []

        # One shared RunState — all sources fold their events into it
        first_data = state_file.load_loop_state(paths[0])
        shared_state = RunState(run_id="replay-all")
        shared_state.model_label = first_data.get("model", "unknown model") + " (replay)"

        remaining = [len(paths)]  # mutable counter; hits 0 when all threads finish

        for path in paths:
            source = ReplaySource(path, step_delay=step_delay)
            self._replay_sources.append(source)

            def _run(src=source):
                for event in src.start():
                    with self._lock:
                        fold_event(shared_state, event)
                        self._on_state(shared_state.to_dict())
                with self._lock:
                    remaining[0] -= 1
                    if remaining[0] == 0:
                        shared_state.finished = True
                        self._on_state(shared_state.to_dict())

            t = threading.Thread(target=_run, daemon=True)
            self._replay_threads.append(t)

        for t in self._replay_threads:
            t.start()

    def start_replay(self, loop_state_path: Path, step_delay: float = 0.6) -> None:
        """Start a replay run for a single target (delegates to start_replay_all)."""
        self.start_replay_all([loop_state_path], step_delay=step_delay)

    def stop(self) -> None:
        for src in self._replay_sources:
            src.stop()
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
                with self._lock:
                    fold_event(state, event)
                    self._on_state(state.to_dict())
            with self._lock:
                state.finished = True
                self._on_state(state.to_dict())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def run_oracle(self, target_id: str, hyp_id: str) -> None:
        """Run the oracle binary for a target/hypothesis pair (delegates to invoke_oracle)."""
        invoke_oracle(target_id, hyp_id)


def invoke_oracle(target_id: str, hyp_id: str) -> None:
    """Run a target's harness_oracle in a background thread to produce timing feedback.

    Writes shared/feedback/timing_<hyp_id>_*.json, which the engine polls for.
    On Windows: invokes via wsl.exe (the harness is a Linux binary). On Linux: runs natively.
    Shared by the Phase A live orchestrator and the Phase B run_session.
    """
    import platform
    import subprocess as _sp
    oracle_bin = REPO_ROOT / "track-a-target" / "targets" / target_id / "harness_oracle"

    def _invoke():
        try:
            if platform.system() == "Windows":
                wsl_path = str(oracle_bin).replace("\\", "/").replace("D:", "/mnt/d")
                cmd = ["wsl", "bash", "-c",
                       f"cd $(dirname '{wsl_path}') && ./harness_oracle {hyp_id} 50000"]
            else:
                cmd = [str(oracle_bin), hyp_id, "50000"]
            # harness_oracle writes to a path relative to its own directory
            # (../../../shared/feedback/...), so it must be run from there.
            _sp.run(cmd, timeout=700, check=False, cwd=oracle_bin.parent,
                    capture_output=True)
        except Exception:
            pass

    threading.Thread(target=_invoke, daemon=True).start()
