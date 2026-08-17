from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACKAGE_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.core_base import Parameters
from src.data import (
    activity_balanced_order,
    choose_low_workers,
    generate_values,
    load_frozen_context,
    load_workloads,
    make_replay,
)
from src.model import ReorganizedIRPPTD


def config() -> dict:
    values = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    values["data_root"] = str((ROOT / values["data_root"]).resolve())
    values["rq1_root"] = str((ROOT / values["rq1_root"]).resolve())
    return values


def test_worker_ids_and_activity_balancing() -> None:
    cfg = config()
    workload = load_workloads(cfg)["Climate_n27"]
    assert set(np.concatenate([task.worker_ids for task in workload.tasks])) == set(range(1, 101))
    order = activity_balanced_order(workload, 20260808)
    assert sorted(order) == list(range(1, 101))
    low = choose_low_workers(workload, 20260808, 0.5)
    assert len(low) == 50
    counts = {wid: 0 for wid in range(1, 101)}
    for task in workload.tasks:
        for wid in task.worker_ids:
            counts[int(wid)] += 1
    good_mean = np.mean([counts[x] for x in counts if x not in low])
    bad_mean = np.mean([counts[x] for x in low])
    assert abs(good_mean - bad_mean) < 1.5


def test_good_and_bad_submission_rules() -> None:
    truth = np.asarray([10.0, 100.0, 1000.0])
    clean, clean_mask = generate_values(truth, False, np.random.default_rng(1))
    bad, bad_mask = generate_values(truth, True, np.random.default_rng(1))
    assert not clean_mask.any() and bad_mask.all()
    assert np.all(np.abs(clean - truth) / truth <= 0.0101)
    relative = np.abs(bad - truth) / truth
    assert np.all(relative >= 0.049) and np.all(relative <= 0.201)


def test_replay_preserves_sumo_incidence_and_strategies_run() -> None:
    cfg = config()
    workload = load_workloads(cfg)["Climate_n27"]
    replay = make_replay(
        workload,
        20260808,
        "stable",
        0.5,
        0.0,
        cfg["switch_task"],
        cfg["hq_seed_ids"],
        cfg["random_extra_ids"],
        cfg["random_extra_reports_per_task"],
    )
    assert replay.initial_low_ids and len(replay.initial_low_ids) == 50
    for incidence, regenerated in zip(workload.tasks, replay.tasks):
        assert list(incidence.worker_ids) == [report.worker_id for report in regenerated.ordinary]
        assert np.array_equal(incidence.truth, regenerated.truth)
    frozen, manifest = load_frozen_context(cfg)
    parameters = Parameters.from_mapping(frozen["selected_parameters"])
    center = np.asarray(manifest[workload.key]["normalization_center"], dtype=float)
    scale = np.asarray(manifest[workload.key]["normalization_scale_q95_minus_q05"], dtype=float)
    for strategy in ("Adaptive-HQ", "No-Extra", "Random-Extra"):
        model = ReorganizedIRPPTD(parameters, center, scale, 20260808, strategy)
        for task in replay.tasks[:3]:
            result = model.process_task(task)
            assert result.prediction is not None
            assert np.isfinite(result.prediction).all()
        if strategy == "Adaptive-HQ":
            assert result.task_record["trusted_hq_count"] == parameters.s_0
        elif strategy == "No-Extra":
            assert result.task_record["extra_report_count"] == 0


if __name__ == "__main__":
    test_worker_ids_and_activity_balancing()
    test_good_and_bad_submission_rules()
    test_replay_preserves_sumo_incidence_and_strategies_run()
    print("All reorganized RQ2 tests passed.")
