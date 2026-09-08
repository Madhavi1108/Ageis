"""Load curated benchmark datasets and materialize a task's repo.

A dataset is a directory under ``benchmarks/datasets/<name>/`` containing one
``*.tasks.yaml`` file and a ``repos/<id>/`` fixture tree per task.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml

from benchmarks import DATASETS_DIR
from benchmarks.schema import BenchmarkTask

_SKIP = {"__pycache__", ".pytest_cache", ".git"}


def dataset_dir(name: str) -> Path:
    d = DATASETS_DIR / name
    if not d.is_dir():
        raise FileNotFoundError(f"no benchmark dataset {name!r} under {DATASETS_DIR}")
    return d


def load_dataset(name: str) -> list[BenchmarkTask]:
    d = dataset_dir(name)
    yamls = sorted(d.glob("*.tasks.yaml"))
    if not yamls:
        raise FileNotFoundError(f"dataset {name!r} has no *.tasks.yaml")
    tasks: list[BenchmarkTask] = []
    seen: set[str] = set()
    for yf in yamls:
        raw = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
        for entry in raw.get("tasks", []):
            task = BenchmarkTask.model_validate({**entry, "dataset": name})
            if task.id in seen:
                raise ValueError(f"duplicate task id {task.id!r} in dataset {name!r}")
            seen.add(task.id)
            _check_repo(d, task)
            tasks.append(task)
    return tasks


def _check_repo(dataset: Path, task: BenchmarkTask) -> None:
    repo = dataset / task.repo_dir
    if not repo.is_dir():
        raise FileNotFoundError(f"task {task.id!r}: repo_dir {task.repo_dir!r} missing")
    for gf in task.gold_files:
        if not (repo / gf).is_file():
            raise FileNotFoundError(f"task {task.id!r}: gold file {gf!r} not in repo")


def repo_path(name: str, task: BenchmarkTask) -> Path:
    return dataset_dir(name) / task.repo_dir


def materialize(name: str, task: BenchmarkTask, dest: Path) -> Path:
    """Copy the fixture repo into ``dest`` (a fresh scratch dir)."""
    src = repo_path(name, task)
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src, dest, ignore=shutil.ignore_patterns(*_SKIP)
    )
    return dest


def dataset_digest(name: str) -> str:
    """A stable content hash of every tracked file in the dataset dir."""
    d = dataset_dir(name)
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file() and not (_SKIP & set(p.relative_to(d).parts)):
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    return "sha256:" + h.hexdigest()[:16]


def list_datasets() -> list[str]:
    return sorted(
        p.name
        for p in DATASETS_DIR.iterdir()
        if p.is_dir() and any(p.glob("*.tasks.yaml"))
    )
