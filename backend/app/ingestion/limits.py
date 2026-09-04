"""Repository size/file-count/history limits. See docs/DECISIONS/ADR-0012.

check_and_partition NEVER raises -- exceeding a limit produces a PARTIALLY_SUPPORTED
snapshot with a human-readable reason, never a crash and never a silent, unprovenanced
truncation (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.9).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.core.config import Settings
from app.ingestion.manifest import ManifestFile


@dataclass(frozen=True)
class RepoLimits:
    max_total_bytes: int
    max_files: int
    max_file_bytes: int
    max_history_depth: int


def limits_from_settings(settings: Settings) -> RepoLimits:
    return RepoLimits(
        max_total_bytes=settings.ingestion_max_repo_bytes,
        max_files=settings.ingestion_max_files,
        max_file_bytes=settings.ingestion_max_file_bytes,
        max_history_depth=settings.ingestion_max_history_depth,
    )


@dataclass(frozen=True)
class LimitBreach:
    reason: str


def check_and_partition(
    files: list[ManifestFile], limits: RepoLimits
) -> tuple[list[ManifestFile], LimitBreach | None]:
    reasons: list[str] = []

    # 1. Per-file size: mark oversized files SKIPPED, keep the row (size known,
    # content not hashed/read) so the manifest still names what was excluded.
    oversized = 0
    sized: list[ManifestFile] = []
    for f in files:
        if f.size_bytes > limits.max_file_bytes:
            oversized += 1
            sized.append(
                replace(
                    f,
                    sha256="",
                    parse_status="SKIPPED",
                    parse_error=f"file size {f.size_bytes} exceeds max_file_bytes {limits.max_file_bytes}",
                )
            )
        else:
            sized.append(f)
    if oversized:
        reasons.append(
            f"{oversized} file(s) exceeded max_file_bytes ({limits.max_file_bytes} bytes)"
        )

    # 2. File-count cap: deterministic truncation (sorted-path order, already sorted
    # by build_manifest), remainder dropped entirely.
    truncated_by_count = 0
    if len(sized) > limits.max_files:
        truncated_by_count = len(sized) - limits.max_files
        sized = sized[: limits.max_files]
        reasons.append(
            f"{truncated_by_count} file(s) dropped: repository exceeds max_files ({limits.max_files})"
        )

    # 3. Total-bytes cap: truncate further, in the same deterministic order.
    total = 0
    within_budget: list[ManifestFile] = []
    for f in sized:
        if total + f.size_bytes > limits.max_total_bytes:
            break
        within_budget.append(f)
        total += f.size_bytes
    truncated_by_bytes = len(sized) - len(within_budget)
    if truncated_by_bytes:
        reasons.append(
            f"{truncated_by_bytes} file(s) dropped: repository exceeds max_total_bytes "
            f"({limits.max_total_bytes} bytes)"
        )

    breach = LimitBreach(reason="; ".join(reasons)) if reasons else None
    return within_budget, breach
