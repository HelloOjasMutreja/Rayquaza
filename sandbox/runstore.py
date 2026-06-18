import json
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "shared" / "runs"


@dataclass
class TargetResult:
    target_id: str
    located: bool
    confirmed: bool
    t_stat: float | None
    cycles: int
    wall_seconds: float
    autonomous: bool
    verdict: str


@dataclass
class Run:
    run_id: str
    model_code: str
    model_reason: str
    provider: str
    targets: list[TargetResult]
    started_at: float
    ended_at: float
    tokens: dict
    cost_usd: float
    cost_estimated: bool
    fp_rate: float
    notes: str = ""


def save_run(run: Run, runs_dir: Path = RUNS_DIR) -> Path:
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"run_{run.run_id}.json"
    path.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
    return path


def load_run(path: Path) -> Run:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["targets"] = [TargetResult(**t) for t in data["targets"]]
    return Run(**data)


def list_runs(runs_dir: Path = RUNS_DIR) -> list[Run]:
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return []
    return [load_run(p) for p in sorted(runs_dir.glob("run_*.json"))]
