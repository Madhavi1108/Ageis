"""Unrelated helper module (distractor for the localization spike)."""


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
