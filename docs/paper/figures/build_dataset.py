#!/usr/bin/env python3
"""
build_dataset.py — consolidate every per-cell experiment run into ONE canonical
dataset for the paper's multi-model evaluation.

The challenge: shared/runs/experiment_*.json holds *all* runs from the multi-LLM
session, including failed diagnostics and the definitive reruns that superseded
them. Dedup rule: for each (model, target) pair, the row from the LATEST-timestamp
experiment file wins -- because throughout the session every failed cell was rerun
in isolation *after* the failure, so "latest" is always the definitive result.

Outputs (into this directory):
  master.json  -- list of canonical per-cell records with full metadata
  master.csv   -- same, flat CSV

Run: python3 docs/paper/figures/build_dataset.py
"""
import csv
import json
import re
from pathlib import Path

RUNS = Path(__file__).resolve().parents[2].parent / "shared" / "runs"
OUT = Path(__file__).resolve().parent

# ── Per-model metadata. Tier/hardware reflect where each model actually ran in
#    the July 2026 session. Prices are (input, output) USD per 1M tokens; None = free/local.
META = {
    # Open-weight, local CPU (WSL2, Intel, no GPU)
    "codellama:7b":      dict(vendor="Open-weight", family="CodeLlama",     size_b=7,   tier="Local CPU",  hw="Intel CPU (WSL2)",  price=None),
    "qwen2.5-coder:7b":  dict(vendor="Open-weight", family="Qwen2.5-Coder", size_b=7,   tier="Local CPU",  hw="Intel CPU (WSL2)",  price=None),
    # Open-weight, cloud GPU
    "codellama:13b":     dict(vendor="Open-weight", family="CodeLlama",     size_b=13,  tier="Cloud GPU",  hw="NVIDIA T4 (16GB)",  price=None),
    "qwen2.5-coder:14b": dict(vendor="Open-weight", family="Qwen2.5-Coder", size_b=14,  tier="Cloud GPU",  hw="NVIDIA T4 (16GB)",  price=None),
    "qwen2.5-coder:32b": dict(vendor="Open-weight", family="Qwen2.5-Coder", size_b=32,  tier="Cloud GPU",  hw="NVIDIA A10G (24GB)", price=None),
    # Anthropic API
    "claude-haiku-4-5":  dict(vendor="Anthropic",   family="Claude",        size_b=None, tier="Frontier API", hw="API", price=(1.0, 5.0)),
    "claude-sonnet-4-6": dict(vendor="Anthropic",   family="Claude",        size_b=None, tier="Frontier API", hw="API", price=(3.0, 15.0)),
    "claude-sonnet-5":   dict(vendor="Anthropic",   family="Claude",        size_b=None, tier="Frontier API", hw="API", price=(2.0, 10.0)),
    "claude-opus-4-8":   dict(vendor="Anthropic",   family="Claude",        size_b=None, tier="Frontier API", hw="API", price=(5.0, 25.0)),
    "claude-fable-5":    dict(vendor="Anthropic",   family="Claude",        size_b=None, tier="Frontier API", hw="API", price=(10.0, 50.0)),
    # OpenAI API
    "gpt-5.4-nano":      dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(0.20, 1.25)),
    "gpt-5.4-mini":      dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(0.75, 4.50)),
    "gpt-5.4":           dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(2.50, 15.0)),
    "gpt-5.6-luna":      dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(1.0, 6.0)),
    "gpt-5.6-terra":     dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(2.50, 15.0)),
    "gpt-5.6-sol":       dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(5.0, 30.0)),
    "gpt-5.5":           dict(vendor="OpenAI",      family="GPT",           size_b=None, tier="Frontier API", hw="API", price=(5.0, 30.0)),
    "gpt-5.3-codex":     dict(vendor="OpenAI",      family="GPT-Codex",     size_b=None, tier="Frontier API", hw="API", price=(1.75, 14.0)),
}

TARGETS = ["kyber512_leak5", "kyber512_leak4", "kyber512_leak2", "mldsa44_leak1"]
TARGET_CLASS = {
    "kyber512_leak2": "secret_dependent_branch",
    "kyber512_leak4": "secret_dependent_branch",
    "kyber512_leak5": "nonconstant_comparison",
    "mldsa44_leak1":  "nonconstant_comparison",
}

TS_RE = re.compile(r"experiment_(\d{8}_\d{6})\.json$")


def load_all_rows(mode="hybrid"):
    """Return {(model,target): (timestamp, row)} keeping the latest timestamp per cell.

    Only consumes runs whose top-level `mode` matches (default "hybrid"): the main
    multi-model matrix was run in hybrid mode. Autonomous-mode runs live in the same
    directory but are analysed separately (build_autonomous below) so they never
    overwrite the canonical hybrid cells.
    """
    best = {}
    for p in sorted(RUNS.glob("experiment_*.json")):
        m = TS_RE.search(p.name)
        if not m:
            continue
        ts = m.group(1)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("mode") != mode:
            continue
        for row in data.get("rows", []):
            key = (row.get("model"), row.get("target"))
            if key[0] is None or key[1] is None:
                continue
            # latest timestamp wins (definitive reruns always came after failures)
            if key not in best or ts > best[key][0]:
                best[key] = (ts, row)
    return best


def outcome(row):
    """Classify a cell: located+confirmed / confirmed-only / miss / refused / incompatible / error."""
    if row.get("located") and row.get("confirmed"):
        return "located_confirmed"
    if row.get("confirmed"):
        return "confirmed_mislocated"
    if row.get("located"):
        return "located_unconfirmed"
    # distinguish the two known hard-failure anomalies by their signature
    err = row.get("error")
    wall = row.get("wall_s") or 0
    cost = row.get("cost_usd") or 0
    return "miss"  # refinement/annotation of refused/incompatible happens downstream


def main():
    best = load_all_rows()
    records = []
    for (model, target), (ts, row) in best.items():
        if model not in META:
            print(f"  WARN unknown model in runs: {model}")
            continue
        meta = META[model]
        records.append({
            "model": model,
            "target": target,
            "vuln_class": TARGET_CLASS.get(target, "?"),
            "vendor": meta["vendor"],
            "family": meta["family"],
            "size_b": meta["size_b"],
            "tier": meta["tier"],
            "hardware": meta["hw"],
            "price_in": meta["price"][0] if meta["price"] else None,
            "price_out": meta["price"][1] if meta["price"] else None,
            "located": bool(row.get("located")),
            "confirmed": bool(row.get("confirmed")),
            "outcome": outcome(row),
            "t_stat": row.get("t_stat"),
            "verdict": row.get("verdict"),
            "wall_s": row.get("wall_s"),
            "cost_usd": row.get("cost_usd"),
            "prompt_tokens": (row.get("tokens") or {}).get("prompt"),
            "completion_tokens": (row.get("tokens") or {}).get("completion"),
            "error": row.get("error"),
            "src_timestamp": ts,
        })

    # Hand-annotate the two known API anomalies (documented in the FINAL summaries):
    for r in records:
        if r["model"] == "gpt-5.3-codex":
            r["outcome"] = "incompatible_endpoint"   # needs /v1/responses, not chat/completions
        if r["model"] == "claude-fable-5":
            r["outcome"] = "refused_cyber"            # safety classifier blocked the domain

    records.sort(key=lambda r: (r["vendor"], r["family"], r["model"], r["target"]))

    (OUT / "master.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    cols = ["model", "vendor", "family", "size_b", "tier", "hardware", "target",
            "vuln_class", "located", "confirmed", "outcome", "t_stat", "verdict",
            "wall_s", "cost_usd", "prompt_tokens", "completion_tokens",
            "price_in", "price_out", "error", "src_timestamp"]
    with (OUT / "master.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c) for c in cols})

    # ── Validation print: canonical model x target matrix ──────────────────
    models = sorted({r["model"] for r in records},
                    key=lambda m: (META[m]["vendor"], META[m]["family"], m))
    cell = {(r["model"], r["target"]): r for r in records}
    sym = {"located_confirmed": "LC", "confirmed_mislocated": "c-", "miss": "..",
           "located_unconfirmed": "L-", "refused_cyber": "RF", "incompatible_endpoint": "XX"}
    print(f"\n{len(records)} canonical cells across {len(models)} models\n")
    hdr = f"{'model':22} " + " ".join(f"{t.split('_')[-1]:>6}" for t in TARGETS) + "   score"
    print(hdr); print("-" * len(hdr))
    for m in models:
        marks = []
        score = 0
        for t in TARGETS:
            r = cell.get((m, t))
            if r is None:
                marks.append("  --"); continue
            marks.append(f"{sym.get(r['outcome'],'?'):>6}")
            if r["outcome"] == "located_confirmed":
                score += 1
        n_present = sum(1 for t in TARGETS if (m, t) in cell)
        print(f"{m:22} " + " ".join(marks) + f"   {score}/{n_present}")
    print("\nLegend: LC=located+confirmed  c-=confirmed but mislocated  ..=miss  "
          "RF=refused  XX=incompatible endpoint")
    print(f"\nwrote master.json + master.csv ({len(records)} cells)")

    # ── Autonomous-mode dataset (static scan OFF): the direct test of whether
    #    the nonconstant_comparison blind spot persists without the directive ──
    auto = load_all_rows(mode="autonomous")
    if auto:
        arecs = []
        for (model, target), (ts, row) in auto.items():
            if model not in META:
                continue
            arecs.append({
                "model": model, "target": target,
                "vuln_class": TARGET_CLASS.get(target, "?"),
                "vendor": META[model]["vendor"], "family": META[model]["family"],
                "located": bool(row.get("located")), "confirmed": bool(row.get("confirmed")),
                "outcome": outcome(row), "t_stat": row.get("t_stat"),
                "verdict": row.get("verdict"), "wall_s": row.get("wall_s"),
                "cost_usd": row.get("cost_usd"), "src_timestamp": ts,
            })
        arecs.sort(key=lambda r: (r["vendor"], r["model"], r["target"]))
        (OUT / "master_autonomous.json").write_text(json.dumps(arecs, indent=2), encoding="utf-8")
        print(f"wrote master_autonomous.json ({len(arecs)} autonomous cells)")


if __name__ == "__main__":
    main()
