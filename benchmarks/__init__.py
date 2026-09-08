"""AEGIS benchmark framework (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 33,
docs/EVAL_HARNESS.md, docs/METRICS.md).

A repeatable, deterministic harness that drives the real ``app/`` pipeline
(Phase 21 orchestrator) over curated mini-repo tasks, captures raw signals, and
computes the 16 objective metrics with generated (never hard-coded) numbers.

Scope in this environment: curated fixtures + ``MockProvider`` + the fake
sandbox. Real SWE-bench-Lite repos, live models, the Docker sandbox, and the
reference agents (metric #15) are out of scope here -- the datasets and the
``benchmarks.agents`` interface are built so a live run is a config change, not
a rewrite.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ``benchmarks`` lives at the repo root but imports ``app.*``; make the backend
# package importable however this module is entered (mirrors
# ``scripts/build_acceptance_repo.py``).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

REPO_ROOT = _REPO_ROOT
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"

__all__ = ["REPO_ROOT", "DATASETS_DIR"]
