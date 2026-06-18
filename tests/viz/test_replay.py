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

    def test_ingest_start_carries_hypothesis_text(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        ingest_start = [e for e in src.start()
                        if e.stage == "ingest" and e.status == "start"]
        assert len(ingest_start) == 1
        assert ingest_start[0].data.get("hypothesis_text")

    def test_wait_done_carries_measurement(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        wait_done = [e for e in src.start()
                     if e.stage == "wait" and e.status == "done"]
        assert len(wait_done) == 1
        m = wait_done[0].data
        assert m.get("mean_A") is not None
        assert m.get("variance_A") is not None

    def test_measurement_and_metadata_fold(self, loop_state_leak5):
        src = ReplaySource(loop_state_leak5, step_delay=0.0)
        state = RunState(run_id="test")
        for event in src.start():
            fold_event(state, event)
        hyp = list(state.targets["kyber512_leak5"].hyps.values())[-1]
        assert hyp.hypothesis_text
        assert hyp.measurement is not None
        assert hyp.measurement["mean_A"] is not None
