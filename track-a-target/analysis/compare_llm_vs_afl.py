#!/usr/bin/env python3
"""
compare_llm_vs_afl.py — LLM adversary loop vs AFL++ coverage-fuzzing baseline.

Track A analysis tool for the Priority-2 comparison (Track B B6 paper input).
Reads, per weakened Kyber512 target:
  - AFL++ run stats from <fuzz-root>/<target>/findings/default/fuzzer_stats
  - LLM adversary-loop outcome from shared/findings/loop_state_kyber512_<target>.json

Emits a factual comparison (JSON + Markdown) to shared/findings/. It does NOT
editorialize a win/loss headline — it reports three honest axes per target:
  1. AFL coverage:   execs, corpus paths, crashes   (vs the clean baseline)
  2. LLM located:    did the loop name the right category + location?
  3. LLM confirmed:  did the oracle return significant under the loop's test vector?

Coverage-guided fuzzing finds crashes/new edges, not timing leaks — so AFL's
"detection" of a timing side channel is 0 by construction. The interesting signal
is whether AFL's corpus even *distinguishes* a weakened target from the clean
baseline (it does for the branch leaks, which add reachable edges; it does not
for the memcmp leak, which is a pure timing difference on the same path).

Run on WSL2 after the fuzz run:  python3 compare_llm_vs_afl.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# Targets that were fuzzed (weakened) + the clean baseline.
FUZZED = ["leak2", "leak4", "leak5"]
BASELINE = "clean"

# Ground truth for the location/category match (from targets.json / EXPERIMENT_LOG).
GROUND_TRUTH = {
    "leak2": {"category": "secret_dependent_branch", "location": "poly_tomsg"},
    "leak4": {"category": "secret_dependent_branch", "location": "indcpa_dec"},
    "leak5": {"category": "nonconstant_comparison", "location": "crypto_kem_dec"},
}

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_fuzzer_stats(path: Path) -> dict | None:
    """Parse an AFL++ fuzzer_stats file (key : value lines) into a dict."""
    if not path.exists():
        return None
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def afl_summary(stats: dict | None) -> dict:
    """Pull the comparison-relevant fields from a fuzzer_stats dict."""
    if stats is None:
        return {"status": "pending", "execs_done": None, "corpus_count": None,
                "saved_crashes": None, "run_time": None}
    def num(key, cast=int):
        v = stats.get(key)
        try:
            return cast(v)
        except (TypeError, ValueError):
            return None
    return {
        "status": "complete",
        "execs_done": num("execs_done"),
        "corpus_count": num("corpus_count"),
        "saved_crashes": num("saved_crashes"),
        "run_time": num("run_time"),
    }


def llm_outcome(target: str) -> dict:
    """Read the LLM loop_state snapshot for a target and summarize the outcome."""
    path = REPO_ROOT / "shared" / "findings" / f"loop_state_kyber512_{target}.json"
    if not path.exists():
        return {"status": "no-record", "located": None, "confirmed": None,
                "t_stat": None, "category": None, "location": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    hyps = data.get("hypotheses", [])
    if not hyps:
        return {"status": "no-hypotheses", "located": None, "confirmed": None,
                "t_stat": None, "category": None, "location": None}
    # Pick the hypothesis with the strongest |t| (the loop's best shot at this target).
    best = max(hyps, key=lambda h: abs(h.get("t_statistic") or 0.0))
    gt = GROUND_TRUTH.get(target, {})
    cat = (best.get("category") or "")
    loc = (best.get("location") or "")
    located = (cat == gt.get("category")) and (gt.get("location", "") in loc)
    return {
        "status": best.get("status", "UNKNOWN"),
        "located": located,
        "confirmed": bool(best.get("significant")),
        "t_stat": best.get("t_statistic"),
        "category": cat,
        "location": loc,
    }


def build_rows(fuzz_root: Path) -> list[dict]:
    baseline_stats = afl_summary(parse_fuzzer_stats(
        fuzz_root / BASELINE / "findings" / "default" / "fuzzer_stats"))
    rows = []
    for t in FUZZED:
        afl = afl_summary(parse_fuzzer_stats(
            fuzz_root / t / "findings" / "default" / "fuzzer_stats"))
        llm = llm_outcome(t)
        distinguishes = None
        if afl["corpus_count"] is not None and baseline_stats["corpus_count"] is not None:
            distinguishes = afl["corpus_count"] != baseline_stats["corpus_count"]
        rows.append({
            "target": t,
            "ground_truth": GROUND_TRUTH[t],
            "afl": afl,
            "afl_distinguishes_from_clean": distinguishes,
            "llm": llm,
        })
    return rows, baseline_stats


def to_markdown(rows: list[dict], baseline: dict) -> str:
    bc = baseline.get("corpus_count")
    lines = [
        "# LLM adversary loop vs AFL++ baseline",
        "",
        f"Clean baseline corpus paths: **{bc}** | crashes: **{baseline.get('saved_crashes')}**",
        "",
        "| Target | Truth | AFL paths | AFL crashes | Distinguishes clean? | LLM located? | LLM confirmed (this vector) | LLM t |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        a, l = r["afl"], r["llm"]
        lines.append(
            f"| {r['target']} | {r['ground_truth']['location']} "
            f"| {a['corpus_count']} | {a['saved_crashes']} "
            f"| {fmt_bool(r['afl_distinguishes_from_clean'])} "
            f"| {fmt_bool(l['located'])} | {fmt_bool(l['confirmed'])} "
            f"| {fmt_t(l['t_stat'])} |"
        )
    lines += [
        "",
        "Notes:",
        "- AFL++ crashes = 0 by construction: a non-constant-time branch/compare is not a",
        "  memory-safety bug, so coverage fuzzing cannot *detect* a timing leak at all.",
        "- 'Distinguishes clean?' = does the weakened target's corpus differ from the clean",
        "  baseline. Branch leaks add reachable edges (corpus differs); the memcmp leak rides",
        "  the same path (corpus identical) — coverage is blind to it even structurally.",
        "- 'LLM located' = named the correct category + location. 'LLM confirmed' = the oracle",
        "  returned significant under the loop's chosen test vector (a stricter, vector-dependent",
        "  bar — e.g. leak2 is located correctly but its recorded vector hit the predictable",
        "  branch direction, which is not significant; the misprediction vector gives t=-139.91).",
    ]
    return "\n".join(lines)


def fmt_bool(b):
    return "—" if b is None else ("yes" if b else "no")


def fmt_t(t):
    if t is None:
        return "—"
    return str(round(t)) if abs(t) >= 1000 else f"{t:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuzz-root", default=str(Path.home() / "fuzz"),
                    help="Root holding <target>/findings/default/fuzzer_stats (default ~/fuzz)")
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "shared" / "findings"))
    args = ap.parse_args()

    fuzz_root = Path(args.fuzz_root)
    rows, baseline = build_rows(fuzz_root)
    md = to_markdown(rows, baseline)
    print(md)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d")
    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fuzz_root": str(fuzz_root),
        "baseline_clean": baseline,
        "targets": rows,
    }
    (out_dir / f"comparison_llm_vs_afl_{stamp}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / f"comparison_llm_vs_afl_{stamp}.md").write_text(md, encoding="utf-8")
    print(f"\nWrote comparison_llm_vs_afl_{stamp}.json + .md to {out_dir}")


if __name__ == "__main__":
    main()
