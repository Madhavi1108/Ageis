"""Order finalization -- calls into the invoice module.

See checkout.py's docstring: both files exist to make the Specification's
"callers of calculate_total" worked example a real, checkable fact. This file
uses `import invoice` + an attribute call (`invoice.calculate_total(...)`)
rather than checkout.py's `from invoice import calculate_total`, so the two
different call-resolution paths (imported-name vs. import-alias) are both
exercised against real code, not just unit-test fixtures.
"""

import invoice


def finalize_order(price: float, discount: float) -> float:
    """Finalize an order's charged amount."""
    return invoice.calculate_total(price, discount)
