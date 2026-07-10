import requests
from .base import Provider, ChatResult

_URL = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    def __init__(self, api_key: str):
        self._key = api_key

    def chat(self, model: str, messages: list[dict], fmt: str | None) -> ChatResult:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        if fmt == "json":
            system = (system + "\nRespond with valid JSON only, no prose.").strip()
        # claude-fable-5 always thinks (unconfigurable), which eats into max_tokens --
        # give it headroom so thinking doesn't crowd out the actual text response.
        max_tokens = 12000 if model == "claude-fable-5" else 4096
        body = {"model": model, "max_tokens": max_tokens, "messages": convo}
        if system:
            body["system"] = system
        headers = {"x-api-key": self._key, "anthropic-version": _VERSION,
                   "content-type": "application/json"}
        # claude-fable-5 deliberates longer by default (always-on thinking); give it
        # more wall-clock room than the other models' 300s.
        timeout = 600 if model == "claude-fable-5" else 300
        resp = requests.post(_URL, json=body, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        u = data.get("usage", {})
        return ChatResult(text=text,
                          usage={"prompt": u.get("input_tokens", 0),
                                 "completion": u.get("output_tokens", 0)})
