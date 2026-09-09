"""Phase 27 performance / soak-shape suite (docs/EXECUTION_MODEL.md §6).

Every test under ``tests/perf/`` is auto-marked ``@pytest.mark.perf`` and is
**deselected unless ``--perf`` is passed** -- these are slow leak-shape / budget
checks, not part of the normal fast suite. Run them with::

    pytest --perf tests/perf
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base

_PERF_DIR = Path(__file__).parent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'perf.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--perf",
        action="store_true",
        default=False,
        help="run the Phase 27 perf / soak-shape suite (tests/perf/)",
    )


def pytest_collection_modifyitems(config, items) -> None:
    run_perf = config.getoption("--perf")
    skip_perf = pytest.mark.skip(reason="perf suite: pass --perf to run")
    for item in items:
        try:
            item_path = Path(str(item.path))
        except Exception:  # pragma: no cover -- older pytest
            item_path = Path(str(item.fspath))
        if _PERF_DIR not in item_path.parents:
            continue
        item.add_marker(pytest.mark.perf)
        if not run_perf:
            item.add_marker(skip_perf)
