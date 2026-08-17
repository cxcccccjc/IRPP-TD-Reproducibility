from __future__ import annotations

from dataclasses import asdict, replace
from typing import Dict, Mapping

import numpy as np
import pandas as pd

from .data_utils import RobustScaler, Workload
from .irpp_td import IRPPParameters, IRPPTD, rabod_scores


def collect_validation_scores(
    workloads: Mapping[str, Workload],
    scalers: Mapping[str, RobustScaler],
    calibration_tasks: int,
    seed: int,
    defaults: IRPPParameters,
) -> np.ndarray:
    values = []
    for workload in workloads.values():
        scaler = scalers[workload.scene]
        for task in workload.tasks[:calibration_tasks]:
            scores, available = rabod_scores(
                scaler.transform(task.report_matrix),
                task.worker_ids,
                set(int(item) for item in task.worker_ids),
                task.task_id,
                seed,
                defaults.delta_max,
                defaults.epsilon_d,
            )
            if available:
                values.extend(scores[np.isfinite(scores)].tolist())
    if not values:
        raise RuntimeError("No finite validation RABOD scores were produced")
    return np.asarray(values, dtype=float)


def tune_irpp(
    workloads: Mapping[str, Workload],
    scalers: Mapping[str, RobustScaler],
    calibration_tasks: int,
    seed: int,
    defaults: IRPPParameters,
    grid: Mapping,
) -> tuple[IRPPParameters, pd.DataFrame, dict]:
    score_values = collect_validation_scores(
        workloads, scalers, calibration_tasks, seed, defaults
    )
    trials = []
    for theta in grid["theta"]:
        for mu2_q in grid["mu2_quantile"]:
            for mu1_q in grid["mu1_quantile"]:
                mu2 = float(np.quantile(score_values, mu2_q))
                mu1 = float(np.quantile(score_values, mu1_q))
                if not mu2 < mu1:
                    continue
                params = replace(defaults, theta=float(theta), mu1=mu1, mu2=mu2)
                norm_sq_sum = 0.0
                dimension_sum = 0
                no_truth = 0
                retained_ratios = []
                seed_ratios = []
                for workload in workloads.values():
                    model = IRPPTD(params, scalers[workload.scene], seed)
                    for task in workload.tasks[:calibration_tasks]:
                        result = model.process_task(task)
                        dimension_sum += task.truth.size
                        retained_ratios.append(result.retained_count / result.participant_count)
                        seed_ratios.append(result.seed_count / max(1, result.active_anchor_count))
                        if result.truth is None:
                            no_truth += 1
                            norm_sq_sum += 4.0 * task.truth.size
                        else:
                            normalized_error = (result.truth - task.truth) / scalers[workload.scene].scale
                            norm_sq_sum += float(np.square(normalized_error).sum())
                nrmse = float(np.sqrt(norm_sq_sum / dimension_sum))
                no_truth_rate = no_truth / (len(workloads) * calibration_tasks)
                # The penalty only resolves near-ties; accuracy remains the dominant objective.
                objective = nrmse + 2.0 * no_truth_rate
                trials.append(
                    {
                        "theta": theta,
                        "mu2_quantile": mu2_q,
                        "mu1_quantile": mu1_q,
                        "mu2": mu2,
                        "mu1": mu1,
                        "validation_nrmse": nrmse,
                        "no_truth_rate": no_truth_rate,
                        "mean_retained_ratio": float(np.mean(retained_ratios)),
                        "mean_seed_anchor_ratio": float(np.mean(seed_ratios)),
                        "objective": objective,
                    }
                )
    trial_frame = pd.DataFrame(trials).sort_values(
        ["objective", "validation_nrmse", "mean_retained_ratio"], ascending=[True, True, False]
    )
    if trial_frame.empty:
        raise RuntimeError("Parameter grid produced no valid trial")
    best = trial_frame.iloc[0]
    frozen = replace(
        defaults,
        theta=float(best["theta"]),
        mu1=float(best["mu1"]),
        mu2=float(best["mu2"]),
    )
    diagnostics = {
        "validation_score_count": int(score_values.size),
        "validation_score_quantiles": {
            str(q): float(np.quantile(score_values, q)) for q in [0.01, 0.05, 0.10, 0.15, 0.35, 0.50, 0.65, 0.90, 0.99]
        },
        "selected_parameters": asdict(frozen),
        "selection_rule": "minimum validation NRMSE plus 2x no-truth rate; tasks 1-20 only",
    }
    return frozen, trial_frame, diagnostics
