"""Lets the tests import the backend modules (`app`, `config`) when pytest runs from the repo root or `backend/`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
