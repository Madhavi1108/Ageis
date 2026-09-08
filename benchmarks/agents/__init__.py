"""Reference-agent adapters for metric #15 (competitive resolution-rate delta).

Only ``NoopReferenceAgent`` ships wired. A real OpenHands / SWE-agent / Aider
adapter runs in its own container with the same resource limits and the same
``fail_to_pass`` / ``pass_to_pass`` verification criterion -- see ``README.md``.
"""

from benchmarks.agents.base import ReferenceAgent
from benchmarks.agents.noop import NoopReferenceAgent

__all__ = ["ReferenceAgent", "NoopReferenceAgent"]
