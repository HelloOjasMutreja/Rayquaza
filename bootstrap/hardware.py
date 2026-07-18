"""bootstrap/hardware.py -- detect available RAM/disk and recommend an
Ollama model tier.

Detection happens from wherever this runs (inside the runner container,
when used via Docker), so it reflects whatever resources are actually
available to the process, not necessarily the host's full specs -- a Docker
Desktop memory limit is respected automatically for exactly this reason.
"""
from dataclasses import dataclass

import platform
import psutil
import shutil


@dataclass(frozen=True)
class ModelTier:
    name: str
    models: tuple[str, ...]
    min_ram_gb: float
    min_disk_gb: float
    approx_download_gb: float
    label: str
    faithful: bool  # True if this tier reproduces the original paper's models


TIERS: tuple[ModelTier, ...] = (
    ModelTier(
        name="original",
        models=("codellama:7b", "qwen3:8b"),
        min_ram_gb=16.0,
        min_disk_gb=12.0,
        approx_download_gb=9.5,
        label="Original models (codellama:7b + qwen3:8b): faithful reproduction",
        faithful=True,
    ),
    ModelTier(
        name="lightweight",
        models=("qwen2.5:3b", "phi3:mini"),
        min_ram_gb=8.0,
        min_disk_gb=6.0,
        approx_download_gb=4.0,
        label="Lightweight models (qwen2.5:3b + phi3:mini): results may differ from the original paper",
        faithful=False,
    ),
)


def detect_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def detect_disk_gb(path: str = "/") -> float:
    return shutil.disk_usage(path).free / (1024 ** 3)


def recommend_tier(ram_gb: float, disk_gb: float) -> ModelTier | None:
    """Return the best-fitting tier for the given resources, preferring the
    faithful/original tier when both fit (TIERS is ordered original-first).
    Returns None if neither tier's minimums are met; the caller decides
    whether to warn and let the user proceed anyway."""
    for tier in TIERS:
        if ram_gb >= tier.min_ram_gb and disk_gb >= tier.min_disk_gb:
            return tier
    return None


def tier_by_name(name: str) -> ModelTier:
    for tier in TIERS:
        if tier.name == name:
            return tier
    raise ValueError(f"unknown tier: {name}")


def fits_disk(tier: ModelTier, disk_gb: float) -> bool:
    """Re-check a specific tier's download size against free disk right
    before pulling, separately from recommend_tier's broader thresholds
    (which include a comfort margin for running the models, not just
    downloading them)."""
    return disk_gb >= tier.approx_download_gb


def is_apple_silicon() -> bool:
    """True on macOS/arm64, where Docker has no Metal passthrough, so
    Ollama running inside a container is CPU-only regardless of what the
    host hardware could otherwise do."""
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")
