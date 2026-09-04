from app.analysis.project_meta import parse_project_metadata


def test_poetry_layout(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "x"

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.0"

[build-system]
build-backend = "poetry.core.masonry.api"
"""
    )
    (tmp_path / "poetry.lock").write_text("")

    meta = parse_project_metadata(tmp_path)
    assert meta.package_manager == "poetry"
    assert meta.build_backend == "poetry.core.masonry.api"
    assert meta.dependencies == ["requests"]
    assert not meta.unknowns


def test_pep621_layout(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
dependencies = ["requests>=2.0", "click"]

[build-system]
build-backend = "setuptools.build_meta"
"""
    )
    (tmp_path / "requirements.txt").write_text("requests\n")

    meta = parse_project_metadata(tmp_path)
    assert meta.package_manager == "pip"
    assert meta.build_backend == "setuptools.build_meta"
    assert set(meta.dependencies) == {"requests", "click"}


def test_requirements_only_layout(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "# comment\nrequests==2.31.0\n-e .\nclick>=8\n\n"
    )

    meta = parse_project_metadata(tmp_path)
    assert meta.package_manager == "pip"
    assert meta.build_backend is None
    assert "build_backend" in meta.unknowns
    assert set(meta.dependencies) == {"requests", "click"}


def test_setup_cfg_only_layout(tmp_path):
    (tmp_path / "setup.cfg").write_text(
        """
[options]
install_requires =
    requests
    click>=8
"""
    )

    meta = parse_project_metadata(tmp_path)
    assert meta.package_manager is None
    assert "package_manager" in meta.unknowns
    assert set(meta.dependencies) == {"requests", "click"}


def test_no_project_files_everything_unknown(tmp_path):
    meta = parse_project_metadata(tmp_path)
    assert meta.package_manager is None
    assert meta.build_backend is None
    assert meta.dependencies == []
    assert set(meta.unknowns) == {"package_manager", "build_backend", "dependencies"}


def test_console_scripts_from_pep621(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"

[project.scripts]
mycli = "mypkg.cli:main"
"""
    )
    meta = parse_project_metadata(tmp_path)
    assert meta.console_scripts == [("mycli", "mypkg.cli:main")]
