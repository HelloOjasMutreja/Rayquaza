"""bootstrap/ollama_client.py -- thin wrapper around the Ollama HTTP API for
the two things the wizard needs: waiting for the service to be reachable,
and pulling a model with progress feedback."""
import json
import time
from typing import Iterator

import requests


def wait_until_ready(base_url: str, timeout_s: float = 60.0, interval_s: float = 2.0) -> bool:
    """Poll base_url until Ollama responds or timeout_s elapses. Returns
    True if it became ready, False on timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = requests.get(base_url, timeout=5)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval_s)
    return False


def pull_model(base_url: str, model: str) -> Iterator[dict]:
    """Stream progress events from Ollama's /api/pull for `model`. Yields the
    parsed JSON object from each non-blank line Ollama sends, e.g.
    {"status": "pulling manifest"} or
    {"status": "downloading", "completed": 123, "total": 456}.
    Raises requests.exceptions.HTTPError if the pull request itself fails."""
    resp = requests.post(
        f"{base_url}/api/pull",
        json={"name": model, "stream": True},
        stream=True,
        timeout=None,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        yield json.loads(line)
