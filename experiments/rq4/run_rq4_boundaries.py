from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_rq4 import make_stability_reports
from src.rq4_core import HIGH, LOW, UNCERTAIN, Parameters, angular_scores, bounded_truth_discovery


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def component_trial(parameters: Parameters, reports: np.ndarray, geometry: str, angular_guard: bool, weight_floor: bool) -> dict:
    ids = np.arange(1, reports.shape[0] + 1, dtype=int)
    scores, available, diagnostic = angular_scores(reports, ids, set(int(x) for x in ids), 1, 20260810, parameters.delta_max, parameters.epsilon_d, "rabod", angular_guard)
    labels = np.full(reports.shape[0], UNCERTAIN, dtype=int)
    if available:
        valid = np.isfinite(scores)
        labels[valid & (scores >= parameters.mu1)] = HIGH
        labels[valid & (scores < parameters.mu2)] = LOW
        retained = labels != LOW
    else:
        retained = np.ones(reports.shape[0], dtype=bool)
    if not retained.any():
        retained[:] = True
    td = bounded_truth_discovery(reports[retained], parameters.epsilon, parameters.epsilon_w, parameters.max_iterations, weight_floor)
    expected_fallback = np.linalg.matrix_rank(reports - reports.mean(axis=0, keepdims=True), tol=parameters.epsilon_d) < 2
    fallback_ok = (not expected_fallback) or (angular_guard and not available)
    finite = td.truth is not None and td.finite
    norm_ok = np.isfinite(td.normalization_error) and td.normalization_error <= 1e-12
    weight_ok = weight_floor and td.max_raw_weight <= np.log(2.0) + 1e-12 or (not weight_floor and finite)
    identical_ok = np.max(np.abs(reports)) > 0.0 or (td.truth is not None and np.array_equal(td.truth, reports[0]))
    return {
        "success": bool(finite and norm_ok and weight_ok and fallback_ok and identical_ok),
        "finite": bool(finite),
        "declared_fallback": bool(angular_guard and not available),
        "max_raw_weight": td.max_raw_weight,
        "normalization_error": td.normalization_error,
        "angular_fallback": diagnostic.fallback,
    }


def run_components(parameters: Parameters, config: dict) -> None:
    rows = []
    variants = [
        ("Full", True, True),
        ("No-weight-floor", True, False),
        ("No-angular-guards", False, True),
        ("Unprotected", False, False),
    ]
    for geometry in ("full-rank", "rank-1"):
        for tau in config["stability_tau"]:
            for trial in range(int(config["stability_trials"])):
                reports, _ = make_stability_reports(trial, float(tau), geometry)
                for variant, angular_guard, weight_floor in variants:
                    rows.append({"variant": variant, "geometry": geometry, "tau": float(tau), "trial": trial, **component_trial(parameters, reports, geometry, angular_guard, weight_floor)})
    frame = pd.DataFrame(rows)
    frame.to_csv(RESULTS / "stability_component_trials.csv", index=False)
    frame.groupby(["variant", "geometry", "tau"], as_index=False).agg(
        success_rate=("success", "mean"),
        finite_rate=("finite", "mean"),
        fallback_rate=("declared_fallback", "mean"),
        max_normalization_error=("normalization_error", "max"),
    ).to_csv(RESULTS / "stability_component_summary.csv", index=False)


def boundary_input(case: str, trial: int) -> tuple[np.ndarray, set[int]]:
    rng = np.random.default_rng(np.random.SeedSequence([20260810, trial, sum(map(ord, case))]))
    if case == "single-report":
        reports = rng.normal(size=(1, 9))
        anchors = {1}
    elif case == "identical-reports":
        reports = np.repeat(rng.normal(size=(1, 9)), 27, axis=0)
        anchors = set(range(1, 28))
    elif case == "duplicate-full-rank":
        unique = rng.normal(size=(9, 9))
        reports = np.repeat(unique, 3, axis=0)
        anchors = set(range(1, 28))
    elif case == "rank-1":
        direction = rng.normal(size=9)
        reports = rng.normal(size=(27, 1)) * direction[None, :]
        anchors = set(range(1, 28))
    elif case == "scalar":
        reports = rng.normal(size=(27, 1))
        anchors = set(range(1, 28))
    elif case == "two-anchors":
        reports = rng.normal(size=(27, 9))
        anchors = {1, 2}
    elif case == "empty-anchor-pool":
        reports = rng.normal(size=(27, 9))
        anchors = set()
    else:
        raise ValueError(case)
    return reports, anchors


def run_boundary_table(parameters: Parameters) -> None:
    cases = ["single-report", "identical-reports", "duplicate-full-rank", "rank-1", "scalar", "two-anchors", "empty-anchor-pool"]
    rows = []
    for case in cases:
        for trial in range(1000):
            reports, anchors = boundary_input(case, trial)
            ids = np.arange(1, reports.shape[0] + 1, dtype=int)
            _, available, diagnostic = angular_scores(reports, ids, anchors, 1, 20260810, parameters.delta_max, parameters.epsilon_d, "rabod", True)
            td = bounded_truth_discovery(reports, parameters.epsilon, parameters.epsilon_w, parameters.max_iterations, True)
            common_correct = case != "identical-reports" or (td.truth is not None and np.array_equal(td.truth, reports[0]))
            rows.append({"case": case, "trial": trial, "angular_available": available, "declared_fallback": diagnostic.fallback, "td_finite": td.finite and td.truth is not None, "common_truth_correct": common_correct, "iterations": td.iterations})
    frame = pd.DataFrame(rows)
    frame.to_csv(RESULTS / "boundary_case_trials.csv", index=False)
    frame.groupby("case", as_index=False).agg(
        angular_available_rate=("angular_available", "mean"),
        fallback_rate=("declared_fallback", "mean"),
        td_finite_rate=("td_finite", "mean"),
        common_truth_correct_rate=("common_truth_correct", "mean"),
        iterations_p95=("iterations", lambda values: float(values.quantile(0.95))),
    ).to_csv(RESULTS / "boundary_case_summary.csv", index=False)


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    parameters = Parameters.from_mapping(config["parameters"])
    run_components(parameters, config)
    run_boundary_table(parameters)
    print("RQ4 component and boundary experiments complete")


if __name__ == "__main__":
    main()
