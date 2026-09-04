# ADR-0005: AI provider abstraction

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Specification §3.8 forbids hard-coding the system around one AI provider and requires structured
prompts, structured outputs, retries, timeouts, token/context limits, error handling, provider
selection, model configuration, and request logging without leaking secrets. §20 requires
schema-validated AI outputs.

## Decision

- An `AIProvider` protocol with `complete(template, variables, schema, tier, timeout_s,
  max_tokens, temperature) -> Validated` and optional `embed(texts)`.
- Implementations: `ClaudeProvider`, `OpenAIProvider`, `LocalProvider`, `MockProvider`
  (deterministic, canned-by-prompt-hash; the CI default).
- Every implementation provides: template-based structured prompt assembly (untrusted content only
  in delimited data fields), JSON-schema-constrained output validated by `ai/schema_guard.py`, one
  automatic repair round then a clean `AIOutputInvalid` failure, retries with backoff on transient
  errors, per-call timeout, deterministic context/token budgeting with dropped-item provenance,
  and redacted request logging (provider, model, params, token counts, latency, prompt digest —
  never raw untrusted bodies).
- Provider + per-stage model tier chosen by config (`ADR-0019`). With no real provider configured,
  the pipeline still runs via rule-based fallbacks at lower confidence.
- `temperature = 0.0` everywhere for determinism / replay.

## Consequences

- Swapping or adding a provider is a new class; nothing else changes.
- All AI I/O is uniformly validated, retried, logged, and budgeted.
- `MockProvider` makes the whole pipeline testable without network or spend.

## Alternatives considered

- **Vendor SDK used directly across the codebase** — rejected by Spec §3.8.
- **A third-party LLM abstraction library** — rejected: another dependency for a thin interface we
  fully control; harder to guarantee redaction and schema-guard behavior.
- **Free-text outputs parsed heuristically** — rejected by Spec §20; brittle and unauditable.
