from sandbox.gateway.chat import handle_chat
from sandbox.gateway.providers.base import Provider, ChatResult
from sandbox.meter import Meter


class FakeRouter:
    def __init__(self, result):
        self._result = result
        self.seen_model = None

    def provider_for(self, model):
        self.seen_model = model
        outer = self

        class P(Provider):
            def chat(self, model, messages, fmt):
                return outer._result
        return P()


def test_handle_chat_returns_ollama_shape_and_meters():
    router = FakeRouter(ChatResult(text="answer", usage={"prompt": 10, "completion": 5}))
    meter = Meter(model="gpt-4o-mini")
    payload = {"model": "gpt-4o-mini",
               "messages": [{"role": "user", "content": "hi"}], "format": "json"}
    out = handle_chat(payload, router, meter)
    assert out["message"]["role"] == "assistant"
    assert out["message"]["content"] == "answer"
    assert out["done"] is True
    assert meter.totals()["tokens"]["prompt"] == 10
    assert router.seen_model == "gpt-4o-mini"


def test_handle_chat_error_returns_ollama_error_shape():
    class BoomRouter:
        def provider_for(self, model):
            raise ValueError("no API key for provider 'anthropic'")
    out = handle_chat({"model": "claude-x", "messages": []}, BoomRouter(), Meter("claude-x"))
    assert "error" in out
    assert "no API key" in out["error"]
