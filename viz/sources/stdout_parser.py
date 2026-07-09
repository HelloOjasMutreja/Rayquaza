import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    event_type: str   # run_start | wait_start | hyp_result | loop_complete | rayqevent
    data: dict = field(default_factory=dict)


_STARTING_RE   = re.compile(r"Starting cycle 1 of (\d+)")
_WAITING_RE    = re.compile(r"waiting for feedback file timing_(.+?)_\*\.json")
_RESULT_RE     = re.compile(
    r"\[Cycle \d+\] Hypothesis (\w+) → (\w+) \(t=([0-9.\-]+), sig=(True|False)\)"
)
_COMPLETE_RE   = re.compile(r"=== LOOP COMPLETE ===")
_RAYQEVENT_RE  = re.compile(r"^RAYQEVENT::(.+)$")


def parse_line(line: str) -> Optional[ParseResult]:
    """Parse one stdout line from the engine. Returns None for unrecognised lines."""
    line = line.strip()
    if not line:
        return None

    m = _RAYQEVENT_RE.match(line)
    if m:
        try:
            data = json.loads(m.group(1))
            return ParseResult(event_type="rayqevent", data=data)
        except json.JSONDecodeError:
            return None

    m = _STARTING_RE.search(line)
    if m:
        return ParseResult(event_type="run_start",
                           data={"total_cycles": int(m.group(1))})

    m = _WAITING_RE.search(line)
    if m:
        return ParseResult(event_type="wait_start",
                           data={"hyp_id": m.group(1)})

    m = _RESULT_RE.search(line)
    if m:
        return ParseResult(event_type="hyp_result", data={
            "hyp_id":      m.group(1),
            "status":      m.group(2),
            "t_stat":      float(m.group(3)),
            "significant": m.group(4) == "True",
        })

    if _COMPLETE_RE.search(line):
        return ParseResult(event_type="loop_complete", data={})

    return None
