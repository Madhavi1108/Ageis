"""Materialize the AEGIS acceptance repository, *with its crafted Git history*,
into a directory for manual inspection (docs/ACCEPTANCE_SCENARIOS.md).

    python scripts/build_acceptance_repo.py <dest> [--unfixable]

The final working tree is byte-identical to ``test-repositories/aegis-acceptance``
(or ``test-repositories/aegis-acceptance-unfixable`` with ``--unfixable``). The
E2E suite (``backend/tests/e2e/test_full_pipeline.py``) builds the same history
into a throwaway dir on every run; this script is only a convenience.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tests.e2e._acceptance_repo import build_acceptance_git_repo  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dest", type=Path, help="target directory (created if absent)")
    ap.add_argument(
        "--unfixable",
        action="store_true",
        help="build the unfixable (scenario C) variant instead",
    )
    args = ap.parse_args(argv)

    name = "aegis-acceptance-unfixable" if args.unfixable else "aegis-acceptance"
    source = ROOT / "test-repositories" / name
    dest = build_acceptance_git_repo(args.dest, source=source)
    print(f"built {name} with crafted history -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
