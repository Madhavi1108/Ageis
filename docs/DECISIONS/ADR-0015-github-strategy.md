# ADR-0015: GitHub strategy

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §16 and §17 require GitHub integration for repository retrieval, issues, PRs, branches,
commits, files, and metadata; a dedicated provider/client abstraction; public repo support; auth
when configured; never exposing tokens; URL validation; and handling invalid/private/inaccessible
repos, rate limiting, network failure, missing permissions, and branch conflicts. A PR must never
be claimed as created unless it actually was.

## Decision

- A thin `github/client.py` over `httpx` (REST), plus a `GitHubProvider` used by the ingestion and
  PR stages. No heavy SDK (`TECH_STACK.md` §2).
- Tokens come from config/secrets, are redacted in all logs, and never persisted.
- URL validation + SSRF guard (`ADR-0011`); explicit mapping of `401/403/404/409/429/5xx`/network
  errors to structured task states.
- **PR creation** is `REVIEW_REQUIRED` by HITL policy for protected branches / external PRs; it
  runs only after `VERIFIED`. Without write credentials, only a **local PR artifact** is produced.
  A `PullRequest` row is marked `state = CREATED` only on an actual `201` with a stored URL/number.
- The PR body is built from the 18-section report (`title`, summary, issue ref, files changed,
  tests added/executed/results, review results, risk, confidence, known limitations).
- MVP: public repos + authenticated repos when a token is configured. Write-automation polish is
  scheduled post-MVP (`MVP_DEFINITION.md` §5).

## Consequences

- "Never claim a PR exists unless it was created" (Spec §55 Rule 8) is structurally enforced.
- All GitHub failure modes surface as task states, not 500s.
- CI mocks GitHub entirely (`respx`); one optional live smoke test.

## Alternatives considered

- **PyGithub** — rejected: hides HTTP details we need to control (rate-limit, redaction, error
  mapping).
- **GraphQL API** — deferred: REST covers the MVP needs with simpler auth/rate handling.
- **Always attempt a real PR** — rejected by Spec §17 / §55 Rule 8 and the HITL policy.
