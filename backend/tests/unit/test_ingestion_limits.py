from app.ingestion.limits import LimitBreach, RepoLimits, check_and_partition
from app.ingestion.manifest import ManifestFile


def _file(path: str, size: int) -> ManifestFile:
    return ManifestFile(
        path=path,
        size_bytes=size,
        sha256="x" * 64,
        language="python",
        is_test=False,
        is_vendored=False,
    )


def test_no_breach_returns_none():
    files = [_file("a.py", 100), _file("b.py", 200)]
    limits = RepoLimits(
        max_total_bytes=10_000, max_files=10, max_file_bytes=1_000, max_history_depth=10
    )
    partitioned, breach = check_and_partition(files, limits)
    assert breach is None
    assert partitioned == files


def test_oversize_file_marked_skipped_with_reason():
    files = [_file("a.py", 100), _file("big.py", 5_000)]
    limits = RepoLimits(
        max_total_bytes=10_000, max_files=10, max_file_bytes=1_000, max_history_depth=10
    )
    partitioned, breach = check_and_partition(files, limits)

    assert isinstance(breach, LimitBreach)
    assert "max_file_bytes" in breach.reason
    big = next(f for f in partitioned if f.path == "big.py")
    assert big.parse_status == "SKIPPED"
    assert big.sha256 == ""
    assert big.parse_error is not None


def test_file_count_breach_truncates_deterministically():
    files = [_file(f"f{i}.py", 10) for i in range(5)]
    limits = RepoLimits(
        max_total_bytes=10_000, max_files=3, max_file_bytes=1_000, max_history_depth=10
    )
    partitioned, breach = check_and_partition(files, limits)

    assert breach is not None
    assert "max_files" in breach.reason
    assert [f.path for f in partitioned] == ["f0.py", "f1.py", "f2.py"]


def test_total_bytes_breach_truncates_deterministically():
    files = [_file("a.py", 400), _file("b.py", 400), _file("c.py", 400)]
    limits = RepoLimits(
        max_total_bytes=700, max_files=10, max_file_bytes=1_000, max_history_depth=10
    )
    partitioned, breach = check_and_partition(files, limits)

    assert breach is not None
    assert "max_total_bytes" in breach.reason
    assert [f.path for f in partitioned] == ["a.py"]
