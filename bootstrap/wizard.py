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
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn
from rich.prompt import Confirm, IntPrompt
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

# Rayquaza design-system palette (docs/style/tokens.css), reused here so the
# terminal wizard visually matches the PDF/DOCX design system and, more
# specifically, the pipeline diagram's own per-stage colors
# (docs/paper/figures/core_pipeline.eraser): Stage 1/3 ingestion/vectorize
# is blue, the Timing Oracle is green, Stage 2 refine is orange, and the
# feedback/re-hypothesize loop -- along with anything else "wrong, miss, or
# warning" -- is red.
BLUE = "#0099FF"
GREEN = "#2FBB45"
ORANGE = "#DC762D"
RED = "#FB2C55"
BORDER = "#BEBEBE"
INK_SOFT = "#313131"

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS_ROOT = REPO_ROOT / "track-a-target" / "targets"
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"
OLLAMA_BASE_URL = os.environ.get("RAYQ_OLLAMA_BASE", "http://ollama:11434")

FOCUSED_TARGETS = {
    name: REPO_ROOT / "track-b-engine" / "ingestion" / "test_targets" / f"{name}_focused.c"
    for name in TARGET_DIRS
}
ALL_TARGET_NAMES = list(FOCUSED_TARGETS.keys())

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold]RAYQUAZA[/bold] -- Post-Quantum Timing-Leak Discovery\n"
        "LLM-guided rediscovery of planted PQC side-channels",
        border_style=BLUE,
    ))
    if is_apple_silicon():
        console.print(
            f"[{ORANGE}]Note:[/] Docker has no Metal passthrough on Apple "
            "Silicon, so Ollama will run CPU-only in this container. A native "
            "Ollama install outside Docker (pointed at with OLLAMA_HOST) would "
            "be faster on this machine if you want it. This run will still "
            "work, just more slowly.\n"
        )


def _check_build() -> str:
    missing = missing_binaries(TARGETS_ROOT, TARGET_DIRS)
    if missing:
        console.print(f"[{RED}]Missing built targets: {', '.join(missing)}[/]")
        console.print("The image build likely failed. Try: [bold]docker compose build --no-cache[/bold]")
        sys.exit(1)
    commit = read_liboqs_commit()
    console.print(f"[{GREEN}]OK[/] Build toolchain OK (liboqs commit {commit})")
    return commit


def _wait_for_ollama() -> None:
    console.print("Waiting for Ollama service...", end=" ")
    if not wait_until_ready(OLLAMA_BASE_URL, timeout_s=90):
        console.print(f"[{RED}]unreachable[/]")
        console.print("Check it with: [bold]docker compose logs ollama[/bold]")
        sys.exit(1)
    console.print(f"[{GREEN}]OK[/]")


def _choose_tier():
    ram_gb = detect_ram_gb()
    disk_gb = detect_disk_gb()

    recommended = recommend_tier(ram_gb, disk_gb)
    warning = ""
    if recommended is None:
        warning = (
            f"\n[{ORANGE}]Neither model tier's minimums are comfortably met on this "
            "machine. You can still try the lightweight tier, but pulls or runs "
            "may be slow.[/]"
        )
        recommended = tier_by_name("lightweight")

    lines = [
        f"RAM available:   {ram_gb:.1f} GB",
        f"Disk available: {disk_gb:.1f} GB",
    ]
    if warning:
        lines.append(warning)
    lines.append("")
    lines.append(f"Recommended: [bold]{recommended.label}[/bold]")
    for i, tier in enumerate(TIERS, start=1):
        marker = " (recommended)" if tier.name == recommended.name else ""
        lines.append(f"  [{i}] {tier.label}{marker}")
    console.print(Panel("\n".join(lines), border_style=BORDER, title="Model tier", title_align="left"))

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
            f"[{ORANGE}]Only {disk_gb:.1f} GB free, but {tier.label} needs "
            f"~{tier.approx_download_gb:.1f} GB to download.[/]"
        )
        if tier.name != "lightweight":
            fallback = tier_by_name("lightweight")
            if fits_disk(fallback, disk_gb):
                console.print(f"Falling back to: [bold]{fallback.label}[/bold]")
                tier = fallback
            else:
                console.print(f"[{RED}]Not enough disk space even for the lightweight tier. Free up space and try again.[/]")
                sys.exit(1)
        else:
            console.print(f"[{RED}]Not enough disk space for the lightweight tier. Free up space and try again.[/]")
            sys.exit(1)

    for model in tier.models:
        console.print(f"Pulling {model}...")
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(complete_style=GREEN, finished_style=GREEN),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(model, total=None)
            for event in pull_model(OLLAMA_BASE_URL, model):
                total = event.get("total")
                completed = event.get("completed")
                if total and completed is not None:
                    progress.update(task, total=total, completed=completed)
        console.print(f"[{GREEN}]OK[/] {model} ready")
    return tier


def _choose_start_mode() -> str:
    """Ask whether to run all 5 Kyber targets back to back, or start with
    just the first one. Returns "all" or "incremental"; the caller
    (_run_targets) decides what to do with that, including whether to ask
    about continuing between targets."""
    console.print("\nRun all 5 Kyber targets, or just one to start?")
    console.print("  [1] All 5 (full reproduction)")
    console.print("  [2] Just kyber512_leak1 (fast first taste, choose whether to continue after)")
    console.print(
        "  Note: mldsa44_leak1 is not included here -- it needs an x86 host "
        "to reproduce a significant result. See docs/reproducing-mldsa.md."
    )
    choice = IntPrompt.ask("Choice", default=2, choices=["1", "2"])
    return "all" if choice == 1 else "incremental"


_STAGE_PATTERNS = (
    ("secret-handling functions flagged", "INGEST"),
    ("analyzing full source", "INGEST"),
    ("detected hypothesis id", "ORACLE"),
    ("running oracle", "ORACLE"),
    ("waiting for feedback", "ORACLE"),
    ("Hypothesis", "REFINE"),
    ("LOOP COMPLETE", "DONE"),
)

_STAGE_COLOR = {
    "INGEST": BLUE,
    "ORACLE": GREEN,
    "REFINE": ORANGE,
    "DONE": GREEN,
}

_STAGE_DESCRIPTION = {
    "INGEST": "reading the target source for secret-dependent branches and unsafe comparisons",
    "ORACLE": "running 50,000 timed executions to measure the difference between conditions",
    "REFINE": "judging whether the timing signal is a real, confirmed leak",
    "DONE": "cycle complete, writing results",
}


def _stage_for_line(line: str) -> str | None:
    """Return which pipeline stage a raw engine/run_focused.sh output line
    belongs to, so the live status spinner reflects what's actually
    happening instead of sitting frozen during a 30s oracle poll. Returns
    None for lines that don't match a known marker; the caller keeps
    showing whatever stage it last saw in that case."""
    for pattern, stage in _STAGE_PATTERNS:
        if pattern in line:
            return stage
    return None


def _status_text(stage: str) -> str:
    """Build the live status line for a pipeline stage: the stage name in
    its color, plus a muted description so there's something to read during
    a long, otherwise-silent wait (e.g. the oracle's 30s polling interval)."""
    color = _STAGE_COLOR[stage]
    description = _STAGE_DESCRIPTION.get(stage, "")
    text = f"[{color}]{stage}[/]"
    if description:
        text += f"  [dim {INK_SOFT}]{description}[/]"
    return text


def _style_line(line: str) -> str:
    """Apply rich markup to a raw output line based on recognizable
    patterns, so the live stream reads as structured progress rather than a
    flat scroll of identical-looking text. The source line is escaped first
    so a literal '[' in engine output (e.g. "[Cycle 1]") can't be
    misinterpreted as rich markup syntax."""
    safe = escape(line)
    if "PROMOTED" in line:
        return f"[bold {GREEN}]{safe}[/]"
    if "DEMOTED" in line or "INVALIDATED" in line:
        return f"[{RED}]{safe}[/]"
    if "WARNING" in line:
        return f"[bold {RED}]{safe}[/]"
    if "waiting for feedback" in line:
        return f"[dim {INK_SOFT}]{safe}[/]"
    if "detected hypothesis id" in line or "running oracle" in line:
        return f"[{GREEN}]{safe}[/]"
    if "LOOP COMPLETE" in line:
        return f"[bold {GREEN}]{safe}[/]"
    return safe


def _run_target(name: str, tier, target_index: int | None = None, target_total: int | None = None) -> None:
    header = name
    if target_index is not None and target_total is not None:
        header = f"{name}  (target {target_index}/{target_total})"
    console.rule(header, style=BORDER)
    script = REPO_ROOT / "track-b-engine" / "run_focused.sh"
    focused_file = FOCUSED_TARGETS[name]
    env = {**os.environ, "RAYQ_CODE_MODEL": tier.models[0], "RAYQ_REASON_MODEL": tier.models[1]}
    proc = subprocess.Popen(
        ["bash", str(script), str(focused_file), name],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stage = "INGEST"
    with console.status(_status_text(stage), spinner="dots", spinner_style=_STAGE_COLOR[stage]) as status:
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            new_stage = _stage_for_line(line)
            if new_stage:
                stage = new_stage
                status.update(_status_text(stage), spinner_style=_STAGE_COLOR[stage])
            console.print(_style_line(line))
    proc.wait()


def _run_targets(tier) -> list[str]:
    """Run targets per the user's chosen mode, returning the ordered list of
    target names actually completed. In "all" mode that's always the full
    five, run back to back with no further prompts. In "incremental" mode,
    it starts at kyber512_leak1 and asks after each target whether to
    continue to the next one, so a user can step through at their own pace
    without restarting the whole wizard -- the returned list reflects
    exactly how far they went, which is what the final consolidated
    summary is built from."""
    mode = _choose_start_mode()
    completed: list[str] = []
    total = len(ALL_TARGET_NAMES)
    for i, name in enumerate(ALL_TARGET_NAMES, start=1):
        _run_target(name, tier, target_index=i, target_total=total)
        completed.append(name)
        is_last = i == total
        if mode == "incremental" and not is_last:
            next_name = ALL_TARGET_NAMES[i]
            if not Confirm.ask(f"Continue to {next_name}?", default=True):
                break
    return completed


_VERDICT_COLOR = {
    "PROMOTED": GREEN,
    "DEMOTED": RED,
    "INVALIDATED": RED,
}


def _style_verdict(verdict: str) -> str:
    color = _VERDICT_COLOR.get(verdict)
    return f"[bold {color}]{verdict}[/]" if color else verdict


def _print_summary(targets: list[str], commit: str) -> None:
    rows = build_summary(FINDINGS_DIR, targets)
    table = Table(title="Summary", border_style=BORDER)
    table.add_column("Target")
    table.add_column("Hypothesis")
    table.add_column("Verdict")
    table.add_column("t-stat")
    for row in rows:
        t_stat = f"{row['t_statistic']:.1f}" if row["t_statistic"] is not None else "-"
        table.add_row(row["target"], row["hypothesis_id"] or "-", _style_verdict(row["verdict"]), t_stat)
    console.print(table)
    console.print(f"liboqs commit: {commit}")
    console.print(f"Full results saved to {FINDINGS_DIR} and {REPO_ROOT / 'shared' / 'feedback'}")
    console.print("Run again any time with: docker compose run --rm runner")


def _print_legend() -> None:
    console.print()
    console.print(f"[{INK_SOFT}]What these numbers mean:[/]")
    console.print(
        f"  [{INK_SOFT}]Verdict[/] means whether the oracle's timing measurement "
        f"backed up the hypothesis. [bold {GREEN}]PROMOTED[/] means a real, "
        f"statistically significant timing difference was found: a confirmed leak. "
        f"[bold {RED}]DEMOTED[/] or [bold {RED}]INVALIDATED[/] means it didn't hold up."
    )
    console.print(
        f"  [{INK_SOFT}]t-stat[/] is a Welch's t-statistic. Its [bold]magnitude[/] "
        "(distance from zero, ignoring sign) is what matters -- the sign just "
        "reflects which of the two measured conditions happened to be timed first. "
        "Roughly, |t-stat| > 4 counts as a statistically significant signal, and the "
        "larger the magnitude, the stronger and more confident the finding. There's "
        "no \"higher is better\" or \"lower is better\" here, only \"further from "
        "zero is a stronger signal.\""
    )


def main() -> None:
    _banner()
    commit = _check_build()
    _wait_for_ollama()
    tier = _choose_tier()
    tier = _pull_models(tier)
    targets = _run_targets(tier)
    _print_summary(targets, commit)
    _print_legend()


if __name__ == "__main__":
    main()
