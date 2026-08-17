from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TABLES = ROOT / "tables"
METADATA = ROOT / "metadata"


def aggregate_from_components(frame: pd.DataFrame, prefix: str = "") -> tuple[float, float]:
    dimension = float(frame[f"{prefix}dimension"].sum())
    nrmse = float(np.sqrt(frame[f"{prefix}norm_sq_sum"].sum() / dimension))
    nmae = float(frame[f"{prefix}norm_abs_sum"].sum() / dimension)
    return nmae, nrmse


def paired_bootstrap(raw: pd.DataFrame, repetitions: int, seed: int) -> pd.DataFrame:
    test = raw.loc[raw["task_id"].between(21, 100)].copy()
    rng = np.random.default_rng(seed)
    rows = []
    for (scene, workers), group in test.groupby(["scene", "target_workers"]):
        irpp = group.loc[group["method"] == "IRPP-TD"]
        irpp_task = (
            irpp.groupby("task_id", as_index=False)
            .agg(norm_sq_sum=("norm_sq_sum", "mean"), dimension=("dimension", "first"))
            .sort_values("task_id")
        )
        retained = group.loc[~group["method"].isin(["IRPP-TD", "Median"])]
        for method, baseline in retained.groupby("method"):
            baseline_task = baseline[["task_id", "norm_sq_sum", "dimension"]].sort_values("task_id")
            merged = irpp_task.merge(baseline_task, on="task_id", suffixes=("_irpp", "_base"))
            irpp_point = float(np.sqrt(merged["norm_sq_sum_irpp"].sum() / merged["dimension_irpp"].sum()))
            base_point = float(np.sqrt(merged["norm_sq_sum_base"].sum() / merged["dimension_base"].sum()))
            task_count = len(merged)
            samples = rng.integers(0, task_count, size=(repetitions, task_count))
            irpp_sq = merged["norm_sq_sum_irpp"].to_numpy()[samples].sum(axis=1)
            base_sq = merged["norm_sq_sum_base"].to_numpy()[samples].sum(axis=1)
            dimensions = merged["dimension_irpp"].to_numpy()[samples].sum(axis=1)
            delta = np.sqrt(irpp_sq / dimensions) - np.sqrt(base_sq / dimensions)
            relative = 1.0 - np.sqrt(irpp_sq / dimensions) / np.sqrt(base_sq / dimensions)
            rows.append(
                {
                    "scene": scene,
                    "target_workers": workers,
                    "baseline": method,
                    "irpp_nrmse": irpp_point,
                    "baseline_nrmse": base_point,
                    "delta_nrmse": irpp_point - base_point,
                    "delta_ci_low": float(np.quantile(delta, 0.025)),
                    "delta_ci_high": float(np.quantile(delta, 0.975)),
                    "relative_reduction": 1.0 - irpp_point / base_point,
                    "relative_ci_low": float(np.quantile(relative, 0.025)),
                    "relative_ci_high": float(np.quantile(relative, 0.975)),
                    "interpretation": (
                        "IRPP-TD lower"
                        if np.quantile(delta, 0.975) < 0
                        else "IRPP-TD higher"
                        if np.quantile(delta, 0.025) > 0
                        else "inconclusive"
                    ),
                }
            )
    return pd.DataFrame(rows)


def irpp_seed_stability(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.loc[(raw["method"] == "IRPP-TD") & raw["task_id"].between(21, 100)]
    rows = []
    for key, group in frame.groupby(["scene", "target_workers", "seed"]):
        scene, workers, seed = key
        rows.append(
            {
                "scene": scene,
                "target_workers": workers,
                "seed": seed,
                "nrmse": float(np.sqrt(group["norm_sq_sum"].sum() / group["dimension"].sum())),
                "nmae": float(group["norm_abs_sum"].sum() / group["dimension"].sum()),
                "runtime_median_ms": float(group["runtime_s"].median() * 1000.0),
                "retained_ratio": float(group["retained_count"].sum() / group["participant_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def metric_text(value: float) -> str:
    value = float(value)
    if abs(value) >= 10:
        return f"{value:.2f}"
    if abs(value) >= 1:
        return f"{value:.3f}"
    if abs(value) >= 0.01:
        return f"{value:.4f}"
    return f"{value:.2e}"


def decorate(value: float, values: pd.Series) -> str:
    ordered = np.sort(values.to_numpy(dtype=float))
    text = metric_text(value)
    if np.isclose(value, ordered[0], rtol=1e-9, atol=1e-12):
        return rf"\textbf{{{text}}}"
    if len(ordered) > 1 and np.isclose(value, ordered[1], rtol=1e-9, atol=1e-12):
        return rf"\underline{{{text}}}"
    return text


def decorate_with_interval(
    value: float,
    ci_low: float,
    ci_high: float,
    values: pd.Series,
) -> str:
    point = metric_text(value)
    half_width = 0.5 * (float(ci_high) - float(ci_low))
    if half_width < 1.0:
        decimals = 2
    elif half_width < 10.0:
        decimals = 1
    else:
        decimals = 0
    factor = 10**decimals
    rounded_up = math.ceil((half_width - 1e-12) * factor) / factor
    spread = f"{rounded_up:.{decimals}f}"
    cell = rf"\mci{{{point}}}{{{spread}}}"
    ordered = np.sort(values.to_numpy(dtype=float))
    if np.isclose(value, ordered[0], rtol=1e-9, atol=1e-12):
        return rf"\textbf{{{cell}}}"
    if len(ordered) > 1 and np.isclose(value, ordered[1], rtol=1e-9, atol=1e-12):
        return rf"\underline{{{cell}}}"
    return cell


def write_main_table(summary: pd.DataFrame) -> None:
    frame = summary.loc[(summary["target_workers"] == 27) & (summary["method"] != "Median")].copy()
    methods = ["Mean", "CRH", "CRH-N", "QE", "RTD", "BLIND", "RPPS-TDC", "PRTD", "IRPP-TD"]
    scenes = ["Climate", "Traffic", "Water"]
    metric_lookup = frame.set_index(["method", "scene"])
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{RQ1 truth-discovery accuracy on held-out tasks 21--100 at $\bar n=27$ (lower is better).}",
        r"\label{tab:rq1-main}",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{2.40pt}",
        r"\renewcommand{\arraystretch}{0.86}",
        r"\newcommand{\dstrut}{\rule[-0.55ex]{0pt}{2.15ex}}",
        r"\newcommand{\mci}[2]{\makebox[2.75em][r]{#1}{\scriptsize$\pm$\makebox[1.35em][l]{#2}}}",
        r"\begin{tabular}{lcccccc>{\centering\arraybackslash}m{4.80em}>{\centering\arraybackslash}m{4.60em}}",
        r"\toprule",
        r"Method & \multicolumn{2}{c}{Climate} & \multicolumn{2}{c}{Traffic} & \multicolumn{2}{c}{Water} & \multicolumn{1}{c}{\multirow{2}{*}{\shortstack[c]{Mean\\[-0.35ex]NRMSE}}} & \multicolumn{1}{c}{\multirow{2}{*}{\shortstack[c]{Time/task\\[-0.35ex](ms)}}} \\[-0.42ex]",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        r" & MAE & RMSE & MAE & RMSE & MAE & RMSE & & \\[-0.30ex]",
        r"\midrule",
    ]
    for method in methods:
        cells = []
        for scene in scenes:
            row = metric_lookup.loc[(method, scene)]
            scene_frame = frame.loc[frame["scene"] == scene]
            cells.extend(
                [
                    decorate_with_interval(
                        row["mae"], row["mae_ci_low"], row["mae_ci_high"], scene_frame["mae"]
                    ),
                    decorate_with_interval(
                        row["rmse"], row["rmse_ci_low"], row["rmse_ci_high"], scene_frame["rmse"]
                    ),
                ]
            )
        method_frame = frame.loc[frame["method"] == method]
        mean_nrmse = float(method_frame["nrmse"].mean())
        mean_time = float(method_frame["runtime_median_ms"].mean())
        all_means = frame.groupby("method")["nrmse"].mean()
        all_times = frame.groupby("method")["runtime_median_ms"].mean()
        cells.extend([decorate(mean_nrmse, all_means), decorate(mean_time, all_times)])
        label = (r"\textbf{IRPP-TD}" if method == "IRPP-TD" else method) + r"\dstrut"
        row_end = r" \\[-0.30ex]" if method == "IRPP-TD" else r" \\"
        lines.append(label + " & " + " & ".join(cells) + row_end)
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\par\vspace{0.70ex}",
            r"\noindent\begin{minipage}{0.98\textwidth}\scriptsize",
            r"Each $\pm$ value is the half-width of a 95\% bootstrap interval (hierarchical seed/task for IRPP-TD; task bootstrap for deterministic baselines). "
            r"IRPP-TD uses 30 anchor-sampling seeds. NMAE/NRMSE use calibration-fitted coordinate scales. "
            r"Bold and underline mark the best and second-best point estimates under the matched adapter protocol.",
            r"\end{minipage}",
            r"\end{table*}",
        ]
    )
    (TABLES / "rq1_main_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_dataset_table(manifest: dict) -> None:
    rows = []
    for key in ["Climate_n27", "Climate_n39", "Traffic_n27", "Traffic_n39", "Water_n27", "Water_n39"]:
        item = manifest[key]
        rows.append(
            f"{item['scene']} & {item['target_workers']} & {item['dimension']} & {item['processed_records']:,} & "
            f"{item['participants_min']} / {item['participants_mean']:.2f} / {item['participants_max']} \\\\"
        )
    text = "\n".join(
        [
            r"\begin{table}[t]",
            r"\centering",
            r"\caption{RQ1 workloads and realized SUMO participation.}",
            r"\label{tab:rq1-workloads}",
            r"\footnotesize",
            r"\setlength{\tabcolsep}{3.2pt}",
            r"\begin{tabular}{lrrrr}",
            r"\toprule",
            r"Scene & Target $\bar n$ & $\ell$ & Clean records & Participants min/mean/max \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    (TABLES / "rq1_workload_table.tex").write_text(text + "\n", encoding="utf-8")


def key_findings(summary: pd.DataFrame, paired: pd.DataFrame, raw: pd.DataFrame, stability: pd.DataFrame) -> dict:
    summary = summary.loc[summary["method"] != "Median"].copy()
    findings = {"settings": {}, "worker_sensitivity": {}, "stability": {}}
    for workers in [27, 39]:
        frame = summary.loc[summary["target_workers"] == workers]
        irpp = frame.loc[frame["method"] == "IRPP-TD"].set_index("scene")
        scene_findings = {}
        for scene in ["Climate", "Traffic", "Water"]:
            ranked = frame.loc[frame["scene"] == scene].sort_values("nrmse")
            rank = int(np.where(ranked["method"].to_numpy() == "IRPP-TD")[0][0] + 1)
            best_baseline = ranked.loc[ranked["method"] != "IRPP-TD"].iloc[0]
            pair = paired.loc[
                (paired["scene"] == scene)
                & (paired["target_workers"] == workers)
                & (paired["baseline"] == best_baseline["method"])
            ].iloc[0]
            scene_findings[scene] = {
                "irpp_nrmse": float(irpp.loc[scene, "nrmse"]),
                "rank": rank,
                "strongest_baseline": str(best_baseline["method"]),
                "baseline_nrmse": float(best_baseline["nrmse"]),
                "relative_change_vs_best_baseline": float(pair["relative_reduction"]),
                "paired_95ci": [float(pair["delta_ci_low"]), float(pair["delta_ci_high"])],
                "paired_interpretation": pair["interpretation"],
            }
        findings["settings"][str(workers)] = {
            "mean_irpp_nrmse_across_scenes": float(irpp["nrmse"].mean()),
            "scenes": scene_findings,
        }
    irpp_summary = summary.loc[summary["method"] == "IRPP-TD"].set_index(["scene", "target_workers"])
    for scene in ["Climate", "Traffic", "Water"]:
        low = float(irpp_summary.loc[(scene, 27), "nrmse"])
        high = float(irpp_summary.loc[(scene, 39), "nrmse"])
        findings["worker_sensitivity"][scene] = {
            "nrmse_n27": low,
            "nrmse_n39": high,
            "relative_reduction": 1.0 - high / low,
        }
    test_irpp = raw.loc[(raw["method"] == "IRPP-TD") & raw["task_id"].between(21, 100)]
    findings["stability"] = {
        "no_truth_rate": float(test_irpp["no_truth"].mean()),
        "mean_iterations": float(test_irpp["iterations"].mean()),
        "max_iterations_observed": int(test_irpp["iterations"].max()),
        "mean_retained_ratio": float(test_irpp["retained_count"].sum() / test_irpp["participant_count"].sum()),
        "seed_nrmse_std_by_workload": {
            f"{scene}_n{workers}": float(group["nrmse"].std(ddof=1))
            for (scene, workers), group in stability.groupby(["scene", "target_workers"])
        },
    }
    return findings


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(RESULTS / "rq1_task_level_results.csv")
    summary = pd.read_csv(RESULTS / "rq1_summary_95ci.csv")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((METADATA / "workload_manifest.json").read_text(encoding="utf-8"))
    paired = paired_bootstrap(raw, int(config["bootstrap_repetitions"]), int(config["random_seeds"][0]))
    stability = irpp_seed_stability(raw)
    paired.to_csv(RESULTS / "rq1_paired_vs_irpp.csv", index=False)
    stability.to_csv(RESULTS / "rq1_irpp_seed_stability.csv", index=False)
    write_main_table(summary)
    write_dataset_table(manifest)
    findings = key_findings(summary, paired, raw, stability)
    (RESULTS / "rq1_key_findings.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
