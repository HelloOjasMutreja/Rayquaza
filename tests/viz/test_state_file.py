from viz.sources.state_file import load_loop_state, hypotheses_from_state, target_id_from_state


class TestLoadLoopState:
    def test_loads_dict(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        assert isinstance(data, dict)

    def test_has_required_keys(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        for key in ("hypotheses", "promoted_ids", "invalidated_ids", "target_file"):
            assert key in data, f"missing key: {key}"

    def test_hypotheses_is_list(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        assert isinstance(data["hypotheses"], list)


class TestHypothesesFromState:
    def test_returns_list_of_dicts(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        hyps = hypotheses_from_state(data)
        assert len(hyps) >= 1
        assert isinstance(hyps[0], dict)

    def test_each_hyp_has_id_and_status(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        for hyp in hypotheses_from_state(data):
            assert "id" in hyp
            assert "status" in hyp

    def test_leak5_h001_is_promoted(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        hyps = hypotheses_from_state(data)
        h001 = next(h for h in hyps if h["id"] == "H001")
        assert h001["status"] == "PROMOTED"
        assert h001["significant"] is True

    def test_leak2_h001_is_invalidated(self, loop_state_leak2):
        data = load_loop_state(loop_state_leak2)
        hyps = hypotheses_from_state(data)
        h001 = next(h for h in hyps if h["id"] == "H001")
        assert h001["status"] == "INVALIDATED"
        assert h001["significant"] is False


class TestTargetIdFromState:
    def test_derives_id_from_target_file(self, loop_state_leak5):
        data = load_loop_state(loop_state_leak5)
        target_id = target_id_from_state(data)
        assert target_id == "kyber512_leak5"

    def test_derives_id_for_leak2(self, loop_state_leak2):
        data = load_loop_state(loop_state_leak2)
        assert target_id_from_state(data) == "kyber512_leak2"
