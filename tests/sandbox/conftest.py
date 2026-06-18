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
