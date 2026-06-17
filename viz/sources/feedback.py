import json
from pathlib import Path


def load_timing(path: Path) -> dict:
    """Parse a timing JSON file, return the raw dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def result_from_timing(timing: dict, status: str) -> dict:
    """Convert a timing dict + hypothesis status into the result payload stored on HypState."""
    return {
        "t_stat": timing.get("t_statistic"),
        "significant": timing.get("significant"),
        "mean_A": timing.get("mean_A"),
        "mean_B": timing.get("mean_B"),
        "verdict": status,
    }
