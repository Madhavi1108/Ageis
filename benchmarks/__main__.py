"""CLI: ``python -m benchmarks <run|report|calibrate|list> ...``

    python -m benchmarks list
    python -m benchmarks run --dataset micro --out .bench/micro
    python -m benchmarks run --dataset micro --check           # CI smoke, exit != 0 on regression
    python -m benchmarks report --in .bench/micro
    python -m benchmarks calibrate --in .bench/micro
    python -m benchmarks publish --out .bench/full     # writes docs/BENCHMARK_RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from benchmarks import dataset as dataset_mod
from benchmarks.calibrate import write_calibration_report
from benchmarks.metrics import compute_all
from benchmarks.report import write_reports
from benchmarks.runner import run_dataset
from benchmarks.schema import BenchmarkResult

# Documented smoke thresholds for --check (curated `micro` dataset, deterministic).
SMOKE_THRESHOLDS = {
    "min_completion_rate": 1.0,   # metric #12
    "min_localization_f1": 0.5,   # metric #1
    "max_scope_violation_rate": 0.0,  # 1 - metric #8
}


def _run(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="aegis-bench-"))
    work = out / "work"
    result = run_dataset(args.dataset, workdir=work)
    paths = write_reports(result, out)
    write_calibration_report(result, out)
    print(f"ran {len(result.runs)} tasks from {args.dataset!r}")
    for k, v in paths.items():
        print(f"  {k}: {v}")

    metrics = {m.number: m for m in compute_all(result)}
    if args.check:
        return _check(result, metrics)
    return 0


def _check(result: BenchmarkResult, metrics) -> int:
    failures: list[str] = []
    errored = [r.task_id for r in result.runs if r.error]
    if errored:
        failures.append(f"tasks errored: {errored}")
    m12 = metrics[12].value
    if m12 is None or m12 < SMOKE_THRESHOLDS["min_completion_rate"]:
        failures.append(f"#12 completion rate {m12} < {SMOKE_THRESHOLDS['min_completion_rate']}")
    m1 = metrics[1].value
    if m1 is None or m1 < SMOKE_THRESHOLDS["min_localization_f1"]:
        failures.append(f"#1 localization F1 {m1} < {SMOKE_THRESHOLDS['min_localization_f1']}")
    m8 = metrics[8].value
    if m8 is None or (1 - m8) > SMOKE_THRESHOLDS["max_scope_violation_rate"]:
        failures.append(f"#8 scope compliance {m8} below ceiling")
    if failures:
        print("BENCHMARK SMOKE FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("benchmark smoke OK")
    return 0


def _report(args: argparse.Namespace) -> int:
    src = Path(args.in_dir) / "results.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    result = BenchmarkResult.model_validate(data["result"])
    paths = write_reports(result, Path(args.in_dir))
    for k, v in paths.items():
        print(f"{k}: {v}")
    return 0


def _calibrate(args: argparse.Namespace) -> int:
    src = Path(args.in_dir) / "results.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    result = BenchmarkResult.model_validate(data["result"])
    path = write_calibration_report(result, Path(args.in_dir))
    print(path.read_text(encoding="utf-8"))
    return 0


def _publish(args: argparse.Namespace) -> int:
    from benchmarks.publish import DEFAULT_DATASETS, write_results_doc

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="aegis-bench-full-"))
    datasets = tuple(args.datasets.split(",")) if args.datasets else DEFAULT_DATASETS
    path = write_results_doc(datasets, workdir=out / "work")
    print(f"wrote {path} from datasets {list(datasets)}")
    return 0


def _list(_args: argparse.Namespace) -> int:
    for name in dataset_mod.list_datasets():
        tasks = dataset_mod.load_dataset(name)
        print(f"{name:24s} {len(tasks):3d} tasks  {dataset_mod.dataset_digest(name)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="benchmarks", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run a dataset through AEGIS")
    p_run.add_argument("--dataset", required=True)
    p_run.add_argument("--out", default=None)
    p_run.add_argument("--check", action="store_true", help="exit != 0 if smoke thresholds regress")
    p_run.set_defaults(fn=_run)

    p_rep = sub.add_parser("report", help="re-render reports from a results.json")
    p_rep.add_argument("--in", dest="in_dir", required=True)
    p_rep.set_defaults(fn=_report)

    p_cal = sub.add_parser("calibrate", help="run the scoring-model calibration check")
    p_cal.add_argument("--in", dest="in_dir", required=True)
    p_cal.set_defaults(fn=_calibrate)

    p_pub = sub.add_parser("publish", help="run every dataset and write docs/BENCHMARK_RESULTS.md")
    p_pub.add_argument("--out", default=None)
    p_pub.add_argument("--datasets", default=None, help="comma-separated (default: micro,seeded)")
    p_pub.set_defaults(fn=_publish)

    sub.add_parser("list", help="list datasets").set_defaults(fn=_list)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
