from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.core_base import Parameters
from src.rq3_data import (
    attack_is_active,
    calibration_directions,
    choose_malicious,
    honest_value,
    load_scalers,
    load_workloads,
    make_replay,
)
from src.rq3_model import aggregate_task_rows, run_irpp_replay


ROOT = Path(__file__).resolve().parents[1]


def load():
    config = json.loads((ROOT / "config.json").read_text())
    workloads = load_workloads(config)
    scalers = load_scalers(config)
    directions = calibration_directions(workloads, scalers, config["calibration_tasks"])
    return config, workloads, scalers, directions


def test_workloads_and_nested_sets():
    _, workloads, _, _ = load()
    assert all(len(workload.tasks) == 100 for workload in workloads.values())
    for workload in workloads.values():
        assert choose_malicious(workload, 20260808, 0.3) < choose_malicious(workload, 20260808, 0.5)


def test_hq_and_attack_schedules():
    config, workloads, scalers, directions = load()
    replay = make_replay(
        workloads["Climate_n27"], scalers["Climate"], directions["Climate"], 20260808,
        "mature_anchor", 0.3, 0.5, config["hq_seed_ids"], config["onoff_attack_blocks"], 41,
    )
    assert all(not report.attack_active and not report.coalition_member for task in replay.tasks for report in task.hq_seeds)
    assert not any(report.attack_active for report in replay.tasks[39].ordinary)
    assert any(report.attack_active for report in replay.tasks[40].ordinary)
    assert [attack_is_active("onoff", t, config["onoff_attack_blocks"], 41) for t in [20, 21, 30, 31]] == [False, True, True, False]


def test_realized_compact_strength_and_model_output():
    config, workloads, scalers, directions = load()
    workload, scaler = workloads["Climate_n27"], scalers["Climate"]
    replay = make_replay(
        workload, scaler, directions["Climate"], 20260808, "compact", 0.3, 0.5,
        config["hq_seed_ids"], config["onoff_attack_blocks"], 41,
    )
    task = replay.tasks[20]
    displacements = []
    for report in task.ordinary:
        if report.attack_active:
            clean = honest_value(task.truth, replay.seed, replay.key, task.task_id, report.worker_id, "ordinary")
            displacements.append(np.linalg.norm(scaler.transform(report.values) - scaler.transform(clean)) / np.sqrt(task.truth.size))
    assert abs(float(np.mean(displacements)) - 0.5) < 0.03
    result = run_irpp_replay(replay, scaler, Parameters(), keep_reports=True)
    assert len(result.task_records) == 100
    assert len(result.report_records) == sum(len(task.ordinary) for task in replay.tasks)
    assert np.isfinite(aggregate_task_rows(result.task_records)["nrmse"])
