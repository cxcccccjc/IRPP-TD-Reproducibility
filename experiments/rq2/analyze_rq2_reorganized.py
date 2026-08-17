from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
METADATA = ROOT / "metadata"
TABLES = ROOT / "tables"


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def bootstrap_seed_mean(values: pd.Series, repetitions: int, token: int) -> tuple[float, float, float]:
    clean = np.asarray(values.dropna(), dtype=float)
    if clean.size == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(np.random.SeedSequence([20260810, int(token), clean.size]))
    draws = rng.choice(clean, size=(repetitions, clean.size), replace=True).mean(axis=1)
    return float(clean.mean()), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def scene_macro_by_seed(frame: pd.DataFrame, value: str, group: Iterable[str]) -> pd.DataFrame:
    group = list(group)
    per_scene = frame.groupby(group + ["seed", "scene"], as_index=False)[value].mean()
    return per_scene.groupby(group + ["seed"], as_index=False)[value].mean()


def summarize_seed_values(frame: pd.DataFrame, value: str, group: Iterable[str], repetitions: int, token_base: int) -> pd.DataFrame:
    rows = []
    for index, (keys, part) in enumerate(frame.groupby(list(group), dropna=False)):
        if not isinstance(keys, tuple):
            keys = (keys,)
        mean, low, high = bootstrap_seed_mean(part[value], repetitions, token_base + index)
        row = dict(zip(group, keys))
        row.update({value: mean, f"{value}_ci_low": low, f"{value}_ci_high": high, "seed_count": int(part["seed"].nunique())})
        rows.append(row)
    return pd.DataFrame(rows)


def add_block(task: pd.DataFrame, size: int) -> pd.DataFrame:
    result = task.copy()
    result["block_end"] = ((result["task_id"] - 1) // size + 1) * size
    return result


def block_nrmse(frame: pd.DataFrame, group: Iterable[str]) -> pd.DataFrame:
    group = list(group)
    rows = []
    for keys, part in frame.groupby(group + ["seed", "scene"], dropna=False):
        denom = float(part.loc[~part["no_truth"], "dimension"].sum())
        value = float(np.sqrt(part.loc[~part["no_truth"], "norm_sq_sum"].sum() / denom)) if denom else np.nan
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group + ["seed", "scene"], keys))
        row["nrmse"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def phase_nrmse(frame: pd.DataFrame, group: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    result["phase"] = np.select(
        [result["task_id"].between(1, 20), result["task_id"].between(21, 60), result["task_id"].between(61, 100)],
        ["Early (1--20)", "Transition (21--60)", "Mature (61--100)"],
        default="Other",
    )
    return block_nrmse(result, list(group) + ["phase"])


def control_aliases(task: pd.DataFrame, runs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    control_task = task.loc[
        (task["experiment"] == "cold-start")
        & (task["strategy"] == "Adaptive-HQ")
        & (task["target_workers"] == 27)
    ].copy()
    control_run = runs.loc[
        (runs["experiment"] == "cold-start")
        & (runs["strategy"] == "Adaptive-HQ")
        & (runs["target_workers"] == 27)
    ].copy()
    control_task["condition"] = "E0"
    control_task["experiment"] = "early-error"
    control_run["condition"] = "E0"
    control_run["experiment"] = "early-error"
    return control_task, control_run


def cold_results(task: pd.DataFrame, runs: pd.DataFrame, repetitions: int, block_size: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cold_task = add_block(task.loc[(task["experiment"] == "cold-start") & (task["target_workers"] == 27)], block_size)
    raw = block_nrmse(cold_task, ["strategy", "block_end"])
    by_seed = raw.groupby(["strategy", "block_end", "seed"], as_index=False)["nrmse"].mean()
    curve = summarize_seed_values(by_seed, "nrmse", ["strategy", "block_end"], repetitions, 1000)

    metrics = [
        "nrmse",
        "final_worker_macro_f1",
        "final_worker_coverage",
        "report_f1",
        "report_fpr",
        "report_fnr",
        "bad_leakage",
        "clean_retention",
        "mean_extra_reports_per_task",
        "bootstrap_task_rate",
        "last_extra_task",
        "temporary_fallback_rate",
    ]
    cold_run = runs.loc[(runs["experiment"] == "cold-start") & (runs["target_workers"] == 27)]
    summaries = []
    for metric_index, metric in enumerate(metrics):
        macro = scene_macro_by_seed(cold_run, metric, ["strategy"])
        summaries.append(summarize_seed_values(macro, metric, ["strategy"], repetitions, 2000 + metric_index * 20))
    summary = summaries[0]
    for item in summaries[1:]:
        summary = summary.merge(item.drop(columns="seed_count"), on="strategy", how="outer")

    cold39 = runs.loc[(runs["experiment"] == "cold-start") & (runs["target_workers"] == 39)]
    raw39 = scene_macro_by_seed(cold39, "nrmse", ["strategy"])
    summary39 = summarize_seed_values(raw39, "nrmse", ["strategy"], repetitions, 2300)
    return curve, summary, summary39


def ratio_results(task: pd.DataFrame, runs: pd.DataFrame, repetitions: int, block_size: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ratio_task = task.loc[(task["experiment"] == "malicious-ratio") & (task["target_workers"] == 27)].copy()
    phases = phase_nrmse(ratio_task, ["malicious_ratio"])
    by_seed = phases.groupby(["malicious_ratio", "phase", "seed"], as_index=False)["nrmse"].mean()
    phase_summary = summarize_seed_values(by_seed, "nrmse", ["malicious_ratio", "phase"], repetitions, 3000)

    ratio_run = runs.loc[(runs["experiment"] == "malicious-ratio") & (runs["target_workers"] == 27)]
    metrics = ["nrmse", "final_worker_macro_f1", "final_worker_coverage", "report_f1", "bad_leakage", "clean_retention"]
    tables = []
    for metric_index, metric in enumerate(metrics):
        macro = scene_macro_by_seed(ratio_run, metric, ["malicious_ratio"])
        tables.append(summarize_seed_values(macro, metric, ["malicious_ratio"], repetitions, 3300 + metric_index * 20))
    summary = tables[0]
    for item in tables[1:]:
        summary = summary.merge(item.drop(columns="seed_count"), on="malicious_ratio", how="outer")

    block = add_block(ratio_task, block_size)
    f1_scene = block.groupby(["malicious_ratio", "block_end", "seed", "scene"], as_index=False)["worker_macro_f1"].mean()
    f1_seed = f1_scene.groupby(["malicious_ratio", "block_end", "seed"], as_index=False)["worker_macro_f1"].mean()
    f1_summary = summarize_seed_values(f1_seed, "worker_macro_f1", ["malicious_ratio", "block_end"], repetitions, 3600)
    return phase_summary, summary, f1_summary


def early_results(task: pd.DataFrame, runs: pd.DataFrame, repetitions: int, block_size: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    control_task, control_run = control_aliases(task, runs)
    early_task = pd.concat(
        [control_task, task.loc[(task["experiment"] == "early-error") & (task["target_workers"] == 27)]],
        ignore_index=True,
    )
    early_run = pd.concat(
        [control_run, runs.loc[(runs["experiment"] == "early-error") & (runs["target_workers"] == 27)]],
        ignore_index=True,
    )
    blocked = add_block(early_task, block_size)
    raw = block_nrmse(blocked, ["condition", "block_end"])
    pivot = raw.pivot_table(index=["seed", "scene", "block_end"], columns="condition", values="nrmse").reset_index()
    deltas = []
    for condition in ("E1", "E3"):
        part = pivot[["seed", "scene", "block_end", "E0", condition]].copy()
        part["condition"] = condition
        part["delta_nrmse"] = part[condition] - part["E0"]
        deltas.append(part[["seed", "scene", "block_end", "condition", "delta_nrmse"]])
    delta = pd.concat(deltas, ignore_index=True)
    delta_seed = delta.groupby(["condition", "block_end", "seed"], as_index=False)["delta_nrmse"].mean()
    delta_summary = summarize_seed_values(delta_seed, "delta_nrmse", ["condition", "block_end"], repetitions, 4000)

    f1_scene = blocked.groupby(["condition", "block_end", "seed", "scene"], as_index=False)["worker_macro_f1"].mean()
    f1_seed = f1_scene.groupby(["condition", "block_end", "seed"], as_index=False)["worker_macro_f1"].mean()
    f1_summary = summarize_seed_values(f1_seed, "worker_macro_f1", ["condition", "block_end"], repetitions, 4300)

    pivot_run = early_run.pivot_table(index=["seed", "scene"], columns="condition", values=["nrmse", "final_worker_macro_f1", "final_worker_coverage"]).reset_index()
    rows = []
    for condition in ("E1", "E3"):
        base = pd.DataFrame({
            "seed": pivot_run["seed"],
            "scene": pivot_run["scene"],
            "condition": condition,
            "delta_nrmse": pivot_run[("nrmse", condition)] - pivot_run[("nrmse", "E0")],
            "delta_final_worker_macro_f1": pivot_run[("final_worker_macro_f1", condition)] - pivot_run[("final_worker_macro_f1", "E0")],
            "delta_final_worker_coverage": pivot_run[("final_worker_coverage", condition)] - pivot_run[("final_worker_coverage", "E0")],
        })
        rows.append(base)
    paired = pd.concat(rows, ignore_index=True)
    table_parts = []
    for metric_index, metric in enumerate(["delta_nrmse", "delta_final_worker_macro_f1", "delta_final_worker_coverage"]):
        macro = scene_macro_by_seed(paired, metric, ["condition"])
        table_parts.append(summarize_seed_values(macro, metric, ["condition"], repetitions, 4600 + metric_index * 20))
    table = table_parts[0]
    for item in table_parts[1:]:
        table = table.merge(item.drop(columns="seed_count"), on="condition", how="outer")
    return delta_summary, f1_summary, table


def switch_results(task: pd.DataFrame, runs: pd.DataFrame, events: pd.DataFrame, repetitions: int, block_size: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stable = task.loc[
        (task["experiment"] == "cold-start") & (task["strategy"] == "Adaptive-HQ") & (task["target_workers"] == 27)
    ].copy()
    stable["series"] = "Stable 50/50"
    htol = task.loc[
        (task["experiment"] == "h-to-l") & (task["switch_fraction"] == 0.5) & (task["target_workers"] == 27)
    ].copy()
    htol["series"] = r"H-to-L (50%)"
    ltoh = task.loc[
        (task["experiment"] == "l-to-h") & (task["switch_fraction"] == 0.5) & (task["target_workers"] == 27)
    ].copy()
    ltoh["series"] = r"L-to-H (50%)"
    combined = add_block(pd.concat([stable, htol, ltoh], ignore_index=True), block_size)
    raw = block_nrmse(combined, ["series", "block_end"])
    by_seed = raw.groupby(["series", "block_end", "seed"], as_index=False)["nrmse"].mean()
    curve = summarize_seed_values(by_seed, "nrmse", ["series", "block_end"], repetitions, 5000)

    f1_scene = combined.groupby(["series", "block_end", "seed", "scene"], as_index=False)["worker_macro_f1"].mean()
    f1_seed = f1_scene.groupby(["series", "block_end", "seed"], as_index=False)["worker_macro_f1"].mean()
    f1_curve = summarize_seed_values(f1_seed, "worker_macro_f1", ["series", "block_end"], repetitions, 5300)

    severity_task = add_block(task.loc[(task["experiment"] == "h-to-l") & (task["target_workers"] == 27)], block_size)
    severity_raw = block_nrmse(severity_task, ["switch_fraction", "block_end"])
    post = severity_raw.loc[severity_raw["block_end"] >= 50].groupby(["switch_fraction", "seed", "scene"], as_index=False)["nrmse"].mean()
    post_seed = post.groupby(["switch_fraction", "seed"], as_index=False)["nrmse"].mean()
    severity_summary = summarize_seed_values(post_seed, "nrmse", ["switch_fraction"], repetitions, 5600)

    event_frame = events.loc[
        (events["target_workers"] == 27)
        & events["event"].isin(["initial-classification-high", "initial-classification-low", "detect-h-to-l", "recover-l-to-h"])
    ].copy()
    event_rows = []
    grouping = ["experiment", "condition", "strategy", "event"]
    for index, (keys, part) in enumerate(event_frame.groupby(grouping)):
        seed_means = part.groupby("seed", as_index=False)["delay_participations"].mean()
        mean, low, high = bootstrap_seed_mean(seed_means["delay_participations"], repetitions, 5800 + index)
        event_rows.append(
            {
                **dict(zip(grouping, keys)),
                "restricted_mean_delay": mean,
                "delay_ci_low": low,
                "delay_ci_high": high,
                "censoring_rate": float(part["censored"].mean()),
                "worker_event_count": len(part),
            }
        )
    return curve, f1_curve, severity_summary, pd.DataFrame(event_rows)


def write_latex_tables(cold: pd.DataFrame, ratio: pd.DataFrame, early: pd.DataFrame, switch_severity: pd.DataFrame, events: pd.DataFrame) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    lines = []
    for row in cold.sort_values("strategy").itertuples(index=False):
        lines.append(
            f"{row.strategy} & {row.nrmse:.5f} & {row.final_worker_macro_f1:.3f} & {row.final_worker_coverage:.3f} & "
            f"{row.report_f1:.3f} & {100*row.bad_leakage:.2f} & {100*row.clean_retention:.2f} & {row.mean_extra_reports_per_task:.2f} \\\\"
        )
    (TABLES / "rq2_cold_start_rows.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ratio_lines = []
    for row in ratio.sort_values("malicious_ratio").itertuples(index=False):
        f1 = "--" if not np.isfinite(row.final_worker_macro_f1) else f"{row.final_worker_macro_f1:.3f}"
        screening_f1 = "--" if not np.isfinite(row.report_f1) else f"{row.report_f1:.3f}"
        leakage = "--" if not np.isfinite(row.bad_leakage) else f"{100*row.bad_leakage:.2f}"
        ratio_lines.append(
            f"{row.malicious_ratio:.1f} & {row.nrmse:.5f} & {f1} & {row.final_worker_coverage:.3f} & "
            f"{screening_f1} & {leakage} & {100*row.clean_retention:.2f} \\\\"
        )
    (TABLES / "rq2_ratio_rows.tex").write_text("\n".join(ratio_lines) + "\n", encoding="utf-8")

    early_lines = []
    for row in early.sort_values("condition").itertuples(index=False):
        early_lines.append(
            f"{row.condition} & {1e4*row.delta_nrmse:.3f} [{1e4*row.delta_nrmse_ci_low:.3f},{1e4*row.delta_nrmse_ci_high:.3f}] & "
            f"{100*row.delta_final_worker_macro_f1:.2f} & {100*row.delta_final_worker_coverage:.2f} \\\\"
        )
    (TABLES / "rq2_early_error_rows.tex").write_text("\n".join(early_lines) + "\n", encoding="utf-8")

    switch_lines = []
    for row in switch_severity.sort_values("switch_fraction").itertuples(index=False):
        switch_lines.append(
            f"{row.switch_fraction:.2f} & {row.nrmse:.5f} [{row.nrmse_ci_low:.5f},{row.nrmse_ci_high:.5f}] \\\\"
        )
    (TABLES / "rq2_switch_severity_rows.tex").write_text("\n".join(switch_lines) + "\n", encoding="utf-8")

    events.to_csv(TABLES / "rq2_event_summary.csv", index=False)


def main() -> None:
    config = load_config()
    repetitions = int(config["bootstrap_repetitions"])
    block_size = int(config["task_block_size"])
    audit = json.loads((METADATA / "formal_run_audit.json").read_text(encoding="utf-8"))
    if not audit.get("formal"):
        raise RuntimeError("Refusing to back-fill from a non-formal run")
    task = pd.read_csv(RESULTS / "formal_task_metrics.csv")
    runs = pd.read_csv(RESULTS / "formal_run_summary.csv")
    events = pd.read_csv(RESULTS / "formal_worker_events.csv")

    cold_curve, cold_summary, cold39 = cold_results(task, runs, repetitions, block_size)
    ratio_phase, ratio_summary, ratio_f1 = ratio_results(task, runs, repetitions, block_size)
    early_delta, early_f1, early_table = early_results(task, runs, repetitions, block_size)
    switch_curve, switch_f1, switch_severity, event_summary = switch_results(task, runs, events, repetitions, block_size)

    outputs = {
        "rq2_cold_curve_95ci.csv": cold_curve,
        "rq2_cold_summary_95ci.csv": cold_summary,
        "rq2_cold_n39_summary_95ci.csv": cold39,
        "rq2_ratio_phase_95ci.csv": ratio_phase,
        "rq2_ratio_summary_95ci.csv": ratio_summary,
        "rq2_ratio_worker_f1_95ci.csv": ratio_f1,
        "rq2_early_delta_95ci.csv": early_delta,
        "rq2_early_worker_f1_95ci.csv": early_f1,
        "rq2_early_summary_95ci.csv": early_table,
        "rq2_switch_curve_95ci.csv": switch_curve,
        "rq2_switch_worker_f1_95ci.csv": switch_f1,
        "rq2_switch_severity_95ci.csv": switch_severity,
        "rq2_event_summary_95ci.csv": event_summary,
    }
    for name, frame in outputs.items():
        frame.to_csv(RESULTS / name, index=False)
    write_latex_tables(cold_summary, ratio_summary, early_table, switch_severity, event_summary)

    findings = {
        "cold_start": cold_summary.to_dict(orient="records"),
        "malicious_ratio": ratio_summary.to_dict(orient="records"),
        "early_error": early_table.to_dict(orient="records"),
        "switch_severity": switch_severity.to_dict(orient="records"),
        "events": event_summary.to_dict(orient="records"),
        "formal_run": audit,
    }
    (RESULTS / "rq2_reorganized_key_findings.json").write_text(json.dumps(findings, indent=2, allow_nan=True), encoding="utf-8")

    checks = {
        "task_rows": len(task),
        "run_rows": len(runs),
        "worker_events": len(events),
        "no_truth_tasks": int(task["no_truth"].sum()),
        "nonfinite_valid_task_errors": int((~task["no_truth"] & ~np.isfinite(task["task_nrmse"])).sum()),
        "angular_unavailable_tasks": int((~task["angular_available"]).sum()),
        "seed_count": int(runs["seed"].nunique()),
        "scene_count": int(runs["scene"].nunique()),
        "condition_count": int(runs[["experiment", "condition", "strategy", "target_workers"]].drop_duplicates().shape[0]),
    }
    (METADATA / "formal_result_audit.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    if checks["no_truth_tasks"] or checks["nonfinite_valid_task_errors"] or checks["seed_count"] != 30:
        raise RuntimeError(checks)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
