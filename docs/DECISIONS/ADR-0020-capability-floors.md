# ADR-0020: Capability-floor thresholds & decision gates

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

`AEGIS_IMPLEMENTATION_PLAN.md` §7.1, §7.5 makes the project's core bet — issue→code localization
and autonomous repair — falsifiable before breadth is built, via a capability spike and staged
decision gates. Not in the Specification; added by the upgraded plan in response to the "wide and
shallow" and "hard-20%-not-de-risked" risks identified when rating the plan.

## Decision

- **G0 (end of Phase 0 capability spike):** issue→code localization `recall@10 >= 0.75` and
  end-to-end verified-fix rate `>= 0.30` on a ~30-task benchmark subset. Below floor: up to two
  bounded retrieval/planning redesign rounds, then re-scope (assisted mode or a narrower task
  class) per `POSITIONING.md` §6.
- **G1 (M2 exit):** localization `recall@10 >= 0.70` on the **held-out** wild set (overfitting
  check) and plan-validation reject rate `>= 0.95` on deliberately bad plans.
- **G2 (M5 exit):** false-complete rate `<= 2%` on the labeled verification set. This is a hard
  release gate, not a target.
- **G3 (M8 exit):** competitive resolution-rate delta `>= 0` vs the best reference agent; cost per
  verified task within `COST_MODEL.md`'s envelope; deterministic-replay fidelity `>= 0.9`.
- Thresholds are recorded here as the initial, illustrative bar; a change to any threshold is a new
  ADR superseding this one, not a silent edit.
- Gate evaluation and results are recorded in `docs/CAPABILITY_SPIKE.md` (G0) and
  `docs/BENCHMARK_RESULTS.md` (G1–G3), dated.

## Consequences

- The project can stop or re-scope early and cheaply if the core capability is not there, instead
  of discovering it after building the dashboard, Excel, and GitHub automation.
- Thresholds are somewhat arbitrary at `v1` — chosen to be a meaningful bar, not proven optimal;
  they are explicitly labeled illustrative and open to a superseding ADR once real data exists.

## Alternatives considered

- **No formal gates, "we'll know it when we see it"** — rejected: exactly the failure mode this
  ADR exists to prevent (sunk-cost continuation on a weak core).
- **A single end-of-project gate** — rejected: too late to be useful; G0 in particular must fire
  before any product-surface investment.
