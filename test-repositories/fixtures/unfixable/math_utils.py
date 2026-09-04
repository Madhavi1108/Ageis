"""A small math helper with a subtle rounding bug.

This fixture exists to exercise the walking skeleton's bounded repair loop
and its clean-stop behavior: no canned MockProvider response exists for this
task (see aegis/ai/provider.py), so the pipeline falls back to a generic,
low-confidence plan that does not actually fix the bug -- honestly
representing "the AI's best attempt did not work" rather than a rigged
success or failure.
"""


def round_half_up(value: float) -> int:
    """Round to the nearest integer, rounding .5 up (not banker's rounding)."""
    # BUG: uses plain round(), which is banker's rounding in Python
    # (round(2.5) == 2, not 3), so this does not actually round half up.
    return round(value)
