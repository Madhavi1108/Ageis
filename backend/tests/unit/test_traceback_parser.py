"""Traceback parser: pytest console + unittest shapes, chained, malformed."""

from __future__ import annotations

from app.debugging.traceback_parser import parse

_PYTEST_ASSERT = """\
============================= test session starts ==============================
collected 2 items

test_invoice.py .F                                                        [100%]

=================================== FAILURES ===================================
______________________ test_discount_capped_at_50_percent ______________________

    def test_discount_capped_at_50_percent():
        # A requested 90% discount must be capped at 50%.
>       assert calculate_total(100.0, 0.9) == 50.0
E       assert 10.000000000000009 == 50.0
E        +  where 10.000000000000009 = calculate_total(100.0, 0.9)

test_invoice.py:9: AssertionError
=========================== short test summary info ============================
FAILED test_invoice.py::test_discount_capped_at_50_percent - assert 10.0 == 50.0
========================= 1 failed, 1 passed in 0.04s =========================
"""

_PYTEST_EXCEPTION = """\
=================================== FAILURES ===================================
_________________________________ test_thing __________________________________

    def test_thing():
>       do_work()

test_x.py:5:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def do_work():
>       raise ValueError("boom")
E       ValueError: boom

app/work.py:12: ValueError
=========================== short test summary info ============================
FAILED test_x.py::test_thing - ValueError: boom
"""

_CHAINED = """\
=================================== FAILURES ===================================
_________________________________ test_chain __________________________________

    def test_chain():
>       load()

test_c.py:4:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

        try:
>           raw()
E           KeyError: 'missing'

app/c.py:8: KeyError

During handling of the above exception, another exception occurred:

        except KeyError:
>           raise RuntimeError("wrapped")
E           RuntimeError: wrapped

app/c.py:10: RuntimeError
=========================== short test summary info ============================
FAILED test_c.py::test_chain - RuntimeError: wrapped
"""

_COLLECTION = """\
==================================== ERRORS ====================================
_______________________ ERROR collecting test_bad.py ________________________
test_bad.py:1: in <module>
    import nonexistent
E   ModuleNotFoundError: No module named 'nonexistent'
=========================== short test summary info ============================
ERROR test_bad.py - ModuleNotFoundError: No module named 'nonexistent'
"""

_UNITTEST = """\
Traceback (most recent call last):
  File "/workspace/tests/test_u.py", line 7, in test_it
    self.assertEqual(add(2, 2), 5)
  File "/workspace/app/calc.py", line 3, in add
    return a + b + 1
AssertionError: 5 != 4
"""


def test_pytest_assertion_block():
    [f] = parse(_PYTEST_ASSERT)
    assert f.test_name == "test_invoice.py::test_discount_capped_at_50_percent"
    assert f.exception_type == "AssertionError"
    assert f.frames and f.frames[-1].file == "test_invoice.py"
    assert f.frames[-1].lineno == 9
    assert "calculate_total" in f.assertion_calls
    assert f.chained is False


def test_pytest_exception_block_has_deep_frame():
    [f] = parse(_PYTEST_EXCEPTION)
    assert f.test_name == "test_x.py::test_thing"
    assert f.exception_type == "ValueError"
    assert f.message == "boom"
    files = [fr.file for fr in f.frames]
    assert "app/work.py" in files
    assert f.frames[-1].lineno == 12


def test_chained_exception_keeps_outermost_primary():
    [f] = parse(_CHAINED)
    assert f.chained is True
    assert f.exception_type == "RuntimeError"
    assert f.message == "wrapped"


def test_collection_error():
    [f] = parse(_COLLECTION)
    assert "test_bad.py" in f.test_name
    assert f.exception_type == "ModuleNotFoundError"


def test_unittest_traceback():
    [f] = parse(_UNITTEST)
    assert f.exception_type == "AssertionError"
    assert [fr.func for fr in f.frames] == ["test_it", "add"]
    assert f.frames[-1].file.endswith("app/calc.py")


def test_two_failing_tests_in_one_run():
    combined = (
        _PYTEST_ASSERT.replace("1 failed, 1 passed", "x") + "\n" + _PYTEST_EXCEPTION
    )
    names = {f.test_name for f in parse(combined)}
    assert any("test_discount_capped_at_50_percent" in n for n in names)
    assert any("test_thing" in n for n in names)


def test_malformed_output_yields_one_raw_record():
    [f] = parse("something went very wrong\nno recognisable structure here\n")
    assert f.test_name == "<unknown>"
    assert f.frames == []
    assert "recognisable structure" in f.raw


def test_empty_input():
    [f] = parse("")
    assert f.test_name == "<unknown>"
    assert f.frames == []
