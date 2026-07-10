from sandbox import pricing


class Meter:
    """Accumulates token usage and $ cost for a single run (one model)."""

    def __init__(self, model: str, max_cost_usd: float | None = None):
        self._model = model
        self._calls = 0
        self._prompt = 0
        self._completion = 0
        self._max_cost_usd = max_cost_usd

    def record(self, usage: dict) -> None:
        self._calls += 1
        self._prompt += int(usage.get("prompt", 0))
        self._completion += int(usage.get("completion", 0))

    def over_budget(self) -> bool:
        """True if accumulated spend has already reached the configured cap.
        Checked BEFORE each call so runaway spend is bounded, not just observed."""
        if self._max_cost_usd is None:
            return False
        return self.totals()["cost_usd"] >= self._max_cost_usd

    def totals(self) -> dict:
        tokens = {"prompt": self._prompt, "completion": self._completion}
        return {
            "calls": self._calls,
            "tokens": tokens,
            "cost_usd": pricing.cost(self._model, tokens),
            "cost_estimated": pricing.estimated(self._model),
        }
