"""Risk-signal bundle: available signals carry values; not-yet-available ones
are null + an unavailable_reason (never fabricated)."""

from __future__ import annotations

from app.analysis.impact import _risk_signal_bundle

_AVAILABLE_NOW = {
    "files_changed",
    "dependency_impact",
    "public_api_touched",
    "architectural_centrality",
    "security_sensitivity",
}
_NOT_YET = {
    "lines_changed",
    "complexity_delta",
    "inverse_coverage",
    "historical_churn",
    "prior_failures",
}


def _bundle(**over):
    base = dict(
        n_files_changed=3,
        n_impacted=5,
        public_api=True,
        max_centrality=0.42,
        security_sensitive=False,
    )
    base.update(over)
    return _risk_signal_bundle(**base)


def test_all_crs_signals_present():
    b = _bundle()
    assert set(b) == _AVAILABLE_NOW | _NOT_YET


def test_available_signals_have_values_and_basis():
    b = _bundle()
    for name in _AVAILABLE_NOW:
        assert b[name]["value"] is not None
        assert b[name]["normalized"] is not None
        assert b[name]["basis"] in ("FACT", "INFERENCE")
        assert b[name]["unavailable_reason"] is None


def test_not_yet_signals_are_null_with_reason():
    b = _bundle()
    for name in _NOT_YET:
        assert b[name]["value"] is None
        assert b[name]["normalized"] is None
        assert b[name]["unavailable_reason"]


def test_normalization_clamped():
    b = _bundle(n_files_changed=999, n_impacted=999)
    assert b["files_changed"]["normalized"] == 1.0
    assert b["dependency_impact"]["normalized"] == 1.0


def test_public_api_and_security_are_binary():
    on = _bundle(public_api=True, security_sensitive=True)
    off = _bundle(public_api=False, security_sensitive=False)
    assert on["public_api_touched"]["value"] == 1.0
    assert off["public_api_touched"]["value"] == 0.0
    assert on["security_sensitivity"]["value"] == 1.0
    assert off["security_sensitivity"]["value"] == 0.0
