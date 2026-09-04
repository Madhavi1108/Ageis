# ADR-0016: Engineering-memory architecture

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §3.2 and §23 require persistent repository knowledge and completed-task memory that future
tasks can retrieve as evidence — but old fixes must not be blindly copied; memory is evidence, not
truth.

## Decision

- Two layers:
  - **Repository knowledge** — per-repo: structure summary, test/build commands, risky files,
    recurring failure patterns, previous issue→code mappings; upserted every run.
  - **Engineering memory** — one `EngineeringMemory` row written at a terminal state (`VERIFIED`
    or `SAFE_STOP`): issue text, touched symbols, failure signatures, fix summary, plan/patch
    refs, review summary, verification verdict, outcome.
- Retrieval (`memory/retrieve.py`) combines lexical FTS + symbol overlap + a same-repository boost
  + optional embeddings; returns `MemoryHit`s with a similarity score and **provenance**.
- Consumers (mapping, planning, RCA, regression selection) receive memory hits as ranked evidence
  explicitly labelled **"historical — verify"**. Memory never auto-applies a patch and never
  overrides current evidence.
- Feature-flagged; the pipeline behaves identically with memory empty or disabled.

## Consequences

- The moat compounds with usage, per customer (`POSITIONING.md` §1).
- Stale/misleading memory is bounded by provenance + recency weighting + the "verify" label +
  non-authoritative status.
- Extra storage + an index to maintain; covered by retention policy.

## Alternatives considered

- **Auto-apply the closest past patch** — rejected by Spec §23 ("do not blindly copy old fixes").
- **A vector DB service** — rejected for the MVP: FTS + symbol overlap suffice; embeddings are
  optional and can use a local model.
- **No memory in the MVP** — rejected: it is a core differentiator; a basic version ships in
  Phase 20.
