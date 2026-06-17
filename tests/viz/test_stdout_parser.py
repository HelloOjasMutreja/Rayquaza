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
