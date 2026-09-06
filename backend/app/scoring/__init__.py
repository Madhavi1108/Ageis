"""Risk & Confidence Engine (Phase 17, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 25, formulas in Section 4.10).

Deterministic, explainable, versioned scoring:

* ``confidence.compute_pcs``   -- Patch Confidence Score (0-100, higher = safer)
* ``risk.compute_crs``         -- Change Risk Score      (0-100, higher = riskier)
* ``repo_health.compute_rhp``  -- Repository Health Profile + Task-Specific Risk Profile

Every constant lives in ``model_registry`` (``scoring-model v1.0.0``); a test
asserts the code constants equal the ``docs/METRICS.md`` Section 2 tables. No AI
is involved anywhere in this package.
"""
