#!/usr/bin/env python3
"""
mock_feedback.py — Generates synthetic timing data matching Track A harness output schema.

Simulates a real but subtle 20ns timing leak:
  class_A (leak path): mean=220ns, std=15ns
  class_B (safe path): mean=200ns, std=15ns

Usage: python3 mock_feedback.py <hypothesis_id>
Example: python3 mock_feedback.py H001
Output: shared/feedback/mock_timing_<timestamp>.json
"""

import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

N_SAMPLES = 10000
MEAN_A = 220.0
MEAN_B = 200.0
STD_DEV = 15.0

OUTPUT_DIR = Path(__file__).parent.parent.parent / "shared" / "feedback"


def compute_stats(samples):
    n = len(samples)
    mean = sum(samples) / n
    variance = sum((x - mean) ** 2 for x in samples) / n
    return mean, variance


def t_statistic(mean_a, var_a, mean_b, var_b, n):
    stderr_a = math.sqrt(var_a / n)
    stderr_b = math.sqrt(var_b / n)
    pooled = math.sqrt(stderr_a ** 2 + stderr_b ** 2)
    if pooled == 0:
        return 0.0
    return (mean_a - mean_b) / pooled


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <hypothesis_id>")
        print("Example: python3 mock_feedback.py H001")
        sys.exit(1)

    hypothesis_id = sys.argv[1]

    random.seed()
    samples_a = [random.gauss(MEAN_A, STD_DEV) for _ in range(N_SAMPLES)]
    samples_b = [random.gauss(MEAN_B, STD_DEV) for _ in range(N_SAMPLES)]

    mean_a, var_a = compute_stats(samples_a)
    mean_b, var_b = compute_stats(samples_b)
    t = t_statistic(mean_a, var_a, mean_b, var_b, N_SAMPLES)
    significant = abs(t) > 2.0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = {
        "hypothesis_id": hypothesis_id,
        "run_count": N_SAMPLES,
        "mean_A": round(mean_a, 4),
        "mean_B": round(mean_b, 4),
        "variance_A": round(var_a, 4),
        "variance_B": round(var_b, 4),
        "t_statistic": round(t, 6),
        "significant": significant,
        "generated_by": "mock",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"mock_timing_{timestamp}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
