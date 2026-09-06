"""RHP sub-scores, risky_modules ordering, and the ``restrict_to`` filter
(docs/METRICS.md Section 2.3). Builds a tiny snapshot directly in an
in-memory SQLite session.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.graph_edge import GraphEdge
from app.models.graph_node import GraphNode
from app.models.repository_file import RepositoryFile
from app.models.repository_symbol import RepositorySymbol
from app.scoring.model_registry import RHP_WEIGHTS
from app.scoring.repo_health import compute_rhp

SNAP = "snap-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _seed(db, *, with_ci: bool, documented: int) -> None:
    files = [
        RepositoryFile(
            snapshot_id=SNAP, path=p, size_bytes=1, sha256="x", language="python"
        )
        for p in ("a.py", "b.py")
    ]
    if with_ci:
        files.append(
            RepositoryFile(
                snapshot_id=SNAP,
                path=".github/workflows/ci.yml",
                size_bytes=1,
                sha256="x",
                language="yaml",
            )
        )
    db.add_all(files)

    # a.py: two short symbols; b.py: one long symbol
    specs = [
        ("a.py::f", "a.py", 1, 6, "docstring here" if documented >= 1 else None),
        ("a.py::g", "a.py", 8, 12, "doc" if documented >= 2 else None),
        ("b.py::big", "b.py", 1, 140, "doc" if documented >= 3 else None),
    ]
    db.add_all(
        RepositorySymbol(
            snapshot_id=SNAP,
            file_id="f",
            symbol_id=sid,
            kind="FUNCTION",
            qualname=sid.split("::")[1],
            lineno=lo,
            end_lineno=hi,
            docstring=doc,
        )
        for sid, _path, lo, hi, doc in specs
    )

    na = GraphNode(snapshot_id=SNAP, node_type="FILE", ref="a.py", label="a.py")
    nb = GraphNode(snapshot_id=SNAP, node_type="FILE", ref="b.py", label="b.py")
    nc = GraphNode(snapshot_id=SNAP, node_type="FILE", ref="c.py", label="c.py")
    db.add_all([na, nb, nc])
    db.flush()
    # a -> b -> c, so b.py sits "between" and gets non-zero betweenness
    db.add_all(
        [
            GraphEdge(
                snapshot_id=SNAP,
                edge_type="IMPORTS",
                source_node_id=na.id,
                target_node_id=nb.id,
            ),
            GraphEdge(
                snapshot_id=SNAP,
                edge_type="IMPORTS",
                source_node_id=nb.id,
                target_node_id=nc.id,
            ),
        ]
    )
    db.commit()


def test_subscores_present_and_weighted(db):
    _seed(db, with_ci=True, documented=2)
    r = compute_rhp(db, SNAP, repository_id="repo-1")

    assert {s.name for s in r.subscores} == set(RHP_WEIGHTS)
    for s in r.subscores:
        assert s.weight == RHP_WEIGHTS[s.name]
        assert 0.0 <= s.normalized <= 1.0
        assert s.contribution == pytest.approx(s.weight * s.normalized)
    assert r.value == round(100 * sum(s.contribution for s in r.subscores))
    assert 0 <= r.value <= 100

    ci = next(s for s in r.subscores if s.name == "ci_presence")
    assert ci.normalized == 1.0
    doc = next(s for s in r.subscores if s.name == "documentation_ratio")
    assert doc.normalized == pytest.approx(2 / 3)


def test_ci_absence_and_no_docs_lower_the_score(db):
    _seed(db, with_ci=False, documented=0)
    r = compute_rhp(db, SNAP, repository_id="repo-1")
    assert next(s for s in r.subscores if s.name == "ci_presence").normalized == 0.0
    assert (
        next(s for s in r.subscores if s.name == "documentation_ratio").normalized
        == 0.0
    )


def test_unavailable_subscores_use_the_prior_with_reason(db):
    _seed(db, with_ci=True, documented=1)
    r = compute_rhp(db, SNAP, repository_id="repo-1")
    for name in ("test_coverage", "churn_stability"):
        s = next(x for x in r.subscores if x.name == name)
        assert s.normalized == 0.5
        assert s.basis == "INFERENCE"
        assert s.unavailable_reason


def test_risky_modules_ranked_and_restrict_to_filters(db):
    # b.py has a long symbol (high complexity proxy) AND sits between a and c
    _seed(db, with_ci=True, documented=1)
    full = compute_rhp(db, SNAP, repository_id="repo-1")
    assert full.risky_modules, "b.py should surface as a risky module"
    assert full.risky_modules[0]["path"] == "b.py"
    scores = [m["score"] for m in full.risky_modules]
    assert scores == sorted(scores, reverse=True)
    assert all(m["score"] > 0 for m in full.risky_modules)

    restricted = compute_rhp(db, SNAP, repository_id="repo-1", restrict_to={"a.py"})
    assert all(m["path"] == "a.py" for m in restricted.risky_modules)
