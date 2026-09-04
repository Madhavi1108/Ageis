# ADR-0019: Model-routing policy (cheap / frontier)

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

`AEGIS_IMPLEMENTATION_PLAN.md` §4.13 makes cost and latency first-class constraints. A single model
tier for every AI call is either too expensive (frontier everywhere) or too weak (cheap
everywhere). Not in the Specification; added by the upgraded plan.

## Decision

- Two tiers behind `AIProvider.complete(..., tier=...)`:
  - **`cheap`** — task normalization, `task_type` classification, lexical/graph candidate
    re-ranking, test-collection triage, summarization, verification-trace phrasing.
  - **`frontier`** — engineering planning, implementation edit-ops, test synthesis, root-cause
    analysis, code review.
- Tier per stage is config (`ai/routing.yaml`), overridable per deployment. Routing decisions are
  logged with token + cost accounting.
- The repair loop's frontier calls are additionally bounded by the Phase 14 iteration and
  wall-clock budgets.
- Cost levers, in order of preference when a budget regresses: push a stage to `cheap`, increase
  context-windowing aggressiveness, lower the repair cap, enable prompt caching, enable the
  marginal-improvement early-exit (`COST_MODEL.md` §5).
- Model **ids** within a tier are config; the abstraction does not hard-code a vendor
  (`ADR-0005`).

## Consequences

- Expected per-task cost drops materially vs frontier-everywhere (`COST_MODEL.md` §4) with little
  quality loss on the cheap-tier stages.
- A stage mis-routed to `cheap` can degrade quality; caught by the Phase 25 metrics and revertible
  in config.
- Two prompt variants per routed stage to maintain.

## Alternatives considered

- **Frontier for everything** — rejected: cost/latency outside the envelope for no quality need on
  simple stages.
- **Cheap for everything** — rejected: planning / edit-ops / RCA / review need the reasoning
  depth.
- **Dynamic per-call routing by a classifier** — deferred: adds a model call and nondeterminism;
  static per-stage routing is simpler and replay-friendly.
