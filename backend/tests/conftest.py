import sys
from pathlib import Path

# Make `app` importable when pytest is run from backend/ (the normal case)
# or from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
