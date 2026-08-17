from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.rq3_data import (
    active_evaluation_tasks,
    calibration_directions,
    load_scalers,
    load_workloads,
    make_replay,
    resolve_config_path,
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def qe_retained_mask(normalized_reports: np.ndarray) -> np.ndarray:
    """Reproduce QE's unchanged r=4, mu=0.31 hard outlier rule.

    The legacy implementation returns outlier indices after counting, for each
    report, the fraction of other reports within Euclidean distance four.  A
    report is an outlier when that fraction is at most 0.31.
    """
    reports = np.asarray(normalized_reports, dtype=float)
    n = len(reports)
    if n <= 2:
        return np.ones(n, dtype=bool)
    squared = np.sum((reports[:, None, :] - reports[None, :, :]) ** 2, axis=2)
    close = np.count_nonzero(squared <= 16.0, axis=1) - 1
    outlier = close / (n - 1) <= 0.31
    return ~outlier


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    workloads = {
        key: value
        for key, value in load_workloads(config).items()
        if value.target_workers == 27
    }
    scalers = load_scalers(config)
    directions = calibration_directions(load_workloads(config), scalers, config["calibration_tasks"])
    modes = ["independent", "compact", "onoff", "mature_anchor"]
    rows: list[dict] = []
    started = time.time()

    for workload in workloads.values():
        scaler = scalers[workload.scene]
        for seed in config["random_seeds"]:
            for mode in modes:
                replay = make_replay(
                    workload,
                    scaler,
                    directions[workload.scene],
                    seed,
                    mode,
                    config["mode_ratio"],
                    config["primary_attack_strength"],
                    config["hq_seed_ids"],
                    config["onoff_attack_blocks"],
                    config["mature_attack_task"],
                )
                totals = {"QE": [0, 0], "PRTD": [0, 0]}
                active_tasks = active_evaluation_tasks(mode)
                for task in replay.tasks:
                    if task.task_id not in active_tasks:
                        continue
                    active = np.asarray([report.attack_active for report in task.ordinary], dtype=bool)
                    if not np.any(active):
                        continue
                    qe_retained = qe_retained_mask(scaler.transform(task.report_matrix))
                    malicious_total = int(np.count_nonzero(active))
                    totals["QE"][0] += int(np.count_nonzero(active & qe_retained))
                    totals["QE"][1] += malicious_total
                    # PRTD has no hard rejection stage: every submitted report
                    # enters its reliability-weighted truth aggregation.
                    totals["PRTD"][0] += malicious_total
                    totals["PRTD"][1] += malicious_total

                for method, (retained, total) in totals.items():
                    if total == 0:
                        raise AssertionError((workload.key, seed, mode, method))
                    rows.append({
                        "method": method,
                        "scene": workload.scene,
                        "target_workers": workload.target_workers,
                        "seed": int(seed),
                        "mode": mode,
                        "malicious_ratio": float(config["mode_ratio"]),
                        "strength": float(config["primary_attack_strength"]),
                        "malicious_retained": int(retained),
                        "malicious_total": int(total),
                        "malicious_report_leakage": float(retained / total),
                    })
        print(f"leakage replay: finished {workload.key}", flush=True)

    frame = pd.DataFrame(rows)
    expected = 3 * len(config["random_seeds"]) * len(modes) * 2
    if len(frame) != expected:
        raise AssertionError((len(frame), expected))
    results = ROOT / "results"
    results.mkdir(parents=True, exist_ok=True)
    output_path = results / "rq3_baseline_leakage_seed_scene.csv"
    frame.to_csv(output_path, index=False)

    legacy_qe = resolve_config_path(config, "baseline_root") / "QE" / "main_system.py"
    manifest = {
        "elapsed_s": time.time() - started,
        "rows": len(frame),
        "seeds": config["random_seeds"],
        "modes": modes,
        "methods": ["QE", "PRTD"],
        "definition": "retained active malicious reports / all active malicious reports",
        "prtd_interpretation": "all reports retained because PRTD has no hard filtering stage",
        "python": sys.version,
        "platform": platform.platform(),
        "source_sha256": {
            "run_mode_leakage_baselines.py": file_hash(Path(__file__)),
            "rq3_data.py": file_hash(ROOT / "src" / "rq3_data.py"),
            "legacy_qe_main_system.py": file_hash(legacy_qe),
        },
    }
    (ROOT / "metadata" / "run_mode_leakage_baselines.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
