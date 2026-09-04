# ADR-0014: Git strategy

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §15 requires deep Git integration for blame, commit history, changed files, previous fixes,
related commits, churn, and regression history, feeding planning and review. Spec §34 warns against
unsafe Git operations.

## Decision

- **Local Git via GitPython** (a library, not shelling `git` with untrusted args). A thin
  `git/` package exposes `history`, `blame`, `churn`, and the four questions from Spec §15
  ("has this area changed?", "what happened after?", "was a similar bug fixed?", "which tests
  changed with similar modifications?").
- Cloning uses hardened options: configurable depth, `core.hooksPath=/dev/null`, no submodule
  recursion, no credential prompts, protocol restricted to `https`/`file`(local roots only).
- Git-derived facts enrich the code graph (`CHANGED_BY`, `FIXED_BY`, `RELATED_TO` edges) and the
  mapping / impact / RCA stages.
- Author emails are stored hashed with a per-repository salt (`GOVERNANCE.md` §5).
- Branch/commit creation for a verified change happens in the **RW workspace** only; pushing is a
  GitHub concern (`ADR-0015`) gated by HITL policy.
- No `git` subprocess ever receives a string interpolated from untrusted input.

## Consequences

- History intelligence is available offline and safely.
- GitPython edge cases (shallow clones, detached HEAD) must be handled explicitly.
- Very deep histories are truncated by the history-depth limit (`ADR-0012`).

## Alternatives considered

- **Shell `git` commands** — rejected: injection surface; harder to test.
- **pygit2 (libgit2)** — viable but a heavier native dependency; GitPython is sufficient for read-
  heavy use.
- **Reimplement history parsing** — rejected: needless.
