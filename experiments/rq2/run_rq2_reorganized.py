from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.core_base import Parameters
from src.data import load_frozen_context, load_workloads, low_ids_for_task, make_replay
from src.model import PREDICTED_HIGH, PREDICTED_LOW, ReorganizedIRPPTD


RESULTS = ROOT / "results"
METADATA = ROOT / "metadata"


@dataclass(frozen=True)
class Job:
    experiment: str
    condition: str
    strategy: str
    profile: str
    malicious_ratio: float
    switch_fraction: float = 0.0
    forced_low: tuple[int, ...] = ()


def load_config() -> dict:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["data_root"] = str((ROOT / config["data_root"]).resolve())
    config["rq1_root"] = str((ROOT / config["rq1_root"]).resolve())
    return config


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def environment_manifest() -> dict:
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": __import__("os").cpu_count(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
    }


def macro_f1_with_abstention(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float, float]:
    if np.unique(y_true).size < 2:
        # At rho=0 (and the all-low endpoint), binary Macro-F1 is undefined;
        # retain NRMSE as the clean/all-low control instead of manufacturing a score.
        coverage = float(np.mean(y_pred != -1))
        present = int(np.unique(y_true)[0])
        recall = float(np.mean(y_pred[y_true == present] == present))
        return np.nan, coverage, recall if present == PREDICTED_HIGH else np.nan, recall if present == PREDICTED_LOW else np.nan
    scores, recalls = [], []
    for label in (PREDICTED_HIGH, PREDICTED_LOW):
        tp = int(np.sum((y_true == label) & (y_pred == label)))
        fp = int(np.sum((y_true != label) & (y_pred == label)))
        fn = int(np.sum((y_true == label) & (y_pred != label)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else np.nan
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores.append(f1)
        recalls.append(recall)
    coverage = float(np.mean(y_pred != -1))
    return float(np.mean(scores)), coverage, float(recalls[0]), float(recalls[1])


def metric_record(prediction, truth: np.ndarray, scale: np.ndarray) -> dict:
    if prediction is None:
        return {
            "no_truth": True,
            "dimension": truth.size,
            "norm_sq_sum": np.nan,
            "norm_abs_sum": np.nan,
            "task_nrmse": np.nan,
            "task_nmae": np.nan,
            "native_rmse": np.nan,
            "native_mae": np.nan,
        }
    residual = np.asarray(prediction, dtype=float) - truth
    normalized = residual / scale
    return {
        "no_truth": False,
        "dimension": truth.size,
        "norm_sq_sum": float(np.square(normalized).sum()),
        "norm_abs_sum": float(np.abs(normalized).sum()),
        "task_nrmse": float(np.sqrt(np.square(normalized).mean())),
        "task_nmae": float(np.abs(normalized).mean()),
        "native_rmse": float(np.sqrt(np.square(residual).mean())),
        "native_mae": float(np.abs(residual).mean()),
    }


def first_correct_event(entries: list[tuple[int, int, int]], desired: int, start_task: int = 1, streak: int = 3) -> tuple[float, bool]:
    relevant = [(participation, prediction) for task_id, participation, prediction in entries if task_id >= start_task]
    if not relevant:
        return 0.0, True
    run = 0
    start_participation = relevant[0][0]
    for participation, prediction in relevant:
        run = run + 1 if prediction == desired else 0
        if run >= streak:
            return float(participation - start_participation - streak + 2), False
    return float(relevant[-1][0] - start_participation + 1), True


def jobs_for_target(config: dict, target: int) -> list[Job]:
    rho0 = float(config["cold_start_malicious_ratio"])
    jobs = [Job("cold-start", strategy, strategy, "stable", rho0) for strategy in config["strategies"]]
    if target != int(config["main_target_workers"]):
        return jobs
    jobs.extend(
        Job("malicious-ratio", f"rho={rho:.2f}", "Adaptive-HQ", "ratio", float(rho))
        for rho in config["malicious_ratios"]
    )
    for condition, participations in config["early_error_conditions"].items():
        if condition == "E0":
            continue  # The Adaptive-HQ cold-start run is the paired E0 control.
        jobs.append(Job("early-error", condition, "Adaptive-HQ", "stable", rho0, forced_low=tuple(participations)))
    jobs.extend(
        Job("h-to-l", f"switch={fraction:.2f}", "Adaptive-HQ", "h_to_l", rho0, float(fraction))
        for fraction in config["h_to_l_fractions"]
    )
    jobs.append(
        Job(
            "l-to-h",
            f"switch={float(config['l_to_h_fraction']):.2f}",
            "Adaptive-HQ",
            "l_to_h",
            rho0,
            float(config["l_to_h_fraction"]),
        )
    )
    return jobs


def run_one(
    replay,
    job: Job,
    parameters: Parameters,
    center: np.ndarray,
    scale: np.ndarray,
    task_limit: int,
) -> tuple[list[dict], dict, list[dict]]:
    model = ReorganizedIRPPTD(parameters, center, scale, replay.seed, job.strategy, job.forced_low)
    task_rows: list[dict] = []
    worker_entries: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    report_totals = defaultdict(float)
    seen_workers: set[int] = set()

    for task in replay.tasks[:task_limit]:
        result = model.process_task(task)
        error = metric_record(result.prediction, task.truth, scale)
        reports = pd.DataFrame(result.report_records)
        seen_workers.update(int(x) for x in reports["worker_id"])

        predicted_bad = reports["predicted_low_report"].astype(bool)
        true_bad = reports["is_bad_report"].astype(bool)
        tp = int((predicted_bad & true_bad).sum())
        fp = int((predicted_bad & ~true_bad).sum())
        fn = int((~predicted_bad & true_bad).sum())
        tn = int((~predicted_bad & ~true_bad).sum())
        bad_retained = int((true_bad & reports["retained"]).sum())
        clean_retained = int((~true_bad & reports["retained"]).sum())
        for key, value in {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "bad_total": int(true_bad.sum()),
            "clean_total": int((~true_bad).sum()),
            "bad_retained": bad_retained,
            "clean_retained": clean_retained,
        }.items():
            report_totals[key] += value

        current_low = low_ids_for_task(
            replay.profile,
            task.task_id,
            replay.initial_low_ids,
            replay.switched_ids,
            replay.switch_task,
        )
        predictions = model.all_worker_predictions()
        y_true = np.asarray([PREDICTED_LOW if wid in current_low else PREDICTED_HIGH for wid in range(1, 101)], dtype=int)
        y_pred = np.asarray([predictions[wid] for wid in range(1, 101)], dtype=int)
        worker_f1, worker_coverage, high_recall, low_recall = macro_f1_with_abstention(y_true, y_pred)
        active_ids = np.asarray(sorted(seen_workers), dtype=int)
        active_true = y_true[active_ids - 1]
        active_pred = y_pred[active_ids - 1]
        active_f1, active_coverage, _, _ = macro_f1_with_abstention(active_true, active_pred)

        for row in reports.itertuples(index=False):
            worker_entries[int(row.worker_id)].append(
                (int(task.task_id), int(row.participation_index), int(row.worker_prediction_after))
            )

        task_rows.append(
            {
                "experiment": job.experiment,
                "condition": job.condition,
                "strategy": job.strategy,
                "profile": job.profile,
                "malicious_ratio": job.malicious_ratio,
                "switch_fraction": job.switch_fraction,
                "scene": replay.scene,
                "target_workers": replay.target_workers,
                "seed": replay.seed,
                "task_id": task.task_id,
                **error,
                **result.task_record,
                "report_tp": tp,
                "report_fp": fp,
                "report_fn": fn,
                "report_tn": tn,
                "bad_report_count": int(true_bad.sum()),
                "clean_report_count": int((~true_bad).sum()),
                "bad_retained": bad_retained,
                "clean_retained": clean_retained,
                "worker_macro_f1": worker_f1,
                "worker_coverage": worker_coverage,
                "worker_high_recall": high_recall,
                "worker_low_recall": low_recall,
                "active_worker_macro_f1": active_f1,
                "active_worker_coverage": active_coverage,
            }
        )

    frame = pd.DataFrame(task_rows)
    valid = frame.loc[~frame["no_truth"]]
    denom = float(valid["dimension"].sum())
    nrmse = float(np.sqrt(valid["norm_sq_sum"].sum() / denom)) if denom else np.nan
    nmae = float(valid["norm_abs_sum"].sum() / denom) if denom else np.nan
    precision = report_totals["tp"] / (report_totals["tp"] + report_totals["fp"]) if report_totals["tp"] + report_totals["fp"] else 0.0
    recall = report_totals["tp"] / (report_totals["tp"] + report_totals["fn"]) if report_totals["tp"] + report_totals["fn"] else np.nan
    report_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    extra_tasks = frame.loc[frame["extra_report_count"] > 0, "task_id"]
    summary = {
        "experiment": job.experiment,
        "condition": job.condition,
        "strategy": job.strategy,
        "profile": job.profile,
        "malicious_ratio": job.malicious_ratio,
        "switch_fraction": job.switch_fraction,
        "scene": replay.scene,
        "target_workers": replay.target_workers,
        "seed": replay.seed,
        "nrmse": nrmse,
        "nmae": nmae,
        "no_truth_rate": float(frame["no_truth"].mean()),
        "report_f1": report_f1,
        "report_fpr": report_totals["fp"] / (report_totals["fp"] + report_totals["tn"]) if report_totals["fp"] + report_totals["tn"] else np.nan,
        "report_fnr": report_totals["fn"] / (report_totals["fn"] + report_totals["tp"]) if report_totals["fn"] + report_totals["tp"] else np.nan,
        "bad_leakage": report_totals["bad_retained"] / report_totals["bad_total"] if report_totals["bad_total"] else np.nan,
        "clean_retention": report_totals["clean_retained"] / report_totals["clean_total"] if report_totals["clean_total"] else np.nan,
        "final_worker_macro_f1": float(frame.iloc[-1]["worker_macro_f1"]),
        "final_worker_coverage": float(frame.iloc[-1]["worker_coverage"]),
        "mean_extra_reports_per_task": float(frame["extra_report_count"].mean()),
        "bootstrap_task_rate": float(frame["bootstrap_active"].mean()),
        "last_extra_task": int(extra_tasks.max()) if len(extra_tasks) else 0,
        "temporary_fallback_rate": float(frame["temporary_fallback"].mean()),
    }

    event_rows = []
    for wid in range(1, 101):
        entries = worker_entries.get(wid, [])
        if job.profile == "h_to_l" and wid in replay.switched_ids:
            desired, start_task, event = PREDICTED_LOW, replay.switch_task, "detect-h-to-l"
        elif job.profile == "l_to_h" and wid in replay.switched_ids:
            desired, start_task, event = PREDICTED_HIGH, replay.switch_task, "recover-l-to-h"
        else:
            desired = PREDICTED_LOW if wid in replay.initial_low_ids else PREDICTED_HIGH
            start_task, event = 1, "initial-classification-low" if desired == PREDICTED_LOW else "initial-classification-high"
        delay, censored = first_correct_event(entries, desired, start_task)
        event_rows.append(
            {
                "experiment": job.experiment,
                "condition": job.condition,
                "strategy": job.strategy,
                "profile": job.profile,
                "malicious_ratio": job.malicious_ratio,
                "switch_fraction": job.switch_fraction,
                "scene": replay.scene,
                "target_workers": replay.target_workers,
                "seed": replay.seed,
                "worker_id": wid,
                "event": event,
                "delay_participations": delay,
                "censored": censored,
                "activity_count": replay.activity_counts[wid],
            }
        )
    return task_rows, summary, event_rows


def write_assignment_audit(workloads: dict, seeds: list[int], config: dict) -> None:
    rows = []
    for workload in workloads.values():
        for seed in seeds:
            replay = make_replay(
                workload,
                seed,
                "stable",
                float(config["cold_start_malicious_ratio"]),
                0.0,
                int(config["switch_task"]),
                config["hq_seed_ids"],
                config["random_extra_ids"],
                int(config["random_extra_reports_per_task"]),
            )
            good = [replay.activity_counts[x] for x in range(1, 101) if x not in replay.initial_low_ids]
            bad = [replay.activity_counts[x] for x in replay.initial_low_ids]
            rows.append(
                {
                    "workload": workload.key,
                    "seed": seed,
                    "good_worker_count": len(good),
                    "bad_worker_count": len(bad),
                    "good_mean_activity": float(np.mean(good)),
                    "bad_mean_activity": float(np.mean(bad)),
                    "activity_mean_difference": float(np.mean(good) - np.mean(bad)),
                }
            )
    pd.DataFrame(rows).to_csv(METADATA / "worker_assignment_audit.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-count", type=int, default=None, help="Use a prefix of frozen seeds; formal run omits this option.")
    parser.add_argument("--task-limit", type=int, default=100, help="Smoke-test horizon; formal run uses 100.")
    parser.add_argument("--output-tag", default="formal")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)
    config = load_config()
    seeds = list(map(int, config["random_seeds"]))
    if args.seed_count is not None:
        seeds = seeds[: args.seed_count]
    workloads = load_workloads(config)
    frozen, manifest = load_frozen_context(config)
    parameters = Parameters.from_mapping(frozen["selected_parameters"])

    selected_workloads = [
        workload
        for workload in workloads.values()
        if workload.target_workers in {int(config["main_target_workers"]), int(config["replication_target_workers"])}
    ]
    total = sum(len(jobs_for_target(config, w.target_workers)) for w in selected_workloads) * len(seeds)
    task_rows, run_rows, event_rows = [], [], []
    started = time.perf_counter()
    job_index = 0
    for seed in seeds:
        for workload in selected_workloads:
            center = np.asarray(manifest[workload.key]["normalization_center"], dtype=float)
            scale = np.asarray(manifest[workload.key]["normalization_scale_q95_minus_q05"], dtype=float)
            for job in jobs_for_target(config, workload.target_workers):
                job_index += 1
                print(
                    f"[{job_index:04d}/{total}] {workload.key} {job.experiment}/{job.condition} seed={seed}",
                    flush=True,
                )
                replay = make_replay(
                    workload,
                    seed,
                    job.profile,
                    job.malicious_ratio,
                    job.switch_fraction,
                    int(config["switch_task"]),
                    config["hq_seed_ids"],
                    config["random_extra_ids"],
                    int(config["random_extra_reports_per_task"]),
                )
                tasks, summary, events = run_one(replay, job, parameters, center, scale, int(args.task_limit))
                task_rows.extend(tasks)
                run_rows.append(summary)
                event_rows.extend(events)

    prefix = f"{args.output_tag}_" if args.output_tag else ""
    pd.DataFrame(task_rows).to_csv(RESULTS / f"{prefix}task_metrics.csv", index=False)
    pd.DataFrame(run_rows).to_csv(RESULTS / f"{prefix}run_summary.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RESULTS / f"{prefix}worker_events.csv", index=False)
    write_assignment_audit(workloads, seeds, config)

    elapsed = time.perf_counter() - started
    audit = {
        "formal": args.seed_count is None and args.task_limit == 100 and len(seeds) == 30,
        "seed_count": len(seeds),
        "task_limit": int(args.task_limit),
        "job_count": len(run_rows),
        "task_record_count": len(task_rows),
        "worker_event_count": len(event_rows),
        "elapsed_seconds": elapsed,
        "parameters": parameters.__dict__,
        "input_hashes": {w.key: w.sha256 for w in workloads.values()},
        "source_hashes": {
            path.name: sha256_file(path)
            for path in [ROOT / "config.json", ROOT / "src" / "data.py", ROOT / "src" / "model.py", ROOT / "src" / "core_base.py", Path(__file__)]
        },
        "result_files": [f"{prefix}task_metrics.csv", f"{prefix}run_summary.csv", f"{prefix}worker_events.csv"],
    }
    (METADATA / f"{prefix}run_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (METADATA / "environment.json").write_text(json.dumps(environment_manifest(), indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    main()
