from app.analysis.imports import classify_import, imports_from_walk
from app.analysis.python_ast import parse_and_walk


def test_classify_stdlib():
    assert classify_import("os", set(), set()) == "STDLIB"
    assert classify_import("os.path", set(), set()) == "STDLIB"


def test_classify_local():
    assert classify_import("invoice", {"invoice"}, set()) == "LOCAL"


def test_classify_third_party_direct_match():
    assert classify_import("requests", set(), {"requests"}) == "THIRD_PARTY"


def test_classify_third_party_via_alias_table():
    assert classify_import("yaml", set(), {"PyYAML"}) == "THIRD_PARTY"


def test_classify_unknown_when_no_match():
    assert classify_import("some_mystery_package", set(), set()) == "UNKNOWN"


def test_local_wins_over_stdlib_name_collision():
    # a local module shadowing a stdlib name should still classify as LOCAL
    assert classify_import("os", {"os"}, set()) == "LOCAL"


def test_relative_import_is_always_local(tmp_path):
    path = tmp_path / "mod.py"
    path.write_text("from . import sibling\n")
    walk = parse_and_walk(path, "mod.py")
    facts = imports_from_walk(
        walk, "f1", local_module_names=set(), declared_third_party=set()
    )
    assert facts[0].classification == "LOCAL"
    assert facts[0].target == "."


def test_imports_from_walk_produces_one_row_per_statement(tmp_path):
    path = tmp_path / "mod.py"
    path.write_text("import os\nfrom invoice import calculate_total\n")
    walk = parse_and_walk(path, "mod.py")
    facts = imports_from_walk(
        walk, "f1", local_module_names={"invoice"}, declared_third_party=set()
    )
    assert len(facts) == 2
    targets = {f.target: f.classification for f in facts}
    assert targets["os"] == "STDLIB"
    assert targets["invoice"] == "LOCAL"
