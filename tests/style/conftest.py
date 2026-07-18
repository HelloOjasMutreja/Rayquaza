from pathlib import Path
import sys

STYLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "style"
sys.path.insert(0, str(STYLE_DIR))
