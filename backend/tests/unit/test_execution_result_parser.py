"""Phase 12 result parser: JUnit-XML -> per-test outcomes."""

from __future__ import annotations

from app.sandbox.result_parser import parse_junit_xml

_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4">
    <testcase classname="test_invoice" name="test_pass" file="test_invoice.py" />
    <testcase classname="test_invoice" name="test_fail" file="test_invoice.py">
      <failure message="assert 1 == 2">AssertionError</failure>
    </testcase>
    <testcase classname="test_invoice" name="test_error" file="test_invoice.py">
      <error message="boom">RuntimeError</error>
    </testcase>
    <testcase classname="test_invoice" name="test_skip" file="test_invoice.py">
      <skipped message="skipped" />
    </testcase>
  </testsuite>
</testsuites>
"""


def test_missing_file_returns_empty(tmp_path):
    assert parse_junit_xml(tmp_path / "nope.xml") == []


def test_unparsable_file_returns_empty(tmp_path):
    path = tmp_path / "bad.xml"
    path.write_text("not xml", encoding="utf-8")
    assert parse_junit_xml(path) == []


def test_parses_pass_fail_error_skip(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text(_JUNIT, encoding="utf-8")
    outcomes = {o.test_id: o.outcome for o in parse_junit_xml(path)}
    assert outcomes["test_invoice.py::test_pass"] == "PASS"
    assert outcomes["test_invoice.py::test_fail"] == "FAIL"
    assert outcomes["test_invoice.py::test_error"] == "ERROR"
    assert outcomes["test_invoice.py::test_skip"] == "SKIPPED"
