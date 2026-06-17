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

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "target_id": self.target_id,
            "hyp_id": self.hyp_id,
            "stage": self.stage,
            "status": self.status,
            "ts": self.ts,
            "data": self.data,
        }


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
    hyps: dict[str, HypState] = field(default_factory=dict)

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
    targets: dict[str, TargetRunState] = field(default_factory=dict)
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
