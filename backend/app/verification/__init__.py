"""Verification Agent (Phase 18, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26,
docs/DATA_MODEL.md Section 2.4 "Verification").

A task is never complete merely because code was generated. ``verify`` runs a
deterministic checklist -- acceptance tests, the regression/full suite, patch
re-application, scope, code review, plan alignment, and the PCS/CRS gate -- and
returns a per-criterion verdict, an overall ``VERIFIED`` / ``NOT_VERIFIED`` /
``PARTIAL``, the plan-alignment breakdown, and the explainability trace
(why file / why change / why test / why safe).

No AI is involved anywhere in this package -- every criterion is mechanically
checked against rows Phases 8/10/12/15/16/17 already persisted.
"""

from __future__ import annotations

VERIFICATION_MODEL_VERSION = "verification-model v1.0.0"
