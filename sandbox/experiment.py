#!/usr/bin/env python3
"""
experiment.py — multi-LLM scale experiment for the paper's central open question
(§5.5): does the `nonconstant_comparison` blind spot shrink as model scale grows?

For each model, runs the full Rayquaza pipeline on a target subset in AUTONOMOUS
mode (no static-scan directive — the decisive test) and records located / confirmed
/ t-stat / cost. Writes shared/runs/experiment_<stamp>.{json,md}: a model × target
matrix that drops straight into a new paper table + figure.

Local models route to Ollama; frontier models (claude-*/gpt-*) route to the API via
the sandbox gateway (needs a key in sandbox/secrets.local.json). Runs are sequential.

Usage:
  python -m sandbox.experiment \
      --models codellama:7b qwen2.5-coder:7b deepseek-coder:6.7b \
      --targets kyber512_leak5 mldsa44_leak1 kyber512_leak4 \
      --mode autonomous
"""
import argparse
import json
import time
import traceback
from pathlib import Path

from sandbox.run_session import RunSession

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS_JSON = REPO_ROOT / "viz" / "targets.json"
RUNS_DIR = REPO_ROOT / "shared" / "runs"

DEFAULT_TARGETS = ["kyber512_leak5", "mldsa44_leak1", "kyber512_leak4"]


def target_c(target_id: str):
    targets = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
    meta = next((t for t in targets if t["id"] == target_id), None)
    if not meta or not meta.get("focused_target"):
        return None
    return REPO_ROOT / meta["focused_target"]


def run_matrix(models, target_ids, static_scan) -> list[dict]:
    rows = []
    for model in models:
        for tid in target_ids:
            tc = target_c(tid)
            if tc is None:
                print(f"  skip {tid}: no focused target in registry")
                continue
            print(f"[run] {model} x {tid}  (static_scan={static_scan}) ...", flush=True)
            try:
                sess = RunSession(model, tid, tc, on_state=lambda s: None,
                                  static_scan=static_scan)
                run = sess.run()
                tr = run.targets[0]
                row = {
                    "model": model, "target": tid,
                    "located": tr.located, "confirmed": tr.confirmed,
                    "t_stat": tr.t_stat, "verdict": tr.verdict,
                    "wall_s": tr.wall_seconds,
                    "cost_usd": run.cost_usd, "tokens": run.tokens,
                    "error": None,
                }
                print(f"      -> located={tr.located} confirmed={tr.confirmed} "
                      f"t={tr.t_stat} ({tr.wall_seconds}s, ${run.cost_usd})", flush=True)
            except Exception as exc:  # keep the matrix going if one cell fails
                row = {"model": model, "target": tid, "located": None,
                       "confirmed": None, "t_stat": None, "verdict": "ERROR",
                       "wall_s": None, "cost_usd": 0.0, "tokens": {},
                       "error": str(exc)}
                print(f"      -> ERROR: {exc}", flush=True)
                traceback.print_exc()
            rows.append(row)
    return rows


def to_markdown(rows, models, target_ids, mode) -> str:
    by = {(r["model"], r["target"]): r for r in rows}
    lines = [
        f"# Multi-LLM {mode}-mode results",
        "",
        "Cell = located / confirmed. 'located' = correct category+location; "
        "'confirmed' = oracle significant under the model's own vector.",
        "",
        "| Target | " + " | ".join(models) + " |",
        "|---|" + "|".join(["---"] * len(models)) + "|",
    ]
    for tid in target_ids:
        cells = []
        for m in models:
            r = by.get((m, tid))
            if not r:
                cells.append("—")
                continue
            if r["verdict"] == "ERROR":
                cells.append("err")
                continue
            loc = "located" if r["located"] else "missed"
            conf = "confirmed" if r["confirmed"] else "no"
            cells.append(f"{loc} / {conf}")
        lines.append(f"| {tid} | " + " | ".join(cells) + " |")
    total_cost = sum(r["cost_usd"] or 0 for r in rows)
    lines += ["", f"Total API cost this run: ${total_cost:.4f}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    ap.add_argument("--mode", choices=["autonomous", "hybrid"], default="autonomous")
    args = ap.parse_args()
    static_scan = (args.mode == "hybrid")

    rows = run_matrix(args.models, args.targets, static_scan)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    payload = {"generated": stamp, "mode": args.mode, "models": args.models,
               "targets": args.targets, "rows": rows}
    (RUNS_DIR / f"experiment_{stamp}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    md = to_markdown(rows, args.models, args.targets, args.mode)
    (RUNS_DIR / f"experiment_{stamp}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"\nwrote shared/runs/experiment_{stamp}.json + .md")


if __name__ == "__main__":
    main()
