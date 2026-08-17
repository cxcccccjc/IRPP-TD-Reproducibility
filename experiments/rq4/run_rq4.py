from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import scipy

from src.rq4_core import (
    HIGH,
    LOW,
    UNCERTAIN,
    Parameters,
    SequentialIRPP,
    angular_scores,
    bounded_truth_discovery,
    error_components,
    fit_scene_scalers,
    full_analytics_once,
    load_workloads,
    screening_macro_f1,
    synthetic_reports,
)


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
METADATA = ROOT / "metadata"


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def run_angular_budget(config: dict, workloads, scalers, parameters: Parameters, quick: bool) -> None:
    seeds = config["random_seeds"][:2] if quick else config["random_seeds"]
    caps = [3, 6, 20] if quick else config["angular_caps"]
    specs = [(f"cap-{cap}", "rabod", int(cap), (parameters.mu1, parameters.mu2)) for cap in caps]
    exact = config["exact_abod_calibration"]
    specs.append(("Exact", "exact_abod", parameters.delta_max, (float(exact["mu1"]), float(exact["mu2"]))))
    rows = []
    total = len(seeds) * len(workloads) * len(specs)
    index = 0
    for spec, mode, cap, thresholds in specs:
        for seed in seeds:
            for workload in workloads.values():
                index += 1
                print(f"[angular {index}/{total}] {spec} seed={seed} {workload.key}", flush=True)
                model = SequentialIRPP(parameters, scalers[workload.scene], int(seed), cap, mode, thresholds)
                for task in workload.tasks:
                    result = model.process_task(task)
                    if task.task_id < int(config["test_tasks"][0]):
                        continue
                    norm_sq, dim = error_components(result.truth, task.truth, scalers[workload.scene].scale)
                    valid_scores = np.flatnonzero(np.isfinite(result.scores))
                    rows.append(
                        {
                            "budget": spec,
                            "mode": mode,
                            "delta_cap": cap,
                            "scene": workload.scene,
                            "target_workers": workload.target_workers,
                            "seed": int(seed),
                            "task_id": task.task_id,
                            "participant_count": len(task.submissions),
                            "norm_sq_sum": norm_sq,
                            "dimension": dim,
                            "no_truth": result.truth is None,
                            "iterations": result.iterations,
                            "converged": result.converged,
                            "pair_evaluations": result.angular.pair_evaluations,
                            "effective_budget": result.angular.effective_budget,
                            "angular_available": result.angular_available,
                            "valid_score_count": len(valid_scores),
                            "scores_json": json.dumps(result.scores.tolist(), separators=(",", ":")),
                            "labels_json": json.dumps(result.labels.tolist(), separators=(",", ":")),
                            "retained_json": json.dumps(result.retained.astype(int).tolist(), separators=(",", ":")),
                            "worker_ids_json": json.dumps(task.worker_ids.tolist(), separators=(",", ":")),
                            "screening_macro_f1": screening_macro_f1(result.labels, task.worker_ids),
                        }
                    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS / ("angular_budget_quick.csv" if quick else "angular_budget_task_results.csv"), index=False)


def run_stopping_grid(config: dict, workloads, scalers, parameters: Parameters, quick: bool) -> None:
    seeds = config["random_seeds"][:2] if quick else config["random_seeds"]
    epsilons = config["stopping_epsilons"] if not quick else [1e-3, 1e-5, 1e-12]
    caps = config["stopping_caps"] if not quick else [2, 5, 50]
    ref_epsilon = float(config["stopping_reference"]["epsilon"])
    ref_cap = int(config["stopping_reference"]["max_iterations"])
    rows = []
    total = len(seeds) * len(workloads)
    index = 0
    for seed in seeds:
        for workload in workloads.values():
            index += 1
            print(f"[stopping {index}/{total}] seed={seed} {workload.key}", flush=True)
            model = SequentialIRPP(parameters, scalers[workload.scene], int(seed))
            for task in workload.tasks:
                result = model.process_task(task)
                if task.task_id < int(config["test_tasks"][0]):
                    continue
                retained = task.report_matrix[result.retained]
                reference = bounded_truth_discovery(retained, ref_epsilon, parameters.epsilon_w, ref_cap, True)
                if reference.truth is None:
                    raise RuntimeError("Stopping reference returned no truth")
                denom = 1.0 + float(np.linalg.norm(reference.truth))
                for epsilon in epsilons:
                    for cap in caps:
                        trial = bounded_truth_discovery(retained, float(epsilon), parameters.epsilon_w, int(cap), True)
                        gap = float("nan") if trial.truth is None else float(np.linalg.norm(trial.truth - reference.truth) / denom)
                        rows.append(
                            {
                                "scene": workload.scene,
                                "target_workers": workload.target_workers,
                                "seed": int(seed),
                                "task_id": task.task_id,
                                "epsilon": float(epsilon),
                                "max_iterations": int(cap),
                                "fixed_point_gap": gap,
                                "iterations": trial.iterations,
                                "converged": trial.converged,
                                "cap_hit": not trial.converged,
                                "reference_iterations": reference.iterations,
                                "reference_converged": reference.converged,
                            }
                        )
    RESULTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS / ("stopping_grid_quick.csv" if quick else "stopping_grid_task_results.csv"), index=False)


def kernel_once(method: str, reports: np.ndarray, ids: np.ndarray, anchors: set[int], reputation: np.ndarray, parameters: Parameters):
    if method == "Exact ABOD":
        return angular_scores(reports, ids, anchors, 1, 20260808, parameters.delta_max, parameters.epsilon_d, "exact_abod", True)[2]
    if method == "RABOD":
        return angular_scores(reports, ids, anchors, 1, 20260808, parameters.delta_max, parameters.epsilon_d, "rabod", True)[2]
    if method == "Full IRPP":
        return full_analytics_once(reports, ids, anchors, reputation, parameters)[1]
    raise ValueError(method)


def measure_kernel(method: str, reports: np.ndarray, ids: np.ndarray, anchors: set[int], reputation: np.ndarray, parameters: Parameters, config: dict, projected_total: float | None = None) -> tuple[list[float], object, bool]:
    limit = float(config["exact_configuration_limit_seconds"]) if method == "Exact ABOD" else float("inf")
    if projected_total is not None and projected_total > limit:
        return [], None, True
    warmups = int(config["timing_warmups"])
    started_config = time.perf_counter()
    diagnostic = None
    for _ in range(warmups):
        diagnostic = kernel_once(method, reports, ids, anchors, reputation, parameters)
        if time.perf_counter() - started_config > limit:
            return [], diagnostic, True
    timings = []
    cumulative = 0.0
    min_repeats = int(config["timing_min_repeats"])
    min_seconds = float(config["timing_min_seconds"])
    while len(timings) < min_repeats or cumulative < min_seconds:
        before = time.perf_counter_ns()
        diagnostic = kernel_once(method, reports, ids, anchors, reputation, parameters)
        elapsed = (time.perf_counter_ns() - before) * 1e-9
        timings.append(elapsed)
        cumulative += elapsed
        if time.perf_counter() - started_config > limit:
            if len(timings) < min_repeats:
                return [], diagnostic, True
            break
        if len(timings) >= 5000:
            break
    return timings, diagnostic, False


def run_scaling(config: dict, parameters: Parameters, quick: bool) -> None:
    n_values = [20, 100, 400] if quick else config["scaling_n"]
    methods = ["RABOD", "Full IRPP", "Exact ABOD"]
    detail_rows = []
    summary_rows = []
    previous_exact = None
    last_exact_n = None
    for n in n_values:
        reports, ids, anchors, reputation = synthetic_reports(int(n), int(config["scaling_dimension"]), 20260808 + int(n), float(config["scaling_anchor_ratio"]))
        for method in methods:
            projected = None
            if method == "Exact ABOD" and previous_exact is not None and last_exact_n is not None:
                per_call = previous_exact * (float(n) / float(last_exact_n)) ** 3
                projected = per_call * (int(config["timing_warmups"]) + int(config["timing_min_repeats"]))
            print(f"[scaling] {method} n={n}" + (f" projected={projected:.1f}s" if projected else ""), flush=True)
            timings, diagnostic, censored = measure_kernel(method, reports, ids, anchors, reputation, parameters, config, projected)
            if censored:
                summary_rows.append({"method": method, "n": n, "censored": True})
                if method == "Exact ABOD":
                    methods = [item for item in methods if item != "Exact ABOD"]
                continue
            for repeat, elapsed in enumerate(timings):
                detail_rows.append({"method": method, "n": n, "repeat": repeat, "runtime_s": elapsed})
            median = float(np.median(timings))
            if method == "Exact ABOD":
                previous_exact, last_exact_n = median, n
            summary_rows.append(
                {
                    "method": method,
                    "n": n,
                    "censored": False,
                    "runtime_median_s": median,
                    "runtime_p95_s": float(np.quantile(timings, 0.95)),
                    "repeat_count": len(timings),
                    "pair_evaluations": diagnostic.pair_evaluations,
                    "effective_budget": diagnostic.effective_budget,
                    "estimated_peak_bytes": diagnostic.estimated_peak_bytes,
                    "reports_per_second": float(n / median),
                    "tasks_per_second": float(1.0 / median),
                }
            )
    RESULTS.mkdir(parents=True, exist_ok=True)
    suffix = "_quick" if quick else ""
    pd.DataFrame(detail_rows).to_csv(RESULTS / f"scaling_timing_repeats{suffix}.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(RESULTS / f"scaling_summary{suffix}.csv", index=False)


def run_secondary_scaling(config: dict, parameters: Parameters, quick: bool) -> None:
    dimension_values = [2, 9, 36] if quick else config["dimension_sweep"]
    delta_values = [3, 20, 80] if quick else config["delta_sweep"]
    rows = []
    n_dimension = 1000 if not quick else 200
    for dimension in dimension_values:
        reports, ids, anchors, reputation = synthetic_reports(n_dimension, int(dimension), 30260000 + int(dimension), float(config["scaling_anchor_ratio"]))
        timings, diagnostic, censored = measure_kernel("Full IRPP", reports, ids, anchors, reputation, parameters, config)
        rows.append({"sweep": "dimension", "value": dimension, "n": n_dimension, "method": "Full IRPP", "runtime_median_s": float(np.median(timings)), "runtime_p95_s": float(np.quantile(timings, 0.95)), "pair_evaluations": diagnostic.pair_evaluations, "censored": censored})
    n_delta = 10000 if not quick else 400
    for delta in delta_values:
        reports, ids, anchors, reputation = synthetic_reports(n_delta, int(config["scaling_dimension"]), 40260000 + int(delta), float(config["scaling_anchor_ratio"]))
        local = Parameters.from_mapping({**parameters.__dict__, "delta_max": int(delta)})
        timings, diagnostic, censored = measure_kernel("RABOD", reports, ids, anchors, reputation, local, config)
        rows.append({"sweep": "delta_max", "value": delta, "n": n_delta, "method": "RABOD", "runtime_median_s": float(np.median(timings)), "runtime_p95_s": float(np.quantile(timings, 0.95)), "pair_evaluations": diagnostic.pair_evaluations, "censored": censored})
    suffix = "_quick" if quick else ""
    pd.DataFrame(rows).to_csv(RESULTS / f"secondary_scaling{suffix}.csv", index=False)


def make_stability_reports(trial: int, tau: float, geometry: str, n: int = 27, dimension: int = 9) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(np.random.SeedSequence([20260810, int(trial), 1 if geometry == "full-rank" else 2]))
    if (n - 1) % 2 != 0:
        raise ValueError("Stability construction requires an odd report count")
    half = (n - 1) // 2
    if geometry == "full-rank":
        positive = rng.normal(size=(half, dimension))
    elif geometry == "rank-1":
        direction = rng.normal(size=dimension)
        direction /= np.linalg.norm(direction)
        positive = rng.normal(size=(half, 1)) * direction[None, :]
    else:
        raise ValueError(geometry)
    # Antithetic pairs make the formal initial mean exactly the zero vector in
    # floating-point arithmetic, so report 1 coincides with the current
    # aggregate rather than merely lying near it.
    deviations = np.empty((n - 1, dimension), dtype=float)
    deviations[0::2] = positive
    deviations[1::2] = -positive
    reports = np.vstack([np.zeros((1, dimension)), float(tau) * deviations])
    return reports, np.zeros(dimension)


def stability_trial(parameters: Parameters, reports: np.ndarray, truth: np.ndarray, geometry: str, protected: bool) -> dict:
    n = reports.shape[0]
    ids = np.arange(1, n + 1, dtype=int)
    anchors = set(int(x) for x in ids)
    scores, available, angular = angular_scores(reports, ids, anchors, 1, 20260810, parameters.delta_max, parameters.epsilon_d, "rabod", guarded=protected)
    labels = np.full(n, UNCERTAIN, dtype=int)
    if available:
        valid = np.isfinite(scores)
        labels[valid & (scores >= parameters.mu1)] = HIGH
        labels[valid & (scores < parameters.mu2)] = LOW
        retained = labels != LOW
    else:
        retained = np.ones(n, dtype=bool)
    if not retained.any():
        retained[:] = True
    td = bounded_truth_discovery(reports[retained], parameters.epsilon, parameters.epsilon_w, parameters.max_iterations, protected=protected)
    centered = reports - reports.mean(axis=0, keepdims=True)
    expected_fallback = bool(np.linalg.matrix_rank(centered, tol=parameters.epsilon_d) < 2)
    declared_fallback = bool(protected and not available)
    identical_correct = bool(np.max(np.abs(reports)) > 0.0 or (td.truth is not None and np.array_equal(td.truth, truth)))
    finite = bool(td.truth is not None and td.finite and np.isfinite(scores[np.isfinite(scores)]).all())
    weight_ok = bool(td.max_raw_weight <= math.log(2.0) + 1e-12 and td.normalization_error <= 1e-12)
    fallback_ok = bool((not expected_fallback) or declared_fallback)
    no_degenerate_low = bool((not expected_fallback) or np.sum(labels == LOW) == 0)
    success = finite and weight_ok and fallback_ok and identical_correct and no_degenerate_low
    return {
        "success": success,
        "finite": finite,
        "expected_fallback": expected_fallback,
        "declared_fallback": declared_fallback,
        "angular_available": available,
        "low_count": int(np.sum(labels == LOW)),
        "retained_count": int(retained.sum()),
        "iterations": td.iterations,
        "converged": td.converged,
        "max_raw_weight": td.max_raw_weight,
        "normalization_error": td.normalization_error,
    }


def run_stability(config: dict, parameters: Parameters, quick: bool) -> None:
    trials = 50 if quick else int(config["stability_trials"])
    tau_values = config["stability_tau"]
    rows = []
    for geometry in ("full-rank", "rank-1"):
        for tau in tau_values:
            print(f"[stability] {geometry} tau={tau:g} trials={trials}", flush=True)
            for trial in range(trials):
                reports, truth = make_stability_reports(trial, float(tau), geometry)
                for protected, method in ((True, "Full"), (False, "Unprotected")):
                    row = stability_trial(parameters, reports, truth, geometry, protected)
                    rows.append({"method": method, "geometry": geometry, "tau": float(tau), "trial": trial, **row})
    suffix = "_quick" if quick else ""
    pd.DataFrame(rows).to_csv(RESULTS / f"stability_trials{suffix}.csv", index=False)


def run_applicability(config: dict, parameters: Parameters, quick: bool) -> None:
    trials = 50 if quick else int(config["applicability_trials"])
    rows = []
    for trial in range(trials):
        rng = np.random.default_rng(np.random.SeedSequence([20260810, trial, 0xA991]))
        dimension = 9
        n = 40
        base = np.zeros(dimension)
        axis = rng.normal(size=dimension)
        axis /= np.linalg.norm(axis)
        offset = 0.5 * axis
        noise = 0.04
        single = base + noise * rng.normal(size=(n, dimension))
        group_a = base - offset + noise * rng.normal(size=(n // 2, dimension))
        group_b = base + offset + noise * rng.normal(size=(n // 2, dimension))
        two = np.vstack([group_a, group_b])
        scenarios = [("single-regime", [single], [base]), ("unpartitioned-two-regime", [two], [None]), ("context-partitioned", [group_a, group_b], [base - offset, base + offset])]
        for scenario, groups, truths in scenarios:
            errors = []
            available_flags = []
            retained_rates = []
            for group, target in zip(groups, truths):
                ids = np.arange(1, group.shape[0] + 1, dtype=int)
                scores, available, _ = angular_scores(group, ids, set(int(x) for x in ids), trial + 1, 20260810, parameters.delta_max, parameters.epsilon_d, "rabod", True)
                labels = np.full(group.shape[0], UNCERTAIN, dtype=int)
                if available:
                    valid = np.isfinite(scores)
                    labels[valid & (scores >= parameters.mu1)] = HIGH
                    labels[valid & (scores < parameters.mu2)] = LOW
                    retained = labels != LOW
                else:
                    retained = np.ones(group.shape[0], dtype=bool)
                td = bounded_truth_discovery(group[retained], parameters.epsilon, parameters.epsilon_w, parameters.max_iterations, True)
                if td.truth is None:
                    errors.append(float("nan"))
                elif target is None:
                    errors.append(float(min(np.linalg.norm(td.truth - (base - offset)), np.linalg.norm(td.truth - (base + offset))) / math.sqrt(dimension)))
                else:
                    errors.append(float(np.linalg.norm(td.truth - target) / math.sqrt(dimension)))
                available_flags.append(float(available))
                retained_rates.append(float(retained.mean()))
            rows.append({"scenario": scenario, "trial": trial, "nrmse": float(np.nanmean(errors)), "angular_available": float(np.mean(available_flags)), "retained_rate": float(np.mean(retained_rates))})
    suffix = "_quick" if quick else ""
    pd.DataFrame(rows).to_csv(RESULTS / f"applicability_trials{suffix}.csv", index=False)


def memory_worker(config: dict, parameters: Parameters, method: str, n: int) -> None:
    reports, ids, anchors, reputation = synthetic_reports(n, int(config["scaling_dimension"]), 50260000 + n, float(config["scaling_anchor_ratio"]))
    gc.collect()
    process = psutil.Process(os.getpid())
    baseline = process.memory_info().rss
    peak = [baseline]
    running = [True]

    def monitor() -> None:
        while running[0]:
            try:
                peak[0] = max(peak[0], process.memory_info().rss)
            except psutil.Error:
                pass
            time.sleep(0.0005)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    before = time.perf_counter_ns()
    diagnostic = kernel_once(method, reports, ids, anchors, reputation, parameters)
    elapsed = (time.perf_counter_ns() - before) * 1e-9
    running[0] = False
    thread.join(timeout=1.0)
    print(json.dumps({"method": method, "n": n, "baseline_rss": baseline, "peak_rss": peak[0], "incremental_peak_rss": max(0, peak[0] - baseline), "runtime_s": elapsed, "estimated_peak_bytes": diagnostic.estimated_peak_bytes}))


def run_memory(config: dict, parameters: Parameters, quick: bool) -> None:
    scaling_path = RESULTS / ("scaling_summary_quick.csv" if quick else "scaling_summary.csv")
    scaling = pd.read_csv(scaling_path)
    rows = []
    for row in scaling.loc[~scaling["censored"].fillna(False)].itertuples(index=False):
        command = [sys.executable, str(Path(__file__).resolve()), "--memory-worker", "--method", str(row.method), "--n", str(int(row.n))]
        completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        rows.append(payload)
        print(f"[memory] {row.method} n={row.n} peak+={payload['incremental_peak_rss'] / 2**20:.2f} MiB", flush=True)
    suffix = "_quick" if quick else ""
    pd.DataFrame(rows).to_csv(RESULTS / f"scaling_memory{suffix}.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--phase", choices=["all", "angular", "stopping", "scaling", "secondary", "stability", "applicability", "memory"], default="all")
    parser.add_argument("--memory-worker", action="store_true")
    parser.add_argument("--method")
    parser.add_argument("--n", type=int)
    args = parser.parse_args()
    config = load_config()
    parameters = Parameters.from_mapping(config["parameters"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)
    if args.memory_worker:
        memory_worker(config, parameters, str(args.method), int(args.n))
        return
    dump_json(
        METADATA / ("environment_quick.json" if args.quick else "environment.json"),
        {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "psutil": psutil.__version__,
            "float64": {
                "eps": float(np.finfo(np.float64).eps),
                "tiny": float(np.finfo(np.float64).tiny),
                "max": float(np.finfo(np.float64).max),
            },
            "quick": args.quick,
        },
    )
    needs_real = args.phase in {"all", "angular", "stopping"}
    workloads = load_workloads(config) if needs_real else None
    scalers = fit_scene_scalers(workloads, int(config["calibration_tasks"])) if needs_real else None
    if needs_real:
        manifest_root = Path(config["workload_root"])
        dump_json(
            METADATA / "input_manifest.json",
            {key: {"path": (manifest_root / value.path.name).as_posix(), "sha256": value.sha256} for key, value in workloads.items()},
        )
    if args.phase in {"all", "angular"}:
        run_angular_budget(config, workloads, scalers, parameters, args.quick)
    if args.phase in {"all", "stopping"}:
        run_stopping_grid(config, workloads, scalers, parameters, args.quick)
    if args.phase in {"all", "scaling"}:
        run_scaling(config, parameters, args.quick)
    if args.phase in {"all", "secondary"}:
        run_secondary_scaling(config, parameters, args.quick)
    if args.phase in {"all", "stability"}:
        run_stability(config, parameters, args.quick)
    if args.phase in {"all", "applicability"}:
        run_applicability(config, parameters, args.quick)
    if args.phase in {"all", "memory"}:
        run_memory(config, parameters, args.quick)


if __name__ == "__main__":
    main()
