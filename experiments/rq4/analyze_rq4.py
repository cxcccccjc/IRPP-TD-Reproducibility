from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
METADATA = ROOT / "metadata"


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    valid = np.isfinite(a) & np.isfinite(b)
    if valid.sum() < 3:
        return float("nan")
    left, right = rankdata(a[valid]), rankdata(b[valid])
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def angular_summary(raw: pd.DataFrame, repetitions: int) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(20260810)
    for (budget, target), frame in raw.groupby(["budget", "target_workers"], sort=False):
        scenes = sorted(frame["scene"].unique())
        seeds = sorted(frame["seed"].unique())
        tasks = sorted(frame["task_id"].unique())
        arrays = {}
        scene_point = []
        scene_pairs = []
        scene_f1 = []
        scene_availability = []
        scene_no_truth = []
        for scene in scenes:
            subset = frame.loc[frame["scene"] == scene].set_index(["seed", "task_id"]).sort_index()
            shape = (len(seeds), len(tasks))
            sq = subset["norm_sq_sum"].to_numpy().reshape(shape)
            dim = subset["dimension"].to_numpy(dtype=float).reshape(shape)
            valid = (~subset["no_truth"].to_numpy(dtype=bool)).reshape(shape)
            pair = subset["pair_evaluations"].to_numpy(dtype=float).reshape(shape)
            f1 = subset["screening_macro_f1"].to_numpy(dtype=float).reshape(shape)
            available = subset["angular_available"].to_numpy(dtype=float).reshape(shape)
            arrays[scene] = (sq, dim, valid, pair, f1, available)
            scene_point.append(float(np.sqrt(np.nansum(sq[valid]) / np.sum(dim[valid]))))
            scene_pairs.append(float(np.mean(pair)))
            scene_f1.append(float(np.mean(f1)))
            scene_availability.append(float(np.mean(available)))
            scene_no_truth.append(float(1.0 - valid.mean()))
        boot_nrmse = []
        boot_pairs = []
        chunk = 100
        for start in range(0, repetitions, chunk):
            count = min(chunk, repetitions - start)
            seed_draw = rng.integers(0, len(seeds), size=(count, len(seeds)))
            task_draw = rng.integers(0, len(tasks), size=(count, len(seeds), len(tasks)))
            nrmse_by_scene = []
            pairs_by_scene = []
            for scene in scenes:
                sq, dim, valid, pair, _, _ = arrays[scene]
                selected_sq = sq[seed_draw[:, :, None], task_draw]
                selected_dim = dim[seed_draw[:, :, None], task_draw]
                selected_valid = valid[seed_draw[:, :, None], task_draw]
                numerator = np.nansum(np.where(selected_valid, selected_sq, 0.0), axis=(1, 2))
                denominator = np.sum(np.where(selected_valid, selected_dim, 0.0), axis=(1, 2))
                nrmse_by_scene.append(np.sqrt(numerator / denominator))
                selected_pair = pair[seed_draw[:, :, None], task_draw]
                pairs_by_scene.append(np.mean(selected_pair, axis=(1, 2)))
            boot_nrmse.extend(np.mean(np.vstack(nrmse_by_scene), axis=0).tolist())
            boot_pairs.extend(np.mean(np.vstack(pairs_by_scene), axis=0).tolist())
        rows.append(
            {
                "budget": budget,
                "target_workers": int(target),
                "scene_macro_nrmse": float(np.mean(scene_point)),
                "nrmse_ci_low": float(np.quantile(boot_nrmse, 0.025)),
                "nrmse_ci_high": float(np.quantile(boot_nrmse, 0.975)),
                "scene_macro_pairs_per_task": float(np.mean(scene_pairs)),
                "pairs_ci_low": float(np.quantile(boot_pairs, 0.025)),
                "pairs_ci_high": float(np.quantile(boot_pairs, 0.975)),
                "screening_macro_f1": float(np.mean(scene_f1)),
                "angular_available_rate": float(np.mean(scene_availability)),
                "no_truth_rate": float(np.mean(scene_no_truth)),
                "effective_budget_mean": float(frame["effective_budget"].mean()),
                "tasks": int(len(frame)),
            }
        )
    return pd.DataFrame(rows)


def angular_scene_summary(raw: pd.DataFrame) -> pd.DataFrame:
    """Create the compact per-scene input used by Fig. S5(a)."""
    rows = []
    for (budget, scene, target), frame in raw.groupby(
        ["budget", "scene", "target_workers"], sort=False
    ):
        valid = frame.loc[~frame["no_truth"]]
        nrmse = (
            float(np.sqrt(valid["norm_sq_sum"].sum() / valid["dimension"].sum()))
            if not valid.empty
            else float("nan")
        )
        rows.append(
            {
                "budget": budget,
                "scene": scene,
                "target_workers": int(target),
                "nrmse": nrmse,
                "no_truth_rate": float(frame["no_truth"].mean()),
                "tasks": int(len(frame)),
            }
        )
    return pd.DataFrame(rows)


def angular_agreement(raw: pd.DataFrame) -> pd.DataFrame:
    keys = ["scene", "target_workers", "seed", "task_id"]
    exact = raw.loc[raw["budget"] == "Exact", keys + ["scores_json", "retained_json", "labels_json"]]
    exact_map = {
        tuple(getattr(row, key) for key in keys): (
            np.asarray(json.loads(row.scores_json), dtype=float),
            np.asarray(json.loads(row.retained_json), dtype=bool),
            np.asarray(json.loads(row.labels_json), dtype=int),
        )
        for row in exact.itertuples(index=False)
    }
    rows = []
    for row in raw.loc[raw["budget"] != "Exact"].itertuples(index=False):
        key = (row.scene, row.target_workers, row.seed, row.task_id)
        exact_scores, exact_retained, exact_labels = exact_map[key]
        scores = np.asarray(json.loads(row.scores_json), dtype=float)
        retained = np.asarray(json.loads(row.retained_json), dtype=bool)
        labels = np.asarray(json.loads(row.labels_json), dtype=int)
        union = np.sum(retained | exact_retained)
        rows.append(
            {
                "budget": row.budget,
                "scene": row.scene,
                "target_workers": row.target_workers,
                "seed": row.seed,
                "task_id": row.task_id,
                "score_spearman_vs_exact": spearman(scores, exact_scores),
                "retained_jaccard_vs_exact": 1.0 if union == 0 else float(np.sum(retained & exact_retained) / union),
                "label_agreement_vs_exact": float(np.mean(labels == exact_labels)),
            }
        )
    return pd.DataFrame(rows)


def stopping_summary(raw: pd.DataFrame) -> pd.DataFrame:
    by_scene = (
        raw.groupby(["epsilon", "max_iterations", "scene"], as_index=False)
        .agg(
            gap=("fixed_point_gap", "mean"),
            gap_p95=("fixed_point_gap", lambda x: float(np.quantile(x, 0.95))),
            gap_max=("fixed_point_gap", "max"),
            cap_hit_rate=("cap_hit", "mean"),
            iterations_mean=("iterations", "mean"),
            iterations_p95=("iterations", lambda x: float(np.quantile(x, 0.95))),
        )
    )
    return (
        by_scene.groupby(["epsilon", "max_iterations"], as_index=False)
        .agg(
            scene_macro_gap=("gap", "mean"),
            scene_macro_gap_p95=("gap_p95", "mean"),
            max_gap=("gap_max", "max"),
            cap_hit_rate=("cap_hit_rate", "mean"),
            iterations_mean=("iterations_mean", "mean"),
            iterations_p95=("iterations_p95", "mean"),
        )
    )


def slope_with_bootstrap(timing: pd.DataFrame, method: str, n_selector, repetitions: int = 2000) -> dict:
    subset = timing.loc[(timing["method"] == method) & timing["n"].map(n_selector)].copy()
    groups = {int(n): frame["runtime_s"].to_numpy() for n, frame in subset.groupby("n")}
    n_values = np.asarray(sorted(groups), dtype=float)
    medians = np.asarray([np.median(groups[int(n)]) for n in n_values])
    point = float(np.polyfit(np.log10(n_values), np.log10(medians), 1)[0])
    rng = np.random.default_rng(20260810 + len(groups))
    values = []
    for _ in range(repetitions):
        sampled = []
        for n in n_values:
            observed = groups[int(n)]
            sampled.append(float(np.median(rng.choice(observed, size=len(observed), replace=True))))
        values.append(float(np.polyfit(np.log10(n_values), np.log10(sampled), 1)[0]))
    return {"slope": point, "ci_low": float(np.quantile(values, 0.025)), "ci_high": float(np.quantile(values, 0.975)), "n_min": int(n_values.min()), "n_max": int(n_values.max())}


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denom
    return center - half, center + half


def stability_summary(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, frame in raw.groupby(["method", "geometry", "tau"], sort=False):
        successes = int(frame["success"].sum())
        low, high = wilson(successes, len(frame))
        rows.append(
            {
                "method": key[0],
                "geometry": key[1],
                "tau": key[2],
                "success_rate": successes / len(frame),
                "success_ci_low": low,
                "success_ci_high": high,
                "finite_rate": float(frame["finite"].mean()),
                "fallback_rate": float(frame["declared_fallback"].mean()),
                "max_raw_weight": float(frame["max_raw_weight"].replace([np.inf, -np.inf], np.nan).max()),
                "max_normalization_error": float(frame["normalization_error"].max()),
                "iterations_p95": float(np.quantile(frame["iterations"], 0.95)),
                "cap_hit_rate": float((~frame["converged"]).mean()),
                "trials": len(frame),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    repetitions = int(config["bootstrap_repetitions"])
    angular_raw = pd.read_csv(RESULTS / "angular_budget_task_results.csv")
    angular = angular_summary(angular_raw, repetitions)
    angular.to_csv(RESULTS / "angular_budget_summary_95ci.csv", index=False)
    angular_scene_summary(angular_raw).to_csv(
        RESULTS / "angular_scene_summary.csv", index=False
    )
    agreement = angular_agreement(angular_raw)
    agreement.to_csv(RESULTS / "angular_exact_agreement_task.csv", index=False)
    agreement_summary = agreement.groupby(["budget", "target_workers"], as_index=False).agg(
        score_spearman=("score_spearman_vs_exact", "mean"),
        retained_jaccard=("retained_jaccard_vs_exact", "mean"),
        label_agreement=("label_agreement_vs_exact", "mean"),
    )
    agreement_summary.to_csv(RESULTS / "angular_exact_agreement_summary.csv", index=False)

    stopping_raw = pd.read_csv(RESULTS / "stopping_grid_task_results.csv")
    stopping = stopping_summary(stopping_raw)
    stopping.to_csv(RESULTS / "stopping_grid_summary.csv", index=False)

    scaling = pd.read_csv(RESULTS / "scaling_summary.csv")
    timing = pd.read_csv(RESULTS / "scaling_timing_repeats.csv")
    slopes = {
        "rabod_pre_cap": slope_with_bootstrap(timing, "RABOD", lambda n: n <= 400),
        "rabod_post_cap": slope_with_bootstrap(timing, "RABOD", lambda n: n >= 400),
        "full_post_cap": slope_with_bootstrap(timing, "Full IRPP", lambda n: n >= 400),
        "exact_observed": slope_with_bootstrap(timing, "Exact ABOD", lambda n: n <= 400),
    }
    dump_json(RESULTS / "scaling_slopes.json", slopes)

    stability_raw = pd.read_csv(RESULTS / "stability_trials.csv")
    stability = stability_summary(stability_raw)
    stability.to_csv(RESULTS / "stability_summary_wilson.csv", index=False)

    applicability_raw = pd.read_csv(RESULTS / "applicability_trials.csv")
    applicability = applicability_raw.groupby("scenario", as_index=False).agg(
        nrmse=("nrmse", "mean"),
        nrmse_ci_low=("nrmse", lambda x: float(np.quantile(x, 0.025))),
        nrmse_ci_high=("nrmse", lambda x: float(np.quantile(x, 0.975))),
        angular_available_rate=("angular_available", "mean"),
        retained_rate=("retained_rate", "mean"),
    )
    applicability.to_csv(RESULTS / "applicability_summary.csv", index=False)

    default_angular = angular.loc[angular["budget"] == "cap-20"].set_index("target_workers")
    exact_angular = angular.loc[angular["budget"] == "Exact"].set_index("target_workers")
    default_stop = stopping.loc[(stopping["epsilon"] == 1e-5) & (stopping["max_iterations"] == 50)].iloc[0]
    at_10000 = scaling.loc[(scaling["method"] == "Full IRPP") & (scaling["n"] == 10000)].iloc[0]
    rabod_400 = scaling.loc[(scaling["method"] == "RABOD") & (scaling["n"] == 400)].iloc[0]
    exact_400 = scaling.loc[(scaling["method"] == "Exact ABOD") & (scaling["n"] == 400)].iloc[0]
    full_stability = stability.loc[stability["method"] == "Full"]
    applicability_index = applicability.set_index("scenario")
    key_findings = {
        "angular_default": {
            str(target): {
                "scene_macro_nrmse": float(default_angular.loc[target, "scene_macro_nrmse"]),
                "nrmse_ci": [float(default_angular.loc[target, "nrmse_ci_low"]), float(default_angular.loc[target, "nrmse_ci_high"])],
                "pairs_per_task": float(default_angular.loc[target, "scene_macro_pairs_per_task"]),
                "no_truth_rate": float(default_angular.loc[target, "no_truth_rate"]),
                "exact_pair_reduction": float(1.0 - default_angular.loc[target, "scene_macro_pairs_per_task"] / exact_angular.loc[target, "scene_macro_pairs_per_task"]),
            }
            for target in (27, 39)
        },
        "stopping_default": {
            "scene_macro_gap": float(default_stop["scene_macro_gap"]),
            "scene_macro_gap_p95": float(default_stop["scene_macro_gap_p95"]),
            "max_gap": float(default_stop["max_gap"]),
            "cap_hit_rate": float(default_stop["cap_hit_rate"]),
            "iterations_p95": float(default_stop["iterations_p95"]),
        },
        "scaling": {
            "full_runtime_at_10000_s": float(at_10000["runtime_median_s"]),
            "full_throughput_at_10000_reports_s": float(at_10000["reports_per_second"]),
            "rabod_runtime_at_400_s": float(rabod_400["runtime_median_s"]),
            "exact_runtime_at_400_s": float(exact_400["runtime_median_s"]),
            "exact_to_rabod_ratio_at_400": float(exact_400["runtime_median_s"] / rabod_400["runtime_median_s"]),
            "exact_first_censored_n": int(scaling.loc[(scaling["method"] == "Exact ABOD") & scaling["censored"].fillna(False), "n"].min()),
            "slopes": slopes,
        },
        "stability": {
            "full_min_success_rate": float(full_stability["success_rate"].min()),
            "full_min_wilson_lower": float(full_stability["success_ci_low"].min()),
            "full_max_raw_weight": float(full_stability["max_raw_weight"].max()),
            "log_2": math.log(2.0),
            "full_max_normalization_error": float(full_stability["max_normalization_error"].max()),
            "trials_per_cell": int(full_stability["trials"].min()),
        },
        "angular_applicability": {
            scenario: {
                "nrmse": float(applicability_index.loc[scenario, "nrmse"]),
                "angular_available_rate": float(applicability_index.loc[scenario, "angular_available_rate"]),
            }
            for scenario in applicability_index.index
        },
    }
    dump_json(RESULTS / "rq4_key_findings.json", key_findings)
    audit = {
        "angular_rows": len(angular_raw),
        "angular_seeds": int(angular_raw["seed"].nunique()),
        "angular_tasks": [int(angular_raw["task_id"].min()), int(angular_raw["task_id"].max())],
        "angular_nonfinite_norm_sq": int((~np.isfinite(angular_raw.loc[~angular_raw["no_truth"], "norm_sq_sum"])).sum()),
        "stopping_rows": len(stopping_raw),
        "stopping_nonfinite_gap": int((~np.isfinite(stopping_raw["fixed_point_gap"])).sum()),
        "timing_min_repeats": int(timing.groupby(["method", "n"]).size().min()),
        "stability_rows": len(stability_raw),
        "stability_trials_per_cell": int(stability_raw.groupby(["method", "geometry", "tau"], dropna=False).size().min()),
        "full_stability_all_success": bool(full_stability["success_rate"].eq(1.0).all()),
        "frozen_parameter_match": config["parameters"],
    }
    dump_json(METADATA / "integrity_audit.json", audit)
    print(json.dumps(key_findings, indent=2))


if __name__ == "__main__":
    main()
