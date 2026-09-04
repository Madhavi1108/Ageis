# AEGIS sandbox image -- Phase 1 (Walking Skeleton) version.
#
# Minimal image with pytest baked in so DockerSandboxRunner (backend/aegis/
# sandbox/runner.py) never needs network access at test-run time (the
# sandbox policy sets network_mode="none" -- see backend/aegis/sandbox/
# policy.py and docs/SECURITY_MODEL.md Section 2).
#
# Build once:  docker build -t aegis-sandbox:py311-skeleton -f docker/sandbox.Dockerfile .
#
# Phase 12 (Secure Execution, full system) replaces this with a digest-pinned,
# further-hardened image and a proper dependency-install pre-step for target
# repositories with their own third-party requirements (docs/DECISIONS/
# ADR-0010). This Dockerfile is intentionally minimal for the walking
# skeleton, which only needs to run a repo's own stdlib-only test suite.

FROM python:3.11-slim

RUN pip install --no-cache-dir pytest==8.3.4 \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin aegis

USER 1000:1000
WORKDIR /workspace
