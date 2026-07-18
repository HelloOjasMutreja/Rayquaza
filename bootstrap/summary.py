"""bootstrap/summary.py -- turn per-target loop_state snapshots (written by
run_focused.sh) into a plain summary the wizard can print, without the
caller needing to understand the full engine JSON schema."""
import json
from pathlib import Path


def build_summary(findings_dir: Path, target_dirs: list[str]) -> list[dict]:
    """For each target dir name, read shared/findings/loop_state_<name>.json
    and return one row per hypothesis found:
    {"target": str, "hypothesis_id": str | None, "verdict": str, "t_statistic": float | None}.
    A target with no snapshot file yet (run failed or hasn't finished) gets a
    single row with verdict "NO RESULT". A snapshot with no hypotheses gets
    a single row with verdict "NO HYPOTHESES"."""
    rows = []
    for name in target_dirs:
        snapshot = findings_dir / f"loop_state_{name}.json"
        if not snapshot.exists():
            rows.append({
                "target": name,
                "hypothesis_id": None,
                "verdict": "NO RESULT",
                "t_statistic": None,
            })
            continue
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        hypotheses = data.get("hypotheses", [])
        if not hypotheses:
            rows.append({
                "target": name,
                "hypothesis_id": None,
                "verdict": "NO HYPOTHESES",
                "t_statistic": None,
            })
            continue
        for hyp in hypotheses:
            rows.append({
                "target": name,
                "hypothesis_id": hyp.get("id"),
                "verdict": hyp.get("status", "UNKNOWN"),
                "t_statistic": hyp.get("t_statistic"),
            })
    return rows
