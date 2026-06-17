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
        data = load_timing(timing_leak5)
        # mutate a copy to simulate invalidated result
        data = dict(data)
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
