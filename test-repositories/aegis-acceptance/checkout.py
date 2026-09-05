"""Checkout flow -- calls into the invoice module.

Added for Phase 5 (Code Graph & Dependency Analysis) to make the
Specification's own worked example ("callers of calculate_total: checkout.py,
order_service.py") a real, checkable fact rather than a simulated one. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 and Section 10's worked example.
"""

from invoice import calculate_total


def process_checkout(price: float, discount: float) -> float:
    """Compute the checkout total for a cart, applying any discount."""
    return calculate_total(price, discount)
