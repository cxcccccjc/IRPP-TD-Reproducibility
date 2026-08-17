from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.core_base import Parameters
from src.rq3_data import calibration_directions, load_scalers, load_workloads, make_replay
from src.rq3_model import run_irpp_replay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    seeds = [seed for index, seed in enumerate(config["random_seeds"]) if index % args.shard_count == args.shard_index]
    workloads = load_workloads(config)
    scalers = load_scalers(config)
    directions = calibration_directions(workloads, scalers, config["calibration_tasks"])
    rows = []
    for workload in [workloads["Climate_n27"], workloads["Traffic_n27"], workloads["Water_n27"]]:
        for seed in seeds:
            for ratio in config["attack_ratios"]:
                for strength in config["attack_strengths"]:
                    replay = make_replay(
                        workload, scalers[workload.scene], directions[workload.scene], seed, "mature_anchor", ratio,
                        strength, config["hq_seed_ids"], config["onoff_attack_blocks"], config["mature_attack_task"],
                    )
                    result = run_irpp_replay(replay, scalers[workload.scene], Parameters(), "Full", keep_reports=False)
                    rows.extend({"experiment_group": "mature_grid", **row} for row in result.task_records)
        print(f"mature-grid shard {args.shard_index}: finished {workload.scene}", flush=True)
    output = ROOT / "results" / f"tasks_mature_grid_shard_{args.shard_index:02d}_of_{args.shard_count:02d}.csv.gz"
    pd.DataFrame(rows).to_csv(output, index=False, compression="gzip")
    print(f"wrote {output} ({len(rows)} rows)", flush=True)


if __name__ == "__main__":
    main()
