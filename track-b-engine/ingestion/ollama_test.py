#!/usr/bin/env python3
"""
ollama_test.py — Stage 1 smoke test: send dummy.c to codellama:7b and validate JSON output.
Run from repo root: python3 track-b-engine/ingestion/ollama_test.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "codellama:7b"
DUMMY_C = Path(__file__).parent / "test_targets" / "dummy.c"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "shared" / "findings"
OUTPUT_FILE = OUTPUT_DIR / "ollama_test_output.json"

SYSTEM_PROMPT = (
    "You are a cryptographic security analyst. "
    "Identify timing side-channel risks in C code. Return ONLY "
    "a JSON array of findings. No explanation. No markdown."
)


def main():
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' library not installed. Run: pip3 install requests")
        sys.exit(1)

    source = DUMMY_C.read_text()

    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": source},
        ],
    }

    print(f"[{datetime.now().isoformat()}] Sending dummy.c to {MODEL} at {OLLAMA_URL} ...")

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("Ollama not running. Start with: ollama serve")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out after 120s. Is Ollama overloaded?")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP {resp.status_code} — {e}")
        sys.exit(1)

    data = resp.json()
    raw_content = data.get("message", {}).get("content", "")

    print("\n--- Raw model response ---")
    print(raw_content)
    print("--------------------------\n")

    try:
        findings = json.loads(raw_content)
        print(f"Parsed {len(findings)} finding(s) successfully.")
    except json.JSONDecodeError as e:
        print(f"WARNING: Response is not valid JSON — {e}")
        findings = {"raw": raw_content, "parse_error": str(e)}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL,
        "source_file": str(DUMMY_C),
        "findings": findings,
    }
    OUTPUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
