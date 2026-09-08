"""Money rounding helpers for the billing domain.

Known bug: round_half_away() is documented to round halves away from zero
(so 2.5 -> 3, -2.5 -> -3) but delegates to Python's built-in round(), which
rounds halves to even (2.5 -> 2). This is the AEGIS acceptance-repository
*unfixable* scenario (scenario C): the seeded MockProvider answers deliberately
never contain a correct fix, so the bounded repair loop exhausts its budget and
the run ends at a clean SAFE_STOP -- not a crash, not a false VERIFIED.
"""


def round_half_away(value: float) -> int:
    """Round ``value`` to the nearest integer, with halves going away from zero.

    round_half_away(2.5) must be 3; round_half_away(-2.5) must be -3.
    """
    return round(value)
