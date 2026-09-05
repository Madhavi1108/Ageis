"""Shared retriever output type.

Each retriever returns an ordered list of ``RetrievedCandidate`` (best first).
The fusion step (fuse.py) consumes several such lists; the mapper turns the
fused result into the API ``MappingCandidate`` schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.schemas.common import Evidence


@dataclass
class RetrievedCandidate:
    """One file a retriever thinks is relevant, with its supporting evidence.

    ``path`` is the snapshot-relative file path -- the unit every retriever
    agrees on (symbols and graph nodes are resolved back to their file).
    """

    path: str
    #: retriever-local score, only used for that retriever's own ranking;
    #: fusion uses rank position, not this value.
    score: float
    evidence: list[Evidence] = field(default_factory=list)
    #: symbols this retriever specifically implicated in ``path`` (may be empty).
    symbols: list[str] = field(default_factory=list)


@dataclass
class RetrieverResult:
    name: str
    candidates: list[RetrievedCandidate]
    #: False for a retriever that could not run (e.g. semantic with no provider).
    available: bool = True
