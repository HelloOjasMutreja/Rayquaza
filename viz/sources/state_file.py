import json
from pathlib import Path


def load_loop_state(path: Path) -> dict:
    """Parse a loop_state JSON file, return the raw dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def hypotheses_from_state(data: dict) -> list:
    """Return the list of hypothesis records from a parsed loop_state dict."""
    return data.get("hypotheses", [])


def target_id_from_state(data: dict) -> str:
    """Derive the target id from the target_file field.

    Consults viz/targets.json first (exact focused_target match), then falls
    back to the '_focused' suffix-strip heuristic for kyber512 targets.
    """
    target_file = data.get("target_file", "")
    if not target_file:
        return ""

    # Normalise path separators for comparison (engine may use any slash)
    target_file_norm = target_file.replace("\\", "/")

    # Registry lookup — most reliable for targets with non-standard filenames
    _TARGETS_JSON = Path(__file__).resolve().parent.parent / "targets.json"
    if _TARGETS_JSON.exists():
        try:
            import json as _json
            registry = _json.loads(_TARGETS_JSON.read_text(encoding="utf-8"))
            for entry in registry:
                ft = (entry.get("focused_target") or "").replace("\\", "/")
                if ft and ft in target_file_norm:
                    return entry["id"]
        except Exception:
            pass

    # Heuristic fallback: strip '_focused' suffix
    stem = Path(target_file).stem
    return stem.replace("_focused", "")
