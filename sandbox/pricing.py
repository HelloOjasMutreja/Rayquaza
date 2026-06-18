from sandbox import config

# Price per 1,000,000 tokens (USD), (input, output). Update as provider pricing changes.
_PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
}


def _is_known_local(model: str) -> bool:
    """True if the model is a registered local (Ollama) model — known to be free."""
    return any(m["id"] == model and m["provider"] == "ollama"
               for m in config.model_registry())


def estimated(model: str) -> bool:
    """True if cost is reliable: a known-free local model, or a priced API model.
    False for unknown models (cost defaults to 0 but is not trustworthy)."""
    return _is_known_local(model) or model in _PRICES


def cost(model: str, usage: dict) -> float:
    """USD cost for a usage dict {prompt, completion}. Free for local + unknown models."""
    if model not in _PRICES:
        return 0.0
    in_rate, out_rate = _PRICES[model]
    p = usage.get("prompt", 0) / 1_000_000 * in_rate
    c = usage.get("completion", 0) / 1_000_000 * out_rate
    return round(p + c, 6)
