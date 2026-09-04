from app.analysis.project_meta import load_pyproject
from app.analysis.python_ast import parse_and_walk
from app.analysis.testdetect import detect_test_setup


def _walk(root, source: str, relpath: str):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return parse_and_walk(path, relpath)


def test_pytest_via_ini(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    setup = detect_test_setup(tmp_path, [], None)
    assert setup.framework == "pytest"
    assert setup.command == "pytest"


def test_pytest_via_pyproject_section(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
    pyproject = load_pyproject(tmp_path)
    setup = detect_test_setup(tmp_path, [], pyproject)
    assert setup.framework == "pytest"
    assert setup.command == "pytest"


def test_pytest_via_bare_conftest(tmp_path):
    walk = _walk(tmp_path, "def pytest_configure(): pass\n", "conftest.py")
    setup = detect_test_setup(tmp_path, [walk], None)
    assert setup.framework == "pytest"


def test_unittest_via_testcase_subclass(tmp_path):
    walk = _walk(
        tmp_path,
        "import unittest\n\nclass MyTest(unittest.TestCase):\n    def test_x(self): pass\n",
        "test_x.py",
    )
    setup = detect_test_setup(tmp_path, [walk], None)
    assert setup.framework == "unittest"
    assert setup.command == "python -m unittest"


def test_tox_ini_used_for_command_when_present(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "tox.ini").write_text("[tox]\n")
    setup = detect_test_setup(tmp_path, [], None)
    # pytest.ini alone already yields command="pytest" (explicit config wins over tox)
    assert setup.command == "pytest"


def test_tox_only_no_pytest_config(tmp_path):
    (tmp_path / "tox.ini").write_text("[tox]\n")
    setup = detect_test_setup(tmp_path, [], None)
    assert setup.command == "tox"


def test_no_signal_returns_unknown(tmp_path):
    setup = detect_test_setup(tmp_path, [], None)
    assert setup.framework is None
    assert setup.command is None
