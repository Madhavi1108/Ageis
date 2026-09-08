"""Test-suite-wide setup.

The ``benchmarks`` package (Phase 25) lives at the repo root, not under
``backend/``. Put the repo root on ``sys.path`` so the benchmark tests can
``import benchmarks`` the same way ``scripts/`` entry points do.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
