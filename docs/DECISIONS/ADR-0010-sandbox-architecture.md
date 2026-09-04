# ADR-0010: Sandbox architecture

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §18 declares target repositories untrusted, forbids executing their code on the host, and asks
for an isolated execution environment (preferred MVP: Docker) with a full threat model and resource
controls.

## Decision

- **Docker-based sandbox.** Each execution runs in a short-lived container from an image pinned by
  **digest**, with: `--network none` (default), `--read-only` rootfs + `tmpfs /tmp`, only the task
  workspace bind-mounted `:rw`, `--cap-drop ALL`, `--security-opt no-new-privileges`,
  `--pids-limit`, `--cpus`, `--memory`, `--memory-swap` (swap off), `--ulimit nofile/nproc`,
  non-root UID, no Docker socket, seccomp default profile.
- Env is scrubbed to an allowlist before entering the container; no secrets mounted.
- Optional dependency install is a separate network-restricted, host-allowlisted, hash-pinned
  pre-step — never during the test step.
- Wall-clock timeout with SIGKILL; container + volume + ephemeral dir removed in a `finally`.
- If Docker is unavailable -> `PARTIALLY_SUPPORTED{reason}`; **no host fallback**.
- Stronger isolation (gVisor, Firecracker microVMs, nsjail) is a documented **post-MVP** option;
  the `sandbox/` backend abstraction keeps it swappable.

## Consequences

- Portable across CI runners and dev machines; meets the Spec's preferred MVP.
- Docker is not as strong a boundary as a VM — accepted residual risk (`SECURITY_MODEL.md` §10),
  mitigated by cap-drop + no-net + non-root + resource caps + static scan + review + human
  approval on risky patches.
- Rootless Docker availability varies; handled by the `PARTIALLY_SUPPORTED` path and the Phase 2
  spike.

## Alternatives considered

- **Run tests on the host in a venv** — rejected outright by Spec §18 / §55 Rule 9.
- **microVMs (Firecracker) now** — rejected for the MVP: heavier setup, worse portability; kept as
  a post-MVP upgrade.
- **gVisor now** — rejected for the MVP for the same reasons; low-friction to add later behind the
  backend abstraction.
