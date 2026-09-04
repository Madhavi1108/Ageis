from pathlib import Path

from aegis.analysis.mapping import rank_files
from aegis.analysis.python_ast import analyze
from aegis.repository.ingest import ingest_local

ACCEPTANCE_REPO = Path(__file__).resolve().parents[3] / "test-repositories" / "aegis-acceptance"


def test_buggy_file_ranks_above_distractor():
    snapshot = ingest_local(ACCEPTANCE_REPO)
    analysis = analyze(snapshot)
    task_text = (ACCEPTANCE_REPO / "task.md").read_text(encoding="utf-8")

    candidates = rank_files(task_text, snapshot, analysis)

    assert candidates, "expected at least one candidate"
    assert candidates[0].path == "invoice.py"
    assert candidates[0].evidence, "every candidate must carry evidence"
    paths = [c.path for c in candidates]
    if "utils.py" in paths:
        assert paths.index("invoice.py") < paths.index("utils.py")


def test_no_evidence_free_candidates():
    snapshot = ingest_local(ACCEPTANCE_REPO)
    analysis = analyze(snapshot)
    candidates = rank_files("completely unrelated issue text xyz", snapshot, analysis)
    for c in candidates:
        assert len(c.evidence) >= 1


def test_test_files_are_never_candidates():
    snapshot = ingest_local(ACCEPTANCE_REPO)
    analysis = analyze(snapshot)
    task_text = (ACCEPTANCE_REPO / "task.md").read_text(encoding="utf-8")
    candidates = rank_files(task_text, snapshot, analysis)
    assert all(not c.path.startswith("test_") for c in candidates)
