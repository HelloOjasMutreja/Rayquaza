"""bootstrap/build_check.py -- verify the Docker image's build step actually
produced what the wizard needs before it tries to use any of it."""
from pathlib import Path

TARGET_DIRS = (
    "kyber512_leak1",
    "kyber512_leak2",
    "kyber512_leak3",
    "kyber512_leak4",
    "kyber512_leak5",
)

LIBOQS_COMMIT_FILE = Path("/build-info/liboqs-commit.txt")


def missing_binaries(targets_root: Path, target_dirs: tuple[str, ...] = TARGET_DIRS) -> list[str]:
    """Return the subset of target_dirs whose harness_oracle binary is missing."""
    missing = []
    for name in target_dirs:
        binary = targets_root / name / "harness_oracle"
        if not binary.exists():
            missing.append(name)
    return missing


def read_liboqs_commit(commit_file: Path = LIBOQS_COMMIT_FILE) -> str:
    """Return the liboqs commit SHA baked into the image, or a placeholder
    string if the file is missing (e.g. when running outside Docker)."""
    if not commit_file.exists():
        return "unknown (not running inside the built image)"
    return commit_file.read_text(encoding="utf-8").strip()
