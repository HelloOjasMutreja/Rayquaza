#!/usr/bin/env python3
"""
run.py — Rayquaza Phase A visualizer entry point.

Usage:
  python run.py           # open window, click Replay All
  python run.py --replay  # open window and auto-start replay
  python run.py --live    # live mode (A2 — not yet implemented)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from viz.app import start_app


def main():
    autostart = "--replay" in sys.argv
    if "--live" in sys.argv:
        print("Live mode (A2) is not yet implemented. Use --replay for now.")
        sys.exit(1)
    start_app(autostart_replay=autostart)


if __name__ == "__main__":
    main()
