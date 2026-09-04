# ADR-0006: Repository abstraction

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

AEGIS must ingest both local repositories and GitHub repositories, snapshot them immutably, and
never execute their code on the host (Spec §3.1, §18, §38).

## Decision

- A `RepositorySource` abstraction with `LocalSource` and `GitHubSource` implementations behind one
  `ingest()` returning a `RepositorySnapshot`.
- Ingestion always produces an **immutable snapshot** keyed by `(repository_id, commit_sha)`; a
  read-only workspace directory; and a manifest (path, size, sha256, language, is_test,
  is_vendored).
- Edits never touch the snapshot workspace — the Implementation agent works on a copy-on-write RW
  workspace (`ADR-0008`).
- Clone hardening: configurable depth, `core.hooksPath=/dev/null`, no submodule recursion, no
  credential prompts (`ADR-0014`).
- URL/path validation + SSRF guard in `repository/url_validator.py` (`ADR-0011`).
- Limits enforced at ingestion; breach -> `snapshot.status = PARTIALLY_SUPPORTED` with
  `limit_reason` (`ADR-0012`).

## Consequences

- Adding a source (GitLab, a tarball) is a new implementation, nothing else.
- Snapshots are reproducible inputs for deterministic replay.
- Extra disk for snapshot + RW copies; managed by artifact GC (`ADR-0009`).

## Alternatives considered

- **Operate directly on a user-provided working directory** — rejected: mutates the user's repo,
  no isolation, no reproducibility (Spec §3.7 requires a recoverable workspace).
- **Shell out to `git` with the raw URL** — rejected: injection / SSRF surface (`ADR-0014`).
- **In-memory-only repo model** — rejected: large repos, and the sandbox needs a real filesystem.
