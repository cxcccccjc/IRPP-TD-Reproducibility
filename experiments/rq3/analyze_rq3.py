from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 20260809


def load_formal(prefix: str, columns: list[str]) -> pd.DataFrame:
    files = sorted(RESULTS.glob(f"{prefix}_shard_*_of_*.csv.gz"))
    if not files:
        raise FileNotFoundError(f"No formal {prefix} shards")
    return pd.concat([pd.read_csv(path, usecols=columns) for path in files], ignore_index=True)


def aggregate_errors(frame: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    valid = frame.loc[~frame.no_truth.astype(bool)]
    sums = valid.groupby(group, as_index=False).agg(
        norm_sq_sum=("norm_sq_sum", "sum"),
        sq_sum=("sq_sum", "sum"),
        norm_abs_sum=("norm_abs_sum", "sum"),
        abs_sum=("abs_sum", "sum"),
        dimension=("dimension", "sum"),
    )
    totals = frame.groupby(group, as_index=False).agg(tasks=("task_id", "size"), no_truth_count=("no_truth", "sum"))
    output = totals.merge(sums, how="left", on=group)
    output["nrmse"] = np.sqrt(output.norm_sq_sum / output.dimension)
    output["rmse"] = np.sqrt(output.sq_sum / output.dimension)
    output["nmae"] = output.norm_abs_sum / output.dimension
    output["mae"] = output.abs_sum / output.dimension
    output["no_truth_rate"] = output.no_truth_count / output.tasks
    return output


def seed_ci(frame: pd.DataFrame, group: list[str], value: str) -> pd.DataFrame:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    for keys, part in frame.groupby(group, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        values = part.groupby("seed")[value].mean().sort_index().to_numpy(float)
        point = float(np.mean(values))
        draws = values[rng.integers(0, len(values), size=(BOOTSTRAP_REPETITIONS, len(values)))].mean(axis=1)
        row = dict(zip(group, keys))
        row.update({value: point, f"{value}_ci_low": float(np.quantile(draws, .025)), f"{value}_ci_high": float(np.quantile(draws, .975)), "seeds": len(values)})
        rows.append(row)
    return pd.DataFrame(rows)


def active_ids(mode: str) -> set[int]:
    if mode in {"independent", "compact", "clean"}:
        return set(range(21, 101))
    if mode == "onoff":
        return set(range(21, 31)) | set(range(41, 51)) | set(range(61, 71)) | set(range(81, 91))
    if mode == "mature_anchor":
        return set(range(41, 101))
    raise ValueError(mode)


def main() -> None:
    task_columns = [
        "method", "variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength",
        "task_id", "dimension", "no_truth", "norm_sq_sum", "sq_sum", "norm_abs_sum", "abs_sum",
        "ordinary_anchor_purity", "malicious_report_leakage", "honest_false_low_rate",
    ]
    report_columns = [
        "variant", "scene", "target_workers", "seed", "mode", "malicious_ratio", "strength", "task_id",
        "coalition_member", "attack_active", "retained", "predicted_low", "anchor_before",
    ]
    tasks = load_formal("tasks", task_columns)
    reports = load_formal("reports", report_columns)
    mode_baseline_files = sorted(RESULTS.glob("tasks_mode_baselines_shard_*_of_*.csv.gz"))
    if not mode_baseline_files:
        raise FileNotFoundError("No formal attack-mode baseline shards")
    mode_baseline_columns = [
        "method", "variant", "scene", "target_workers", "seed", "mode",
        "malicious_ratio", "strength", "task_id", "dimension", "no_truth",
        "norm_sq_sum", "sq_sum", "norm_abs_sum", "abs_sum",
    ]
    mode_baselines = pd.concat(
        [pd.read_csv(path, usecols=mode_baseline_columns) for path in mode_baseline_files],
        ignore_index=True,
    )
    calibrated_columns = [
        "experiment_group", "method", "variant", "scene", "target_workers", "seed", "mode",
        "malicious_ratio", "strength", "task_id", "gate_threshold", "calibration_acceptance",
        "malicious_total", "malicious_retained", "honest_total", "honest_retained",
        "dimension", "no_truth", "norm_sq_sum", "sq_sum", "norm_abs_sum", "abs_sum",
    ]
    calibrated = load_formal("tasks_calibrated_baselines", calibrated_columns)
    calibration_files = sorted(RESULTS.glob("calibration_calibrated_baselines_shard_*_of_*.csv"))
    if not calibration_files:
        raise FileNotFoundError("No formal clean-calibration summaries")
    calibrations = pd.concat([pd.read_csv(path) for path in calibration_files], ignore_index=True)
    rpps_task_files = sorted(RESULTS.glob("tasks_rpps_calibrated_shard_*_of_06.csv.gz"))
    rpps_calibration_files = sorted(RESULTS.glob("calibration_rpps_calibrated_shard_*_of_06.csv"))
    if len(rpps_task_files) != 6 or len(rpps_calibration_files) != 6:
        raise FileNotFoundError("Expected six formal RPPS-TDC screening shards")
    rpps_columns = [
        "method", "variant", "scene", "target_workers", "seed", "mode",
        "malicious_ratio", "strength", "task_id", "gate_threshold",
        "calibration_acceptance", "malicious_total", "malicious_retained",
        "honest_total", "honest_retained",
    ]
    rpps_tasks = pd.concat(
        [pd.read_csv(path, usecols=rpps_columns) for path in rpps_task_files],
        ignore_index=True,
    )
    rpps_calibrations = pd.concat(
        [pd.read_csv(path) for path in rpps_calibration_files], ignore_index=True
    )
    for column in ["ordinary_anchor_purity", "malicious_report_leakage", "honest_false_low_rate"]:
        tasks[column] = pd.to_numeric(tasks[column], errors="coerce")

    irpp_calibration = reports.loc[
        (reports.variant == "Full") & (reports.target_workers == 27)
        & (reports["mode"] == "clean") & np.isclose(reports.malicious_ratio, 0.0)
        & reports.task_id.between(1, 20)
    ].groupby(["scene", "seed"], as_index=False).retained.mean().rename(
        columns={"retained": "clean_report_acceptance"}
    )
    irpp_calibration_macro = irpp_calibration.groupby("seed", as_index=False).clean_report_acceptance.mean()
    irpp_calibration_macro["scope"] = "IRPP-TD"
    irpp_calibration_summary = seed_ci(
        irpp_calibration_macro, ["scope"], "clean_report_acceptance"
    )

    # Fig. 3a and the n=39 replication.
    prevalence = tasks.loc[
        (tasks["mode"] == "compact") & np.isclose(tasks.strength, .5) & tasks.task_id.between(21, 100)
        & tasks.method.isin(["IRPP-TD", "CRH-N", "PRTD", "QE"])
    ]
    prevalence_seed_scene = aggregate_errors(
        prevalence,
        ["method", "target_workers", "malicious_ratio", "scene", "seed"],
    )
    prevalence_macro = prevalence_seed_scene.groupby(
        ["method", "target_workers", "malicious_ratio", "seed"], as_index=False
    )[["nrmse", "no_truth_rate"]].mean()
    prevalence_summary = seed_ci(prevalence_macro, ["method", "target_workers", "malicious_ratio"], "nrmse")
    prevalence_nt = seed_ci(prevalence_macro, ["method", "target_workers", "malicious_ratio"], "no_truth_rate")
    prevalence_summary = prevalence_summary.merge(prevalence_nt, on=["method", "target_workers", "malicious_ratio", "seeds"])

    # Fig. 3b: the harder delayed mature-anchor prevalence-strength surface.
    mature_files = sorted(RESULTS.glob("tasks_mature_grid_shard_*_of_*.csv.gz"))
    if not mature_files:
        raise FileNotFoundError("No mature-anchor grid shards")
    mature_columns = ["malicious_ratio", "strength", "scene", "seed", "task_id", "dimension", "no_truth", "norm_sq_sum", "sq_sum", "norm_abs_sum", "abs_sum"]
    strength = pd.concat([pd.read_csv(path, usecols=mature_columns) for path in mature_files], ignore_index=True)
    strength = strength.loc[strength.task_id.between(41, 100)]
    strength_seed_scene = aggregate_errors(strength, ["malicious_ratio", "strength", "scene", "seed"])
    clean = strength_seed_scene.loc[np.isclose(strength_seed_scene.malicious_ratio, 0.0), ["scene", "seed", "nrmse"]].copy()
    clean = clean.groupby(["scene", "seed"], as_index=False).nrmse.mean().rename(columns={"nrmse": "clean_nrmse"})
    strength_seed_scene = strength_seed_scene.merge(clean, on=["scene", "seed"])
    strength_seed_scene["error_ratio"] = strength_seed_scene.nrmse / strength_seed_scene.clean_nrmse
    strength_macro = strength_seed_scene.groupby(["malicious_ratio", "strength", "seed"], as_index=False)[["error_ratio", "no_truth_rate"]].mean()
    strength_summary = seed_ci(strength_macro, ["malicious_ratio", "strength"], "error_ratio")
    strength_nt = seed_ci(strength_macro, ["malicious_ratio", "strength"], "no_truth_rate")
    strength_summary = strength_summary.merge(strength_nt, on=["malicious_ratio", "strength", "seeds"])
    strength_summary["operational_failure"] = (
        (strength_summary.error_ratio >= 5.0) | (strength_summary.no_truth_rate > .05)
    )

    # Fig. 3c: active-task accuracy plus report-level leakage and false-low rate.
    mode_task_parts = []
    mode_report_parts = []
    for mode in ["clean", "independent", "compact", "onoff", "mature_anchor"]:
        ids = active_ids(mode)
        mode_task_parts.append(tasks.loc[
            (tasks.method == "IRPP-TD") & (tasks.variant == "Full") & (tasks.target_workers == 27)
            & (tasks["mode"] == mode) & tasks.task_id.isin(ids)
            & np.isclose(tasks.malicious_ratio, 0.0 if mode == "clean" else .3)
            & np.isclose(tasks.strength, .5)
        ])
        if mode != "clean":
            mode_report_parts.append(reports.loc[
                (reports.variant == "Full") & (reports.target_workers == 27) & (reports["mode"] == mode)
                & reports.task_id.isin(ids) & np.isclose(reports.malicious_ratio, .3) & np.isclose(reports.strength, .5)
            ])
    mode_tasks = pd.concat(mode_task_parts, ignore_index=True)
    mode_seed_scene = aggregate_errors(mode_tasks, ["mode", "scene", "seed"])
    ratio_rows = []
    for mode in ["independent", "compact", "onoff", "mature_anchor"]:
        attacked = mode_seed_scene.loc[mode_seed_scene["mode"] == mode].copy()
        control_rows = tasks.loc[
            (tasks.method == "IRPP-TD") & (tasks.variant == "Full") & (tasks.target_workers == 27)
            & (tasks["mode"] == "clean") & tasks.task_id.isin(active_ids(mode))
        ]
        control = aggregate_errors(control_rows, ["scene", "seed"])[["scene", "seed", "nrmse"]].rename(columns={"nrmse": "clean_nrmse"})
        attacked = attacked.merge(control, on=["scene", "seed"])
        attacked["error_ratio"] = attacked.nrmse / attacked.clean_nrmse
        ratio_rows.append(attacked)
    mode_metrics = pd.concat(ratio_rows, ignore_index=True)
    mode_reports = pd.concat(mode_report_parts, ignore_index=True)
    leakage = mode_reports.loc[mode_reports.attack_active.astype(bool)].groupby(["mode", "scene", "seed"], as_index=False).retained.mean().rename(columns={"retained": "malicious_report_leakage"})
    false_low = mode_reports.loc[~mode_reports.coalition_member.astype(bool)].groupby(["mode", "scene", "seed"], as_index=False).predicted_low.mean().rename(columns={"predicted_low": "honest_false_low_rate"})
    mode_metrics = mode_metrics.merge(leakage, on=["mode", "scene", "seed"]).merge(false_low, on=["mode", "scene", "seed"])
    mode_macro = mode_metrics.groupby(["mode", "seed"], as_index=False)[["error_ratio", "no_truth_rate", "malicious_report_leakage", "honest_false_low_rate"]].mean()
    mode_summary = None
    for value in ["error_ratio", "no_truth_rate", "malicious_report_leakage", "honest_false_low_rate"]:
        piece = seed_ci(mode_macro, ["mode"], value)
        mode_summary = piece if mode_summary is None else mode_summary.merge(piece, on=["mode", "seeds"])

    # Fig. 3c: hard-screening penetration.  IRPP-TD and RPPS-TDC use their
    # declared native decisions; PRTD uses its clean-only calibrated weight
    # gate because the retained PRTD source has no hard rejection output.
    irpp_leakage = leakage.copy()
    irpp_leakage.insert(0, "method", "IRPP-TD")
    calibrated_active = []
    for mode in ["independent", "compact", "onoff", "mature_anchor"]:
        calibrated_active.append(calibrated.loc[
            (calibrated.experiment_group == "mode") & (calibrated.target_workers == 27)
            & (calibrated["mode"] == mode) & calibrated.task_id.isin(active_ids(mode))
            & np.isclose(calibrated.malicious_ratio, .3) & np.isclose(calibrated.strength, .5)
            & (calibrated.method == "PRTD")
        ])
    calibrated_active = pd.concat(calibrated_active, ignore_index=True)
    calibrated_leakage = calibrated_active.groupby(
        ["method", "mode", "scene", "seed"], as_index=False
    )[["malicious_retained", "malicious_total"]].sum()
    calibrated_leakage["malicious_report_leakage"] = (
        calibrated_leakage.malicious_retained / calibrated_leakage.malicious_total
    )
    rpps_active = []
    for mode in ["independent", "compact", "onoff", "mature_anchor"]:
        rpps_active.append(rpps_tasks.loc[
            (rpps_tasks.target_workers == 27) & (rpps_tasks["mode"] == mode)
            & rpps_tasks.task_id.isin(active_ids(mode))
            & np.isclose(rpps_tasks.malicious_ratio, .3)
            & np.isclose(rpps_tasks.strength, .5)
        ])
    rpps_active = pd.concat(rpps_active, ignore_index=True)
    rpps_leakage = rpps_active.groupby(
        ["method", "mode", "scene", "seed"], as_index=False
    )[["malicious_retained", "malicious_total"]].sum()
    rpps_leakage["malicious_report_leakage"] = (
        rpps_leakage.malicious_retained / rpps_leakage.malicious_total
    )
    leakage_seed_scene = pd.concat(
        [
            irpp_leakage[["method", "mode", "scene", "seed", "malicious_report_leakage"]],
            calibrated_leakage[["method", "mode", "scene", "seed", "malicious_report_leakage"]],
            rpps_leakage[["method", "mode", "scene", "seed", "malicious_report_leakage"]],
        ],
        ignore_index=True,
    )
    leakage_macro = leakage_seed_scene.groupby(
        ["method", "mode", "seed"], as_index=False
    ).malicious_report_leakage.mean()
    leakage_method_summary = seed_ci(
        leakage_macro, ["method", "mode"], "malicious_report_leakage"
    )
    irpp_honest = mode_reports.loc[~mode_reports.coalition_member.astype(bool)].groupby(
        ["mode", "scene", "seed"], as_index=False
    ).retained.mean().rename(columns={"retained": "honest_report_acceptance"})
    irpp_honest.insert(0, "method", "IRPP-TD")
    calibrated_honest = calibrated_active.groupby(
        ["method", "mode", "scene", "seed"], as_index=False
    )[["honest_retained", "honest_total"]].sum()
    calibrated_honest["honest_report_acceptance"] = (
        calibrated_honest.honest_retained / calibrated_honest.honest_total
    )
    rpps_honest = rpps_active.groupby(
        ["method", "mode", "scene", "seed"], as_index=False
    )[["honest_retained", "honest_total"]].sum()
    rpps_honest["honest_report_acceptance"] = (
        rpps_honest.honest_retained / rpps_honest.honest_total
    )
    honest_acceptance_seed_scene = pd.concat([
        irpp_honest[["method", "mode", "scene", "seed", "honest_report_acceptance"]],
        calibrated_honest[["method", "mode", "scene", "seed", "honest_report_acceptance"]],
        rpps_honest[["method", "mode", "scene", "seed", "honest_report_acceptance"]],
    ], ignore_index=True)
    honest_acceptance_macro = honest_acceptance_seed_scene.groupby(
        ["method", "mode", "seed"], as_index=False
    ).honest_report_acceptance.mean()
    honest_acceptance_summary = seed_ci(
        honest_acceptance_macro, ["method", "mode"], "honest_report_acceptance"
    )

    # Fig. 3b: method accuracy under the same clean and four attack-mode replays.
    mode_method_parts = []
    for mode in ["clean", "independent", "compact", "onoff", "mature_anchor"]:
        ratio = 0.0 if mode == "clean" else .3
        ids = active_ids(mode)
        irpp_part = tasks.loc[
            (tasks.method == "IRPP-TD") & (tasks.variant == "Full")
            & (tasks.target_workers == 27) & (tasks["mode"] == mode)
            & tasks.task_id.isin(ids) & np.isclose(tasks.malicious_ratio, ratio)
            & np.isclose(tasks.strength, .5)
        ]
        baseline_part = mode_baselines.loc[
            (mode_baselines.target_workers == 27) & (mode_baselines["mode"] == mode)
            & mode_baselines.task_id.isin(ids) & np.isclose(mode_baselines.malicious_ratio, ratio)
            & np.isclose(mode_baselines.strength, .5)
            & mode_baselines.method.isin(["CRH-N", "PRTD", "QE"])
        ]
        mode_method_parts.extend([irpp_part, baseline_part])
    mode_method_tasks = pd.concat(mode_method_parts, ignore_index=True)
    mode_method_seed_scene = aggregate_errors(
        mode_method_tasks, ["method", "mode", "scene", "seed"]
    )
    mode_method_macro = mode_method_seed_scene.groupby(
        ["method", "mode", "seed"], as_index=False
    )[["nrmse", "no_truth_rate"]].mean()
    mode_method_summary = seed_ci(mode_method_macro, ["method", "mode"], "nrmse")
    mode_method_nt = seed_ci(mode_method_macro, ["method", "mode"], "no_truth_rate")
    mode_method_summary = mode_method_summary.merge(
        mode_method_nt, on=["method", "mode", "seeds"]
    )

    # Ten-task recovery trajectory, normalized by the matched clean block.
    block_source = tasks.loc[
        (tasks.method == "IRPP-TD") & (tasks.variant == "Full") & (tasks.target_workers == 27)
        & tasks["mode"].isin(["clean", "mature_anchor", "onoff"]) & np.isclose(tasks.strength, .5)
    ].copy()
    block_source = block_source.loc[
        ((block_source["mode"] == "clean") & np.isclose(block_source.malicious_ratio, 0.0))
        | ((block_source["mode"] != "clean") & np.isclose(block_source.malicious_ratio, .3))
    ]
    block_source["block_end"] = ((block_source.task_id - 1) // 10 + 1) * 10
    block_seed_scene = aggregate_errors(block_source, ["mode", "block_end", "scene", "seed"])
    block_clean = block_seed_scene.loc[block_seed_scene["mode"] == "clean", ["block_end", "scene", "seed", "nrmse"]].rename(columns={"nrmse": "clean_nrmse"})
    block_attack = block_seed_scene.loc[block_seed_scene["mode"].isin(["mature_anchor", "onoff"])].merge(block_clean, on=["block_end", "scene", "seed"])
    block_attack["error_ratio"] = block_attack.nrmse / block_attack.clean_nrmse
    block_macro = block_attack.groupby(["mode", "block_end", "seed"], as_index=False).error_ratio.mean()
    block_summary = seed_ci(block_macro, ["mode", "block_end"], "error_ratio")

    # Fig. 3d: ordinary-anchor purity in 10-task blocks under delayed poisoning.
    feedback_reports = reports.loc[
        (reports.target_workers == 27) & (reports["mode"] == "mature_anchor")
        & np.isclose(reports.malicious_ratio, .3) & np.isclose(reports.strength, .5)
    ].copy()
    feedback_reports["block_end"] = ((feedback_reports.task_id - 1) // 10 + 1) * 10
    anchors = feedback_reports.loc[feedback_reports.anchor_before.astype(bool)].copy()
    anchors["anchor_honest"] = (~anchors.coalition_member.astype(bool)).astype(float)
    feedback_seed_scene = anchors.groupby(["variant", "block_end", "scene", "seed"], as_index=False).anchor_honest.mean().rename(columns={"anchor_honest": "ordinary_anchor_purity"})
    feedback_macro = feedback_seed_scene.groupby(["variant", "block_end", "seed"], as_index=False).ordinary_anchor_purity.mean()
    feedback_summary = seed_ci(feedback_macro, ["variant", "block_end"], "ordinary_anchor_purity")

    # Scene-level mode evidence and concise appendix tables.
    table_prevalence = prevalence_summary.loc[prevalence_summary.malicious_ratio.isin([0.0, .3, .5, .8])].copy()
    boundary = strength_summary.loc[strength_summary.operational_failure].groupby("strength", as_index=False).malicious_ratio.min().rename(columns={"malicious_ratio": "first_failed_ratio"})
    all_strengths = pd.DataFrame({"strength": sorted(strength_summary.strength.unique())})
    boundary = all_strengths.merge(boundary, how="left", on="strength")
    scene_mode = mode_metrics.groupby(["mode", "scene"], as_index=False)[["error_ratio", "no_truth_rate", "malicious_report_leakage", "honest_false_low_rate"]].mean()

    for name, frame in {
        "prevalence_seed_scene": prevalence_seed_scene,
        "prevalence_summary": prevalence_summary,
        "strength_seed_scene": strength_seed_scene,
        "strength_summary": strength_summary,
        "mode_seed_scene": mode_metrics,
        "mode_summary": mode_summary,
        "mode_method_seed_scene": mode_method_seed_scene,
        "mode_method_summary": mode_method_summary,
        "leakage_method_seed_scene": leakage_seed_scene,
        "leakage_method_summary": leakage_method_summary,
        "honest_acceptance_method_seed_scene": honest_acceptance_seed_scene,
        "honest_acceptance_method_summary": honest_acceptance_summary,
        "calibrated_thresholds": calibrations,
        "rpps_thresholds": rpps_calibrations,
        "irpp_calibration_acceptance": irpp_calibration_summary,
        "mode_block_summary": block_summary,
        "feedback_seed_scene": feedback_seed_scene,
        "feedback_summary": feedback_summary,
        "table_prevalence": table_prevalence,
        "boundary_summary": boundary,
        "scene_mode_summary": scene_mode,
    }.items():
        frame.to_csv(RESULTS / f"rq3_{name}.csv", index=False)

    findings = {
        "formal_task_rows": int(len(tasks)),
        "mode_baseline_task_rows": int(len(mode_baselines)),
        "calibrated_baseline_task_rows": int(len(calibrated)),
        "rpps_screening_task_rows": int(len(rpps_tasks)),
        "calibration_rows": int(len(calibrations)),
        "rpps_threshold_rows": int(len(rpps_calibrations)),
        "irpp_clean_calibration_acceptance": float(irpp_calibration_summary.clean_report_acceptance.iloc[0]),
        "formal_report_rows": int(len(reports)),
        "seeds": sorted(int(x) for x in tasks.seed.unique()),
        "prevalence": prevalence_summary.to_dict(orient="records"),
        "boundary": boundary.to_dict(orient="records"),
        "modes": mode_summary.to_dict(orient="records"),
        "mode_methods": mode_method_summary.to_dict(orient="records"),
        "leakage_methods": leakage_method_summary.to_dict(orient="records"),
        "honest_acceptance_methods": honest_acceptance_summary.to_dict(orient="records"),
        "feedback": feedback_summary.to_dict(orient="records"),
    }
    (RESULTS / "rq3_key_findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(json.dumps({"task_rows": len(tasks), "report_rows": len(reports), "seeds": findings["seeds"]}, indent=2))


if __name__ == "__main__":
    main()
