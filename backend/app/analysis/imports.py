"""Turn a file's RawWalk import list into persistable DependencyFact (IMPORT-kind) rows,
classified STDLIB / THIRD_PARTY / LOCAL / UNKNOWN.

See docs/REPOSITORY_ANALYSIS.md Section 2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from app.analysis.python_ast import RawWalk
from app.models.dependency import DependencyClassification, DependencyKind

# PyPI distribution name -> import name, for the small set of common mismatches. Not a
# real distribution-metadata resolver (Phase 4 has no installed environment to
# introspect) -- just enough to avoid an easily-avoidable UNKNOWN on frequent packages.
_DIST_TO_IMPORT_ALIASES = {
    "pyyaml": "yaml",
    "pillow": "pil",
    "beautifulsoup4": "bs4",
    "python-dateutil": "dateutil",
    "protobuf": "google",
    "scikit-learn": "sklearn",
}

_STDLIB_NAMES = set(sys.stdlib_module_names)


@dataclass(frozen=True)
class DependencyFact:
    kind: str
    from_file_id: str | None
    target: str
    classification: str
    version_spec: str | None = None
    extras: list | None = None


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_")


def classify_import(
    module_name: str, local_module_names: set[str], declared_third_party: set[str]
) -> str:
    top_level = module_name.split(".")[0]
    if top_level in local_module_names:
        return DependencyClassification.LOCAL.value
    if top_level in _STDLIB_NAMES:
        return DependencyClassification.STDLIB.value

    normalized = _normalize(top_level)
    normalized_declared = {
        _normalize(_DIST_TO_IMPORT_ALIASES.get(_normalize(d), _normalize(d)))
        for d in declared_third_party
    }
    if normalized in normalized_declared:
        return DependencyClassification.THIRD_PARTY.value
    return DependencyClassification.UNKNOWN.value


def imports_from_walk(
    walk: RawWalk,
    file_id: str,
    local_module_names: set[str],
    declared_third_party: set[str],
) -> list[DependencyFact]:
    facts: list[DependencyFact] = []
    for imp in walk.imports:
        if imp.level > 0:
            # Relative import: local by definition, no classification lookup needed.
            target = "." * imp.level + (imp.module or "")
            classification = DependencyClassification.LOCAL.value
        else:
            target = imp.module or ""
            classification = classify_import(
                target, local_module_names, declared_third_party
            )
        facts.append(
            DependencyFact(
                kind=DependencyKind.IMPORT.value,
                from_file_id=file_id,
                target=target,
                classification=classification,
            )
        )
    return facts
