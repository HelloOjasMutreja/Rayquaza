from sandbox import pricing


class Meter:
    """Accumulates token usage and $ cost for a single run (one model)."""

    def __init__(self, model: str):
        self._model = model
        self._calls = 0
        self._prompt = 0
        self._completion = 0

    def record(self, usage: dict) -> None:
        self._calls += 1
        self._prompt += int(usage.get("prompt", 0))
        self._completion += int(usage.get("completion", 0))

    def totals(self) -> dict:
        tokens = {"prompt": self._prompt, "completion": self._completion}
        return {
            "calls": self._calls,
            "tokens": tokens,
            "cost_usd": pricing.cost(self._model, tokens),
            "cost_estimated": pricing.estimated(self._model),
        }
