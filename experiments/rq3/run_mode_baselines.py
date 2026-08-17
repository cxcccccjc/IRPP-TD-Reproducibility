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
from src.rq3_baselines import RQ3Baselines
from src.rq3_data import calibration_directions, load_scalers, load_workloads, make_replay, resolve_config_path


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
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    seeds = config["random_seeds"][:1] if args.quick else config["random_seeds"]
    seeds = [seed for idx, seed in enumerate(seeds) if idx % args.shard_count == args.shard_index]
    all_workloads = load_workloads(config)
    workloads = {
        key: value for key, value in all_workloads.items() if value.target_workers == 27
    }
    scalers = load_scalers(config)
    directions = calibration_directions(all_workloads, scalers, config["calibration_tasks"])
    parameters = Parameters()
    baselines = RQ3Baselines(
        resolve_config_path(config, "baseline_root"), parameters.epsilon, parameters.max_iterations
    )

    modes = ["clean", "independent", "compact", "onoff", "mature_anchor"]
    methods = [method for method in config["baseline_methods"] if method != "IRPP-TD"]
    rows: list[dict] = []
    started = time.time()

    for workload in workloads.values():
        for seed in seeds:
            for mode in modes:
                ratio = 0.0 if mode == "clean" else config["mode_ratio"]
                replay = make_replay(
                    workload,
                    scalers[workload.scene],
                    directions[workload.scene],
                    seed,
                    mode,
                    ratio,
                    config["primary_attack_strength"],
                    config["hq_seed_ids"],
                    config["onoff_attack_blocks"],
                    config["mature_attack_task"],
                )
                for method in methods:
                    result = baselines.run(method, replay, scalers[workload.scene])
                    rows.extend({"experiment_group": "mode_baseline", **row} for row in result)
        print(
            f"mode-baseline shard {args.shard_index}: finished {workload.key} "
            f"({len(seeds)} seeds)",
            flush=True,
        )

    results = ROOT / "results"
    results.mkdir(parents=True, exist_ok=True)
    metadata = ROOT / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    suffix = "quick" if args.quick else f"shard_{args.shard_index:02d}_of_{args.shard_count:02d}"
    output_path = results / f"tasks_mode_baselines_{suffix}.csv.gz"
    pd.DataFrame(rows).to_csv(output_path, index=False, compression="gzip")

    manifest = {
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "quick": args.quick,
        "seeds": seeds,
        "elapsed_s": time.time() - started,
        "task_rows": len(rows),
        "modes": modes,
        "methods": methods,
        "python": sys.version,
        "platform": platform.platform(),
        "source_sha256": {
            path.name: file_hash(path)
            for path in [
                ROOT / "src" / "rq3_data.py",
                ROOT / "src" / "rq3_baselines.py",
                ROOT / "run_mode_baselines.py",
            ]
        },
    }
    (metadata / f"run_mode_baselines_{suffix}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
