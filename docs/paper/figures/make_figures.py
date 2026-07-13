#!/usr/bin/env python3
"""
make_figures.py — generate the paper's figures from the confirmed oracle data
and the AFL++ comparison. Run: python docs/paper/figures/make_figures.py
Outputs PNG + PDF into docs/paper/figures/.

Palette, fonts, and neutrals are ported directly from the design-token
system (docs/style/tokens.css) so every figure reads as part of the same
document as the PDF/docx it's embedded in. See
docs/superpowers/specs/2026-07-12-pdf-design-system-design.md for the
system this mirrors -- if that spec's hex values change, update here too.
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
FONTS_DIR = OUT.parent.parent / "style" / "fonts"

# ── design tokens (mirror of docs/style/tokens.css) ──────────────────────────
PAPER = "#F9F8F3"
SURFACE = "#E2E1DA"
BORDER = "#BEBEBE"
INK = "#262626"
INK_SOFT = "#313131"
BLUE = "#0099FF"
GREEN = "#2FBB45"
ORANGE = "#DC762D"
RED = "#FB2C55"

FONT_SANS = "Public Sans"
FONT_SANS_SEMIBOLD = "Public Sans SemiBold"
FONT_MONO = "Roboto Mono"

for _f in ("publicsans-400.ttf", "publicsans-500.ttf", "publicsans-600.ttf",
           "publicsans-400i.ttf", "robotomono-400.ttf"):
    _p = FONTS_DIR / _f
    if _p.exists():
        fm.fontManager.addfont(str(_p))

plt.rcParams.update({
    # DejaVu Sans as an explicit fallback: Public Sans (a trimmed static
    # subset) doesn't cover every symbol we use in annotations (e.g. Δ, ≈),
    # so without a fallback matplotlib would render a missing-glyph tofu box.
    "font.size": 11, "font.family": [FONT_SANS, "DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
    "axes.edgecolor": BORDER, "axes.linewidth": 1.0,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": BORDER, "grid.alpha": 0.6, "grid.linewidth": 0.7,
    "figure.dpi": 150,
    "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor=PAPER)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", facecolor=PAPER)
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
    ax.plot(x, pdf(x, mB, sB), color=ORANGE, lw=2,
            label="Class B — invalid ct, early exit at byte 0")
    ax.fill_between(x, pdf(x, mB, sB), color=ORANGE, alpha=0.12)
    ax.plot(x, pdf(x, mA, sA), color=BLUE, lw=2,
            label="Class A — valid ct, full 768-byte scan")
    ax.fill_between(x, pdf(x, mA, sA), color=BLUE, alpha=0.12)
    ax.axvline(mB, color=ORANGE, ls=":", lw=1)
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
    colors = [BORDER, BORDER, ORANGE, ORANGE]
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    bars = ax.bar(labels, paths, color=colors, width=0.6, zorder=3)
    for b, v in zip(bars, paths):
        ax.text(b.get_x() + b.get_width()/2, v + 0.4, str(v),
                ha="center", va="bottom", fontsize=10)
    ax.axhline(2, color=INK_SOFT, ls=":", lw=1)
    # Annotation sits entirely ABOVE every bar top (tallest bar = 20), in the
    # headroom created by the extended ylim below -- previously it sat at
    # y=11 next to x=1.15, whose text box extended rightward across the
    # LEAK-2 bar (x=1.7-2.3, height 20), rendering red text directly on top
    # of the solid orange bar fill and making it unreadable.
    ax.annotate("memcmp leak's corpus is\nIDENTICAL to clean (2 = 2):\ncoverage is structurally blind",
                xy=(1, 2), xytext=(0.55, 23),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2),
                fontsize=9, color=RED, ha="left", va="top")
    ax.set_ylabel("AFL++ corpus paths after 24 h")
    ax.set_title("Coverage cannot see the memcmp timing leak; "
                 "branch leaks add edges but stay unidentified", fontsize=10.5)
    ax.set_ylim(0, 29)
    save(fig, "fig3_afl_corpus")


# ── Figure 4 — ISA portability of the memcmp oracle ──────────────────────────
def fig_isa_portability():
    fig, ax = plt.subplots(figsize=(5.2, 3.9))
    labels = ["x86-64\n(glibc byte-loop memcmp)", "AArch64 -O2\n(NEON fixed-width)"]
    vals = [164.30, 0.9]
    colors = [BLUE, BORDER]
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


# ── Figure 0 — architecture: closed loop + provider-agnostic model gateway ──
def fig_architecture():
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.set_xlim(0, 105); ax.set_ylim(0, 58); ax.axis("off")

    def box(x, y, w, h, label, color, fontsize=9.2, textcolor="white"):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=3",
                            linewidth=0, facecolor=color, alpha=0.92, zorder=2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center", fontsize=fontsize,
                color=textcolor, zorder=3, wrap=True, linespacing=1.35)
        return (x, y, w, h)

    def arrow(b1, b2, label="", style="-", color="black", rad=0.0, lw=1.4,
              label_dy=1.6, label_dx=0.0):
        x1, y1, w1, h1 = b1; x2, y2, w2, h2 = b2
        p1 = (x1 + w1/2, y1) if y1 > y2 else (x1 + w1/2, y1 + h1)
        p2 = (x2 + w2/2, y2 + h2) if y1 > y2 else (x2 + w2/2, y2)
        a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                            linewidth=lw, color=color, linestyle=style,
                            connectionstyle=f"arc3,rad={rad}", zorder=1)
        ax.add_patch(a)
        if label:
            mx, my = (p1[0]+p2[0])/2 + label_dx, (p1[1]+p2[1])/2 + label_dy
            ax.text(mx, my, label, ha="center", fontsize=7.6, color=INK_SOFT, zorder=4)

    # Pipeline spine (left -> right), y=30..46
    src   = box(1,  32, 14, 10, "Weakened\nPQC Source", INK_SOFT, fontsize=8.6)
    s1    = box(19, 32, 16, 10, "Stage 1\nIngestion", BLUE)
    s3    = box(39, 32, 16, 10, "Stage 3\nVectorize", BLUE)
    oracle= box(59, 32, 16, 10, "Timing Oracle\n(harness, Welch t)", GREEN)
    s2    = box(79, 32, 16, 10, "Stage 2\nRefine", ORANGE)
    conf  = box(79, 46, 16, 9, "Confirmed Leak\nclass + location + t + exploit", GREEN, fontsize=8.0)

    arrow(src, s1)
    arrow(s1, s3, "ranked hypotheses")
    arrow(s3, oracle, "C timing harness")
    arrow(oracle, s2, "timing JSON\n(ground truth)")
    arrow(s2, conf, "PROMOTED")
    # closed-loop dashed feedback arrow, curving under the spine
    a = FancyArrowPatch((87, 32), (27, 32), connectionstyle="arc3,rad=-0.34",
                        arrowstyle="-|>", mutation_scale=13, linewidth=1.3,
                        linestyle=(0, (5, 3)), color=RED, zorder=1)
    ax.add_patch(a)
    ax.text(57, 15.5, "refine & re-hypothesise -- closed loop", ha="center",
            fontsize=8, color=RED)

    # Model Gateway: one box, three provider families, feeding all 3 LLM stages
    gw = box(19, 2, 76, 16, "", INK, fontsize=1)  # background only
    ax.text(22, 15.3, "Model Gateway", fontsize=10.5, fontfamily=FONT_SANS_SEMIBOLD, color="white")
    ax.text(22, 12.6, "Router (model id -> provider)  +  Meter (tokens, cost, budget cap)",
            fontsize=7.8, color=SURFACE)
    prov = [
        ("Open-weight (Ollama)", "CodeLlama, Qwen2.5-Coder\n7B-32B -- local CPU / cloud GPU", 22),
        ("Anthropic API", "Haiku, Sonnet 4.6/5,\nOpus 4.8, Fable 5", 48),
        ("OpenAI API", "GPT-5.4 nano..base,\nGPT-5.6 luna..sol, 5.5, Codex", 73),
    ]
    for name, detail, x in prov:
        pb = FancyBboxPatch((x, 3.5), 20, 6.5, boxstyle="round,pad=0.4,rounding_size=2",
                            linewidth=0.8, edgecolor="white", facecolor=INK_SOFT, zorder=3)
        ax.add_patch(pb)
        ax.text(x + 10, 8.1, name, ha="center", fontsize=7.6, color="white", fontfamily=FONT_SANS_SEMIBOLD, zorder=4)
        ax.text(x + 10, 5.6, detail, ha="center", fontsize=6.6, color=SURFACE, zorder=4, linespacing=1.3)

    for target, x in ((s1, 27), (s3, 47), (s2, 87)):
        a = FancyArrowPatch((x, 18), (x, 32), arrowstyle="-|>", mutation_scale=11,
                            linewidth=1.0, linestyle=(0, (2, 2)), color=INK_SOFT, zorder=1)
        ax.add_patch(a)
    ax.text(1, 20.5, "RAYQ_CODE_MODEL / RAYQ_REASON_MODEL\n-- same engine code, any provider",
            fontsize=7.6, color=INK_SOFT, style="italic")

    ax.set_title("Rayquaza: closed-loop pipeline over a provider-agnostic model gateway",
                fontsize=11.5, pad=10)
    save(fig, "fig0_architecture")


# ── Multi-model figures (from docs/paper/figures/master.json) ────────────────
import json as _json

_MASTER = OUT / "master.json"
_TIER_ORDER = ["Local CPU", "Cloud GPU", "Frontier API"]
_TARGET_ORDER = ["kyber512_leak5", "kyber512_leak4", "kyber512_leak2", "mldsa44_leak1"]
_TARGET_LABEL = {"kyber512_leak5": "LEAK-5\nmemcmp", "kyber512_leak4": "LEAK-4\nbranch",
                  "kyber512_leak2": "LEAK-2\nbranch", "mldsa44_leak1": "MLDSA-1\nmemcmp"}
_VENDOR_COLOR = {"Anthropic": ORANGE, "OpenAI": GREEN, "Open-weight": BLUE}


def _load_master():
    return _json.loads(_MASTER.read_text(encoding="utf-8"))


# ── Figure 5 — the extended headline: vulnerability class gap at n=63 cells ──
def fig_class_gap():
    recs = _load_master()
    classes = ["secret_dependent_branch", "nonconstant_comparison"]
    rates, ns = [], []
    for c in classes:
        rows = [r for r in recs if r["vuln_class"] == c]
        loc = sum(1 for r in rows if r["located"])
        rates.append(100 * loc / len(rows)); ns.append((loc, len(rows)))
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    labels = ["secret_dependent_branch\n(explicit if/for on secret data)",
              "nonconstant_comparison\n(memcmp/verify substitution)"]
    bars = ax.bar(labels, rates, color=[BLUE, ORANGE], width=0.55, zorder=3)
    for b, r, (loc, n) in zip(bars, rates, ns):
        ax.text(b.get_x() + b.get_width()/2, r + 2, f"{loc}/{n}\n({r:.0f}%)",
                ha="center", va="bottom", fontsize=10, fontfamily=FONT_SANS_SEMIBOLD)
    ax.set_ylabel("Located rate across 18 models (%)")
    ax.set_ylim(0, 115)
    ax.set_title("The class gap persists at scale: n=63 cells, 18 models, 5 vendors",
                fontsize=10.8)
    save(fig, "fig5_class_gap")


# ── Figure 6 — cross-vendor gap on the hard (nonconstant_comparison) targets ─
def fig_vendor_gap():
    recs = [r for r in _load_master() if r["vuln_class"] == "nonconstant_comparison"]
    vendors = ["Anthropic", "Open-weight", "OpenAI"]
    rates, ns = [], []
    for v in vendors:
        rows = [r for r in recs if r["vendor"] == v]
        loc = sum(1 for r in rows if r["located"])
        rates.append(100 * loc / len(rows) if rows else 0); ns.append((loc, len(rows)))
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    bars = ax.bar(vendors, rates, color=[_VENDOR_COLOR[v] for v in vendors], width=0.5, zorder=3)
    for b, r, (loc, n) in zip(bars, rates, ns):
        ax.text(b.get_x() + b.get_width()/2, r + 2, f"{loc}/{n}\n({r:.0f}%)",
                ha="center", va="bottom", fontsize=10, fontfamily=FONT_SANS_SEMIBOLD)
    ax.set_ylabel("Located rate,\nnonconstant_comparison targets (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Vendor spread on the hard class: LEAK-5 + MLDSA-1 combined",
                fontsize=10.8)
    save(fig, "fig6_vendor_gap")


# ── Figure 7 — full outcome matrix: 18 models x 4 targets ────────────────────
def fig_model_matrix():
    recs = _load_master()
    by_model = {}
    for r in recs:
        by_model.setdefault(r["model"], {})[r["target"]] = r
    def sort_key(m):
        rows = list(by_model[m].values())
        tier = rows[0]["tier"]; vendor = rows[0]["vendor"]
        return (_TIER_ORDER.index(tier), vendor, m)
    models = sorted(by_model.keys(), key=sort_key)

    code = {"located_confirmed": (GREEN, "LC"), "confirmed_mislocated": (ORANGE, "cm"),
            "located_unconfirmed": (BLUE, "L-"), "miss": (BORDER, ".."),
            "refused_cyber": (INK, "RF"), "incompatible_endpoint": (INK_SOFT, "XX")}

    fig, ax = plt.subplots(figsize=(7.6, 8.0))
    for i, m in enumerate(models):
        y = len(models) - 1 - i
        for j, t in enumerate(_TARGET_ORDER):
            r = by_model[m].get(t)
            color, tag = code[r["outcome"]] if r else ("white", "")
            ax.add_patch(plt.Rectangle((j, y), 0.92, 0.92, facecolor=color,
                                        edgecolor="white", linewidth=1.5, zorder=2))
            if tag:
                textcolor = "white" if color in (GREEN, INK, INK_SOFT) else INK
                ax.text(j + 0.46, y + 0.46, tag, ha="center", va="center",
                        fontsize=7.5, color=textcolor, zorder=3)
    ax.set_xlim(0, len(_TARGET_ORDER)); ax.set_ylim(0, len(models))
    ax.set_xticks([j + 0.46 for j in range(len(_TARGET_ORDER))])
    ax.set_xticklabels([_TARGET_LABEL[t] for t in _TARGET_ORDER], fontsize=8.5)
    ax.set_yticks([len(models) - 1 - i + 0.46 for i in range(len(models))])
    ax.set_yticklabels(models, fontsize=8.2, fontfamily=FONT_MONO)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(False)
    # vendor/tier separators
    prev_tier = None
    for i, m in enumerate(models):
        tier = by_model[m][list(by_model[m].keys())[0]]["tier"]
        if prev_tier is not None and tier != prev_tier:
            y = len(models) - i
            ax.axhline(y, color=BORDER, lw=1.0, xmin=-0.35, xmax=1.0, clip_on=False)
        prev_tier = tier
    legend_items = [mpatch(GREEN, "located + confirmed"), mpatch(ORANGE, "confirmed, mislocated"),
                    mpatch(BORDER, "miss"), mpatch(INK, "refused (cyber classifier)"),
                    mpatch(INK_SOFT, "incompatible API endpoint")]
    ax.legend(handles=legend_items, loc="upper center", bbox_to_anchor=(0.5, -0.045),
              ncol=2, frameon=False, fontsize=8)
    ax.set_title("Every model x target outcome, hybrid mode (63 cells)", fontsize=11, pad=12)
    save(fig, "fig7_model_matrix")


def mpatch(color, label):
    import matplotlib.patches as mpatches
    return mpatches.Patch(facecolor=color, edgecolor="white", label=label)


# ── Figure 8 — cost vs. accuracy (API models, fully-tested n=4 only; open-weight
#    models ran at $0 and are noted in the caption rather than plotted on a log axis) ──
def fig_cost_vs_accuracy():
    recs = _load_master()
    by_model = {}
    for r in recs:
        by_model.setdefault(r["model"], []).append(r)
    points = []
    for m, rows in by_model.items():
        if rows[0]["tier"] != "Frontier API" or len(rows) < 4:
            continue  # exclude breadth-only (n=1) cells: not comparable to full n=4 runs
        total_cost = sum(r["cost_usd"] or 0 for r in rows)
        if total_cost <= 0:
            continue
        loc_rate = 100 * sum(1 for r in rows if r["located"]) / len(rows)
        points.append((m, total_cost, loc_rate, rows[0]["vendor"]))
    points.sort(key=lambda p: p[1])

    fig, ax = plt.subplots(figsize=(7.6, 5.6))
    for m, cost, loc_rate, vendor in points:
        ax.scatter(cost, loc_rate, s=115, color=_VENDOR_COLOR[vendor],
                  edgecolor="white", linewidth=1.2, zorder=3)
    # Collision-avoidance: group points sharing a y-level (the common case here --
    # many models tie at 100%/75%), sort each group by x, and alternate the label
    # above/below with increasing amplitude so a run of 3+ close points fans out
    # instead of stacking on just two rows.
    from collections import defaultdict
    groups = defaultdict(list)
    for m, cost, loc_rate, vendor in points:
        groups[round(loc_rate)].append((cost, m))
    for y, members in groups.items():
        members.sort()
        for i, (cost, m) in enumerate(members):
            rung = (i + 1) // 2
            dy = 0 if i == 0 else (rung * 13 if i % 2 else -rung * 13)
            ax.annotate(m, (cost, y), fontsize=7.4, fontfamily=FONT_MONO,
                        xytext=(7, dy), textcoords="offset points", va="center", zorder=4)
    ax.set_xscale("log")
    ax.set_xlabel("Total cost across 4 targets (USD, log scale)")
    ax.set_ylabel("Located rate (%)")
    ax.set_ylim(-5, 112)
    ax.set_xlim(0.008, 1.6)
    ax.set_title("Price does not predict accuracy on this task\n"
                "(open-weight models, at zero cost, matched or beat every API tier here)",
                fontsize=10.5)
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
              markersize=9, label=v) for v, c in _VENDOR_COLOR.items() if v != "Open-weight"]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    save(fig, "fig8_cost_vs_accuracy")


if __name__ == "__main__":
    fig_architecture()
    fig_timing_distribution()
    fig_t_vs_afl()
    fig_afl_corpus()
    fig_isa_portability()
    if _MASTER.exists():
        fig_class_gap()
        fig_vendor_gap()
        fig_model_matrix()
        fig_cost_vs_accuracy()
    print("all figures written to", OUT)
