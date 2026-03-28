"""
Root conftest.py – ensures the project root is on sys.path so that
``import extrarrfin`` works when running pytest from the project directory.
"""

import sys
from pathlib import Path

# Add project root to path so `extrarrfin` package is importable
sys.path.insert(0, str(Path(__file__).parent))
