"""bootstrap/wizard.py -- the interactive CLI that runs inside the `runner`
container. Detects hardware, picks a model tier, pulls it, runs the engine
against the chosen Kyber512 target(s) via run_focused.sh, and prints a
summary.

ML-DSA-44 (mldsa44_leak1) is intentionally not part of this automated flow:
it needs a bespoke synthetic target file (not a generic "*_focused.c" file
like the five Kyber leaks) and its timing signal only reproduces on x86 (see
EXPERIMENT_LOG.md, 2026-06-17 REPS check). ARM hosts read a non-significant
t-stat that would look like a broken setup rather than a documented,
already-published architecture difference. See docs/reproducing-mldsa.md
for the manual steps.
"""
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn
from rich.prompt import IntPrompt
from rich.table import Table

from bootstrap.build_check import TARGET_DIRS, missing_binaries, read_liboqs_commit
from bootstrap.hardware import (
    TIERS,
    detect_disk_gb,
    detect_ram_gb,
    fits_disk,
    is_apple_silicon,
    recommend_tier,
    tier_by_name,
)
from bootstrap.ollama_client import pull_model, wait_until_ready
from bootstrap.summary import build_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS_ROOT = REPO_ROOT / "track-a-target" / "targets"
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"
OLLAMA_BASE_URL = os.environ.get("RAYQ_OLLAMA_BASE", "http://ollama:11434")

FOCUSED_TARGETS = {
    name: REPO_ROOT / "track-b-engine" / "ingestion" / "test_targets" / f"{name}_focused.c"
    for name in TARGET_DIRS
}

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold]RAYQUAZA[/bold] -- Post-Quantum Timing-Leak Discovery\n"
        "LLM-guided rediscovery of planted PQC side-channels",
        border_style="cyan",
    ))
    if is_apple_silicon():
        console.print(
            "[yellow]Note:[/yellow] Docker has no Metal passthrough on Apple "
            "Silicon, so Ollama will run CPU-only in this container. A native "
            "Ollama install outside Docker (pointed at with OLLAMA_HOST) would "
            "be faster on this machine if you want it. This run will still "
            "work, just more slowly.\n"
        )


def _check_build() -> str:
    missing = missing_binaries(TARGETS_ROOT, TARGET_DIRS)
    if missing:
        console.print(f"[red]Missing built targets: {', '.join(missing)}[/red]")
        console.print("The image build likely failed. Try: [bold]docker compose build --no-cache[/bold]")
        sys.exit(1)
    commit = read_liboqs_commit()
    console.print(f"[green]OK[/green] Build toolchain OK (liboqs commit {commit})")
    return commit


def _wait_for_ollama() -> None:
    console.print("Waiting for Ollama service...", end=" ")
    if not wait_until_ready(OLLAMA_BASE_URL, timeout_s=90):
        console.print("[red]unreachable[/red]")
        console.print("Check it with: [bold]docker compose logs ollama[/bold]")
        sys.exit(1)
    console.print("[green]OK[/green]")


def _choose_tier():
    ram_gb = detect_ram_gb()
    disk_gb = detect_disk_gb()
    console.print(f"RAM available:   {ram_gb:.1f} GB")
    console.print(f"Disk available: {disk_gb:.1f} GB")

    recommended = recommend_tier(ram_gb, disk_gb)
    if recommended is None:
        console.print(
            "[yellow]Neither model tier's minimums are comfortably met on this "
            "machine. You can still try the lightweight tier, but pulls or runs "
            "may be slow.[/yellow]"
        )
        recommended = tier_by_name("lightweight")

    console.print(f"\nRecommended: [bold]{recommended.label}[/bold]")
    for i, tier in enumerate(TIERS, start=1):
        marker = " (recommended)" if tier.name == recommended.name else ""
        console.print(f"  [{i}] {tier.label}{marker}")

    default_choice = next(i for i, t in enumerate(TIERS, start=1) if t.name == recommended.name)
    choice = IntPrompt.ask(
        "Which would you like?",
        default=default_choice,
        choices=[str(i) for i in range(1, len(TIERS) + 1)],
    )
    return TIERS[choice - 1]


def _pull_models(tier):
    """Pull every model in `tier`, re-checking free disk right before
    pulling (recommend_tier already checked once, but that was before the
    user's final choice, and disk can be tighter than the broader
    recommendation thresholds account for). Falls back to the lightweight
    tier once, with a clear message, rather than starting a download that
    can't finish; exits if even that doesn't fit. Returns the tier actually
    used, since a fallback means it may differ from what was passed in."""
    disk_gb = detect_disk_gb()
    if not fits_disk(tier, disk_gb):
        console.print(
            f"[yellow]Only {disk_gb:.1f} GB free, but {tier.label} needs "
            f"~{tier.approx_download_gb:.1f} GB to download.[/yellow]"
        )
        if tier.name != "lightweight":
            fallback = tier_by_name("lightweight")
            if fits_disk(fallback, disk_gb):
                console.print(f"Falling back to: [bold]{fallback.label}[/bold]")
                tier = fallback
            else:
                console.print("[red]Not enough disk space even for the lightweight tier. Free up space and try again.[/red]")
                sys.exit(1)
        else:
            console.print("[red]Not enough disk space for the lightweight tier. Free up space and try again.[/red]")
            sys.exit(1)

    for model in tier.models:
        console.print(f"Pulling {model}...")
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(model, total=None)
            for event in pull_model(OLLAMA_BASE_URL, model):
                total = event.get("total")
                completed = event.get("completed")
                if total and completed is not None:
                    progress.update(task, total=total, completed=completed)
        console.print(f"[green]OK[/green] {model} ready")
    return tier


def _choose_targets() -> list[str]:
    console.print("\nRun all 5 Kyber targets, or just one to start?")
    console.print("  [1] All 5 (full reproduction)")
    console.print("  [2] Just kyber512_leak1 (fast first taste)")
    console.print(
        "  Note: mldsa44_leak1 is not included here -- it needs an x86 host "
        "to reproduce a significant result. See docs/reproducing-mldsa.md."
    )
    choice = IntPrompt.ask("Choice", default=2, choices=["1", "2"])
    if choice == 1:
        return list(FOCUSED_TARGETS.keys())
    return ["kyber512_leak1"]


def _run_target(name: str, tier) -> None:
    console.rule(name)
    script = REPO_ROOT / "track-b-engine" / "run_focused.sh"
    focused_file = FOCUSED_TARGETS[name]
    env = {**os.environ, "RAYQ_CODE_MODEL": tier.models[0], "RAYQ_REASON_MODEL": tier.models[1]}
    subprocess.run(
        ["bash", str(script), str(focused_file), name],
        cwd=REPO_ROOT,
        check=False,
        env=env,
    )


def _print_summary(targets: list[str], commit: str) -> None:
    rows = build_summary(FINDINGS_DIR, targets)
    table = Table(title="Summary")
    table.add_column("Target")
    table.add_column("Hypothesis")
    table.add_column("Verdict")
    table.add_column("t-stat")
    for row in rows:
        t_stat = f"{row['t_statistic']:.1f}" if row["t_statistic"] is not None else "-"
        table.add_row(row["target"], row["hypothesis_id"] or "-", row["verdict"], t_stat)
    console.print(table)
    console.print(f"liboqs commit: {commit}")
    console.print(f"Full results saved to {FINDINGS_DIR} and {REPO_ROOT / 'shared' / 'feedback'}")
    console.print("Run again any time with: docker compose run --rm runner")


def main() -> None:
    _banner()
    commit = _check_build()
    _wait_for_ollama()
    tier = _choose_tier()
    tier = _pull_models(tier)
    targets = _choose_targets()
    for name in targets:
        _run_target(name, tier)
    _print_summary(targets, commit)


if __name__ == "__main__":
    main()
