#!/usr/bin/env python3
"""
main.py — Rayquaza Track B CLI entry point for the LLM adversary loop (Phase B3).

Usage:
  python3 track-b-engine/main.py --target <path.c> --cycles <n> [--use-mock] [--resume]
"""

import argparse
import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from adversary_loop import AdversaryLoop  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(
        description="Rayquaza Track B — LLM Adversary Engine"
    )
    p.add_argument("--target", required=True, help="path to .c file to analyze")
    p.add_argument("--cycles", type=int, default=3,
                   help="number of hypotheses to process (default 3)")
    p.add_argument("--use-mock", action="store_true",
                   help="use mock feedback instead of waiting for Track A")
    p.add_argument("--resume", action="store_true",
                   help="resume from shared/findings/loop_state.json if present")
    return p.parse_args()


def main():
    args = parse_args()
    mode = "mock" if args.use_mock else "live"

    print("Rayquaza Track B — LLM Adversary Engine")
    print(f"Target: {Path(args.target).name}")
    code_model = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")
    reason_model = os.environ.get("RAYQ_REASON_MODEL", "qwen3:8b")
    print(f"Models: {code_model} (analysis) / {reason_model} (refinement)")
    print(f"Mode: {mode}")
    print(f"Starting cycle 1 of {args.cycles}...\n")

    loop = AdversaryLoop(
        target=args.target,
        cycles=args.cycles,
        use_mock=args.use_mock,
        resume=args.resume,
    )

    try:
        loop.run()
    except Exception as e:  # noqa: BLE001
        try:
            import requests
            if isinstance(e, requests.exceptions.ConnectionError):
                print("Ollama not running. Start with: ollama serve")
                sys.exit(1)
        except ImportError:
            pass
        raise

    print("\n=== LOOP COMPLETE ===")
    print(f"Promoted: {loop.promoted_ids}")
    print(f"Demoted: {loop.demoted_ids}")
    print(f"Invalidated: {loop.invalidated_ids}")
    print("Full results: shared/findings/loop_state.json")


if __name__ == "__main__":
    main()
