from sandbox import config

# Price per 1,000,000 tokens (USD), (input, output). Update as provider pricing changes.
_PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    # Intro pricing through 2026-08-31; reverts to (3.0, 15.0) after -- update then.
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-fable-5": (10.0, 50.0),
    # Unverified as of 2026-07 -- no longer on OpenAI's current pricing page.
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    # Verified against https://developers.openai.com/api/docs/pricing on 2026-07-11.
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4": (2.50, 15.0),
    "gpt-5.6-luna": (1.0, 6.0),
    "gpt-5.6-terra": (2.50, 15.0),
    "gpt-5.6-sol": (5.0, 30.0),
    "gpt-5.5": (5.0, 30.0),
    "gpt-5.3-codex": (1.75, 14.0),
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
