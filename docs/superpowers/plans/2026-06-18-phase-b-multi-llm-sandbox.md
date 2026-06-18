# Phase B — Multi-LLM Sandbox + Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run different LLMs (local Ollama + Anthropic/OpenAI APIs) against the PQC targets through the same adversary-loop engine, save each run as a JSON artifact, and compare runs side-by-side across detection / signal / efficiency / robustness.

**Architecture:** A Track-A `sandbox/` package hosts an Ollama-compatible "gateway" HTTP server that routes by model name to Ollama or a provider API and meters tokens/cost. The existing engine is launched as a subprocess (reusing Phase A's `LiveSource`) pointed at the gateway via env vars; one additive engine change reads model/URL from env. Runs are saved under `shared/runs/`; a comparison module builds the side-by-side report. Ships in two slices: **B-i** (run any model + save) then **B-ii** (compare).

**Tech Stack:** Python 3.10+, stdlib `http.server` for the gateway, `requests` for provider + Ollama calls (already an engine dependency), `pytest`, `dataclasses`, `pathlib`, `json`, `threading`. Frontend is the existing vanilla HTML/CSS/JS in `viz/web/`.

**Branch:** `phase-b-sandbox`. Spec: `docs/superpowers/specs/2026-06-18-phase-b-multi-llm-sandbox-design.md`.

---

## File map

```
sandbox/
  __init__.py                  new — package marker
  config.py                    new — model registry + API-key loading (gitignored secrets)
  pricing.py                   new — per-model $ price table; cost(model, usage)
  meter.py                     new — per-run token/cost accumulator
  gateway/
    __init__.py                new
    chat.py                    new — pure handle_chat(payload, router, meter) -> ollama-shaped dict
    router.py                  new — model name -> Provider
    server.py                  new — http.server wrapper exposing /api/chat + /api/tags
    providers/
      __init__.py              new
      base.py                  new — Provider ABC + ChatResult/Usage
      ollama.py                new — passthrough proxy to localhost:11434
      anthropic.py             new — Anthropic Messages API -> ollama-shaped
      openai.py                new — OpenAI Chat Completions -> ollama-shaped
  runstore.py                  new — Run/TargetResult dataclasses + save/load (shared/runs/)
  run_session.py               new — orchestrate one run (gateway + engine subprocess + artifact)
  comparison.py                new — load runs -> per-axis table + markdown report   (B-ii)
tests/sandbox/
  __init__.py                  new
  conftest.py                  new — fixtures (sample ollama payload, recorded provider replies)
  test_config.py               new
  test_pricing.py              new
  test_meter.py                new
  test_providers.py            new
  test_router.py               new
  test_chat.py                 new
  test_runstore.py             new
  test_comparison.py           new   (B-ii)
viz/
  app.py                       modify — API: list_models, add_api_model, start_sandbox_run,
                                        list_runs, build_comparison
  web/index.html               modify — model-import panel + comparison-view mode
  web/styles.css               modify — import panel + comparison columns
  web/sandbox.js               new — import panel + comparison view logic
track-b-engine/
  engine/adversary_loop.py     modify (additive) — OLLAMA_URL/CODE_MODEL/REASON_MODEL from env
  ingestion/ingest.py          modify (additive) — OLLAMA_URL/MODEL from env
shared/runs/.gitkeep           new — artifact directory placeholder
.gitignore                     modify — ignore sandbox/secrets.local.json
requirements-sandbox.txt       new — requests>=2.28, pytest>=8.0
```

---

# SLICE B-i — run any model, save it

## Task 1: Scaffold sandbox package + secrets ignore

**Files:**
- Create: `sandbox/__init__.py`, `sandbox/gateway/__init__.py`, `sandbox/gateway/providers/__init__.py`
- Create: `tests/sandbox/__init__.py`, `tests/sandbox/conftest.py`
- Create: `shared/runs/.gitkeep`, `requirements-sandbox.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Create empty package markers**

Create `sandbox/__init__.py`, `sandbox/gateway/__init__.py`, `sandbox/gateway/providers/__init__.py`, `tests/sandbox/__init__.py` as empty files.

- [ ] **Step 2: Create requirements-sandbox.txt**

```
requests>=2.28
pytest>=8.0
```

- [ ] **Step 3: Add secrets ignore to .gitignore**

Append to `.gitignore`:
```
# Phase B sandbox local secrets (API keys) — never commit
sandbox/secrets.local.json
```

- [ ] **Step 4: Create shared/runs/.gitkeep**

Create `shared/runs/.gitkeep` as an empty file.

- [ ] **Step 5: Create tests/sandbox/conftest.py**

```python
import json
import pytest


@pytest.fixture
def ollama_chat_payload():
    return {
        "model": "codellama:7b",
        "messages": [
            {"role": "system", "content": "You are a security analyst."},
            {"role": "user", "content": "Find the leak."},
        ],
        "stream": False,
    }


@pytest.fixture
def anthropic_reply():
    return {
        "content": [{"type": "text", "text": "hypothesis text"}],
        "usage": {"input_tokens": 120, "output_tokens": 45},
    }


@pytest.fixture
def openai_reply():
    return {
        "choices": [{"message": {"role": "assistant", "content": "hypothesis text"}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 45},
    }
```

- [ ] **Step 6: Commit**

```bash
git add sandbox tests/sandbox shared/runs/.gitkeep requirements-sandbox.txt .gitignore
git commit -m "[A] Phase B: scaffold sandbox package + secrets ignore"
```

---

## Task 2: config.py — model registry + key loading

**Files:**
- Create: `sandbox/config.py`
- Test: `tests/sandbox/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
from sandbox import config


def test_builtin_models_present():
    reg = config.model_registry()
    ids = {m["id"] for m in reg}
    assert "codellama:7b" in ids
    assert any(m["provider"] == "anthropic" for m in reg)


def test_provider_for_model():
    assert config.provider_for("codellama:7b") == "ollama"
    assert config.provider_for("claude-sonnet-4-6") == "anthropic"
    assert config.provider_for("gpt-4o") == "openai"


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    assert config.api_key("anthropic") == "sk-test-123"


def test_api_key_from_secrets_file(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets.local.json"
    secrets.write_text(json.dumps({"openai": "sk-file-456"}), encoding="utf-8")
    monkeypatch.setattr(config, "SECRETS_PATH", secrets)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert config.api_key("openai") == "sk-file-456"


def test_missing_key_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SECRETS_PATH", tmp_path / "nope.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.api_key("anthropic") is None
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'sandbox.config'`

- [ ] **Step 3: Implement config.py**

```python
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
    {"id": "gpt-4o", "provider": "openai", "label": "GPT-4o"},
    {"id": "gpt-4o-mini", "provider": "openai", "label": "GPT-4o mini"},
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_config.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/config.py tests/sandbox/test_config.py
git commit -m "[A] Phase B: config.py — model registry + API key loading"
```

---

## Task 3: pricing.py — cost from token usage

**Files:**
- Create: `sandbox/pricing.py`
- Test: `tests/sandbox/test_pricing.py`

- [ ] **Step 1: Write the failing tests**

```python
from sandbox import pricing


def test_ollama_is_free():
    assert pricing.cost("codellama:7b", {"prompt": 1000, "completion": 1000}) == 0.0
    assert pricing.estimated("codellama:7b") is True  # local => known-zero, estimated flag true


def test_known_api_model_cost():
    # gpt-4o-mini priced at 0.15 / 0.60 per Mtok in/out
    c = pricing.cost("gpt-4o-mini", {"prompt": 1_000_000, "completion": 1_000_000})
    assert abs(c - 0.75) < 1e-6


def test_unknown_model_zero_cost_not_estimated():
    assert pricing.cost("mystery-model", {"prompt": 100, "completion": 100}) == 0.0
    assert pricing.estimated("mystery-model") is False
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_pricing.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement pricing.py**

```python
# Price per 1,000,000 tokens (USD), (input, output). Update as provider pricing changes.
_PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
}


def estimated(model: str) -> bool:
    """True if we have a real price (or a known-free local model); False if unknown."""
    if _is_local(model):
        return True
    return model in _PRICES


def cost(model: str, usage: dict) -> float:
    """USD cost for a usage dict {prompt, completion}. Local models and unknowns => 0.0."""
    if _is_local(model) or model not in _PRICES:
        return 0.0
    in_rate, out_rate = _PRICES[model]
    p = usage.get("prompt", 0) / 1_000_000 * in_rate
    c = usage.get("completion", 0) / 1_000_000 * out_rate
    return round(p + c, 6)


def _is_local(model: str) -> bool:
    return not (model.startswith("claude") or model.startswith(("gpt-", "o1", "o3", "o4")))
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_pricing.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/pricing.py tests/sandbox/test_pricing.py
git commit -m "[A] Phase B: pricing.py — token-usage cost table"
```

---

## Task 4: meter.py — per-run token/cost accumulator

**Files:**
- Create: `sandbox/meter.py`
- Test: `tests/sandbox/test_meter.py`

- [ ] **Step 1: Write the failing tests**

```python
from sandbox.meter import Meter


def test_accumulates_usage():
    m = Meter(model="gpt-4o-mini")
    m.record({"prompt": 500_000, "completion": 0})
    m.record({"prompt": 500_000, "completion": 1_000_000})
    totals = m.totals()
    assert totals["calls"] == 2
    assert totals["tokens"]["prompt"] == 1_000_000
    assert totals["tokens"]["completion"] == 1_000_000
    assert abs(totals["cost_usd"] - 0.75) < 1e-6
    assert totals["cost_estimated"] is True


def test_local_model_zero_cost():
    m = Meter(model="codellama:7b")
    m.record({"prompt": 9_999, "completion": 9_999})
    assert m.totals()["cost_usd"] == 0.0
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_meter.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement meter.py**

```python
from sandbox import pricing


class Meter:
    """Accumulates token usage and $ cost for a single run (one model)."""

    def __init__(self, model: str):
        self._model = model
        self._calls = 0
        self._prompt = 0
        self._completion = 0

    def record(self, usage: dict) -> None:
        self._calls += 1
        self._prompt += int(usage.get("prompt", 0))
        self._completion += int(usage.get("completion", 0))

    def totals(self) -> dict:
        tokens = {"prompt": self._prompt, "completion": self._completion}
        return {
            "calls": self._calls,
            "tokens": tokens,
            "cost_usd": pricing.cost(self._model, tokens),
            "cost_estimated": pricing.estimated(self._model),
        }
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_meter.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/meter.py tests/sandbox/test_meter.py
git commit -m "[A] Phase B: meter.py — per-run token/cost accumulator"
```

---

## Task 5: providers/base.py — Provider interface

**Files:**
- Create: `sandbox/gateway/providers/base.py`

(No unit test — pure interface; exercised by the concrete provider tests in Task 6.)

- [ ] **Step 1: Implement base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatResult:
    text: str
    usage: dict = field(default_factory=lambda: {"prompt": 0, "completion": 0})


class Provider(ABC):
    """Translates an Ollama-style chat request to a backend and back.

    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    fmt: "json" to request JSON-only output, else None.
    """

    @abstractmethod
    def chat(self, model: str, messages: list[dict], fmt: str | None) -> ChatResult: ...
```

- [ ] **Step 2: Commit**

```bash
git add sandbox/gateway/providers/base.py
git commit -m "[A] Phase B: provider interface (base.py)"
```

---

## Task 6: providers — ollama, anthropic, openai

**Files:**
- Create: `sandbox/gateway/providers/ollama.py`, `anthropic.py`, `openai.py`
- Test: `tests/sandbox/test_providers.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_providers.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement ollama.py**

```python
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
```

- [ ] **Step 4: Implement anthropic.py**

```python
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
```

- [ ] **Step 5: Implement openai.py**

```python
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
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_providers.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add sandbox/gateway/providers/ tests/sandbox/test_providers.py
git commit -m "[A] Phase B: ollama/anthropic/openai providers"
```

---

## Task 7: router.py — model name → Provider

**Files:**
- Create: `sandbox/gateway/router.py`
- Test: `tests/sandbox/test_router.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_router.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement router.py**

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_router.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/gateway/router.py tests/sandbox/test_router.py
git commit -m "[A] Phase B: router.py — model -> provider"
```

---

## Task 8: chat.py — pure request handler + meter integration

**Files:**
- Create: `sandbox/gateway/chat.py`
- Test: `tests/sandbox/test_chat.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_chat.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement chat.py**

```python
def handle_chat(payload: dict, router, meter) -> dict:
    """Pure handler: Ollama-style chat payload -> Ollama-style response dict.

    Routes to a provider, meters usage, and normalizes both success and failure to
    shapes the engine already understands (it reads response['message']['content']).
    """
    model = payload.get("model", "")
    messages = payload.get("messages", [])
    fmt = payload.get("format")
    try:
        provider = router.provider_for(model)
        result = provider.chat(model, messages, fmt)
        meter.record(result.usage)
        return {"model": model, "message": {"role": "assistant", "content": result.text},
                "done": True}
    except Exception as exc:  # provider/network/key failure -> ollama-shaped error
        return {"model": model, "error": str(exc), "done": True,
                "message": {"role": "assistant", "content": ""}}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_chat.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/gateway/chat.py tests/sandbox/test_chat.py
git commit -m "[A] Phase B: chat.py — pure gateway handler + metering"
```

---

## Task 9: server.py — http.server wrapper

**Files:**
- Create: `sandbox/gateway/server.py`

(No unit test — thin stdlib HTTP wrapper around the tested `handle_chat`. Smoke-tested via the CLI snippet below.)

- [ ] **Step 1: Implement server.py**

```python
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from sandbox.gateway.chat import handle_chat


class Gateway:
    """Ollama-compatible local server. Serves POST /api/chat and GET /api/tags.

    /api/chat routes through the Router + Meter (handle_chat). /api/tags lists local
    Ollama models so the UI can populate its dropdown. Runs on a background thread.
    """

    def __init__(self, router, meter, ollama_url: str = "http://localhost:11434", port: int = 0):
        self._router = router
        self._meter = meter
        self._ollama_url = ollama_url.rstrip("/")
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), self._make_handler())
        self._thread = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/chat"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()

    def _make_handler(self):
        router, meter, ollama_url = self._router, self._meter, self._ollama_url

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence default stderr logging
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/api/tags"):
                    try:
                        r = requests.get(ollama_url + "/api/tags", timeout=10)
                        self._send(200, r.json())
                    except Exception:
                        self._send(200, {"models": []})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self.path.startswith("/api/chat"):
                    self._send(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                self._send(200, handle_chat(payload, router, meter))

        return Handler
```

- [ ] **Step 2: Smoke-test the server in isolation**

```bash
python -c "
from sandbox.gateway.server import Gateway
from sandbox.gateway.router import Router
from sandbox.meter import Meter
import requests, json
g = Gateway(Router(keys={}), Meter('codellama:7b'), port=0)
g.start()
print('listening on', g.url)
# /api/tags should answer (empty list if Ollama not running)
print('tags:', requests.get(f'http://127.0.0.1:{g.port}/api/tags', timeout=5).json())
g.stop()
print('stopped OK')
"
```

Expected: prints a URL, a `tags:` line (a models list or `{"models": []}`), and `stopped OK`.

- [ ] **Step 3: Commit**

```bash
git add sandbox/gateway/server.py
git commit -m "[A] Phase B: server.py — Ollama-compatible gateway"
```

---

## Task 10: Engine env change (additive, Track B files)

**Files:**
- Modify: `track-b-engine/engine/adversary_loop.py` (the `OLLAMA_URL`/`CODE_MODEL`/`REASON_MODEL` constants near the top, ~lines 48-50)
- Modify: `track-b-engine/ingestion/ingest.py` (the `OLLAMA_URL`/`MODEL` constants, ~lines 19-20)

- [ ] **Step 1: Read the current constants**

Run: `grep -n "OLLAMA_URL\|CODE_MODEL\|REASON_MODEL\|^MODEL" track-b-engine/engine/adversary_loop.py track-b-engine/ingestion/ingest.py`
Confirm they are module-level string literals.

- [ ] **Step 2: Make adversary_loop.py read from env**

Ensure `import os` is present at the top of `track-b-engine/engine/adversary_loop.py` (add it if missing). Replace the three constant assignments with:

```python
OLLAMA_URL = os.environ.get("RAYQ_OLLAMA_URL", "http://localhost:11434/api/chat")
CODE_MODEL = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")
REASON_MODEL = os.environ.get("RAYQ_REASON_MODEL", "qwen3:8b")
```

- [ ] **Step 3: Make ingest.py read from env**

Ensure `import os` is present at the top of `track-b-engine/ingestion/ingest.py` (add it if missing). Replace the two constant assignments with:

```python
OLLAMA_URL = os.environ.get("RAYQ_OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")
```

- [ ] **Step 4: Verify defaults unchanged when env unset**

```bash
python -c "
import importlib.util, os
for v in ('RAYQ_OLLAMA_URL','RAYQ_CODE_MODEL','RAYQ_REASON_MODEL'):
    os.environ.pop(v, None)
spec = importlib.util.spec_from_file_location('al', 'track-b-engine/engine/adversary_loop.py')
" 2>/dev/null
grep -n "RAYQ_" track-b-engine/engine/adversary_loop.py track-b-engine/ingestion/ingest.py
```

Expected: the three/two `os.environ.get(...)` lines with the original literals as defaults. (Behaviour is identical when the vars are unset.)

- [ ] **Step 5: Log the change in tracking/SYNC.md**

Append under the `Track A -> Track B` section:

```
- [DELIVERED] 2026-06-18 A->B (Phase B): adversary_loop.py + ingest.py now read model/URL from
  env (RAYQ_OLLAMA_URL / RAYQ_CODE_MODEL / RAYQ_REASON_MODEL), defaulting to the previous
  hardcoded values. Additive, no behaviour change when unset. Lets the Phase B sandbox point the
  engine at the model gateway and swap models without editing engine code.
```

- [ ] **Step 6: Commit**

```bash
git add track-b-engine/engine/adversary_loop.py track-b-engine/ingestion/ingest.py tracking/SYNC.md
git commit -m "[A] Phase B: engine reads model/URL from env (additive, defaults unchanged)"
```

---

## Task 11: runstore.py — Run artifacts

**Files:**
- Create: `sandbox/runstore.py`
- Test: `tests/sandbox/test_runstore.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
from sandbox.runstore import Run, TargetResult, save_run, load_run, list_runs


def _sample_run():
    return Run(
        run_id="r1", model_code="gpt-4o", model_reason="gpt-4o", provider="openai",
        targets=[
            TargetResult("kyber512_leak5", located=True, confirmed=True, t_stat=141.0,
                         cycles=2, wall_seconds=12.3, autonomous=True, verdict="PROMOTED"),
            TargetResult("kyber512_leak2", located=True, confirmed=False, t_stat=-0.17,
                         cycles=3, wall_seconds=20.1, autonomous=True, verdict="INVALIDATED"),
        ],
        started_at=1000.0, ended_at=1100.0,
        tokens={"prompt": 5000, "completion": 1200}, cost_usd=0.05,
        cost_estimated=True, fp_rate=0.0, notes="",
    )


def test_round_trip(tmp_path):
    run = _sample_run()
    path = save_run(run, runs_dir=tmp_path)
    assert path.exists()
    loaded = load_run(path)
    assert loaded.run_id == "r1"
    assert loaded.targets[0].t_stat == 141.0
    assert loaded.targets[1].confirmed is False
    assert loaded.cost_usd == 0.05


def test_list_runs_sorted(tmp_path):
    a = _sample_run(); a.run_id = "aaa"
    b = _sample_run(); b.run_id = "bbb"
    save_run(a, runs_dir=tmp_path)
    save_run(b, runs_dir=tmp_path)
    ids = [r.run_id for r in list_runs(runs_dir=tmp_path)]
    assert ids == ["aaa", "bbb"]


def test_artifact_has_no_key_fields(tmp_path):
    import json
    path = save_run(_sample_run(), runs_dir=tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "api_key" not in raw and "key" not in raw
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_runstore.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement runstore.py**

```python
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "shared" / "runs"


@dataclass
class TargetResult:
    target_id: str
    located: bool
    confirmed: bool
    t_stat: float | None
    cycles: int
    wall_seconds: float
    autonomous: bool
    verdict: str


@dataclass
class Run:
    run_id: str
    model_code: str
    model_reason: str
    provider: str
    targets: list[TargetResult]
    started_at: float
    ended_at: float
    tokens: dict
    cost_usd: float
    cost_estimated: bool
    fp_rate: float
    notes: str = ""


def save_run(run: Run, runs_dir: Path = RUNS_DIR) -> Path:
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"run_{run.run_id}.json"
    path.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
    return path


def load_run(path: Path) -> Run:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["targets"] = [TargetResult(**t) for t in data["targets"]]
    return Run(**data)


def list_runs(runs_dir: Path = RUNS_DIR) -> list[Run]:
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return []
    return [load_run(p) for p in sorted(runs_dir.glob("run_*.json"))]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_runstore.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/runstore.py tests/sandbox/test_runstore.py
git commit -m "[A] Phase B: runstore.py — Run artifacts"
```

---

## Task 12: run_session.py — orchestrate one run

**Files:**
- Create: `sandbox/run_session.py`

(No unit test — integration glue over already-tested units + the engine subprocess. Smoke-tested with a stubbed engine below.)

- [ ] **Step 1: Implement run_session.py**

```python
import time
import uuid
from pathlib import Path

from sandbox import config
from sandbox.meter import Meter
from sandbox.gateway.router import Router
from sandbox.gateway.server import Gateway
from sandbox.runstore import Run, TargetResult, save_run
from viz.sources.state_file import load_loop_state
from viz.sources.live import LiveSource
from viz.events import RunState, fold_event

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS = REPO_ROOT / "shared" / "findings"

GROUND_TRUTH = {
    "kyber512_leak2": {"category": "secret_dependent_branch", "location": "poly_tomsg"},
    "kyber512_leak4": {"category": "secret_dependent_branch", "location": "indcpa_dec"},
    "kyber512_leak5": {"category": "nonconstant_comparison", "location": "crypto_kem_dec"},
}


class RunSession:
    """Runs one model across one target via the engine subprocess behind the gateway,
    folds live events for the UI, and writes a Run artifact at the end."""

    def __init__(self, model: str, target_id: str, target_c: Path, on_state):
        self._model = model
        self._target_id = target_id
        self._target_c = Path(target_c)
        self._on_state = on_state
        self._run_id = uuid.uuid4().hex[:8]
        self._meter = Meter(model=model)
        keys = {p: config.api_key(p) for p in ("anthropic", "openai")}
        self._router = Router(keys={k: v for k, v in keys.items() if v})
        self._gateway = Gateway(self._router, self._meter)

    def run(self) -> Run:
        self._gateway.start()
        env = {
            "RAYQ_OLLAMA_URL": self._gateway.url,
            "RAYQ_CODE_MODEL": self._model,
            "RAYQ_REASON_MODEL": self._model,
        }
        started = time.time()
        state = RunState(run_id=self._run_id, model_label=f"{self._model} (live)")
        source = LiveSource(self._target_c, cycles=3, env_overrides=env)
        for event in source.start():
            if not event.target_id:
                event.target_id = self._target_id
            fold_event(state, event)
            self._on_state(state.to_dict())
        ended = time.time()
        self._gateway.stop()

        result = self._collect_target_result(started, ended)
        run = Run(
            run_id=self._run_id, model_code=self._model, model_reason=self._model,
            provider=config.provider_for(self._model), targets=[result],
            started_at=started, ended_at=ended,
            tokens=self._meter.totals()["tokens"],
            cost_usd=self._meter.totals()["cost_usd"],
            cost_estimated=self._meter.totals()["cost_estimated"],
            fp_rate=self._fp_rate([result]), notes="",
        )
        save_run(run)
        return run

    def _collect_target_result(self, started, ended) -> TargetResult:
        """Derive located/confirmed from the loop_state the engine wrote."""
        path = FINDINGS / f"loop_state_{self._target_id}.json"
        located = confirmed = autonomous = False
        t_stat = None
        verdict = "UNKNOWN"
        if path.exists():
            data = load_loop_state(path)
            hyps = data.get("hypotheses", [])
            if hyps:
                best = max(hyps, key=lambda h: abs(h.get("t_statistic") or 0.0))
                gt = GROUND_TRUTH.get(self._target_id, {})
                cat = best.get("category", "")
                loc = best.get("location", "")
                located = (cat == gt.get("category")) and (gt.get("location", "") in loc)
                confirmed = bool(best.get("significant"))
                t_stat = best.get("t_statistic")
                verdict = best.get("status", "UNKNOWN")
                autonomous = "MANDATORY" not in (best.get("evidence", "") or "").upper()
        return TargetResult(
            target_id=self._target_id, located=located, confirmed=confirmed,
            t_stat=t_stat, cycles=data.get("current_cycle", 0) if path.exists() else 0,
            wall_seconds=round(ended - started, 1), autonomous=autonomous, verdict=verdict)

    @staticmethod
    def _fp_rate(results) -> float:
        promoted = [r for r in results if r.verdict == "PROMOTED"]
        if not promoted:
            return 0.0
        wrong = [r for r in promoted if not r.located]
        return round(len(wrong) / len(promoted), 3)
```

- [ ] **Step 2: Add `env_overrides` to LiveSource**

In `viz/sources/live.py`, extend `LiveSource.__init__` to accept `env_overrides: dict | None = None` (store as `self._env = env_overrides or {}`), and in `start()` pass the merged environment to `subprocess.Popen` via `env=`:

```python
import os
...
        full_env = {**os.environ, **self._env}
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, bufsize=1,
                                      env=full_env)
```

- [ ] **Step 3: Smoke-test with a stub engine**

```bash
python -c "
import os, sandbox.run_session as rs
# Confirm env wiring + artifact path resolve without launching a real model:
print('FINDINGS:', rs.FINDINGS)
print('ground truth targets:', list(rs.GROUND_TRUTH))
print('import OK')
"
```

Expected: prints the findings dir, the 3 ground-truth target ids, and `import OK`.

- [ ] **Step 4: Commit**

```bash
git add sandbox/run_session.py viz/sources/live.py
git commit -m "[A] Phase B: run_session.py — gateway + engine + artifact orchestration"
```

---

## Task 13: viz/app.py + import-panel UI (B-i milestone)

**Files:**
- Modify: `viz/app.py` (add API methods)
- Modify: `viz/web/index.html` (import panel)
- Create: `viz/web/sandbox.js`
- Modify: `viz/web/styles.css` (import panel styling)

- [ ] **Step 1: Add API methods to viz/app.py**

In the `API` class in `viz/app.py`, add:

```python
    def list_models(self) -> None:
        from sandbox import config
        self._window.evaluate_js(
            f"window.onModels({json.dumps(config.model_registry())})")

    def model_available(self, model: str) -> bool:
        from sandbox import config
        provider = config.provider_for(model)
        return provider == "ollama" or config.api_key(provider) is not None

    def start_sandbox_run(self, model: str, target_id: str) -> None:
        import threading
        from pathlib import Path
        from sandbox.run_session import RunSession
        targets = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
        meta = next((t for t in targets if t["id"] == target_id), None)
        if not meta or not meta.get("focused_target"):
            return
        target_c = REPO_ROOT / meta["focused_target"]

        def _go():
            RunSession(model, target_id, target_c, on_state=self._push_state).run()

        threading.Thread(target=_go, daemon=True).start()
```

- [ ] **Step 2: Add the import panel to index.html**

In `viz/web/index.html`, inside `#hud` (after `#hud-model`), add:

```html
      <span id="import-panel">
        <select id="model-select"><option value="">— model —</option></select>
        <span id="model-status" class="mono"></span>
      </span>
```

And add `<script src="sandbox.js"></script>` before `pipeline.js`.

- [ ] **Step 3: Create viz/web/sandbox.js**

```javascript
// sandbox.js — Phase B model import. Populates the model dropdown from Python and
// wires Run to start a sandbox run with the selected model.
let selectedModel = "";

window.onModels = function (models) {
  const sel = document.getElementById("model-select");
  models.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.id; o.textContent = m.label;
    sel.appendChild(o);
  });
};

document.addEventListener("DOMContentLoaded", () => {
  if (window.pywebview) window.pywebview.api.list_models();
  const sel = document.getElementById("model-select");
  sel.addEventListener("change", async () => {
    selectedModel = sel.value;
    const status = document.getElementById("model-status");
    if (!selectedModel) { status.textContent = ""; return; }
    const ok = await window.pywebview.api.model_available(selectedModel);
    status.textContent = ok ? selectedModel + " selected" : "no API key for " + selectedModel;
    status.style.color = ok ? "var(--cy)" : "var(--rd)";
  });
});

// Phase B Run: if a model is selected, run it on the focused target via the sandbox.
window.sandboxRun = function (targetId) {
  if (selectedModel && window.pywebview) {
    window.pywebview.api.start_sandbox_run(selectedModel, targetId);
    return true;
  }
  return false;
};
```

- [ ] **Step 4: Style the import panel**

Append to `viz/web/styles.css`:

```css
#import-panel { display: flex; align-items: center; gap: 8px; margin-left: 8px; }
#model-select {
  background: var(--p2); color: var(--tx); border: 1px solid var(--ln);
  border-radius: 6px; padding: 4px 8px; font-family: var(--mono); font-size: 11px;
}
#model-status { font-size: 11px; }
```

- [ ] **Step 5: Manual integration test**

```bash
ollama serve &   # for a local-model run
python run.py
```
In the window: pick "CodeLlama 7B (local)" → "codellama:7b selected" → click a specimen to focus it → Run. The console animates the live run; on finish a `run_*.json` appears in `shared/runs/`. (For an API model, first put a key in `sandbox/secrets.local.json`, e.g. `{"anthropic": "sk-..."}`.)

- [ ] **Step 6: Commit — B-i complete**

```bash
git add viz/app.py viz/web/index.html viz/web/sandbox.js viz/web/styles.css
git commit -m "[A] Phase B B-i complete: model import panel + sandbox run end-to-end"
```

---

# SLICE B-ii — compare

## Task 14: comparison.py — per-axis table + report

**Files:**
- Create: `sandbox/comparison.py`
- Test: `tests/sandbox/test_comparison.py`

- [ ] **Step 1: Write the failing tests**

```python
from sandbox.runstore import Run, TargetResult
from sandbox.comparison import build_comparison, to_markdown


def _run(rid, model, t5_conf, t5_t, cost):
    return Run(
        run_id=rid, model_code=model, model_reason=model, provider="x",
        targets=[TargetResult("kyber512_leak5", located=True, confirmed=t5_conf,
                              t_stat=t5_t, cycles=2, wall_seconds=10.0,
                              autonomous=True, verdict="PROMOTED" if t5_conf else "INVALIDATED")],
        started_at=0.0, ended_at=10.0, tokens={"prompt": 100, "completion": 50},
        cost_usd=cost, cost_estimated=True, fp_rate=0.0, notes="")


def test_build_comparison_axes():
    runs = [_run("a", "codellama:7b", True, 141.0, 0.0),
            _run("b", "gpt-4o", True, 150.0, 0.02)]
    comp = build_comparison(runs)
    assert comp["models"] == ["codellama:7b", "gpt-4o"]
    cell = comp["detection"]["kyber512_leak5"]
    assert cell[0]["confirmed"] is True and cell[1]["t_stat"] == 150.0
    assert comp["efficiency"]["cost_usd"] == [0.0, 0.02]


def test_to_markdown_contains_models_and_targets():
    runs = [_run("a", "codellama:7b", True, 141.0, 0.0)]
    md = to_markdown(build_comparison(runs))
    assert "codellama:7b" in md
    assert "kyber512_leak5" in md
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/sandbox/test_comparison.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement comparison.py**

```python
def build_comparison(runs: list) -> dict:
    """Build a per-axis side-by-side structure from a list of Run objects."""
    models = [r.model_code for r in runs]
    target_ids = []
    for r in runs:
        for t in r.targets:
            if t.target_id not in target_ids:
                target_ids.append(t.target_id)

    detection = {}
    for tid in target_ids:
        detection[tid] = []
        for r in runs:
            tr = next((t for t in r.targets if t.target_id == tid), None)
            detection[tid].append({
                "located": tr.located if tr else None,
                "confirmed": tr.confirmed if tr else None,
                "t_stat": tr.t_stat if tr else None,
            })

    efficiency = {
        "wall_seconds": [round(r.ended_at - r.started_at, 1) for r in runs],
        "cost_usd": [r.cost_usd for r in runs],
        "tokens": [r.tokens.get("prompt", 0) + r.tokens.get("completion", 0) for r in runs],
    }
    robustness = {"fp_rate": [r.fp_rate for r in runs]}
    return {"models": models, "targets": target_ids, "detection": detection,
            "efficiency": efficiency, "robustness": robustness}


def to_markdown(comp: dict) -> str:
    models = comp["models"]
    lines = ["# Model comparison", "",
             "| Target | " + " | ".join(models) + " |",
             "|---|" + "|".join(["---"] * len(models)) + "|"]
    for tid in comp["targets"]:
        cells = []
        for cell in comp["detection"][tid]:
            mark = "✓" if cell["confirmed"] else ("·located" if cell["located"] else "✗")
            t = "" if cell["t_stat"] is None else f" t={cell['t_stat']:.1f}"
            cells.append(mark + t)
        lines.append(f"| {tid} | " + " | ".join(cells) + " |")
    lines += ["",
              "| Axis | " + " | ".join(models) + " |",
              "|---|" + "|".join(["---"] * len(models)) + "|",
              "| wall (s) | " + " | ".join(str(x) for x in comp["efficiency"]["wall_seconds"]) + " |",
              "| cost ($) | " + " | ".join(str(x) for x in comp["efficiency"]["cost_usd"]) + " |",
              "| tokens | " + " | ".join(str(x) for x in comp["efficiency"]["tokens"]) + " |",
              "| fp-rate | " + " | ".join(str(x) for x in comp["robustness"]["fp_rate"]) + " |"]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/sandbox/test_comparison.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add sandbox/comparison.py tests/sandbox/test_comparison.py
git commit -m "[A] Phase B: comparison.py — per-axis table + markdown report"
```

---

## Task 15: Comparison view UI + report (B-ii milestone)

**Files:**
- Modify: `viz/app.py` (comparison API methods)
- Modify: `viz/web/index.html` (comparison-view container + toggle)
- Modify: `viz/web/sandbox.js` (render comparison)
- Modify: `viz/web/styles.css` (comparison columns)

- [ ] **Step 1: Add comparison API to viz/app.py**

In the `API` class:

```python
    def list_runs(self) -> None:
        from dataclasses import asdict
        from sandbox.runstore import list_runs
        runs = [asdict(r) for r in list_runs()]
        self._window.evaluate_js(f"window.onRuns({json.dumps(runs)})")

    def build_comparison(self, run_ids: list) -> None:
        import time
        from pathlib import Path
        from sandbox.runstore import list_runs, RUNS_DIR
        from sandbox.comparison import build_comparison, to_markdown
        chosen = [r for r in list_runs() if r.run_id in run_ids]
        comp = build_comparison(chosen)
        md = to_markdown(comp)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        (RUNS_DIR / f"comparison_{stamp}.md").write_text(md, encoding="utf-8")
        self._window.evaluate_js(f"window.onComparison({json.dumps(comp)})")
```

- [ ] **Step 2: Add comparison-view container + toggle to index.html**

In `#hud`, add a toggle button:
```html
      <button id="btn-compare" onclick="toggleCompare()">⇄ Compare</button>
```
After `#stage`, add a hidden comparison container:
```html
    <section id="compare-view" style="display:none;">
      <div id="compare-runs"></div>
      <div id="compare-table"></div>
    </section>
```

- [ ] **Step 3: Render comparison in sandbox.js**

Append to `viz/web/sandbox.js`:

```javascript
let allRuns = [];
const chosenRuns = new Set();

window.onRuns = function (runs) {
  allRuns = runs;
  const box = document.getElementById("compare-runs");
  box.innerHTML = runs.map((r) =>
    `<label class="run-chip"><input type="checkbox" value="${r.run_id}"
      onchange="toggleRun('${r.run_id}', this.checked)"> ${r.model_code}
      <span class="mono">${r.run_id}</span></label>`).join("") ||
    '<span class="mono" style="color:var(--dim)">no saved runs yet</span>';
};

window.toggleRun = function (id, on) {
  if (on) chosenRuns.add(id); else chosenRuns.delete(id);
  if (chosenRuns.size >= 2) window.pywebview.api.build_comparison([...chosenRuns]);
};

window.onComparison = function (comp) {
  const t = document.getElementById("compare-table");
  let html = "<table class='cmp'><tr><th>Target</th>" +
    comp.models.map((m) => `<th>${m}</th>`).join("") + "</tr>";
  comp.targets.forEach((tid) => {
    html += `<tr><td>${tid}</td>` + comp.detection[tid].map((c) => {
      const mark = c.confirmed ? "✓" : (c.located ? "·loc" : "✗");
      const ts = c.t_stat == null ? "" : ` t=${c.t_stat.toFixed(1)}`;
      return `<td>${mark}${ts}</td>`;
    }).join("") + "</tr>";
  });
  html += "<tr><td>cost $</td>" + comp.efficiency.cost_usd.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "<tr><td>wall s</td>" + comp.efficiency.wall_seconds.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "<tr><td>fp-rate</td>" + comp.robustness.fp_rate.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "</table>";
  t.innerHTML = html;
};

window.toggleCompare = function () {
  const cv = document.getElementById("compare-view");
  const stage = document.getElementById("stage");
  const show = cv.style.display === "none";
  cv.style.display = show ? "" : "none";
  stage.style.display = show ? "none" : "grid";
  if (show && window.pywebview) window.pywebview.api.list_runs();
};
```

- [ ] **Step 4: Style the comparison table**

Append to `viz/web/styles.css`:

```css
#compare-view { padding: 16px 20px; overflow-y: auto; }
#compare-runs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.run-chip { font-size: 12px; color: var(--tx2); display: flex; align-items: center; gap: 5px; }
table.cmp { border-collapse: collapse; font-family: var(--mono); font-size: 12px; }
table.cmp th, table.cmp td { border: 1px solid var(--ln); padding: 6px 12px; text-align: left; }
table.cmp th { color: var(--mut); }
```

- [ ] **Step 5: Manual integration test**

```bash
python run.py
```
Run two models on the same target (Task 13 flow) so `shared/runs/` has ≥2 artifacts. Click ⇄ Compare → check two runs → the comparison table renders columns per model and a `comparison_*.md` is written to `shared/runs/`.

- [ ] **Step 6: Commit — B-ii complete**

```bash
git add viz/app.py viz/web/index.html viz/web/sandbox.js viz/web/styles.css
git commit -m "[A] Phase B B-ii complete: comparison view + report"
```

---

## Self-review notes (addressed)

- **Spec coverage:** gateway shim (Tasks 6-9), Ollama+Anthropic+OpenAI providers (Task 6), sequential saved runs (Tasks 11-12), four axes — detection (Task 12 `_collect_target_result`), signal t-stat (TargetResult.t_stat), efficiency tokens/cost/wall (meter + run_session), robustness fp_rate/autonomous (run_session) — all present. Engine env change additive (Task 10). Security: keys via config, gitignored, never in artifacts (Task 11 test asserts no key fields). Two slices delivered (Task 13 = B-i, Task 15 = B-ii).
- **`located` data source:** derived from the engine's `loop_state` file in `_collect_target_result`, matching the spec (stdout lacks category/location).
- **Type consistency:** `Run`/`TargetResult` fields are identical across runstore (def), run_session (construction), comparison (consumption), and the runstore tests. `Meter.totals()` shape (`calls`/`tokens`/`cost_usd`/`cost_estimated`) consumed consistently in run_session. `ChatResult.usage` is `{prompt, completion}` everywhere; meter and pricing consume the same keys.
- **LiveSource change:** Task 12 Step 2 adds the `env_overrides` parameter the run_session relies on; no other caller passes it (default `None` keeps Phase A behaviour).
