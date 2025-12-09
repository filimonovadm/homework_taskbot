"""Test configuration for adjusting import paths.

The repository is not installed as a package, so we extend ``sys.path`` to
allow tests to import both module-style files (e.g. ``main.py`` inside the
functions folder) and the ``functions`` package itself.
"""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
FUNCTIONS_DIR = CURRENT_DIR.parent
REPO_ROOT = FUNCTIONS_DIR.parent

sys.path.insert(0, str(FUNCTIONS_DIR))
sys.path.insert(0, str(REPO_ROOT))

