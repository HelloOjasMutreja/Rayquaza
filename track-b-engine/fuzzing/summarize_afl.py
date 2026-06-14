#!/usr/bin/env python3
"""
summarize_afl.py — Parse an AFL++ output directory into a baseline summary JSON.

Usage: python3 summarize_afl.py <afl_findings_dir> <duration_seconds>
Output: shared/findings/afl_baseline_<date>.json

AFL++ output layout (single-instance, "default" sub-dir on AFL++ 4.x; older
layouts put the files at the top level — both are handled):
  <out>/default/fuzzer_stats
  <out>/default/crashes/
  <out>/default/queue/
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SHARED_FINDINGS = REPO_ROOT / "shared" / "findings"


def _resolve_instance_dir(out_dir: Path) -> Path:
    """AFL++ 4.x writes into <out>/default/; fall back to <out> itself."""
    default = out_dir / "default"
    if (default / "fuzzer_stats").exists() or (default / "queue").exists():
        return default
    return out_dir


def _parse_fuzzer_stats(stats_path: Path) -> dict:
    stats = {}
    if not stats_path.exists():
        return stats
    for line in stats_path.read_text().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            stats[k.strip()] = v.strip()
    return stats


def _count_files(d: Path) -> int:
    if not d.is_dir():
        return 0
    # Exclude AFL++ bookkeeping entries like README.txt and .state.
    return sum(
        1
        for p in d.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.name != "README.txt"
    )


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <afl_findings_dir> <duration_seconds>")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    duration = int(sys.argv[2])
    inst = _resolve_instance_dir(out_dir)

    stats = _parse_fuzzer_stats(inst / "fuzzer_stats")
    total_execs = int(stats.get("execs_done", 0) or 0)

    unique_crashes = _count_files(inst / "crashes")
    unique_paths = _count_files(inst / "queue")

    start_time = stats.get("start_time")
    last_update = stats.get("last_update")
    start_iso = (
        datetime.fromtimestamp(int(start_time)).isoformat() if start_time else None
    )
    end_iso = (
        datetime.fromtimestamp(int(last_update)).isoformat() if last_update else None
    )

    result = {
        "total_execs": total_execs,
        "unique_crashes": unique_crashes,
        "unique_paths": unique_paths,
        "duration_seconds": duration,
        "start_time": start_iso,
        "end_time": end_iso,
        "coverage_estimate": "see afl++ plot_data",
        "generated_by": "summarize_afl.py",
        "afl_instance_dir": str(inst),
    }

    SHARED_FINDINGS.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    out_path = SHARED_FINDINGS / f"afl_baseline_{date}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
