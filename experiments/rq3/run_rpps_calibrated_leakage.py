from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.rq3_data import calibration_directions, load_scalers, load_workloads, make_replay, resolve_config_path
from src.rq3_rpps_calibrated import CalibratedRPPSTDCFilter


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError((args.shard_index, args.shard_count))

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    all_workloads = load_workloads(config)
    workloads = {key: value for key, value in all_workloads.items() if value.target_workers == 27}
    scalers = load_scalers(config)
    directions = calibration_directions(all_workloads, scalers, config["calibration_tasks"])
    seeds = config["random_seeds"][args.shard_index :: args.shard_count]
    modes = ["independent", "compact", "onoff", "mature_anchor"]
    adapter = CalibratedRPPSTDCFilter(resolve_config_path(config, "baseline_root"))
    task_rows: list[dict] = []
    calibration_rows: list[dict] = []
    started = time.time()

    for workload in workloads.values():
        scaler = scalers[workload.scene]
        direction = directions[workload.scene]
        for seed in seeds:
            clean = make_replay(
                workload,
                scaler,
                direction,
                seed,
                "clean",
                0.0,
                config["primary_attack_strength"],
                config["hq_seed_ids"],
                config["onoff_attack_blocks"],
                config["mature_attack_task"],
            )
            # RPPS-TDC already declares p=0.3 as its native hard-screening
            # threshold.  Keep that source setting fixed and measure its clean
            # collateral cost; no attack result is used to choose p.
            calibration = adapter.evaluate_fixed_threshold(clean, args.threshold)
            calibration_rows.append(
                {
                    "method": "RPPS-TDC",
                    "scene": workload.scene,
                    "target_workers": workload.target_workers,
                    "seed": int(seed),
                    "calibration_tasks": int(config["calibration_tasks"]),
                    "threshold_policy": calibration.policy,
                    "gate_threshold": calibration.threshold,
                    "clean_acceptance": calibration.clean_acceptance,
                    "clean_retained": calibration.clean_retained,
                    "clean_total": calibration.clean_total,
                }
            )
            for mode in modes:
                replay = make_replay(
                    workload,
                    scaler,
                    direction,
                    seed,
                    mode,
                    config["mode_ratio"],
                    config["primary_attack_strength"],
                    config["hq_seed_ids"],
                    config["onoff_attack_blocks"],
                    config["mature_attack_task"],
                )
                task_rows.extend(adapter.run(replay, calibration))
            print(
                f"RPPS-TDC: {workload.key}, seed={seed}, p={calibration.threshold:.5f}, "
                f"clean_acceptance={calibration.clean_acceptance:.4f}",
                flush=True,
            )

    results = ROOT / "results"
    metadata = ROOT / "metadata"
    results.mkdir(parents=True, exist_ok=True)
    metadata.mkdir(parents=True, exist_ok=True)
    suffix = f"shard_{args.shard_index:02d}_of_{args.shard_count:02d}"
    task_path = results / f"tasks_rpps_calibrated_{suffix}.csv.gz"
    calibration_path = results / f"calibration_rpps_calibrated_{suffix}.csv"
    pd.DataFrame(task_rows).to_csv(task_path, index=False, compression="gzip")
    pd.DataFrame(calibration_rows).to_csv(calibration_path, index=False)

    legacy = resolve_config_path(config, "baseline_root") / "RPPS-TDC"
    manifest = {
        "elapsed_s": time.time() - started,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "seeds": seeds,
        "workloads": list(workloads),
        "modes": modes,
        "task_rows": len(task_rows),
        "calibration_rows": len(calibration_rows),
        "native_threshold": args.threshold,
        "threshold_policy": "fixed p from retained RPPS-TDC source",
        "clean_measurement_scope": "separate clean replay, tasks 1--20 only",
        "attack_scope": "frozen p, sequential tasks 1--100",
        "python": sys.version,
        "platform": platform.platform(),
        "source_sha256": {
            "run_rpps_calibrated_leakage.py": file_hash(Path(__file__)),
            "rq3_rpps_calibrated.py": file_hash(ROOT / "src" / "rq3_rpps_calibrated.py"),
            "legacy_truth_discovery.py": file_hash(legacy / "truth_discovery.py"),
            "legacy_reputation_update.py": file_hash(legacy / "reputation_update.py"),
        },
    }
    (metadata / f"run_rpps_calibrated_{suffix}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
