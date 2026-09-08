"""Unrelated scale helpers -- a distractor for localization."""


def clamp(value, low, high):
    return max(low, min(high, value))
