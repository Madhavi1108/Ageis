"""Billing configuration constants.

Added in Phase 24 (End-to-End Controlled Repository) so the acceptance repo has
a realistic "configured maximum" for the discount-cap rule rather than a magic
number scattered through the code. See docs/ACCEPTANCE_SCENARIOS.md.
"""

#: The largest discount rate the business allows on any single line item. A
#: requested discount above this must be clamped to it before being applied.
MAX_DISCOUNT = 0.5
