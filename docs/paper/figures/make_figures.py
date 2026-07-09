#!/usr/bin/env python3
"""
make_figures.py — generate the paper's figures from the confirmed oracle data
and the AFL++ comparison. Run: python docs/paper/figures/make_figures.py
Outputs PNG + PDF into docs/paper/figures/.
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

# Clean, print-friendly, colour-blind-safe palette
BLUE = "#2c6fbb"   # class A / LLM
AMBER = "#e08214"  # class B / contrast
GREY = "#9aa0a6"
RED = "#c0392b"
plt.rcParams.update({
    "font.size": 11, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "figure.dpi": 150,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ── Figure 1 — the money figure: timing distributions separate (LEAK-5) ──────
def fig_timing_distribution():
    # LEAK-5 crypto_kem_dec memcmp: per-sample timing distributions (mean, variance)
    mA, vA = 45.375, 138.153   # equal buffers, full 768-byte scan
    mB, vB = 30.975, 330.61    # differ at byte 0, early exit
    sA, sB = vA ** 0.5, vB ** 0.5
    x = np.linspace(min(mA - 4*sA, mB - 4*sB), max(mA + 4*sA, mB + 4*sB), 800)

    def pdf(x, m, s):
        return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * np.sqrt(2 * np.pi))

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(x, pdf(x, mB, sB), color=AMBER, lw=2,
            label="Class B — invalid ct, early exit at byte 0")
    ax.fill_between(x, pdf(x, mB, sB), color=AMBER, alpha=0.12)
    ax.plot(x, pdf(x, mA, sA), color=BLUE, lw=2,
            label="Class A — valid ct, full 768-byte scan")
    ax.fill_between(x, pdf(x, mA, sA), color=BLUE, alpha=0.12)
    ax.axvline(mB, color=AMBER, ls=":", lw=1)
    ax.axvline(mA, color=BLUE, ls=":", lw=1)
    ax.annotate("", xy=(mA, 0.002), xytext=(mB, 0.002),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1))
    ax.text((mA + mB) / 2, 0.0035, f"Δ = {mA-mB:.1f} ns\nt = 141.09",
            ha="center", va="bottom", fontsize=10)
    ax.set_xlabel("Per-call decapsulation time (ns)")
    ax.set_ylabel("Probability density")
    ax.set_title("LEAK-5: non-constant-time memcmp separates the two input classes",
                 fontsize=11)
    ax.set_yticks([])
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    save(fig, "fig1_timing_distribution")


# ── Figure 2 — headline contrast: LLM |t| per leak vs AFL zero detections ─────
def fig_t_vs_afl():
    leaks = ["LEAK-1\ncmov", "LEAK-2\npoly_tomsg", "LEAK-3\nbasemul",
             "LEAK-4\nindcpa_dec", "LEAK-5\nmemcmp", "MLDSA-1\nmemcmp"]
    t_abs = [213.48, 139.91, 2421.91, 901.41, 141.09, 164.30]
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    bars = ax.bar(leaks, t_abs, color=BLUE, width=0.62, zorder=3)
    ax.set_yscale("log")
    ax.axhline(2.0, color=RED, ls="--", lw=1.2, zorder=2)
    ax.text(len(leaks) - 0.4, 2.4, "significance threshold |t| = 2",
            color=RED, fontsize=9, ha="right")
    for b, v in zip(bars, t_abs):
        ax.text(b.get_x() + b.get_width()/2, v * 1.08, f"{v:.0f}",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Oracle |t| (log scale)")
    ax.set_title("LLM-confirmed timing signal for every leak — "
                 "AFL++ detected none (24 h, ~120M execs/target)", fontsize=10.5)
    ax.set_ylim(1, 6000)
    save(fig, "fig2_t_vs_afl")


# ── Figure 3 — AFL structural blindness: corpus paths ────────────────────────
def fig_afl_corpus():
    labels = ["Clean\nbaseline", "LEAK-5\nmemcmp", "LEAK-2\npoly_tomsg", "LEAK-4\nindcpa_dec"]
    paths = [2, 2, 20, 18]
    colors = [GREY, GREY, AMBER, AMBER]
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    bars = ax.bar(labels, paths, color=colors, width=0.6, zorder=3)
    for b, v in zip(bars, paths):
        ax.text(b.get_x() + b.get_width()/2, v + 0.4, str(v),
                ha="center", va="bottom", fontsize=10)
    ax.axhline(2, color=GREY, ls=":", lw=1)
    ax.annotate("memcmp leak's corpus is\nIDENTICAL to clean (2 = 2):\ncoverage is structurally blind",
                xy=(1, 2), xytext=(1.15, 11),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2),
                fontsize=9, color=RED)
    ax.set_ylabel("AFL++ corpus paths after 24 h")
    ax.set_title("Coverage cannot see the memcmp timing leak; "
                 "branch leaks add edges but stay unidentified", fontsize=10.5)
    ax.set_ylim(0, 24)
    save(fig, "fig3_afl_corpus")


# ── Figure 4 — ISA portability of the memcmp oracle ──────────────────────────
def fig_isa_portability():
    fig, ax = plt.subplots(figsize=(5.2, 3.9))
    labels = ["x86-64\n(glibc byte-loop memcmp)", "AArch64 -O2\n(NEON fixed-width)"]
    vals = [164.30, 0.9]
    colors = [BLUE, GREY]
    bars = ax.bar(labels, vals, color=colors, width=0.55, zorder=3)
    ax.axhline(2.0, color=RED, ls="--", lw=1.2)
    ax.text(1.4, 2.6, "|t| = 2", color=RED, fontsize=9, ha="right")
    for b, v, txt in zip(bars, vals, ["t = 164.30\n(detectable)", "t ≈ 0.9\n(invisible)"]):
        ax.text(b.get_x() + b.get_width()/2, v + 4, txt, ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("MLDSA-1 memcmp oracle |t|")
    ax.set_title("Same code, same leak — detectable on x86-64, invisible on AArch64",
                 fontsize=10)
    ax.set_ylim(0, 185)
    save(fig, "fig4_isa_portability")


if __name__ == "__main__":
    fig_timing_distribution()
    fig_t_vs_afl()
    fig_afl_corpus()
    fig_isa_portability()
    print("all figures written to", OUT)
