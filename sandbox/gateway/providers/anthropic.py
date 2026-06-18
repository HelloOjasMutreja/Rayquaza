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
        body = {"model": model, "max_tokens": 4096, "messages": convo}
        if system:
            body["system"] = system
        headers = {"x-api-key": self._key, "anthropic-version": _VERSION,
                   "content-type": "application/json"}
        resp = requests.post(_URL, json=body, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        u = data.get("usage", {})
        return ChatResult(text=text,
                          usage={"prompt": u.get("input_tokens", 0),
                                 "completion": u.get("output_tokens", 0)})
