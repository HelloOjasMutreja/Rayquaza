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
