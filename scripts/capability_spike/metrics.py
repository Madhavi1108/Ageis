"""Metric computation for the capability spike.

Mirrors, at throwaway scale, the formulas frozen in docs/METRICS.md #1 and
docs/CAPABILITY_SPIKE.md #2. Kept dependency-free and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass


def recall_at_k(predicted: list[str], gold: list[str], k: int = 10) -> float:
    """Fraction of gold files present in the top-k predicted files.

    Matches docs/CAPABILITY_SPIKE.md #2: |top_k ∩ gold| / |gold|.
    """
    if not gold:
        return 1.0
    top_k = set(predicted[:k])
    hit = len(top_k & set(gold))
    return hit / len(gold)


@dataclass
class TaskResult:
    task_id: str
    predicted_files: list[str]
    gold_files: list[str]
    recall_at_10: float
    verified_fix: bool
    fail_to_pass_results: dict[str, bool]
    pass_to_pass_results: dict[str, bool]
    error: str | None = None


def aggregate(results: list[TaskResult]) -> dict[str, float]:
    if not results:
        return {"mean_recall_at_10": 0.0, "verified_fix_rate": 0.0, "n_tasks": 0}
    mean_recall = sum(r.recall_at_10 for r in results) / len(results)
    fix_rate = sum(1 for r in results if r.verified_fix) / len(results)
    return {
        "mean_recall_at_10": mean_recall,
        "verified_fix_rate": fix_rate,
        "n_tasks": len(results),
    }
