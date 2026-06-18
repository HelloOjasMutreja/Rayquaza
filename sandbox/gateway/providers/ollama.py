import requests
from .base import Provider, ChatResult


class OllamaProvider(Provider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self._url = base_url.rstrip("/") + "/api/chat"

    def chat(self, model: str, messages: list[dict], fmt: str | None) -> ChatResult:
        payload = {"model": model, "messages": messages, "stream": False}
        if fmt:
            payload["format"] = fmt
        resp = requests.post(self._url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return ChatResult(
            text=data.get("message", {}).get("content", ""),
            usage={"prompt": data.get("prompt_eval_count", 0),
                   "completion": data.get("eval_count", 0)},
        )
