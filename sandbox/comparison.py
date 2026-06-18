def build_comparison(runs: list) -> dict:
    """Build a per-axis side-by-side structure from a list of Run objects."""
    models = [r.model_code for r in runs]
    target_ids = []
    for r in runs:
        for t in r.targets:
            if t.target_id not in target_ids:
                target_ids.append(t.target_id)

    detection = {}
    for tid in target_ids:
        detection[tid] = []
        for r in runs:
            tr = next((t for t in r.targets if t.target_id == tid), None)
            detection[tid].append({
                "located": tr.located if tr else None,
                "confirmed": tr.confirmed if tr else None,
                "t_stat": tr.t_stat if tr else None,
            })

    efficiency = {
        "wall_seconds": [round(r.ended_at - r.started_at, 1) for r in runs],
        "cost_usd": [r.cost_usd for r in runs],
        "tokens": [r.tokens.get("prompt", 0) + r.tokens.get("completion", 0) for r in runs],
    }
    robustness = {"fp_rate": [r.fp_rate for r in runs]}
    return {"models": models, "targets": target_ids, "detection": detection,
            "efficiency": efficiency, "robustness": robustness}


def to_markdown(comp: dict) -> str:
    models = comp["models"]
    lines = ["# Model comparison", "",
             "| Target | " + " | ".join(models) + " |",
             "|---|" + "|".join(["---"] * len(models)) + "|"]
    for tid in comp["targets"]:
        cells = []
        for cell in comp["detection"][tid]:
            mark = "✓" if cell["confirmed"] else ("·located" if cell["located"] else "✗")
            t = "" if cell["t_stat"] is None else f" t={cell['t_stat']:.1f}"
            cells.append(mark + t)
        lines.append(f"| {tid} | " + " | ".join(cells) + " |")
    lines += ["",
              "| Axis | " + " | ".join(models) + " |",
              "|---|" + "|".join(["---"] * len(models)) + "|",
              "| wall (s) | " + " | ".join(str(x) for x in comp["efficiency"]["wall_seconds"]) + " |",
              "| cost ($) | " + " | ".join(str(x) for x in comp["efficiency"]["cost_usd"]) + " |",
              "| tokens | " + " | ".join(str(x) for x in comp["efficiency"]["tokens"]) + " |",
              "| fp-rate | " + " | ".join(str(x) for x in comp["robustness"]["fp_rate"]) + " |"]
    return "\n".join(lines)
