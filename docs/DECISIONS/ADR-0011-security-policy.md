# ADR-0011: Security policy

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §34 requires protection against command injection, path traversal, arbitrary host execution,
malicious repositories and generated code, secret leakage, unsafe env vars, insecure file
handling, SSRF, unauthorized repository access, unsafe Git operations, and untrusted AI outputs —
and says never to trust repo files, Git metadata, AI outputs, issue descriptions, generated
patches, or test code.

## Decision

- A single `core/security/` package is the enforcement point: `validate.py` (central input gate),
  `pathjail.py` (resolve + assert containment for every fs op), `subprocess_guard.py`
  (no `shell=True`; allowlist `docker`, `git`; args as lists), `env_allowlist.py` (sandbox env
  scrub), `redaction.py` (log/secret filter), `ssrf.py` (host allowlist + private-IP block for
  ingestion and the GitHub client).
- AI outputs are always schema-validated; AI-produced code is never `exec`'d in-process;
  AI-produced paths are jailed; AI-produced shell strings are rejected.
- Secrets live only in process env / a secrets file; never in the DB, artifacts, or logs; a CI
  scanner fails on a secret pattern in test output.
- RBAC on every mutating route (`GOVERNANCE.md` §4). Overrides are audit-logged with a reason.
- `AuditLog` is an append-only hash chain (`GOVERNANCE.md` §3).
- HITL policy `AUTO` / `REVIEW_REQUIRED` / `BLOCKED` gates risky actions (`SECURITY_MODEL.md` §6).
- Dependencies pinned + hashed; `pip-audit` + `bandit` CI gates; SBOM per build; sandbox image
  scanned before promotion.
- Phase 26 performs a full threat-to-control audit and turns the security test suite into a hard
  gate.

## Consequences

- One place to review for each vulnerability class; new abuse cases become permanent tests.
- Some developer friction (no `shell=True`, all paths jailed) — intentional.

## Alternatives considered

- **Per-module ad-hoc validation** — rejected: inconsistent, unauditable.
- **Trust AI JSON because it is "structured"** — rejected: schema validity is not safety
  (`SECURITY_MODEL.md` §10).
