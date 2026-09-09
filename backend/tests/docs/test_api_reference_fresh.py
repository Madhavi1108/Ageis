"""Phase 28 docs gate: docs/API_REFERENCE.md is in sync with the live OpenAPI.

Runs scripts/gen_api_reference.py's renderer against the app and compares to the
committed file. Also asserts every (path, method) in the schema appears in the
doc. Fix a failure with `python scripts/gen_api_reference.py --write`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "API_REFERENCE.md"
GEN = REPO_ROOT / "scripts" / "gen_api_reference.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("aegis_gen_api_reference", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_api_reference_matches_generator() -> None:
    from app.main import app

    gen = _load_generator()
    expected = gen.render(app)
    actual = DOC.read_text(encoding="utf-8")
    assert actual == expected, (
        "docs/API_REFERENCE.md is stale -- run "
        "`python scripts/gen_api_reference.py --write`"
    )


def test_every_route_is_documented() -> None:
    from app.main import app

    text = DOC.read_text(encoding="utf-8")
    missing = []
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            token = f"{method.upper()} `{path}`"
            if token not in text:
                missing.append(token)
    assert not missing, f"routes absent from API_REFERENCE.md: {missing}"
