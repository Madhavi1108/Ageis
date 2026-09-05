"""Lexical FTS retriever: ranking, evidence shape, size cap, degraded path."""

from __future__ import annotations

from app.analysis.mapping import lexical
from app.analysis.mapping.inputs import FileDoc, SymbolDoc

_INVOICE = FileDoc(
    path="invoice.py",
    text=(
        "def calculate_total(price, discount):\n"
        "    # discount must be capped at the configured maximum\n"
        "    return price * (1 - discount)\n"
    ),
    is_test=False,
)
_UTILS = FileDoc(
    path="utils.py",
    text="def format_currency(value):\n    return f'${value:.2f}'\n",
    is_test=False,
)


def test_ranks_the_file_that_mentions_issue_terms_first():
    res = lexical.retrieve(
        "the discount is not capped at the maximum in calculate_total",
        [_INVOICE, _UTILS],
        [],
    )
    assert res.candidates
    assert res.candidates[0].path == "invoice.py"


def test_every_candidate_carries_file_evidence():
    res = lexical.retrieve("discount capped maximum", [_INVOICE, _UTILS], [])
    for c in res.candidates:
        assert c.evidence
        ev = c.evidence[0]
        assert ev.kind == "file"
        assert ev.ref == c.path
        assert "lexical hit" in ev.detail


def test_symbol_text_is_indexed_alongside_source():
    # issue term only appears in the symbol docstring, not the (stubbed) source
    doc = FileDoc(path="mod.py", text="def f():\n    pass\n", is_test=False)
    sym = SymbolDoc(
        path="mod.py",
        symbol_id="mod.py::f",
        qualname="f",
        kind="FUNCTION",
        signature="f()",
        docstring="Handles the quarterly reconciliation edge case.",
        is_exported=True,
    )
    res = lexical.retrieve("quarterly reconciliation", [doc], [sym])
    assert [c.path for c in res.candidates] == ["mod.py"]


def test_empty_query_returns_no_candidates():
    assert lexical.retrieve("the a an of", [_INVOICE], []).candidates == []


def test_no_match_returns_empty():
    assert (
        lexical.retrieve("kubernetes helm chart", [_INVOICE, _UTILS], []).candidates
        == []
    )
