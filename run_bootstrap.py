#!/usr/bin/env python3
"""run_bootstrap.py -- Rayquaza Docker reproducibility wizard entry point.

Usage (inside the runner container): python run_bootstrap.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bootstrap.wizard import main

if __name__ == "__main__":
    main()
