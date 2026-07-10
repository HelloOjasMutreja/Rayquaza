import json
import os
from pathlib import Path

SECRETS_PATH = Path(__file__).resolve().parent / "secrets.local.json"

_ENV_VAR = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# Built-in model registry. Ollama entries are the local defaults the engine ships with;
# API entries are selectable once a key is configured. Prefixes drive provider routing.
_BUILTIN = [
    {"id": "codellama:7b", "provider": "ollama", "label": "CodeLlama 7B (local)"},
    {"id": "qwen3:8b", "provider": "ollama", "label": "Qwen3 8B (local)"},
    {"id": "claude-sonnet-4-6", "provider": "anthropic", "label": "Claude Sonnet 4.6"},
    {"id": "claude-sonnet-5", "provider": "anthropic", "label": "Claude Sonnet 5"},
    {"id": "claude-haiku-4-5", "provider": "anthropic", "label": "Claude Haiku 4.5"},
    {"id": "claude-opus-4-8", "provider": "anthropic", "label": "Claude Opus 4.8"},
    {"id": "claude-fable-5", "provider": "anthropic", "label": "Claude Fable 5"},
    # NOTE: gpt-4o/gpt-4o-mini pricing below is unverified as of 2026-07 -- these
    # models no longer appear on OpenAI's current pricing page, only in the live
    # /v1/models list. Don't spend against these prices without re-verifying.
    {"id": "gpt-4o", "provider": "openai", "label": "GPT-4o"},
    {"id": "gpt-4o-mini", "provider": "openai", "label": "GPT-4o mini"},
    {"id": "gpt-5.4-nano", "provider": "openai", "label": "GPT-5.4 nano"},
    {"id": "gpt-5.4-mini", "provider": "openai", "label": "GPT-5.4 mini"},
    {"id": "gpt-5.4", "provider": "openai", "label": "GPT-5.4"},
    {"id": "gpt-5.6-luna", "provider": "openai", "label": "GPT-5.6 Luna"},
    {"id": "gpt-5.6-terra", "provider": "openai", "label": "GPT-5.6 Terra"},
    {"id": "gpt-5.6-sol", "provider": "openai", "label": "GPT-5.6 Sol"},
    {"id": "gpt-5.5", "provider": "openai", "label": "GPT-5.5"},
    {"id": "gpt-5.3-codex", "provider": "openai", "label": "GPT-5.3 Codex"},
]


def model_registry() -> list[dict]:
    """Return the list of selectable models (built-ins for v1)."""
    return [dict(m) for m in _BUILTIN]


def provider_for(model: str) -> str:
    """Route a model id to its provider by prefix."""
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "ollama"


def api_key(provider: str) -> str | None:
    """Load an API key: env var first, then the gitignored secrets file. None if absent."""
    env = _ENV_VAR.get(provider)
    if env and os.environ.get(env):
        return os.environ[env]
    if SECRETS_PATH.exists():
        try:
            data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
            return data.get(provider)
        except (json.JSONDecodeError, OSError):
            return None
    return None
