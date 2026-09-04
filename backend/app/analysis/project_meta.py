"""Project metadata detection: package manager, build backend, declared dependencies.

Snapshot-root only (no monorepo sub-project detection -- REPOSITORY_ANALYSIS.md's own
open question R3 frames this as "heuristic in Phase 4, refine later"). Reads raw file
content from the materialized workspace path, since RepositoryFile rows only carry
hashes/metadata, not content.

See docs/REPOSITORY_ANALYSIS.md Section 3 (first match wins, else UNKNOWN).
"""

from __future__ import annotations

import configparser
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_REQUIREMENT_LINE = re.compile(r"^([A-Za-z0-9_.-]+)")


@dataclass(frozen=True)
class ProjectMetadata:
    package_manager: str | None
    build_backend: str | None
    dependencies: list[str]  # PyPI distribution names (or import names, best-effort)
    console_scripts: list[tuple[str, str]] = field(
        default_factory=list
    )  # (name, "module:func")
    unknowns: list[str] = field(default_factory=list)


def load_pyproject(root: Path) -> dict | None:
    path = root / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return None


def _detect_package_manager(root: Path, pyproject: dict | None) -> str | None:
    if (
        (root / "poetry.lock").exists()
        and pyproject
        and "poetry" in pyproject.get("tool", {})
    ):
        return "poetry"
    if (root / "uv.lock").exists():
        return "uv"
    if (root / "Pipfile").exists():
        return "pipenv"
    if any(root.glob("requirements*.txt")):
        return "pip"
    return None


def _detect_build_backend(pyproject: dict | None) -> str | None:
    if not pyproject:
        return None
    return pyproject.get("build-system", {}).get("build-backend")


def _parse_pep508_name(spec: str) -> str | None:
    match = _REQUIREMENT_LINE.match(spec.strip())
    return match.group(1) if match else None


def _dependencies_from_pyproject(pyproject: dict) -> list[str] | None:
    project_deps = pyproject.get("project", {}).get("dependencies")
    if project_deps:
        names = [_parse_pep508_name(d) for d in project_deps]
        return [n for n in names if n]

    poetry_deps = pyproject.get("tool", {}).get("poetry", {}).get("dependencies")
    if poetry_deps:
        return [name for name in poetry_deps.keys() if name.lower() != "python"]

    return None


def _dependencies_from_requirements(root: Path) -> list[str]:
    names: list[str] = []
    for req_file in sorted(root.glob("requirements*.txt")):
        try:
            lines = req_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(("-r", "-e", "--")):
                continue
            name = _parse_pep508_name(line)
            if name:
                names.append(name)
    return names


def _dependencies_from_setup_cfg(root: Path) -> list[str] | None:
    path = root / "setup.cfg"
    if not path.exists():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return None
    if not parser.has_option("options", "install_requires"):
        return None
    raw = parser.get("options", "install_requires")
    names = [_parse_pep508_name(line) for line in raw.splitlines() if line.strip()]
    return [n for n in names if n]


def _console_scripts(pyproject: dict | None) -> list[tuple[str, str]]:
    if not pyproject:
        return []
    scripts = pyproject.get("project", {}).get("scripts") or pyproject.get(
        "tool", {}
    ).get("poetry", {}).get("scripts")
    if not scripts:
        return []
    return list(scripts.items())


def parse_project_metadata(root: Path) -> ProjectMetadata:
    unknowns: list[str] = []
    pyproject = load_pyproject(root)

    package_manager = _detect_package_manager(root, pyproject)
    if package_manager is None:
        unknowns.append("package_manager")

    build_backend = _detect_build_backend(pyproject)
    if build_backend is None:
        unknowns.append("build_backend")

    dependencies: list[str] | None = None
    if pyproject:
        dependencies = _dependencies_from_pyproject(pyproject)
    if dependencies is None:
        req_deps = _dependencies_from_requirements(root)
        dependencies = req_deps if req_deps else None
    if dependencies is None:
        dependencies = _dependencies_from_setup_cfg(root)
    if dependencies is None:
        dependencies = []
        unknowns.append("dependencies")

    return ProjectMetadata(
        package_manager=package_manager,
        build_backend=build_backend,
        dependencies=dependencies,
        console_scripts=_console_scripts(pyproject),
        unknowns=unknowns,
    )
