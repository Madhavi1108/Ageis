"""Public-API detector: route decorators + Phase 4's is_exported flag."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.impact import _public_api_touched


@dataclass
class FakeSym:
    symbol_id: str
    is_exported: bool = False
    decorators: list = field(default_factory=list)
    qualname: str = ""


def test_route_decorator_wins_reason_route():
    syms = [FakeSym("api.py::create", decorators=["router.post('/things')"])]
    out = _public_api_touched(["api.py::create"], syms)
    assert out == [{"symbol_id": "api.py::create", "reason": "route"}]


def test_exported_symbol_flagged_exported():
    syms = [FakeSym("mod.py::PublicThing", is_exported=True)]
    out = _public_api_touched(["mod.py::PublicThing"], syms)
    assert out == [{"symbol_id": "mod.py::PublicThing", "reason": "exported"}]


def test_internal_helper_not_flagged():
    syms = [FakeSym("mod.py::_helper", is_exported=False)]
    assert _public_api_touched(["mod.py::_helper"], syms) == []


def test_only_changed_symbols_considered():
    syms = [
        FakeSym("a.py::x", is_exported=True),
        FakeSym("b.py::y", is_exported=True),
    ]
    out = _public_api_touched(["a.py::x"], syms)
    assert [o["symbol_id"] for o in out] == ["a.py::x"]


def test_output_is_sorted():
    syms = [
        FakeSym("z.py::z", is_exported=True),
        FakeSym("a.py::a", is_exported=True),
    ]
    out = _public_api_touched(["z.py::z", "a.py::a"], syms)
    assert [o["symbol_id"] for o in out] == ["a.py::a", "z.py::z"]
