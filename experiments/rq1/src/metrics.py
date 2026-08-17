from __future__ import annotations

import json
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd


def make_record(
    *,
    method: str,
    scene: str,
    target_workers: int,
    seed: int,
    task_id: int,
    participant_count: int,
    prediction: Optional[np.ndarray],
    truth: np.ndarray,
    scale: np.ndarray,
    runtime_s: float,
    iterations: int = 0,
    retained_count: int = 0,
    extras: Optional[Mapping] = None,
) -> dict:
    truth = np.asarray(truth, dtype=float)
    dim = int(truth.size)
    record = {
        "method": method,
        "scene": scene,
        "target_workers": int(target_workers),
        "seed": int(seed),
        "task_id": int(task_id),
        "participant_count": int(participant_count),
        "runtime_s": float(runtime_s),
        "iterations": int(iterations),
        "retained_count": int(retained_count),
        "dimension": dim,
        "no_truth": prediction is None,
        "truth": json.dumps(truth.tolist(), separators=(",", ":")),
        "prediction": "" if prediction is None else json.dumps(np.asarray(prediction).tolist(), separators=(",", ":")),
    }
    if prediction is None:
        record.update(
            {
                "abs_sum": np.nan,
                "sq_sum": np.nan,
                "norm_abs_sum": np.nan,
                "norm_sq_sum": np.nan,
                "task_mae": np.nan,
                "task_rmse": np.nan,
                "task_nmae": np.nan,
                "task_nrmse": np.nan,
            }
        )
    else:
        error = np.asarray(prediction, dtype=float) - truth
        normalized = error / np.asarray(scale, dtype=float)
        abs_sum = float(np.abs(error).sum())
        sq_sum = float(np.square(error).sum())
        norm_abs_sum = float(np.abs(normalized).sum())
        norm_sq_sum = float(np.square(normalized).sum())
        record.update(
            {
                "abs_sum": abs_sum,
                "sq_sum": sq_sum,
                "norm_abs_sum": norm_abs_sum,
                "norm_sq_sum": norm_sq_sum,
                "task_mae": abs_sum / dim,
                "task_rmse": float(np.sqrt(sq_sum / dim)),
                "task_nmae": norm_abs_sum / dim,
                "task_nrmse": float(np.sqrt(norm_sq_sum / dim)),
            }
        )
    if extras:
        record.update(extras)
    return record


def aggregate_metrics(frame: pd.DataFrame) -> dict:
    valid = frame.loc[~frame["no_truth"].astype(bool)].copy()
    total_tasks = len(frame)
    if valid.empty:
        return {
            "mae": np.nan,
            "rmse": np.nan,
            "nmae": np.nan,
            "nrmse": np.nan,
            "runtime_median_ms": float(frame["runtime_s"].median() * 1000.0),
            "runtime_p95_ms": float(frame["runtime_s"].quantile(0.95) * 1000.0),
            "no_truth_rate": 1.0,
            "tasks": total_tasks,
        }
    denominator = float(valid["dimension"].sum())
    return {
        "mae": float(valid["abs_sum"].sum() / denominator),
        "rmse": float(np.sqrt(valid["sq_sum"].sum() / denominator)),
        "nmae": float(valid["norm_abs_sum"].sum() / denominator),
        "nrmse": float(np.sqrt(valid["norm_sq_sum"].sum() / denominator)),
        "runtime_median_ms": float(frame["runtime_s"].median() * 1000.0),
        "runtime_p95_ms": float(frame["runtime_s"].quantile(0.95) * 1000.0),
        "no_truth_rate": float(frame["no_truth"].mean()),
        "tasks": total_tasks,
    }


def _bootstrap_metric_arrays(
    frame: pd.DataFrame, repetitions: int, rng: np.random.Generator
) -> dict[str, np.ndarray]:
    """Vectorized hierarchical seed/task bootstrap for one method/workload."""
    seeds = np.sort(frame["seed"].unique())
    tasks = np.sort(frame["task_id"].unique())
    seed_index = {value: idx for idx, value in enumerate(seeds)}
    task_index = {value: idx for idx, value in enumerate(tasks)}
    shape = (len(seeds), len(tasks))

    def matrix(column: str, dtype=float) -> np.ndarray:
        output = np.full(shape, np.nan, dtype=dtype)
        for row in frame[["seed", "task_id", column]].itertuples(index=False):
            output[seed_index[row.seed], task_index[row.task_id]] = getattr(row, column)
        return output

    seed_draws = rng.integers(0, len(seeds), size=(repetitions, len(seeds)))
    task_draws = rng.integers(0, len(tasks), size=(repetitions, len(seeds), len(tasks)))
    selected_seed = seed_draws[:, :, None]

    no_truth = matrix("no_truth", dtype=float)[selected_seed, task_draws].astype(bool)
    dimension = matrix("dimension")[selected_seed, task_draws]
    valid_dimension = np.where(no_truth, 0.0, dimension)
    denominator = valid_dimension.sum(axis=(1, 2))
    denominator = np.where(denominator > 0.0, denominator, np.nan)

    def selected_sum(column: str) -> np.ndarray:
        values = matrix(column)[selected_seed, task_draws]
        return np.nansum(np.where(no_truth, 0.0, values), axis=(1, 2))

    runtime = matrix("runtime_s")[selected_seed, task_draws]
    return {
        "mae": selected_sum("abs_sum") / denominator,
        "rmse": np.sqrt(selected_sum("sq_sum") / denominator),
        "nmae": selected_sum("norm_abs_sum") / denominator,
        "nrmse": np.sqrt(selected_sum("norm_sq_sum") / denominator),
        "runtime_median_ms": np.nanmedian(runtime, axis=(1, 2)) * 1000.0,
        "no_truth_rate": no_truth.mean(axis=(1, 2)),
    }


def summarize_with_bootstrap(
    records: pd.DataFrame,
    test_start: int,
    test_end: int,
    repetitions: int,
    seed: int = 20260808,
) -> pd.DataFrame:
    test = records.loc[records["task_id"].between(test_start, test_end)].copy()
    rows = []
    group_columns = ["method", "scene", "target_workers"]
    rng = np.random.default_rng(seed)
    metric_names = ["mae", "rmse", "nmae", "nrmse", "runtime_median_ms", "no_truth_rate"]
    for group_key, frame in test.groupby(group_columns, sort=False):
        point = aggregate_metrics(frame)
        bootstrap = _bootstrap_metric_arrays(frame, repetitions, rng)
        row = dict(zip(group_columns, group_key))
        row.update(point)
        for metric in metric_names:
            values = np.asarray(bootstrap[metric], dtype=float)
            row[f"{metric}_ci_low"] = float(np.nanquantile(values, 0.025))
            row[f"{metric}_ci_high"] = float(np.nanquantile(values, 0.975))
        rows.append(row)
    return pd.DataFrame(rows)


def phase_summary(records: pd.DataFrame) -> pd.DataFrame:
    phase_labels = {
        "Calibration (1-20)": (1, 20),
        "Early test (21-50)": (21, 50),
        "Mature test (51-100)": (51, 100),
    }
    rows = []
    for phase, (start, end) in phase_labels.items():
        subset = records.loc[records["task_id"].between(start, end)]
        for group_key, frame in subset.groupby(["method", "scene", "target_workers"], sort=False):
            row = dict(zip(["method", "scene", "target_workers"], group_key))
            row.update({"phase": phase, **aggregate_metrics(frame)})
            rows.append(row)
    return pd.DataFrame(rows)
