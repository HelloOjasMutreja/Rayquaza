from sandbox.meter import Meter


def test_accumulates_usage():
    m = Meter(model="gpt-4o-mini")
    m.record({"prompt": 500_000, "completion": 0})
    m.record({"prompt": 500_000, "completion": 1_000_000})
    totals = m.totals()
    assert totals["calls"] == 2
    assert totals["tokens"]["prompt"] == 1_000_000
    assert totals["tokens"]["completion"] == 1_000_000
    assert abs(totals["cost_usd"] - 0.75) < 1e-6
    assert totals["cost_estimated"] is True


def test_local_model_zero_cost():
    m = Meter(model="codellama:7b")
    m.record({"prompt": 9_999, "completion": 9_999})
    assert m.totals()["cost_usd"] == 0.0
