from sandbox import config
from sandbox.gateway.providers.ollama import OllamaProvider
from sandbox.gateway.providers.anthropic import AnthropicProvider
from sandbox.gateway.providers.openai import OpenAIProvider


class Router:
    """Maps a model id to a Provider instance, supplying API keys for remote providers."""

    def __init__(self, keys: dict, ollama_url: str = "http://localhost:11434"):
        self._keys = keys
        self._ollama_url = ollama_url

    def provider_for(self, model: str):
        provider = config.provider_for(model)
        if provider == "ollama":
            return OllamaProvider(base_url=self._ollama_url)
        key = self._keys.get(provider)
        if not key:
            raise ValueError(f"no API key for provider '{provider}' (model {model})")
        if provider == "anthropic":
            return AnthropicProvider(api_key=key)
        return OpenAIProvider(api_key=key)
