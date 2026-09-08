# Task: Add order-level tax to the checkout flow

Orders are currently charged without any tax. Add tax support:

- Create a new module `tax.py` with `apply_tax(subtotal: float, rate: float) -> float`
  that returns `subtotal * (1 + rate)`.
- Wire it into `order_service.finalize_order()` so the finalized amount has tax applied
  on top of the discounted total.
- Add tests for the new `tax.py` module.

This is the AEGIS acceptance-repository **feature** scenario (scenario B): it exercises the
implementation agent's file-creation path and end-to-end verification of brand-new modules and
tests. See `docs/ACCEPTANCE_SCENARIOS.md`.
