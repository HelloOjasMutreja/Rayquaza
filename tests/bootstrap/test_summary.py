import json
from pathlib import Path

from bootstrap.summary import build_summary


def _write_snapshot(findings_dir: Path, target: str, hypotheses: list[dict]) -> None:
    findings_dir.mkdir(parents=True, exist_ok=True)
    snapshot = findings_dir / f"loop_state_{target}.json"
    snapshot.write_text(json.dumps({"hypotheses": hypotheses}), encoding="utf-8")


def test_build_summary_reads_promoted_hypothesis(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak1", [
        {"id": "H001", "status": "PROMOTED", "t_statistic": 213.4791},
    ])

    rows = build_summary(tmp_path, ["kyber512_leak1"])

    assert rows == [{
        "target": "kyber512_leak1",
        "hypothesis_id": "H001",
        "verdict": "PROMOTED",
        "t_statistic": 213.4791,
    }]


def test_build_summary_handles_missing_snapshot(tmp_path):
    rows = build_summary(tmp_path, ["kyber512_leak2"])

    assert rows == [{
        "target": "kyber512_leak2",
        "hypothesis_id": None,
        "verdict": "NO RESULT",
        "t_statistic": None,
    }]


def test_build_summary_handles_empty_hypotheses_list(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak3", [])

    rows = build_summary(tmp_path, ["kyber512_leak3"])

    assert rows == [{
        "target": "kyber512_leak3",
        "hypothesis_id": None,
        "verdict": "NO HYPOTHESES",
        "t_statistic": None,
    }]


def test_build_summary_handles_multiple_hypotheses_for_one_target(tmp_path):
    _write_snapshot(tmp_path, "kyber512_leak4", [
        {"id": "H001", "status": "DEMOTED", "t_statistic": 1.2},
        {"id": "H002", "status": "PROMOTED", "t_statistic": 88.0},
    ])

    rows = build_summary(tmp_path, ["kyber512_leak4"])

    assert len(rows) == 2
    assert rows[0]["verdict"] == "DEMOTED"
    assert rows[1]["verdict"] == "PROMOTED"
