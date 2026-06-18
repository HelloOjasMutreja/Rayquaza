from pathlib import Path
import sys

# Add project root to path for all tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
