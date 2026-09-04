from app.ingestion.manifest import build_manifest, detect_language, is_vendored


def test_language_by_extension(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("print(1)\n")
    assert detect_language(f) == "python"


def test_language_by_shebang_fallback(tmp_path):
    f = tmp_path / "run"
    f.write_text("#!/usr/bin/env python3\nprint(1)\n")
    assert detect_language(f) == "python"


def test_unknown_extension_is_other(tmp_path):
    f = tmp_path / "data.xyz"
    f.write_bytes(b"\x01\x02\x03")
    assert detect_language(f) == "other"


def test_is_vendored_detects_known_dir_names():
    assert is_vendored("vendor/lib/util.py")
    assert is_vendored("frontend/node_modules/react/index.js")
    assert not is_vendored("app/core/config.py")


def test_build_manifest_is_deterministic(tmp_path):
    (tmp_path / "b.py").write_text("b = 1\n")
    (tmp_path / "a.py").write_text("a = 1\n")
    (tmp_path / "test_a.py").write_text("def test_x(): pass\n")

    manifest_1 = build_manifest(tmp_path)
    manifest_2 = build_manifest(tmp_path)

    assert [f.path for f in manifest_1] == sorted(f.path for f in manifest_1)
    assert [(f.path, f.sha256) for f in manifest_1] == [
        (f.path, f.sha256) for f in manifest_2
    ]


def test_build_manifest_flags_test_files(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_x(): pass\n")
    (tmp_path / "a.py").write_text("a = 1\n")

    manifest = build_manifest(tmp_path)
    by_path = {f.path: f for f in manifest}
    assert by_path["test_a.py"].is_test is True
    assert by_path["a.py"].is_test is False


def test_build_manifest_skips_ignored_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "src.py").write_text("x = 1\n")

    manifest = build_manifest(tmp_path)
    assert [f.path for f in manifest] == ["src.py"]
