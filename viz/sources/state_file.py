import json
from pathlib import Path


def load_loop_state(path: Path) -> dict:
    """Parse a loop_state JSON file, return the raw dict."""
    return json.loads(Path(path).read_text())


def hypotheses_from_state(data: dict) -> list:
    """Return the list of hypothesis records from a parsed loop_state dict."""
    return data.get("hypotheses", [])


def target_id_from_state(data: dict) -> str:
    """Derive the target id (e.g. 'kyber512_leak5') from the target_file field.

    target_file looks like: 'track-b-engine/ingestion/test_targets/kyber512_leak5_focused.c'
    We take the stem ('kyber512_leak5_focused') and strip '_focused'.
    """
    target_file = data.get("target_file", "")
    stem = Path(target_file).stem          # e.g. 'kyber512_leak5_focused'
    return stem.replace("_focused", "")    # e.g. 'kyber512_leak5'
