from app.analysis.python_ast import parse_and_walk


def _walk(tmp_path, source: str, relpath: str = "mod.py"):
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return parse_and_walk(path, relpath)


def test_syntax_error_is_captured_not_raised(tmp_path):
    walk = _walk(tmp_path, "def broken(:\n    pass\n")
    assert walk.parse_error is not None
    assert walk.defs == []


def test_nested_classes_and_methods_get_dotted_qualnames(tmp_path):
    walk = _walk(
        tmp_path,
        """
class Outer:
    class Inner:
        def method(self):
            pass
""",
    )
    kinds = {d.qualname: d.kind for d in walk.defs}
    assert kinds["Outer"] == "CLASS"
    assert kinds["Outer.Inner"] == "CLASS"
    assert kinds["Outer.Inner.method"] == "METHOD"


def test_async_def_captured_as_function_or_method(tmp_path):
    walk = _walk(
        tmp_path,
        """
async def fetch():
    pass

class Client:
    async def get(self):
        pass
""",
    )
    kinds = {d.qualname: d.kind for d in walk.defs}
    assert kinds["fetch"] == "FUNCTION"
    assert kinds["Client.get"] == "METHOD"


def test_decorators_are_rendered(tmp_path):
    walk = _walk(
        tmp_path,
        """
@staticmethod
@app.route("/x")
def handler():
    pass
""",
    )
    handler = next(d for d in walk.defs if d.qualname == "handler")
    assert handler.decorators == ["staticmethod", "app.route('/x')"]


def test_comprehensions_do_not_pollute_scope(tmp_path):
    walk = _walk(
        tmp_path,
        """
def outer():
    return [x for x in range(10)]
""",
    )
    qualnames = [d.qualname for d in walk.defs if d.kind != "MODULE"]
    assert qualnames == ["outer"]


def test_conditional_and_relative_imports(tmp_path):
    walk = _walk(
        tmp_path,
        """
try:
    import simplejson as json
except ImportError:
    import json

from . import sibling
from ..pkg import other
""",
    )
    modules = [(i.module, i.asname, i.level) for i in walk.imports]
    assert ("simplejson", "json", 0) in modules
    assert ("json", None, 0) in modules
    assert (None, None, 1) in modules
    assert ("pkg", None, 2) in modules


def test_dunder_all_literal_list(tmp_path):
    walk = _walk(tmp_path, '__all__ = ["a", "b"]\n')
    assert walk.dunder_all == ["a", "b"]


def test_dunder_all_non_literal_is_none(tmp_path):
    walk = _walk(tmp_path, "__all__ = _compute_exports()\n")
    assert walk.dunder_all is None


def test_main_guard_detected(tmp_path):
    walk = _walk(tmp_path, 'if __name__ == "__main__":\n    pass\n')
    assert walk.has_main_guard is True


def test_no_main_guard(tmp_path):
    walk = _walk(tmp_path, "x = 1\n")
    assert walk.has_main_guard is False


def test_unittest_usage_detected(tmp_path):
    walk = _walk(
        tmp_path,
        """
import unittest

class MyTest(unittest.TestCase):
    def test_x(self):
        pass
""",
    )
    assert walk.uses_unittest_import is True
    assert walk.testcase_class_qualnames == ["MyTest"]


def test_module_level_call_for_asgi_detection(tmp_path):
    walk = _walk(tmp_path, "from fastapi import FastAPI\napp = FastAPI()\n")
    assert ("app", "FastAPI") in walk.module_level_calls


def test_argparse_call_detected(tmp_path):
    walk = _walk(tmp_path, "import argparse\np = argparse.ArgumentParser()\n")
    assert walk.has_argparse_call is True


def test_click_decorator_detected(tmp_path):
    walk = _walk(
        tmp_path,
        """
import click

@click.command()
def main():
    pass
""",
    )
    assert walk.click_decorated_qualnames == ["main"]
