"""Central typed accessors for every size / count / duration / budget limit
(docs/AEGIS_IMPLEMENTATION_PLAN.md §35, docs/EXECUTION_MODEL.md §5-§6, ADR-0012).

`config.py` holds the *values*; this module is the one import site that names
them, so a limit is looked up as ``limits.analysis_seconds(settings)`` rather
than reaching into ``settings.limit_analysis_seconds`` from a dozen places.
Exceeding a §37 limit degrades to ``PARTIALLY_SUPPORTED{reason}`` with partial
artifacts -- never a crash, never a silent unprovenanced truncation.
"""

from __future__ import annotations

from app.core.config import Settings

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def request_body_bytes(settings: Settings) -> int:
    """Max accepted size of an incoming HTTP request body."""
    return settings.request_max_body_bytes


# --------------------------------------------------------------------------- #
# Repository ingestion (Spec §37) -- enforced in ingestion/limits.py
# --------------------------------------------------------------------------- #


def repo_bytes(settings: Settings) -> int:
    return settings.ingestion_max_repo_bytes


def file_count(settings: Settings) -> int:
    return settings.ingestion_max_files


def file_bytes(settings: Settings) -> int:
    return settings.ingestion_max_file_bytes


def history_depth(settings: Settings) -> int:
    return settings.ingestion_max_history_depth


# --------------------------------------------------------------------------- #
# Analysis (Spec §37) -- enforced in analysis/analyze.py
# --------------------------------------------------------------------------- #


def analysis_seconds(settings: Settings) -> int:
    """Wall-clock budget for one ``analyze_snapshot`` pass; over budget -> the
    remaining files are SKIPPED with provenance and the task goes
    PARTIALLY_SUPPORTED."""
    return settings.limit_analysis_seconds


def graph_nodes(settings: Settings) -> int:
    """Soft cap on code-graph nodes; a larger repo yields a partial graph with a
    provenance note rather than a long stall."""
    return settings.limit_graph_nodes


# --------------------------------------------------------------------------- #
# AI (Spec §37)
# --------------------------------------------------------------------------- #


def ai_context_tokens(settings: Settings) -> int:
    """Input-context budget (estimated). Over budget -> the lowest-priority
    context sections are dropped deterministically with a provenance note
    (ai/context.py::fit_context)."""
    return settings.limit_ai_context_tokens


# --------------------------------------------------------------------------- #
# Test generation & repair (Spec §37)
# --------------------------------------------------------------------------- #


def generated_tests(settings: Settings) -> int:
    """Soft cap on generated test cases kept per task (newest trimmed with
    provenance). ``settings.testing_max_cases`` is the separate hard ceiling on
    a single provider response."""
    return settings.limit_generated_tests


def patch_candidates(settings: Settings) -> int:
    """Repair patch candidates == the repair-loop iteration budget."""
    return settings.repair_max_iterations


def repair_wall_clock_seconds(settings: Settings) -> int:
    return settings.repair_wall_clock_s


# --------------------------------------------------------------------------- #
# Sandbox (Spec §18) -- applied in sandbox/policy.py via ResourceLimits
# --------------------------------------------------------------------------- #


def sandbox_wall_clock_seconds(settings: Settings) -> int:
    return settings.sandbox_wall_clock_s


def sandbox_memory_mb(settings: Settings) -> int:
    return settings.sandbox_memory_mb


def sandbox_cpus(settings: Settings) -> float:
    return settings.sandbox_cpus
