# ADR-0018: Frontend state model

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §27, §28, §31 require a professional React + TypeScript dashboard that exposes real backend
data (not decorative), shows the full task pipeline with each stage inspectable, includes a
diff/patch viewer, and uses real-time or polling status updates. The MVP ships the task-pipeline
view; the full 14 screens are post-MVP.

## Decision

- **Server state via TanStack Query.** The backend is the single source of truth; the frontend
  holds almost no local state. Query keys mirror API resources
  (`['task', id]`, `['task', id, 'timeline']`, ...).
- **Polling driven by task state:** active tasks poll on a state-dependent interval; terminal
  tasks stop polling. An optional SSE/WebSocket channel for the timeline is a later enhancement.
- **Typed API client generated/derived from the OpenAPI schema**; no hand-written response types.
- **Local UI state only** for ephemeral view concerns (selected tab, expanded panel), kept in
  component state or the URL, not a global store.
- **No mock data in the shipped app.** A Phase 22 test asserts every pipeline panel issues a
  backend call.
- Diff viewer: `react-diff-view` / Monaco showing files changed, +/-, modified functions, risk,
  scope compliance, related tests, review findings, and the exact patch before approval.
- HITL controls (approve / block) appear where policy = `REVIEW_REQUIRED`.

## Consequences

- Minimal client-side state bugs; the dashboard cannot drift from the backend.
- Polling load is bounded by the state-based interval; SSE is the optimization if needed.
- Generated types couple the frontend build to an up-to-date OpenAPI document (a drift check runs
  in CI, Phase 28).

## Alternatives considered

- **Redux / Zustand global store for server data** — rejected: re-implements caching TanStack
  Query already does; invites drift.
- **SSR (Next.js)** — rejected: internal dashboard, no SEO/SSR need (`TECH_STACK.md` §2).
- **Hand-written API types** — rejected: drift risk; OpenAPI is the contract.
