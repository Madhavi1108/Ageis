"""Pre-execution static safety scan for AI-generated test code
(docs/SECURITY_MODEL.md Section 2/3). Unsafe generated files are blocked
*before* they are written into the workspace or run.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.testing.safety import scan_code, scan_generated_cases

SAFE = "from mod import f\n\n\ndef test_f():\n    assert f(1) == 2\n"

UNSAFE = {
    "eval": "def test_x():\n    eval('1+1')\n",
    "exec": "def test_x():\n    exec('x=1')\n",
    "dunder-import": "def test_x():\n    __import__('os').system('id')\n",
    "os.system": "import os\n\n\ndef test_x():\n    os.system('id')\n",
    "subprocess-import": "import subprocess\n\n\ndef test_x():\n    subprocess.run(['id'])\n",
    "socket-import": "import socket\n\n\ndef test_x():\n    socket.socket()\n",
    "ctypes": "import ctypes\n\n\ndef test_x():\n    ctypes.CDLL('libc.so.6')\n",
    "secret-literal": 'def test_x():\n    key = "ghp_'
    + "a" * 36
    + '"\n    assert key\n',
    "path-escape": SAFE,  # combined with a bad path below
    "syntax-error": "def test_x(:\n    pass\n",
}


def test_safe_code_has_no_findings():
    assert scan_code("test_ok.py", SAFE) == []


@pytest.mark.parametrize("name", [k for k in UNSAFE if k != "path-escape"])
def test_unsafe_code_is_flagged(name):
    findings = scan_code("test_bad.py", UNSAFE[name])
    assert findings, name


def test_path_escape_is_flagged():
    findings = scan_code("../../evil.py", SAFE)
    assert findings and findings[0].rule == "path-escape"


def test_scan_generated_cases_aggregates():
    cases = [
        SimpleNamespace(path="test_a.py", code=SAFE),
        SimpleNamespace(path="test_b.py", code=UNSAFE["eval"]),
    ]
    findings = scan_generated_cases(cases)
    assert [f.path for f in findings] == ["test_b.py"]


def test_execution_service_blocks_unsafe_cases(
    db_session, security_settings, monkeypatch
):
    """The execute-tests service raises UnsafeGeneratedCodeError rather than
    write + run an unsafe generated file."""
    from app.services import execution
    from app.testing.errors import UnsafeGeneratedCodeError

    bad_case = SimpleNamespace(path="test_evil.py", code=UNSAFE["os.system"])
    with pytest.raises(UnsafeGeneratedCodeError):
        execution._guard_generated_cases([bad_case], security_settings)

    # opt-out flag disables the gate
    relaxed = security_settings.model_copy(
        update={"security_block_unsafe_generated_code": False}
    )
    execution._guard_generated_cases([bad_case], relaxed)  # no raise
