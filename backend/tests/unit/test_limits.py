"""Phase 27 unit: core/limits.py accessors just forward the matching setting.

Cheap guard so a future rename of a ``Settings`` field can't silently leave a
``limits.*`` accessor pointing at the wrong (or a stale) value.
"""

from __future__ import annotations

import pytest

from app.core import limits
from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.mark.parametrize(
    ("accessor", "field"),
    [
        ("request_body_bytes", "request_max_body_bytes"),
        ("repo_bytes", "ingestion_max_repo_bytes"),
        ("file_count", "ingestion_max_files"),
        ("file_bytes", "ingestion_max_file_bytes"),
        ("history_depth", "ingestion_max_history_depth"),
        ("analysis_seconds", "limit_analysis_seconds"),
        ("graph_nodes", "limit_graph_nodes"),
        ("ai_context_tokens", "limit_ai_context_tokens"),
        ("generated_tests", "limit_generated_tests"),
        ("patch_candidates", "repair_max_iterations"),
        ("repair_wall_clock_seconds", "repair_wall_clock_s"),
        ("sandbox_wall_clock_seconds", "sandbox_wall_clock_s"),
        ("sandbox_memory_mb", "sandbox_memory_mb"),
        ("sandbox_cpus", "sandbox_cpus"),
    ],
)
def test_accessor_forwards_setting(settings: Settings, accessor: str, field: str):
    assert getattr(limits, accessor)(settings) == getattr(settings, field)
