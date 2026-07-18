import json
from unittest.mock import Mock, patch

import requests

from bootstrap.ollama_client import pull_model, wait_until_ready


def test_wait_until_ready_returns_true_on_first_success():
    with patch("bootstrap.ollama_client.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200)
        assert wait_until_ready("http://ollama:11434", timeout_s=5, interval_s=0.01) is True


def test_wait_until_ready_returns_false_on_timeout():
    with patch(
        "bootstrap.ollama_client.requests.get",
        side_effect=requests.exceptions.ConnectionError(),
    ):
        assert wait_until_ready("http://ollama:11434", timeout_s=0.05, interval_s=0.01) is False


def test_pull_model_yields_parsed_progress_lines():
    fake_lines = [
        json.dumps({"status": "pulling manifest"}).encode(),
        json.dumps({"status": "downloading", "completed": 50, "total": 100}).encode(),
        json.dumps({"status": "success"}).encode(),
    ]
    mock_resp = Mock()
    mock_resp.iter_lines.return_value = fake_lines
    mock_resp.raise_for_status.return_value = None

    with patch("bootstrap.ollama_client.requests.post", return_value=mock_resp):
        events = list(pull_model("http://ollama:11434", "qwen2.5:3b"))

    assert events[0]["status"] == "pulling manifest"
    assert events[1]["completed"] == 50
    assert events[-1]["status"] == "success"


def test_pull_model_skips_blank_lines():
    fake_lines = [b"", json.dumps({"status": "success"}).encode(), b""]
    mock_resp = Mock()
    mock_resp.iter_lines.return_value = fake_lines
    mock_resp.raise_for_status.return_value = None

    with patch("bootstrap.ollama_client.requests.post", return_value=mock_resp):
        events = list(pull_model("http://ollama:11434", "phi3:mini"))

    assert events == [{"status": "success"}]
