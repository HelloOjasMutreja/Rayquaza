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
