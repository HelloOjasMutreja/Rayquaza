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
    simulated delays. Use step_delay=0.0 in tests; ~0.6s for a watchable demo.
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
                if timing:
                    result_data = result_from_timing(timing, status)
                else:
                    result_data = {
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
