#!/usr/bin/env python3
"""AEGIS capability spike -- Stage A / gate G0 (docs/CAPABILITY_SPIKE.md).

Throwaway wiring, NOT the hardened AEGIS pipeline: no Docker sandbox, no
persistence, no orchestrator. It exists only to (a) prove the mapping +
plan + patch + test loop end-to-end before Phases 1-17 are built for real,
and (b) produce the wiring-proof mock numbers in docs/CAPABILITY_SPIKE.md.

Usage:
    python scripts/capability_spike/run.py [--provider mock|claude|openai]
                                            [--tasks tasks.example.yaml]

Exit code 0 on a successful run (regardless of the measured rates -- this
script measures, it does not gate; docs/CAPABILITY_SPIKE.md #6 applies the
gate to the numbers it prints).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapping  # noqa: E402
import metrics  # noqa: E402
import provider as provider_mod  # noqa: E402

HERE = Path(__file__).resolve().parent


def _apply_edit(work_dir: Path, edit: dict[str, str]) -> None:
    target = work_dir / edit["file"]
    text = target.read_text(encoding="utf-8")
    find = edit["find"]
    if find not in text:
        raise RuntimeError(
            f"edit anchor not found in {edit['file']!r} "
            f"(this mirrors the real editor's 'ambiguous/missing anchor -> stop "
            f"loudly' rule, docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 9)"
        )
    text = text.replace(find, edit["replace"], 1)
    prepend = edit.get("prepend")
    if prepend:
        text = prepend + text
    target.write_text(text, encoding="utf-8")


def _run_test_ids(work_dir: Path, test_ids: list[str]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for test_id in test_ids:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_id],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        results[test_id] = proc.returncode == 0
    return results


def run_task(task: dict, prov, provider_name: str) -> metrics.TaskResult:
    task_id = task["id"]
    repo_src = HERE / task["repo_dir"]
    work_dir = Path(tempfile.mkdtemp(prefix=f"aegis-spike-{task_id}-"))
    try:
        shutil.copytree(repo_src, work_dir, dirs_exist_ok=True)

        candidates = mapping.rank_files(task["problem_statement"], work_dir)
        predicted_files = [c.path for c in candidates]
        recall = metrics.recall_at_k(predicted_files, task["gold_files"], k=10)

        if provider_name == "mock":
            edit = prov.get_edit(task)
        else:
            file_contents = {c.path: (work_dir / c.path).read_text(encoding="utf-8")
                              for c in candidates[:3]}
            edit = prov.get_edit(task, file_contents)

        _apply_edit(work_dir, edit)

        fail_to_pass = _run_test_ids(work_dir, task.get("fail_to_pass", []))
        pass_to_pass = _run_test_ids(work_dir, task.get("pass_to_pass", []))
        verified_fix = all(fail_to_pass.values()) and all(pass_to_pass.values())

        return metrics.TaskResult(
            task_id=task_id,
            predicted_files=predicted_files,
            gold_files=task["gold_files"],
            recall_at_10=recall,
            verified_fix=verified_fix,
            fail_to_pass_results=fail_to_pass,
            pass_to_pass_results=pass_to_pass,
        )
    except Exception as exc:  # noqa: BLE001 -- record, never crash the whole run
        return metrics.TaskResult(
            task_id=task_id,
            predicted_files=[],
            gold_files=task["gold_files"],
            recall_at_10=0.0,
            verified_fix=False,
            fail_to_pass_results={},
            pass_to_pass_results={},
            error=str(exc),
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="mock", choices=["mock", "claude", "openai"])
    parser.add_argument("--tasks", default=str(HERE / "tasks.example.yaml"))
    args = parser.parse_args()

    tasks_doc = yaml.safe_load(Path(args.tasks).read_text(encoding="utf-8"))
    tasks = tasks_doc["tasks"]

    prov = provider_mod.get_provider(args.provider)

    results = [run_task(t, prov, args.provider) for t in tasks]
    agg = metrics.aggregate(results)

    print(f"AEGIS capability spike -- provider={args.provider} tasks={args.tasks}")
    print("-" * 72)
    for r in results:
        status = "ERROR" if r.error else ("FIXED" if r.verified_fix else "NOT-FIXED")
        print(f"  {r.task_id:24s} recall@10={r.recall_at_10:.2f}  {status}"
              + (f"  ({r.error})" if r.error else ""))
    print("-" * 72)
    print(f"mean_recall_at_10   = {agg['mean_recall_at_10']:.4f}")
    print(f"verified_fix_rate   = {agg['verified_fix_rate']:.4f}")
    print(f"n_tasks             = {agg['n_tasks']}")
    if args.provider == "mock":
        print()
        print("NOTE: this is a MOCK run (docs/CAPABILITY_SPIKE.md #5.1) -- it proves the")
        print("harness wiring and metric computation, not real capability. Gate G0")
        print("(docs/CAPABILITY_SPIKE.md #6) requires the LIVE run against the ~30-task")
        print("benchmark subset, which is PENDING.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
