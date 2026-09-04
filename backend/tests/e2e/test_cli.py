"""The CLI is the walking skeleton's front door -- exercised end-to-end here
so `python -m aegis.skeleton run ...` is proven, not just the library API."""
from pathlib import Path

from aegis.skeleton import main

ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_REPO = ROOT / "test-repositories" / "aegis-acceptance"
ACCEPTANCE_TASK = ACCEPTANCE_REPO / "task.md"


def test_cli_run_verified_via_fake_sandbox(tmp_path, capsys):
    json_out = tmp_path / "report.json"
    exit_code = main(
        [
            "run",
            str(ACCEPTANCE_REPO),
            str(ACCEPTANCE_TASK),
            "--provider", "mock",
            "--sandbox", "fake",
            "--json-out", str(json_out),
            "--no-artifact",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "VERIFIED" in out
    assert json_out.exists()
    assert '"outcome": "VERIFIED"' in json_out.read_text(encoding="utf-8")


def test_cli_run_docker_absent_exits_nonzero(tmp_path, capsys):
    exit_code = main(
        [
            "run",
            str(ACCEPTANCE_REPO),
            str(ACCEPTANCE_TASK),
            "--provider", "mock",
            "--sandbox", "docker",
            "--no-artifact",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "PARTIALLY_SUPPORTED" in out
