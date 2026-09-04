from app.analysis.python_ast import parse_and_walk
from app.analysis.symbols import symbols_from_walk


def _walk(tmp_path, source: str, relpath: str = "mod.py"):
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return parse_and_walk(path, relpath)


def test_symbol_id_scheme(tmp_path):
    walk = _walk(tmp_path, "def foo():\n    pass\n", relpath="pkg/mod.py")
    facts = symbols_from_walk(walk, file_id="file-1")
    foo = next(f for f in facts if f.qualname == "foo")
    assert foo.symbol_id == "pkg/mod.py::foo"


def test_signature_renders_defaults_star_args_and_annotations(tmp_path):
    walk = _walk(
        tmp_path,
        "def f(a, b: int = 2, /, c=3, *args, d: str, e=5, **kwargs) -> bool:\n    pass\n",
    )
    facts = symbols_from_walk(walk, file_id="f1")
    f = next(x for x in facts if x.qualname == "f")
    assert (
        f.signature == "(a, b: int = 2, /, c=3, *args, d: str, e=5, **kwargs) -> bool"
    )


def test_signature_with_no_args(tmp_path):
    walk = _walk(tmp_path, "def f():\n    pass\n")
    facts = symbols_from_walk(walk, file_id="f1")
    f = next(x for x in facts if x.qualname == "f")
    assert f.signature == "()"


def test_docstring_extraction(tmp_path):
    walk = _walk(tmp_path, '"""Module doc."""\n\n\ndef f():\n    """Func doc."""\n')
    facts = symbols_from_walk(walk, file_id="f1")
    module = next(x for x in facts if x.kind == "MODULE")
    func = next(x for x in facts if x.qualname == "f")
    assert module.docstring == "Module doc."
    assert func.docstring == "Func doc."


def test_module_symbol_synthesized(tmp_path):
    walk = _walk(tmp_path, "x = 1\n")
    facts = symbols_from_walk(walk, file_id="f1")
    modules = [f for f in facts if f.kind == "MODULE"]
    assert len(modules) == 1
    assert modules[0].symbol_id == "mod.py::"


def test_is_exported_true_for_top_level_public_function(tmp_path):
    walk = _walk(
        tmp_path, "def public_fn():\n    pass\n\ndef _private_fn():\n    pass\n"
    )
    facts = {f.qualname: f for f in symbols_from_walk(walk, file_id="f1")}
    assert facts["public_fn"].is_exported is True
    assert facts["_private_fn"].is_exported is False


def test_is_exported_respects_dunder_all(tmp_path):
    walk = _walk(
        tmp_path,
        '__all__ = ["only_this"]\n\ndef only_this():\n    pass\n\ndef not_this():\n    pass\n',
    )
    facts = {f.qualname: f for f in symbols_from_walk(walk, file_id="f1")}
    assert facts["only_this"].is_exported is True
    assert facts["not_this"].is_exported is False


def test_is_exported_true_for_route_decorator(tmp_path):
    walk = _walk(
        tmp_path, "class C:\n    @app.get('/x')\n    def handler(self):\n        pass\n"
    )
    facts = {f.qualname: f for f in symbols_from_walk(walk, file_id="f1")}
    assert facts["C.handler"].is_exported is True


def test_is_exported_false_for_nested_function(tmp_path):
    walk = _walk(
        tmp_path, "def outer():\n    def inner():\n        pass\n    return inner\n"
    )
    facts = {f.qualname: f for f in symbols_from_walk(walk, file_id="f1")}
    assert facts["outer.inner"].is_exported is False


def test_method_kind_vs_function_kind(tmp_path):
    walk = _walk(
        tmp_path, "class C:\n    def m(self):\n        pass\n\ndef f():\n    pass\n"
    )
    facts = {f.qualname: f for f in symbols_from_walk(walk, file_id="f1")}
    assert facts["C.m"].kind == "METHOD"
    assert facts["f"].kind == "FUNCTION"
