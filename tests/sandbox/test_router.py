import pytest
from sandbox.gateway.router import Router
from sandbox.gateway.providers.ollama import OllamaProvider
from sandbox.gateway.providers.anthropic import AnthropicProvider
from sandbox.gateway.providers.openai import OpenAIProvider


def test_routes_local_to_ollama():
    r = Router(keys={})
    assert isinstance(r.provider_for("codellama:7b"), OllamaProvider)


def test_routes_claude_to_anthropic():
    r = Router(keys={"anthropic": "sk-a"})
    assert isinstance(r.provider_for("claude-sonnet-4-6"), AnthropicProvider)


def test_routes_gpt_to_openai():
    r = Router(keys={"openai": "sk-o"})
    assert isinstance(r.provider_for("gpt-4o"), OpenAIProvider)


def test_missing_key_raises():
    r = Router(keys={})
    with pytest.raises(ValueError, match="no API key"):
        r.provider_for("claude-sonnet-4-6")
