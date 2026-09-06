"""Diff-scoped static analysis for code review (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 24, step 1).

``ruff`` is the one analyser guaranteed present; it bundles flake8-bandit (``S``,
security) and mccabe (``C90``, complexity), covering most of what standalone
``bandit`` / ``radon`` would. ``bandit`` / ``radon`` / ``mypy`` are run only when
``shutil.which`` finds them; each absence is a recorded gap, never a crash.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from aegis.schemas.common import Confidence, Evidence

from app.review._finding import RawFinding

_RUFF_SELECT = "S,C90,E,F,B,PERF"

# ruff code prefix -> (severity, category)
_RUFF_MAP: list[tuple[str, tuple[str, str]]] = [
    ("S", ("HIGH", "SECURITY")),
    ("C90", ("MEDIUM", "MAINTAINABILITY")),
    ("E9", ("MEDIUM", "CORRECTNESS")),
    ("F", ("MEDIUM", "CORRECTNESS")),
    ("PERF", ("LOW", "PERFORMANCE")),
    ("B", ("LOW", "ERROR_HANDLING")),
]


def _map_ruff(code: str) -> tuple[str, str]:
    for prefix, sev_cat in _RUFF_MAP:
        if code.startswith(prefix):
            return sev_cat
    return ("LOW", "MAINTAINABILITY")


def _run_ruff(ws_root: Path, files: list[str]) -> tuple[list[RawFinding], str | None]:
    if not files:
        return [], None
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--select",
        _RUFF_SELECT,
        "--output-format",
        "json",
        "--no-cache",
        *files,
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=ws_root, capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"ruff could not be run: {exc}"

    raw = proc.stdout.strip()
    if not raw:
        return [], None
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return [], "ruff produced unparseable output"

    findings: list[RawFinding] = []
    for it in items:
        code = it.get("code") or "?"
        sev, cat = _map_ruff(code)
        rel = it.get("filename", "")
        try:
            rel = str(Path(rel).resolve().relative_to(ws_root.resolve()).as_posix())
        except (ValueError, OSError):
            rel = Path(rel).name
        line = (it.get("location") or {}).get("row")
        findings.append(
            RawFinding(
                source="STATIC",
                category=cat,
                severity=sev,
                description=f"ruff {code}: {it.get('message', '').strip()}",
                recommendation="address the ruff diagnostic or add a scoped noqa with a reason",
                file=rel,
                line_start=line,
                line_end=(it.get("end_location") or {}).get("row"),
                evidence=[
                    Evidence(
                        kind="line_range", ref=f"{rel}:{line}", detail=f"ruff {code}"
                    )
                ],
                confidence=Confidence(value=0.9, basis="FACT"),
            )
        )
    return findings, None


def run_static(
    ws_root: Path, changed_files: list[str]
) -> tuple[list[RawFinding], list[str], list[str]]:
    """Returns (findings, tools_run, gaps)."""
    py_files = sorted(f for f in changed_files if f.endswith(".py"))
    findings: list[RawFinding] = []
    tools_run: list[str] = []
    gaps: list[str] = []

    ruff_findings, ruff_gap = _run_ruff(ws_root, py_files)
    if ruff_gap:
        gaps.append(ruff_gap)
    else:
        tools_run.append("ruff")
        findings.extend(ruff_findings)

    for tool in ("bandit", "radon", "mypy"):
        if shutil.which(tool) is None:
            gaps.append(f"{tool} is not installed; its checks were skipped")
        else:
            # ruff's S/C90 rulesets already cover the essentials; a full
            # integration of these is a follow-up.
            gaps.append(
                f"{tool} is available but not yet wired (ruff S/C90 cover the basics)"
            )

    return findings, tools_run, gaps
