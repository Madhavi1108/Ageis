"""Engineering memory (Phase 20, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28,
ADR-0016).

Two layers, both opt-in behind ``settings.memory_enabled``:

* a completed-task record (``EngineeringMemory``) written at a terminal state
  (``VERIFIED`` / ``SAFE_STOP``), and a per-repository aggregate
  (``RepositoryKnowledge``);
* deterministic retrieval (``index`` + ``retrieve``) that combines a lexical
  index, symbol overlap, a same-repository boost and recency decay into ranked
  ``MemoryHit``s.

Every hit is labelled ``MEMORY_LABEL`` and carries provenance. Memory is
evidence, never truth: it never overrides current evidence and a past patch is
never auto-applied.
"""

from __future__ import annotations

MEMORY_LABEL = "historical — verify (not authoritative)"
