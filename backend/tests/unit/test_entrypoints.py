from app.analysis.entrypoints import EntryPoint, detect_entrypoints
from app.analysis.project_meta import ProjectMetadata
from app.analysis.python_ast import parse_and_walk

_EMPTY_META = ProjectMetadata(package_manager=None, build_backend=None, dependencies=[])


def _walk(tmp_path, source: str, relpath: str = "mod.py"):
    path = tmp_path / relpath
    path.write_text(source)
    return parse_and_walk(path, relpath)


def test_main_guard_entrypoint(tmp_path):
    walk = _walk(tmp_path, 'if __name__ == "__main__":\n    pass\n')
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert any(e.type == "main_guard" and e.file == "mod.py" for e in eps)


def test_fastapi_asgi_entrypoint(tmp_path):
    walk = _walk(tmp_path, "from fastapi import FastAPI\napp = FastAPI()\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    asgi = [e for e in eps if e.type == "asgi_app"]
    assert len(asgi) == 1
    assert asgi[0].symbol == "app"
    assert asgi[0].detail == "FastAPI"


def test_flask_asgi_entrypoint(tmp_path):
    walk = _walk(tmp_path, "from flask import Flask\napp = Flask(__name__)\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert any(e.type == "asgi_app" and e.detail == "Flask" for e in eps)


def test_argparse_cli_entrypoint(tmp_path):
    walk = _walk(tmp_path, "import argparse\np = argparse.ArgumentParser()\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert any(e.type == "cli" and e.detail == "argparse.ArgumentParser" for e in eps)


def test_click_cli_entrypoint(tmp_path):
    walk = _walk(tmp_path, "import click\n\n@click.command()\ndef main():\n    pass\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert any(e.type == "cli" and e.symbol == "main" for e in eps)


def test_console_script_from_project_meta(tmp_path):
    meta = ProjectMetadata(
        package_manager=None,
        build_backend=None,
        dependencies=[],
        console_scripts=[("mycli", "mypkg.cli:main")],
    )
    eps = detect_entrypoints([], meta)
    assert eps == [
        EntryPoint(
            type="console_script", file=None, symbol="mycli", detail="mypkg.cli:main"
        )
    ]


def test_no_false_positive_on_unrelated_assignment(tmp_path):
    walk = _walk(tmp_path, "x = some_other_function()\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert eps == []


def test_file_with_parse_error_is_skipped(tmp_path):
    walk = _walk(tmp_path, "def broken(:\n")
    eps = detect_entrypoints([walk], _EMPTY_META)
    assert eps == []
