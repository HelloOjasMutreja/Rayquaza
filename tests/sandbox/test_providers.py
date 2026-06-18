from unittest.mock import patch, MagicMock
from sandbox.gateway.providers.anthropic import AnthropicProvider
from sandbox.gateway.providers.openai import OpenAIProvider
from sandbox.gateway.providers.ollama import OllamaProvider


def _resp(json_body):
    m = MagicMock()
    m.json.return_value = json_body
    m.raise_for_status.return_value = None
    return m


def test_anthropic_splits_system_and_maps_usage(anthropic_reply):
    p = AnthropicProvider(api_key="sk-test")
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    with patch("sandbox.gateway.providers.anthropic.requests.post", return_value=_resp(anthropic_reply)) as post:
        r = p.chat("claude-sonnet-4-6", msgs, fmt=None)
    body = post.call_args.kwargs["json"]
    assert body["system"] == "sys"                      # system hoisted out of messages
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert r.text == "hypothesis text"
    assert r.usage == {"prompt": 120, "completion": 45}


def test_openai_passes_messages_and_json_mode(openai_reply):
    p = OpenAIProvider(api_key="sk-test")
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    with patch("sandbox.gateway.providers.openai.requests.post", return_value=_resp(openai_reply)) as post:
        r = p.chat("gpt-4o", msgs, fmt="json")
    body = post.call_args.kwargs["json"]
    assert body["messages"] == msgs                      # system stays inline for OpenAI
    assert body["response_format"] == {"type": "json_object"}
    assert r.text == "hypothesis text"
    assert r.usage == {"prompt": 120, "completion": 45}


def test_ollama_passthrough_extracts_usage():
    reply = {"message": {"role": "assistant", "content": "out"},
             "prompt_eval_count": 30, "eval_count": 12}
    p = OllamaProvider(base_url="http://localhost:11434")
    msgs = [{"role": "user", "content": "hi"}]
    with patch("sandbox.gateway.providers.ollama.requests.post", return_value=_resp(reply)) as post:
        r = p.chat("codellama:7b", msgs, fmt="json")
    body = post.call_args.kwargs["json"]
    assert body["model"] == "codellama:7b"
    assert body["format"] == "json"
    assert r.text == "out"
    assert r.usage == {"prompt": 30, "completion": 12}
