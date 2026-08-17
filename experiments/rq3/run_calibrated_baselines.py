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

from src.core_base import Parameters
from src.rq3_calibrated_baselines import CalibratedBaselineGates
from src.rq3_data import calibration_directions, load_scalers, load_workloads, make_replay, resolve_config_path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay_for(workload, scaler, direction, seed, mode, ratio, config):
    return make_replay(
        workload,
        scaler,
        direction,
        seed,
        mode,
        ratio,
        config["primary_attack_strength"],
        config["hq_seed_ids"],
        config["onoff_attack_blocks"],
        config["mature_attack_task"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--modes-only", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    seeds = config["random_seeds"][:1] if args.quick else config["random_seeds"]
    seeds = [seed for idx, seed in enumerate(seeds) if idx % args.shard_count == args.shard_index]
    workloads = load_workloads(config)
    scalers = load_scalers(config)
    directions = calibration_directions(workloads, scalers, config["calibration_tasks"])
    params = Parameters()
    gates = CalibratedBaselineGates(
        resolve_config_path(config, "baseline_root"), params.epsilon, params.max_iterations
    )
    target_acceptance = 0.96
    task_rows: list[dict] = []
    calibration_rows: list[dict] = []
    started = time.time()

    for workload in workloads.values():
        if args.modes_only and workload.target_workers != 27:
            continue
        scaler = scalers[workload.scene]
        direction = directions[workload.scene]
        for seed in seeds:
            clean = replay_for(workload, scaler, direction, seed, "clean", 0.0, config)
            calibration = gates.calibrate(clean, scaler, target_acceptance)
            calibration_rows.append({
                "workload": workload.key,
                "scene": workload.scene,
                "target_workers": workload.target_workers,
                "seed": seed,
                **calibration.__dict__,
            })

            experiments = []
            if not args.modes_only:
                experiments.extend(
                    ("prevalence", "compact", float(ratio))
                    for ratio in config["attack_ratios"]
                )
            if workload.target_workers == 27:
                experiments.extend([
                    ("mode", "clean", 0.0),
                    ("mode", "independent", config["mode_ratio"]),
                    ("mode", "compact", config["mode_ratio"]),
                    ("mode", "onoff", config["mode_ratio"]),
                    ("mode", "mature_anchor", config["mode_ratio"]),
                ])

            for group, mode, ratio in experiments:
                replay = replay_for(workload, scaler, direction, seed, mode, ratio, config)
                for method in ["PRTD", "QE"]:
                    rows = gates.run(method, replay, scaler, calibration)
                    task_rows.extend({"experiment_group": group, **row} for row in rows)
        print(
            f"calibrated shard {args.shard_index}: finished {workload.key} ({len(seeds)} seeds)",
            flush=True,
        )

    results = ROOT / "results"
    metadata = ROOT / "metadata"
    results.mkdir(parents=True, exist_ok=True)
    metadata.mkdir(parents=True, exist_ok=True)
    suffix = "quick" if args.quick else f"shard_{args.shard_index:02d}_of_{args.shard_count:02d}"
    if args.modes_only:
        suffix += "_modes"
    pd.DataFrame(task_rows).to_csv(
        results / f"tasks_calibrated_baselines_{suffix}.csv.gz", index=False, compression="gzip"
    )
    pd.DataFrame(calibration_rows).to_csv(
        results / f"calibration_calibrated_baselines_{suffix}.csv", index=False
    )
    manifest = {
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "quick": args.quick,
        "modes_only": args.modes_only,
        "seeds": seeds,
        "target_clean_acceptance": target_acceptance,
        "task_rows": len(task_rows),
        "calibration_rows": len(calibration_rows),
        "elapsed_s": time.time() - started,
        "python": sys.version,
        "platform": platform.platform(),
        "source_sha256": {
            p.name: file_hash(p)
            for p in [
                ROOT / "src" / "rq3_data.py",
                ROOT / "src" / "rq3_calibrated_baselines.py",
                ROOT / "run_calibrated_baselines.py",
            ]
        },
    }
    (metadata / f"run_calibrated_baselines_{suffix}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
