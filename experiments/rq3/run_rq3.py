from __future__ import annotations

import argparse
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

from src.core_base import Parameters
from src.rq3_baselines import RQ3Baselines
from src.rq3_data import calibration_directions, load_scalers, load_workloads, make_replay, resolve_config_path
from src.rq3_model import run_irpp_replay


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay_key(workload, seed, mode, ratio, strength):
    return (workload.key, int(seed), mode, round(float(ratio), 8), round(float(strength), 8))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    seeds = config["random_seeds"]
    if args.quick:
        seeds = seeds[:1]
    seeds = [seed for idx, seed in enumerate(seeds) if idx % args.shard_count == args.shard_index]
    workloads = load_workloads(config)
    scalers = load_scalers(config)
    directions = calibration_directions(workloads, scalers, config["calibration_tasks"])
    parameters = Parameters()
    baselines = RQ3Baselines(resolve_config_path(config, "baseline_root"), parameters.epsilon, parameters.max_iterations)
    task_rows: list[dict] = []
    report_rows: list[dict] = []
    completed: set[tuple] = set()
    completed_reports: set[tuple] = set()
    started_all = time.time()

    def construct(workload, seed, mode, ratio, strength):
        return make_replay(
            workload,
            scalers[workload.scene],
            directions[workload.scene],
            seed,
            mode,
            ratio,
            strength,
            config["hq_seed_ids"],
            config["onoff_attack_blocks"],
            config["mature_attack_task"],
        )

    def run_irpp(workload, seed, mode, ratio, strength, variant="Full", group=""):
        key = ("IRPP-TD", variant, *replay_key(workload, seed, mode, ratio, strength))
        keep_reports = group in {"mode", "feedback"}
        if key in completed and (not keep_reports or key in completed_reports):
            return
        replay = construct(workload, seed, mode, ratio, strength)
        result = run_irpp_replay(replay, scalers[workload.scene], parameters, variant, keep_reports=keep_reports)
        if key not in completed:
            task_rows.extend({"experiment_group": group, **row} for row in result.task_records)
        report_rows.extend({"experiment_group": group, **row} for row in result.report_records)
        completed.add(key)
        if keep_reports:
            completed_reports.add(key)

    def run_baseline(workload, seed, mode, ratio, strength, method, group=""):
        key = (method, method, *replay_key(workload, seed, mode, ratio, strength))
        if key in completed:
            return
        replay = construct(workload, seed, mode, ratio, strength)
        rows = baselines.run(method, replay, scalers[workload.scene])
        task_rows.extend({"experiment_group": group, **row} for row in rows)
        completed.add(key)

    for workload in workloads.values():
        for seed in seeds:
            # A: primary compact-collusion prevalence, n=27 and n=39.
            for ratio in config["attack_ratios"]:
                run_irpp(workload, seed, "compact", ratio, config["primary_attack_strength"], group="prevalence")
                for method in config["baseline_methods"]:
                    if method != "IRPP-TD":
                        run_baseline(workload, seed, "compact", ratio, config["primary_attack_strength"], method, "prevalence")

            if workload.target_workers != 27:
                continue

            # B: IRPP prevalence-strength plane. The kappa=.5 cells reuse A.
            for ratio in config["attack_ratios"]:
                for strength in config["attack_strengths"]:
                    run_irpp(workload, seed, "compact", ratio, strength, group="strength")

            # C: matched attack modes at rho=.3, kappa=.5; compact reuses A.
            for mode in ["clean", "independent", "compact", "onoff", "mature_anchor"]:
                ratio = 0.0 if mode == "clean" else config["mode_ratio"]
                run_irpp(workload, seed, mode, ratio, config["primary_attack_strength"], group="mode")

            # D: reputation/anchor feedback variants under delayed poisoning.
            for variant in config["supplement_variants"]:
                run_irpp(
                    workload,
                    seed,
                    "mature_anchor",
                    config["mode_ratio"],
                    config["primary_attack_strength"],
                    variant=variant,
                    group="feedback",
                )

        print(f"shard {args.shard_index}: finished {workload.key} ({len(seeds)} seeds)", flush=True)

    results = ROOT / "results"
    results.mkdir(parents=True, exist_ok=True)
    suffix = "quick" if args.quick else f"shard_{args.shard_index:02d}_of_{args.shard_count:02d}"
    pd.DataFrame(task_rows).to_csv(results / f"tasks_{suffix}.csv.gz", index=False, compression="gzip")
    pd.DataFrame(report_rows).to_csv(results / f"reports_{suffix}.csv.gz", index=False, compression="gzip")
    manifest = {
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "quick": args.quick,
        "seeds": seeds,
        "elapsed_s": time.time() - started_all,
        "task_rows": len(task_rows),
        "report_rows": len(report_rows),
        "python": sys.version,
        "platform": platform.platform(),
        "parameters": parameters.__dict__,
        "source_sha256": {
            path.name: file_hash(path)
            for path in [ROOT / "src" / "rq3_data.py", ROOT / "src" / "rq3_model.py", ROOT / "src" / "rq3_baselines.py"]
        },
    }
    (ROOT / "metadata" / f"run_{suffix}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
