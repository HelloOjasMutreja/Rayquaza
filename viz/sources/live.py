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
                self._after_ingest = True

            elif result.event_type == "rayqevent":
                d = result.data
                yield StageEvent(
                    run_id=self._run_id,
                    target_id="",
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
            target_id="",
            hyp_id=hyp_id,
            stage=stage,
            status=status,
            ts=time.time(),
            data=data or {},
        )
