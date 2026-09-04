"""Repository ingestion domain logic (Phase 3). See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11.

Kept separate from app/repository/ (Phase 2's data-access layer, e.g. JobRepository) --
this package holds business logic (validation, cloning, hashing, limit enforcement) that
*uses* the data-access repositories, not another data-access layer itself.
"""
