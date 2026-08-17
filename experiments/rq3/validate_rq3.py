from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def main() -> None:
    manifests = [json.loads(path.read_text()) for path in sorted((ROOT / "metadata").glob("run_shard_*_of_*.json"))]
    if len(manifests) != 6:
        raise AssertionError(f"expected 6 manifests, found {len(manifests)}")
    hashes = {json.dumps(item["source_sha256"], sort_keys=True) for item in manifests}
    if len(hashes) != 1:
        raise AssertionError("source hash mismatch across shards")
    task_files = sorted(RESULTS.glob("tasks_shard_*_of_*.csv.gz"))
    report_files = sorted(RESULTS.glob("reports_shard_*_of_*.csv.gz"))
    tasks = pd.concat([pd.read_csv(path, usecols=["method", "variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id", "no_truth", "task_nrmse"]) for path in task_files], ignore_index=True)
    reports = pd.concat([pd.read_csv(path, usecols=["variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id", "worker_id", "attack_active", "coalition_member", "retained"]) for path in report_files], ignore_index=True)
    mature = pd.concat([pd.read_csv(path, usecols=["scene", "seed", "malicious_ratio", "strength", "task_id", "no_truth", "task_nrmse"]) for path in sorted(RESULTS.glob("tasks_mature_grid_shard_*_of_*.csv.gz"))], ignore_index=True)
    mode_manifests = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "metadata").glob("run_mode_baselines_shard_*_of_*.json"))
    ]
    if len(mode_manifests) != 6:
        raise AssertionError(f"expected 6 mode-baseline manifests, found {len(mode_manifests)}")
    mode_hashes = {json.dumps(item["source_sha256"], sort_keys=True) for item in mode_manifests}
    if len(mode_hashes) != 1:
        raise AssertionError("mode-baseline source hash mismatch across shards")
    mode_files = sorted(RESULTS.glob("tasks_mode_baselines_shard_*_of_*.csv.gz"))
    mode_baselines = pd.concat(
        [
            pd.read_csv(
                path,
                usecols=[
                    "method", "variant", "scene", "target_workers", "seed", "mode",
                    "malicious_ratio", "strength", "task_id", "no_truth", "task_nrmse",
                ],
            )
            for path in mode_files
        ],
        ignore_index=True,
    )
    leakage_manifest_path = ROOT / "metadata" / "run_mode_leakage_baselines.json"
    if not leakage_manifest_path.exists():
        raise AssertionError("missing leakage replay manifest")
    leakage_manifest = json.loads(leakage_manifest_path.read_text())
    baseline_leakage = pd.read_csv(RESULTS / "rq3_baseline_leakage_seed_scene.csv")
    calibrated_manifests = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "metadata").glob("run_calibrated_baselines_shard_*_of_*.json"))
    ]
    if len(calibrated_manifests) != 6:
        raise AssertionError(f"expected 6 calibrated-baseline manifests, found {len(calibrated_manifests)}")
    calibrated_hashes = {json.dumps(item["source_sha256"], sort_keys=True) for item in calibrated_manifests}
    if len(calibrated_hashes) != 1:
        raise AssertionError("calibrated-baseline source hash mismatch")
    calibrated_files = sorted(RESULTS.glob("tasks_calibrated_baselines_shard_*_of_*.csv.gz"))
    calibrated = pd.concat([
        pd.read_csv(path, usecols=[
            "experiment_group", "method", "scene", "target_workers", "seed", "mode",
            "malicious_ratio", "strength", "task_id", "gate_threshold",
            "calibration_acceptance", "malicious_total", "malicious_retained",
            "honest_total", "honest_retained", "no_truth", "task_nrmse",
        ])
        for path in calibrated_files
    ], ignore_index=True)
    calibration_files = sorted(RESULTS.glob("calibration_calibrated_baselines_shard_*_of_*.csv"))
    calibrations = pd.concat([pd.read_csv(path) for path in calibration_files], ignore_index=True)
    rpps_manifests = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "metadata").glob("run_rpps_calibrated_shard_*_of_06.json"))
    ]
    if len(rpps_manifests) != 6:
        raise AssertionError(f"expected 6 RPPS-TDC manifests, found {len(rpps_manifests)}")
    rpps_hashes = {json.dumps(item["source_sha256"], sort_keys=True) for item in rpps_manifests}
    if len(rpps_hashes) != 1:
        raise AssertionError("RPPS-TDC source hash mismatch")
    rpps_files = sorted(RESULTS.glob("tasks_rpps_calibrated_shard_*_of_06.csv.gz"))
    rpps = pd.concat([
        pd.read_csv(path, usecols=[
            "method", "variant", "scene", "target_workers", "seed", "mode",
            "malicious_ratio", "strength", "task_id", "gate_threshold",
            "calibration_acceptance", "malicious_total", "malicious_retained",
            "honest_total", "honest_retained",
        ])
        for path in rpps_files
    ], ignore_index=True)
    rpps_calibration_files = sorted(
        RESULTS.glob("calibration_rpps_calibrated_shard_*_of_06.csv")
    )
    rpps_calibrations = pd.concat(
        [pd.read_csv(path) for path in rpps_calibration_files], ignore_index=True
    )
    if len(tasks) != 1_044_000 or len(reports) != 2_226_690 or len(mature) != 405_000:
        raise AssertionError((len(tasks), len(reports), len(mature)))
    if len(mode_baselines) != 135_000:
        raise AssertionError(f"expected 135000 mode-baseline rows, found {len(mode_baselines)}")
    if len(baseline_leakage) != 720 or leakage_manifest.get("rows") != 720:
        raise AssertionError(f"expected 720 baseline-leakage rows, found {len(baseline_leakage)}")
    if len(calibrated) != 414_000 or len(calibrations) != 180:
        raise AssertionError((len(calibrated), len(calibrations)))
    if len(rpps) != 36_000 or len(rpps_calibrations) != 90:
        raise AssertionError((len(rpps), len(rpps_calibrations)))
    if sorted(tasks.seed.unique()) != list(range(20260808, 20260838)):
        raise AssertionError("seed coverage mismatch")
    task_key = ["method", "variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id"]
    report_key = ["variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id", "worker_id"]
    if tasks.duplicated(task_key).any() or reports.duplicated(report_key).any():
        raise AssertionError("duplicate replay rows")
    if mode_baselines.duplicated(task_key).any():
        raise AssertionError("duplicate mode-baseline replay rows")
    leakage_key = ["method", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength"]
    if baseline_leakage.duplicated(leakage_key).any():
        raise AssertionError("duplicate baseline-leakage replay rows")
    if sorted(baseline_leakage.seed.unique()) != list(range(20260808, 20260838)):
        raise AssertionError("baseline-leakage seed coverage mismatch")
    if set(baseline_leakage.method.unique()) != {"QE", "PRTD"}:
        raise AssertionError("baseline-leakage method mismatch")
    if not baseline_leakage.malicious_report_leakage.between(0.0, 1.0).all():
        raise AssertionError("baseline-leakage rate outside [0,1]")
    if not np.allclose(
        baseline_leakage.loc[baseline_leakage.method == "PRTD", "malicious_report_leakage"], 1.0
    ):
        raise AssertionError("PRTD hard-retention interpretation mismatch")
    if not np.allclose(
        baseline_leakage.loc[baseline_leakage.method == "QE", "malicious_report_leakage"], 1.0
    ):
        raise AssertionError("unexpected QE retention result at the primary point")
    calibrated_key = [
        "experiment_group", "method", "scene", "target_workers", "seed", "mode",
        "malicious_ratio", "strength", "task_id",
    ]
    if calibrated.duplicated(calibrated_key).any():
        raise AssertionError("duplicate calibrated-baseline task rows")
    if sorted(calibrated.seed.unique()) != list(range(20260808, 20260838)):
        raise AssertionError("calibrated-baseline seed coverage mismatch")
    if set(calibrated.method.unique()) != {"QE", "PRTD"}:
        raise AssertionError("calibrated-baseline method mismatch")
    if not calibrations.qe_clean_acceptance.between(.95, .97).all():
        raise AssertionError("QE clean calibration acceptance outside tolerance")
    if not calibrations.prtd_clean_acceptance.between(.95, .97).all():
        raise AssertionError("PRTD clean calibration acceptance outside tolerance")
    if not ((calibrations.qe_radius > 0).all() and (calibrations.prtd_relative_weight > 0).all()):
        raise AssertionError("nonpositive calibrated gate")
    if calibrated.loc[~calibrated.no_truth.astype(bool), "task_nrmse"].isna().any():
        raise AssertionError("calibrated baseline returned task without finite NRMSE")
    active = calibrated.loc[
        (calibrated.experiment_group == "mode") & (calibrated.malicious_total > 0)
    ]
    leakage = active.groupby(["method", "mode"], as_index=False)[
        ["malicious_retained", "malicious_total"]
    ].sum()
    leakage["rate"] = leakage.malicious_retained / leakage.malicious_total
    if (leakage.rate >= .999).all():
        raise AssertionError("calibrated leakage remains degenerate")
    rpps_key = [
        "method", "variant", "scene", "target_workers", "seed", "mode",
        "malicious_ratio", "strength", "task_id",
    ]
    if rpps.duplicated(rpps_key).any():
        raise AssertionError("duplicate RPPS-TDC screening rows")
    if sorted(rpps.seed.unique()) != list(range(20260808, 20260838)):
        raise AssertionError("RPPS-TDC seed coverage mismatch")
    if set(rpps.method.unique()) != {"RPPS-TDC"}:
        raise AssertionError("RPPS-TDC method label mismatch")
    if not np.allclose(rpps.gate_threshold, .3):
        raise AssertionError("RPPS-TDC native p changed")
    if not np.allclose(rpps_calibrations.gate_threshold, .3):
        raise AssertionError("RPPS-TDC threshold record changed")
    if set(rpps_calibrations.threshold_policy.unique()) != {"native-fixed"}:
        raise AssertionError("RPPS-TDC threshold policy mismatch")
    if not rpps_calibrations.clean_acceptance.between(0.0, 1.0).all():
        raise AssertionError("RPPS-TDC clean acceptance outside [0,1]")
    rpps_active = rpps.loc[rpps.malicious_total > 0].groupby(
        ["mode"], as_index=False
    )[["malicious_retained", "malicious_total"]].sum()
    rpps_active["rate"] = rpps_active.malicious_retained / rpps_active.malicious_total
    if not rpps_active.rate.between(0.0, 1.0).all() or rpps_active.rate.nunique() <= 1:
        raise AssertionError("RPPS-TDC leakage is invalid or degenerate")
    compact_keys = ["method", "variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id"]
    formal_compact = tasks.loc[
        (tasks.method != "IRPP-TD") & (tasks.target_workers == 27)
        & (tasks["mode"] == "compact") & np.isclose(tasks.malicious_ratio, .3)
        & np.isclose(tasks.strength, .5),
        compact_keys + ["task_nrmse"],
    ]
    replay_compact = mode_baselines.loc[
        (mode_baselines["mode"] == "compact") & np.isclose(mode_baselines.malicious_ratio, .3)
        & np.isclose(mode_baselines.strength, .5),
        compact_keys + ["task_nrmse"],
    ]
    compact_check = formal_compact.merge(
        replay_compact, on=compact_keys, suffixes=("_formal", "_mode"), validate="one_to_one"
    )
    if len(compact_check) != len(formal_compact) or not np.allclose(
        compact_check.task_nrmse_formal, compact_check.task_nrmse_mode, equal_nan=True
    ):
        raise AssertionError("mode-baseline compact replay differs from prevalence replay")
    if tasks.loc[~tasks.no_truth.astype(bool), "task_nrmse"].isna().any():
        raise AssertionError("returned task without finite NRMSE")
    if reports.loc[reports.attack_active.astype(bool), "coalition_member"].eq(False).any():
        raise AssertionError("active poison outside coalition")
    audit = {
        "status": "passed",
        "formal_shards": len(manifests),
        "source_hash_consistent": True,
        "task_rows": len(tasks),
        "report_rows": len(reports),
        "mature_grid_rows": len(mature),
        "mode_baseline_task_rows": len(mode_baselines),
        "mode_baseline_source_hash_consistent": True,
        "mode_compact_replay_matches_prevalence": True,
        "baseline_leakage_rows": len(baseline_leakage),
        "baseline_leakage_seed_count": int(baseline_leakage.seed.nunique()),
        "baseline_leakage_key_unique": True,
        "baseline_leakage_rates_bounded": True,
        "prtd_all_reports_retained": True,
        "qe_all_primary_attack_reports_retained": True,
        "calibrated_baseline_task_rows": len(calibrated),
        "calibration_rows": len(calibrations),
        "calibrated_source_hash_consistent": True,
        "calibrated_task_key_unique": True,
        "calibrated_acceptance_target": 0.96,
        "calibrated_acceptance_within_tolerance": True,
        "calibrated_leakage_non_degenerate": True,
        "rpps_screening_task_rows": len(rpps),
        "rpps_threshold_rows": len(rpps_calibrations),
        "rpps_source_hash_consistent": True,
        "rpps_task_key_unique": True,
        "rpps_native_threshold": 0.3,
        "rpps_clean_acceptance_macro": float(
            rpps_calibrations.groupby("seed").clean_acceptance.mean().mean()
        ),
        "rpps_leakage_non_degenerate": True,
        "seed_count": int(tasks.seed.nunique()),
        "task_key_unique": True,
        "report_key_unique": True,
        "returned_metrics_finite": True,
        "max_no_truth_rate_main": float(tasks.no_truth.mean()),
        "max_no_truth_rate_mature_grid": float(mature.no_truth.mean()),
        "active_poison_implies_coalition": True,
    }
    (ROOT / "metadata" / "integrity_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
