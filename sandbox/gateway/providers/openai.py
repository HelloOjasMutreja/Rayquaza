import requests
from .base import Provider, ChatResult

_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(Provider):
    def __init__(self, api_key: str):
        self._key = api_key

    def chat(self, model: str, messages: list[dict], fmt: str | None) -> ChatResult:
        body = {"model": model, "messages": messages}
        if fmt == "json":
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self._key}",
                   "Content-Type": "application/json"}
        resp = requests.post(_URL, json=body, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage", {})
        return ChatResult(text=text,
                          usage={"prompt": u.get("prompt_tokens", 0),
                                 "completion": u.get("completion_tokens", 0)})
