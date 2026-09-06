# AEGIS sandbox image -- shared by the Phase 1 walking skeleton
# (backend/aegis/sandbox/runner.py) and the Phase 12 full-system sandbox
# (backend/app/sandbox/runner.py).
#
# Minimal image with pytest baked in so neither DockerSandboxRunner ever
# needs network access at test-run time (the sandbox policy sets
# network_mode="none" -- see {backend/aegis,backend/app}/sandbox/policy.py
# and docs/SECURITY_MODEL.md Section 2 / docs/DECISIONS/ADR-0010).
#
# Build for the walking skeleton: docker build -t aegis-sandbox:py311-skeleton -f docker/sandbox.Dockerfile .
# Build for Phase 12:              docker build -t aegis-sandbox:py311 -f docker/sandbox.Dockerfile .
#
# Open item (documented, not a gap): ADR-0010 calls for the image to be
# pinned by digest; no registry/CI publishing pipeline exists yet to produce
# and record one, so app/sandbox/policy.py::DEFAULT_IMAGE is tag-pinned only.
# This Dockerfile is intentionally minimal -- it only needs to run a repo's
# own stdlib-only test suite; the guarded dependency-install pre-step for
# repositories with third-party requirements is a separate open item (see
# docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20's status note).

FROM python:3.11-slim

RUN pip install --no-cache-dir pytest==8.3.4 \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin aegis

USER 1000:1000
WORKDIR /workspace
