from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .core_base import InstrumentedIRPPTD, Parameters
from .rq3_data import AttackReplay, Scaler


VARIANTS = {
    "Full": {"score_mode": "full", "anchor_mode": "guided"},
    "Binary-Rep.": {"score_mode": "beta", "anchor_mode": "guided"},
    "No-U": {"score_mode": "no_u", "anchor_mode": "guided"},
    "All-Anchors": {"score_mode": "full", "anchor_mode": "all"},
    "Sequential": {"score_mode": "full", "anchor_mode": "sequential"},
}


@dataclass(frozen=True)
class ReplayResult:
    task_records: tuple[dict, ...]
    report_records: tuple[dict, ...]


def error_fields(prediction: np.ndarray | None, truth: np.ndarray, scale: np.ndarray) -> dict:
    truth = np.asarray(truth, dtype=float)
    if prediction is None:
        return {
            "no_truth": True,
            "dimension": int(truth.size),
            "abs_sum": np.nan,
            "sq_sum": np.nan,
            "norm_abs_sum": np.nan,
            "norm_sq_sum": np.nan,
            "task_mae": np.nan,
            "task_rmse": np.nan,
            "task_nmae": np.nan,
            "task_nrmse": np.nan,
        }
    error = np.asarray(prediction, dtype=float) - truth
    normalized = error / np.asarray(scale, dtype=float)
    return {
        "no_truth": False,
        "dimension": int(truth.size),
        "abs_sum": float(np.abs(error).sum()),
        "sq_sum": float(np.square(error).sum()),
        "norm_abs_sum": float(np.abs(normalized).sum()),
        "norm_sq_sum": float(np.square(normalized).sum()),
        "task_mae": float(np.abs(error).mean()),
        "task_rmse": float(np.sqrt(np.square(error).mean())),
        "task_nmae": float(np.abs(normalized).mean()),
        "task_nrmse": float(np.sqrt(np.square(normalized).mean())),
    }


def run_irpp_replay(
    replay: AttackReplay,
    scaler: Scaler,
    parameters: Parameters,
    variant: str = "Full",
    keep_reports: bool = True,
) -> ReplayResult:
    if variant not in VARIANTS:
        raise ValueError(variant)
    settings = VARIANTS[variant]
    model = InstrumentedIRPPTD(
        parameters,
        scaler.center,
        scaler.scale,
        replay.seed,
        score_mode=settings["score_mode"],
        anchor_mode=settings["anchor_mode"],
        seed_mode="adaptive",
        reliable_probability_max=0.0,
    )
    tasks: list[dict] = []
    reports: list[dict] = []
    for task in replay.tasks:
        started = time.perf_counter()
        result = model.process_task(task)
        runtime_s = time.perf_counter() - started
        by_worker = {int(report.worker_id): report for report in task.ordinary}
        enriched_reports = []
        for record in result.report_records:
            source = by_worker[int(record["worker_id"])]
            row = {
                "method": "IRPP-TD",
                "variant": variant,
                "scene": replay.scene,
                "target_workers": replay.target_workers,
                "seed": replay.seed,
                "mode": replay.mode,
                "malicious_ratio": replay.malicious_ratio,
                "strength": replay.strength,
                "task_id": task.task_id,
                "coalition_member": bool(source.coalition_member),
                "attack_active": bool(source.attack_active),
                **record,
            }
            enriched_reports.append(row)
            if keep_reports:
                reports.append(row)

        anchors = [row for row in enriched_reports if row["anchor_before"]]
        honest_anchors = [row for row in anchors if not row["coalition_member"]]
        active_poison = [row for row in enriched_reports if row["attack_active"]]
        honest = [row for row in enriched_reports if not row["coalition_member"]]
        task_row = {
            "method": "IRPP-TD",
            "variant": variant,
            "scene": replay.scene,
            "target_workers": replay.target_workers,
            "seed": replay.seed,
            "mode": replay.mode,
            "malicious_ratio": replay.malicious_ratio,
            "strength": replay.strength,
            "task_id": task.task_id,
            "participant_count": len(task.ordinary),
            "runtime_s": float(runtime_s),
            "iterations": int(result.iterations),
            "retained_count": int(result.task_record["retained_ordinary_count"]),
            "ordinary_anchor_purity": float(len(honest_anchors) / len(anchors)) if anchors else np.nan,
            "malicious_report_leakage": float(np.mean([row["retained"] for row in active_poison])) if active_poison else np.nan,
            "honest_false_low_rate": float(np.mean([row["predicted_low"] for row in honest])) if honest else np.nan,
            "active_poison_count": len(active_poison),
            "coalition_participant_count": int(sum(row["coalition_member"] for row in enriched_reports)),
            **result.task_record,
            **error_fields(result.prediction, task.truth, scaler.scale),
        }
        tasks.append(task_row)
    return ReplayResult(tuple(tasks), tuple(reports))


def aggregate_task_rows(rows: Iterable[dict], start: int = 21, end: int = 100) -> dict:
    selected = [row for row in rows if start <= int(row["task_id"]) <= end]
    valid = [row for row in selected if not row["no_truth"]]
    denominator = float(sum(row["dimension"] for row in valid))
    return {
        "nrmse": float(np.sqrt(sum(row["norm_sq_sum"] for row in valid) / denominator)) if denominator else np.nan,
        "rmse": float(np.sqrt(sum(row["sq_sum"] for row in valid) / denominator)) if denominator else np.nan,
        "nmae": float(sum(row["norm_abs_sum"] for row in valid) / denominator) if denominator else np.nan,
        "mae": float(sum(row["abs_sum"] for row in valid) / denominator) if denominator else np.nan,
        "no_truth_rate": float(np.mean([row["no_truth"] for row in selected])) if selected else np.nan,
    }
