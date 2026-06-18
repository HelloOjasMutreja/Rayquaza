from sandbox import pricing


def test_ollama_is_free():
    assert pricing.cost("codellama:7b", {"prompt": 1000, "completion": 1000}) == 0.0
    assert pricing.estimated("codellama:7b") is True  # local => known-zero, estimated flag true


def test_known_api_model_cost():
    # gpt-4o-mini priced at 0.15 / 0.60 per Mtok in/out
    c = pricing.cost("gpt-4o-mini", {"prompt": 1_000_000, "completion": 1_000_000})
    assert abs(c - 0.75) < 1e-6


def test_unknown_model_zero_cost_not_estimated():
    assert pricing.cost("mystery-model", {"prompt": 100, "completion": 100}) == 0.0
    assert pricing.estimated("mystery-model") is False
