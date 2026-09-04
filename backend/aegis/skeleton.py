#!/usr/bin/env python3
"""AEGIS Walking Skeleton CLI. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 9.

Usage:
    python -m aegis.skeleton run <repo_path> <task_path> [--provider mock|claude]
                                                          [--sandbox docker|fake]
                                                          [--json-out PATH]

`--sandbox docker` (the default) uses the real, hardened DockerSandboxRunner
-- if Docker is unavailable, the run ends in PARTIALLY_SUPPORTED, which is
the honest, designed behaviour (never a host-execution fallback).

`--sandbox fake` uses FakeSandboxRunner, which runs pytest as a local
subprocess. It exists ONLY to demonstrate the pipeline's logic end-to-end in
environments without Docker, and must never be pointed at an untrusted
repository (see aegis/sandbox/runner.py).
"""
from __future__ import annotations

import argparse
import sys

from aegis.ai.provider import MockProvider, get_provider
from aegis.ai.scenarios import register_walking_skeleton_scenarios
from aegis.orchestrator import run_pipeline
from aegis.sandbox.runner import DockerSandboxRunner, FakeSandboxRunner


def _build_sandbox(name: str):
    if name == "docker":
        return DockerSandboxRunner()
    if name == "fake":
        return FakeSandboxRunner()
    raise ValueError(f"unknown sandbox {name!r}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="python -m aegis.skeleton")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run the walking skeleton on one task")
    run_p.add_argument("repo_path")
    run_p.add_argument("task_path")
    run_p.add_argument("--provider", default="mock", choices=["mock", "claude"])
    run_p.add_argument("--sandbox", default="docker", choices=["docker", "fake"])
    run_p.add_argument(
        "--json-out", default=None, help="write the Trust Report JSON here"
    )
    run_p.add_argument(
        "--no-artifact", action="store_true", help="skip the scratch SQLite log"
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        provider = get_provider(args.provider)
        if isinstance(provider, MockProvider):
            register_walking_skeleton_scenarios(provider)
        sandbox = _build_sandbox(args.sandbox)

        if args.sandbox == "fake":
            print(
                "WARNING: --sandbox fake runs tests as a local subprocess, not in Docker. "
                "Only use this against repositories you trust (e.g. AEGIS's own fixtures).",
                file=sys.stderr,
            )

        report = run_pipeline(
            repo_path=args.repo_path,
            task_path=args.task_path,
            provider=provider,
            sandbox=sandbox,
            record_artifact=not args.no_artifact,
        )

        print(f"AEGIS Walking Skeleton -- {report.task_title}")
        print(f"Repository: {report.task_repo}")
        print(f"Outcome:    {report.outcome}")
        print()
        print("Why safe:  ", report.evidence_trace.why_safe)
        print("Why file:  ", ", ".join(report.evidence_trace.why_file) or "(none)")
        print("Why change:", report.evidence_trace.why_change)
        if report.tests:
            print()
            print(
                f"Tests: {report.tests.get('outcome')}  "
                f"passed={report.tests.get('passed')}  failed={report.tests.get('failed')}"
            )
        if report.limitations:
            print()
            print("Limitations:")
            for lim in report.limitations:
                print(f"  - {lim}")
        if report.diff_text.strip():
            print()
            print("--- diff ---")
            print(report.diff_text)

        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
            print(f"\nTrust Report written to {args.json_out}")

        return 0 if report.outcome == "VERIFIED" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
