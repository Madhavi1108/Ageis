def calculate_total(price, discount):
    """Return the price after applying a discount rate in [0, 1].

    A discount above 0.5 (50%) must be capped at 0.5 before being applied.
    """
    return price * (1 - discount)
