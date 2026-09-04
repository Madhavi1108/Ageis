"""Invoice total calculation.

Known bug: calculate_total() does not cap the discount rate, so a discount
above 0.5 (50%) is applied in full instead of being capped at 50%.
"""


def calculate_total(price: float, discount: float) -> float:
    """Return the price after applying a discount rate in [0, 1].

    The discount must never exceed 50%: any requested discount above 0.5
    should be capped at 0.5 before being applied.
    """
    return price * (1 - discount)
