from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.data_utils import dump_json, fit_scene_scalers, load_workloads, sha256_file, workload_manifest
from src.irpp_td import IRPPParameters, IRPPTD
from src.legacy_adapters import LegacySuite
from src.metrics import make_record, phase_summary, summarize_with_bootstrap
from src.tuning import tune_irpp


RESULTS = ROOT / "results"
METADATA = ROOT / "metadata"


def load_config() -> dict:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["legacy_algorithm_root"] = str((ROOT / config["legacy_algorithm_root"]).resolve())
    config["data_root"] = str((ROOT / config["data_root"]).resolve())
    return config


def environment_manifest() -> dict:
    return {
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
    }


def load_frozen(path: Path) -> IRPPParameters:
    return IRPPParameters.from_mapping(json.loads(path.read_text(encoding="utf-8"))["selected_parameters"])


def run_tuning(config: dict, workloads, scalers) -> IRPPParameters:
    defaults = IRPPParameters.from_mapping(config["irpp_defaults"])
    frozen, trials, diagnostics = tune_irpp(
        workloads=workloads,
        scalers=scalers,
        calibration_tasks=int(config["calibration_tasks"]),
        seed=int(config["random_seeds"][0]),
        defaults=defaults,
        grid=config["tuning_grid"],
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    trials.to_csv(RESULTS / "tuning_trials.csv", index=False)
    dump_json(RESULTS / "frozen_parameters.json", diagnostics)
    print(
        "Frozen IRPP-TD parameters:",
        f"theta={frozen.theta:.6g}, mu1={frozen.mu1:.6e}, mu2={frozen.mu2:.6e}",
    )
    return frozen


def run_experiments(config: dict, workloads, scalers, frozen: IRPPParameters) -> pd.DataFrame:
    records = []
    suite = LegacySuite(
        Path(config["legacy_algorithm_root"]),
        epsilon=frozen.epsilon,
        max_iterations=frozen.max_iterations,
    )
    dump_json(METADATA / "legacy_source_manifest.json", suite.source_manifest())

    for method in config["baselines"]:
        for workload in workloads.values():
            print(f"Baseline {method:9s} | {workload.key}", flush=True)
            results = suite.run_dataset(method, workload, scalers[workload.scene])
            for task in workload.tasks:
                result = results[task.task_id]
                records.append(
                    make_record(
                        method=method,
                        scene=workload.scene,
                        target_workers=workload.target_workers,
                        seed=-1,
                        task_id=task.task_id,
                        participant_count=len(task.submissions),
                        prediction=result.prediction,
                        truth=task.truth,
                        scale=scalers[workload.scene].scale,
                        runtime_s=result.runtime_s,
                        iterations=result.iterations,
                        retained_count=result.retained_count,
                    )
                )

    for seed_index, seed in enumerate(config["random_seeds"], start=1):
        for workload in workloads.values():
            print(
                f"IRPP-TD seed {seed_index:02d}/{len(config['random_seeds'])} | {workload.key}",
                flush=True,
            )
            model = IRPPTD(frozen, scalers[workload.scene], int(seed))
            for task in workload.tasks:
                start = time.perf_counter()
                result = model.process_task(task)
                runtime = time.perf_counter() - start
                extras = {
                    "high_count": result.high_count,
                    "uncertain_count": result.uncertain_count,
                    "low_count": result.low_count,
                    "mature_anchor_count": result.mature_anchor_count,
                    "active_anchor_count": result.active_anchor_count,
                    "seed_count": result.seed_count,
                    "angular_available": result.angular_available,
                    "mean_rabod_score": result.mean_rabod_score,
                }
                records.append(
                    make_record(
                        method="IRPP-TD",
                        scene=workload.scene,
                        target_workers=workload.target_workers,
                        seed=int(seed),
                        task_id=task.task_id,
                        participant_count=result.participant_count,
                        prediction=result.truth,
                        truth=task.truth,
                        scale=scalers[workload.scene].scale,
                        runtime_s=runtime,
                        iterations=result.iterations,
                        retained_count=result.retained_count,
                        extras=extras,
                    )
                )
    frame = pd.DataFrame(records)
    RESULTS.mkdir(parents=True, exist_ok=True)
    frame.to_csv(RESULTS / "rq1_task_level_results.csv", index=False)
    return frame


def summarize(config: dict, records: pd.DataFrame) -> None:
    test_start, test_end = config["test_tasks"]
    summary = summarize_with_bootstrap(
        records,
        test_start=int(test_start),
        test_end=int(test_end),
        repetitions=int(config["bootstrap_repetitions"]),
        seed=int(config["random_seeds"][0]),
    )
    summary.to_csv(RESULTS / "rq1_summary_95ci.csv", index=False)
    phase_summary(records).to_csv(RESULTS / "rq1_phase_summary.csv", index=False)

    n27 = summary.loc[summary["target_workers"] == 27]
    strongest = (
        n27.loc[n27["method"] != "IRPP-TD"]
        .sort_values(["scene", "nrmse"])
        .groupby("scene", as_index=False)
        .first()[["scene", "method", "nrmse"]]
    )
    strongest.to_csv(RESULTS / "strongest_baseline_by_scene.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete IRPP-TD RQ1 experiment")
    parser.add_argument(
        "--stage",
        choices=["tune", "run", "summarize", "all"],
        default="all",
        help="Execution stage; all performs tune, run, and summarize.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite reusable result CSV files")
    args = parser.parse_args()

    config = load_config()
    workloads = load_workloads(config)
    scalers = fit_scene_scalers(workloads, int(config["calibration_tasks"]))
    METADATA.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    dump_json(METADATA / "environment.json", environment_manifest())
    dump_json(METADATA / "workload_manifest.json", workload_manifest(workloads, scalers))
    source_files = sorted(ROOT.glob("*.py")) + sorted((ROOT / "src").glob("*.py"))
    dump_json(
        METADATA / "experiment_source_manifest.json",
        {str(path.relative_to(ROOT)): sha256_file(path) for path in source_files},
    )

    frozen_path = RESULTS / "frozen_parameters.json"
    if args.stage in {"tune", "all"}:
        frozen = run_tuning(config, workloads, scalers)
    elif frozen_path.exists():
        frozen = load_frozen(frozen_path)
    else:
        raise FileNotFoundError("Run --stage tune before run/summarize")

    raw_path = RESULTS / "rq1_task_level_results.csv"
    if args.stage in {"run", "all"}:
        if raw_path.exists() and not args.force:
            print(f"Reusing {raw_path}; pass --force to rerun algorithms")
            records = pd.read_csv(raw_path)
        else:
            records = run_experiments(config, workloads, scalers, frozen)
    elif raw_path.exists():
        records = pd.read_csv(raw_path)
    else:
        records = None

    if args.stage in {"summarize", "all"}:
        if records is None:
            raise FileNotFoundError("No task-level results available for summarization")
        summarize(config, records)
        print("RQ1 statistical summaries written to results/", flush=True)


if __name__ == "__main__":
    main()
