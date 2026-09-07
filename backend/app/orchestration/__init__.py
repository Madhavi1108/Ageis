"""Workflow orchestration (Phase 21, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 29, state machine in Section 4.3).

* ``state_machine`` -- the guarded §4.3 transition table + the single writer
  (``transition``) that closes the prior step, sets ``Task.state``, and appends
  a linked ``TaskStep`` (``input_ref`` / ``output_ref``).
* ``orchestrator``  -- ``run_task``: sequences every pipeline stage service,
  each consuming the prior stage's persisted output; checkpoints the job.
* ``job_queue``     -- FIFO claim, dedup, retry/backoff, crash-recovery reclaim.
* ``worker``        -- an asyncio worker (concurrency-capped) that claims
  ``RUN_TASK`` jobs and runs the orchestrator; ``run_once`` for tests.
"""

from __future__ import annotations
