# ADR-0004: Agent orchestration model

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Specification §4 and §55 (Rule 2) warn against optimizing for the number of agents and require a
small set of meaningful specialized agents coordinated by a central orchestrator, communicating
via typed schemas rather than uncontrolled text.

## Decision

- Exactly **seven** agents: Repository Analyst, Planning, Implementation, Testing, Debugging, Code
  Review, Verification (`AI_AGENT_DESIGN.md` §2).
- A central **Orchestrator** owns workflow state, budgets (calls / cost / wall-clock), retries,
  checkpoints, and the HITL policy. Agents never call each other and never drive control flow via
  the model.
- Every agent input and output is a Pydantic schema (`schemas/`); the Orchestrator passes the
  previous phase's persisted output as the next phase's input (the connectedness invariant).
- Agents are stateless services over the engines (`analysis`, `implementation`, `testing`,
  `sandbox`, `scoring`, ...) plus the `AIProvider`.
- Engineering Memory is read before mapping/planning/RCA and written once at a terminal state.

## Consequences

- The pipeline is auditable and replayable; a Phase 21 test asserts stage-input == prior
  stage-output.
- No agent sprawl; each agent maps to a Spec §5 responsibility.
- Cross-agent coordination logic concentrates in the Orchestrator — it must stay small and
  table-driven (`ADR-0002`).

## Alternatives considered

- **Many micro-agents / a negotiation protocol** — rejected by Spec §55 Rule 2; adds text-passing
  ambiguity.
- **An agent framework (LangGraph, OpenHands, AutoGen)** — rejected: obscures the typed
  connectedness invariant and the schema contracts (`TECH_STACK.md` §2).
- **Agents call each other directly** — rejected: breaks single-owner state and makes recovery /
  replay hard.
