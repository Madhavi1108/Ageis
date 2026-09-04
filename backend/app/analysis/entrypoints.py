"""Entry-point detection: `__main__` guards, console_scripts, ASGI/WSGI app objects,
CLI frameworks. Literal-pattern-only (no deep ASGI protocol inspection, no
Typer/Fire/docopt) -- see docs/REPOSITORY_ANALYSIS.md Section 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.project_meta import ProjectMetadata
from app.analysis.python_ast import RawWalk

_ASGI_WSGI_FACTORIES = {"FastAPI", "Flask", "Starlette"}


@dataclass(frozen=True)
class EntryPoint:
    type: str  # "main_guard" | "console_script" | "asgi_app" | "cli"
    file: str | None
    symbol: str | None = None
    detail: str | None = None


def detect_entrypoints(
    walks: list[RawWalk], project_meta: ProjectMetadata
) -> list[EntryPoint]:
    entry_points: list[EntryPoint] = []

    for walk in walks:
        if walk.parse_error is not None:
            continue

        if walk.has_main_guard:
            entry_points.append(EntryPoint(type="main_guard", file=walk.relpath))

        for assigned_name, call_target in walk.module_level_calls:
            factory = call_target.rsplit(".", 1)[-1]
            if factory in _ASGI_WSGI_FACTORIES:
                entry_points.append(
                    EntryPoint(
                        type="asgi_app",
                        file=walk.relpath,
                        symbol=assigned_name,
                        detail=factory,
                    )
                )

        if walk.has_argparse_call:
            entry_points.append(
                EntryPoint(
                    type="cli", file=walk.relpath, detail="argparse.ArgumentParser"
                )
            )
        for qualname in walk.click_decorated_qualnames:
            entry_points.append(
                EntryPoint(
                    type="cli", file=walk.relpath, symbol=qualname, detail="click"
                )
            )

    for script_name, script_target in project_meta.console_scripts:
        entry_points.append(
            EntryPoint(
                type="console_script",
                file=None,
                symbol=script_name,
                detail=script_target,
            )
        )

    return entry_points
