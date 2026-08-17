from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

COLORS = {
    "Climate": "#0B5CAD",
    "Traffic": "#B7791F",
    "Water": "#B64040",
    "proposed": "#0B5CAD",
    "close": "#0F766E",
    "traditional": "#B64040",
    "neutral": "#6B7280",
    "grid": "#D7DEE8",
    "text": "#172033",
}
MARKERS = {"Climate": "o", "Traffic": "s", "Water": "^"}
LINESTYLES = {"Climate": "-", "Traffic": "--", "Water": ":"}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.2,
            "axes.labelsize": 7.0,
            "axes.titlesize": 7.5,
            "xtick.labelsize": 6.3,
            "ytick.labelsize": 6.3,
            "legend.fontsize": 6.2,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": COLORS["text"],
            "axes.labelcolor": COLORS["text"],
            "text.color": COLORS["text"],
            "xtick.color": COLORS["text"],
            "ytick.color": COLORS["text"],
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.55,
            "grid.alpha": 0.7,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(0.01, 0.98, f"({letter})", transform=ax.transAxes, fontweight="bold", va="top", ha="left", zorder=10)


def save_bundle(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg"):
        fig.savefig(FIGURES / f"{stem}.{extension}", bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.tiff", dpi=600, bbox_inches="tight")


def main_figure(summary: pd.DataFrame, raw: pd.DataFrame, layout: str) -> None:
    if layout == "2x2":
        fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.85), constrained_layout=True)
        stem = "fig_rq1_main_2x2"
    elif layout == "1x4":
        fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.60), constrained_layout=True)
        stem = "fig_rq1_main_1x4"
    else:
        raise ValueError(f"Unsupported layout: {layout}")
    ax_a, ax_b, ax_c, ax_d = np.asarray(axes).reshape(-1)
    compact = layout == "1x4"
    selected = ["CRH-N", "QE", "BLIND", "RPPS-TDC", "PRTD", "IRPP-TD"]
    n27 = summary.loc[(summary["target_workers"] == 27) & summary["method"].isin(selected)]
    x = np.arange(len(selected))
    ax_a.axvspan(len(selected) - 1.38, len(selected) - 0.62, color="#E6F1FB", zorder=0)
    for scene in ["Climate", "Traffic", "Water"]:
        scene_frame = n27.loc[n27["scene"] == scene].set_index("method").loc[selected]
        y = scene_frame["nrmse"].to_numpy()
        lower = y - scene_frame["nrmse_ci_low"].to_numpy()
        upper = scene_frame["nrmse_ci_high"].to_numpy() - y
        ax_a.errorbar(
            x,
            y,
            yerr=np.vstack([lower, upper]),
            label=scene,
            color=COLORS[scene],
            marker=MARKERS[scene],
            linestyle=LINESTYLES[scene],
            linewidth=1.0 if compact else 1.15,
            markersize=3.2 if compact else 4.0,
            capsize=1.4 if compact else 1.8,
        )
    ax_a.set_yscale("log")
    ax_a.set_ylim(top=5.0e-2)
    ax_a.set_xticks(x, selected, rotation=30, ha="right")
    ax_a.set_ylabel("NRMSE (log)" if compact else "NRMSE (log scale, lower is better)")
    ax_a.set_title(r"Accuracy ($\bar n=27$)" if compact else r"Held-out accuracy at $\bar n=27$")
    ax_a.grid(axis="y", which="both")
    legend_options = {
        "ncol": 3,
        "loc": "upper center",
        "bbox_to_anchor": (0.5, 0.995),
        "fontsize": 4.6 if compact else 6.0,
        "handlelength": 1.0,
        "handletextpad": 0.25,
        "columnspacing": 0.55,
        "borderaxespad": 0.15,
        "labelspacing": 0.15,
        "frameon": True,
        "framealpha": 0.78,
        "edgecolor": "none",
    }
    ax_a.legend(**legend_options)
    panel_label(ax_a, "a")

    test = raw.loc[(raw["target_workers"] == 27) & raw["task_id"].between(21, 100)]
    irpp_task = test.loc[test["method"] == "IRPP-TD"].groupby(["scene", "task_id"], as_index=False)["task_nrmse"].mean()
    comparisons = {
        "IRPP-TD": irpp_task["task_nrmse"].to_numpy(),
        "CRH-N": test.loc[test["method"] == "CRH-N", "task_nrmse"].to_numpy(),
        "PRTD": test.loc[test["method"] == "PRTD", "task_nrmse"].to_numpy(),
        "RPPS-TDC": test.loc[test["method"] == "RPPS-TDC", "task_nrmse"].to_numpy(),
    }
    cdf_styles = {
        "IRPP-TD": (COLORS["proposed"], "-"),
        "CRH-N": (COLORS["neutral"], "--"),
        "PRTD": (COLORS["close"], ":"),
        "RPPS-TDC": (COLORS["traditional"], "-."),
    }
    for method, values in comparisons.items():
        values = np.sort(values[np.isfinite(values)])
        cumulative = np.arange(1, len(values) + 1) / len(values)
        color, linestyle = cdf_styles[method]
        ax_b.plot(values, cumulative, label=method, color=color, linestyle=linestyle, linewidth=1.15 if compact else 1.25)
    ax_b.set_xscale("log")
    ax_b.set_xlabel("Task NRMSE (log)" if compact else r"Task NRMSE at $\bar n=27$ (log scale)")
    ax_b.set_ylabel("Empirical CDF")
    ax_b.set_title("Task-error distribution" if compact else "Normalized task-error distribution")
    ax_b.grid(which="both")
    ax_b.legend(
        loc="lower right",
        fontsize=5.0 if compact else 6.2,
        handlelength=1.35,
        handletextpad=0.35,
        labelspacing=0.18,
        borderaxespad=0.25,
    )
    panel_label(ax_b, "b")

    ratios = []
    for method in selected:
        method_frame = summary.loc[summary["method"] == method].set_index(["scene", "target_workers"])
        scene_ratios = np.asarray(
            [
                method_frame.loc[(scene, 39), "nrmse"] / method_frame.loc[(scene, 27), "nrmse"]
                for scene in ["Climate", "Traffic", "Water"]
            ]
        )
        ratios.append(scene_ratios)
    means = np.asarray([item.mean() for item in ratios])
    lower = means - np.asarray([item.min() for item in ratios])
    upper = np.asarray([item.max() for item in ratios]) - means
    colors = [COLORS["neutral"]] * (len(selected) - 1) + [COLORS["proposed"]]
    sizes = [24] * (len(selected) - 1) + [38]
    for idx, (mean, low, high, color, size) in enumerate(zip(means, lower, upper, colors, sizes)):
        ax_c.errorbar(idx, mean, yerr=np.asarray([[low], [high]]), fmt="none", ecolor=color, capsize=2.2, linewidth=1.0)
        ax_c.scatter(idx, mean, c=color, s=size * (0.72 if compact else 1.0), marker="o", edgecolor="white", linewidth=0.5, zorder=3)
    ax_c.axhline(1.0, color=COLORS["neutral"], linewidth=0.9, linestyle="--")
    ax_c.set_xticks(x, selected, rotation=30, ha="right")
    ax_c.set_ylabel(r"NRMSE ratio: $39/27$")
    ax_c.set_title("Participation sensitivity" if compact else "Participant sensitivity (mean and scene range)")
    ax_c.grid(axis="y")
    panel_label(ax_c, "c")

    pareto = summary.loc[summary["target_workers"] == 27].groupby("method", as_index=False).agg(
        nrmse=("nrmse", "mean"), runtime=("runtime_median_ms", "mean")
    )
    roles = {
        "IRPP-TD": "proposed",
        "PRTD": "close",
        "RPPS-TDC": "close",
        "CRH": "traditional",
        "CRH-N": "traditional",
    }
    label_layout = {
        "Mean": ((4, -5), "left", "top"),
        "CRH": ((5, 4), "left", "bottom"),
        "CRH-N": ((-7, -6), "right", "top"),
        "QE": ((-4, 4), "right", "bottom"),
        "RTD": ((0, -7), "center", "top"),
        "BLIND": ((0, -7), "center", "top"),
        "PRTD": ((4, -4), "left", "center"),
        "RPPS-TDC": ((7, -8), "left", "top"),
        "IRPP-TD": ((6, 0), "left", "center"),
    }
    for row in pareto.loc[pareto["method"] != "Median"].itertuples(index=False):
        role = roles.get(row.method, "neutral")
        if row.method == "IRPP-TD":
            size = 40 if compact else 52
            marker = "*"
        else:
            size = 22 if compact else 28
            marker = "o"
        ax_d.scatter(row.runtime, row.nrmse, s=size, marker=marker, color=COLORS[role], edgecolor="white", linewidth=0.5, zorder=3)
        (dx, dy), ha, va = label_layout.get(row.method, ((4, -3), "left", "center"))
        arrowprops = (
            {
                "arrowstyle": "-",
                "color": COLORS["neutral"],
                "linewidth": 0.4,
                "shrinkA": 1.5,
                "shrinkB": 2.5,
            }
            if row.method in {"CRH", "CRH-N", "RPPS-TDC"}
            else None
        )
        if row.method == "CRH":
            # Preserve the leader at its pre-offset geometry while allowing
            # the visible label to move independently.
            ax_d.annotate(
                row.method,
                (row.runtime, row.nrmse),
                xytext=(7, 6),
                textcoords="offset points",
                ha="left",
                va="bottom",
                fontsize=5.4 if compact else 6.2,
                color=(0.0, 0.0, 0.0, 0.0),
                arrowprops=arrowprops,
            )
            arrowprops = None
        ax_d.annotate(
            row.method,
            (row.runtime, row.nrmse),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=5.4 if compact else 6.2,
            arrowprops=arrowprops,
        )
    ax_d.set_xscale("log")
    ax_d.set_yscale("log")
    ax_d.set_ylim(8.0e-4, 4.0e-2)
    ax_d.set_xlabel("Runtime/task (ms, log)" if compact else "Median runtime per task (ms, log scale)")
    ax_d.set_ylabel("Mean NRMSE (log)" if compact else "Scene-mean NRMSE (log scale)")
    ax_d.set_title("Accuracy--cost" if compact else "Accuracy--cost operating points")
    ax_d.grid(which="both")
    panel_label(ax_d, "d")

    if compact:
        fig.set_constrained_layout_pads(w_pad=0.015, h_pad=0.01, wspace=0.015, hspace=0.0)

    save_bundle(fig, stem)
    if compact:
        save_bundle(fig, "fig_rq1_main")
    plt.close(fig)


def diagnostics_figure(
    raw: pd.DataFrame,
    phases: pd.DataFrame,
    stability: pd.DataFrame,
    paired: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.85), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat
    base = raw.loc[raw["method"] == "Mean"]
    labels, participant_values = [], []
    for scene in ["Climate", "Traffic", "Water"]:
        for workers in [27, 39]:
            frame = base.loc[(base["scene"] == scene) & (base["target_workers"] == workers)]
            labels.append(f"{scene[0]}-{workers}")
            participant_values.append(frame["participant_count"].to_numpy())
    bp = ax_a.boxplot(participant_values, tick_labels=labels, patch_artist=True, widths=0.62, showfliers=False)
    for patch, idx in zip(bp["boxes"], range(6)):
        patch.set_facecolor([COLORS["Climate"], COLORS["Climate"], COLORS["Traffic"], COLORS["Traffic"], COLORS["Water"], COLORS["Water"]][idx])
        patch.set_alpha(0.65)
    ax_a.set_ylabel("Realized participants per task")
    ax_a.set_title("SUMO participation variability")
    ax_a.grid(axis="y")
    panel_label(ax_a, "a")

    stability_groups, stability_labels = [], []
    for scene in ["Climate", "Traffic", "Water"]:
        for workers in [27, 39]:
            values = stability.loc[(stability["scene"] == scene) & (stability["target_workers"] == workers), "nrmse"].to_numpy()
            stability_groups.append(values)
            stability_labels.append(f"{scene[0]}-{workers}")
    bp2 = ax_b.boxplot(stability_groups, tick_labels=stability_labels, patch_artist=True, widths=0.62, showfliers=True)
    for patch, idx in zip(bp2["boxes"], range(6)):
        patch.set_facecolor([COLORS["Climate"], COLORS["Climate"], COLORS["Traffic"], COLORS["Traffic"], COLORS["Water"], COLORS["Water"]][idx])
        patch.set_alpha(0.65)
    ax_b.set_yscale("log")
    ax_b.set_ylabel("IRPP-TD NRMSE over 30 seeds")
    ax_b.set_title("Run-to-run stability")
    ax_b.grid(axis="y", which="both")
    panel_label(ax_b, "b")

    strongest = paired.loc[paired["baseline"] == "CRH-N"].copy()
    y_positions = np.arange(len(strongest))
    point = strongest["delta_nrmse"].to_numpy()
    errors = np.vstack([point - strongest["delta_ci_low"].to_numpy(), strongest["delta_ci_high"].to_numpy() - point])
    colors = [COLORS[row.scene] for row in strongest.itertuples(index=False)]
    for idx, (value, position, color) in enumerate(zip(point, y_positions, colors)):
        ax_c.errorbar(value, position, xerr=np.asarray([[errors[0, idx]], [errors[1, idx]]]), fmt="none", ecolor=color, capsize=2.2, linewidth=1.1)
        ax_c.scatter(value, position, c=color, marker="o", s=28, zorder=3, edgecolor="white", linewidth=0.5)
    ax_c.axvline(0.0, color=COLORS["neutral"], linestyle="--", linewidth=0.9)
    ax_c.set_yticks(y_positions, [f"{row.scene}-$n${row.target_workers}" for row in strongest.itertuples(index=False)])
    ax_c.set_xlabel("Paired NRMSE difference (IRPP-TD - CRH-N)")
    ax_c.set_title("95% task-bootstrap intervals")
    ax_c.grid(axis="x")
    panel_label(ax_c, "c")

    phase_order = ["Calibration (1-20)", "Early test (21-50)", "Mature test (51-100)"]
    phase_x = np.arange(3)
    n27_phase = phases.loc[phases["target_workers"] == 27]
    for scene in ["Climate", "Traffic", "Water"]:
        irpp = n27_phase.loc[(n27_phase["scene"] == scene) & (n27_phase["method"] == "IRPP-TD")].set_index("phase")
        phase_nrmse = irpp.loc[phase_order, "nrmse"].to_numpy()
        ax_d.plot(
            phase_x,
            phase_nrmse,
            color=COLORS[scene],
            marker=MARKERS[scene],
            linestyle=LINESTYLES[scene],
            linewidth=1.25,
            markersize=4.2,
            label=scene,
        )
    ax_d.axvspan(-0.35, 0.35, color="#F3F4F6", zorder=0)
    ax_d.set_xticks(phase_x, ["Calibration\n1--20", "Early\n21--50", "Mature\n51--100"])
    ax_d.set_yscale("log")
    ax_d.set_ylim(2.6e-4, 1.2e-2)
    ax_d.set_ylabel("IRPP-TD NRMSE (log)")
    ax_d.set_title("IRPP-TD task-phase behavior")
    ax_d.grid(axis="y", which="both")
    ax_d.legend(loc="upper right")
    panel_label(ax_d, "d")

    save_bundle(fig, "fig_rq1_diagnostics")
    plt.close(fig)


def write_captions() -> None:
    caption = r"""\textbf{Fig.~1.} RQ1 truth-discovery effectiveness on the three SUMO-driven workloads. (a) Held-out NRMSE (tasks 21--100) at $\bar n=27$ with 95\% bootstrap intervals. (b) Empirical CDF of held-out task NRMSE at $\bar n=27$ for IRPP-TD and the three closest retained accuracy competitors. (c) Change in NRMSE when target participation increases from 27 to 39; points show the scene mean and bars the scene range. (d) Scene-mean accuracy--cost operating points. Lower is better in panels (a), (c), and (d); a left-shifted CDF indicates lower task error in panel (b).

\textbf{Fig.~S1.} RQ1 diagnostics. (a) Realized rather than requested task participation in the six stored SUMO workloads (C/T/W denote Climate/Traffic/Water). (b) IRPP-TD NRMSE over 30 anchor-sampling seeds. (c) Paired IRPP-TD-minus-CRH-N NRMSE with 95\% task-bootstrap intervals. (d) Absolute IRPP-TD NRMSE across calibration, early-test, and mature-test phases at $\bar n=27$.
"""
    (FIGURES / "rq1_captions.tex").write_text(caption, encoding="utf-8")


def main() -> None:
    apply_style()
    summary = pd.read_csv(RESULTS / "rq1_summary_95ci.csv")
    phases = pd.read_csv(RESULTS / "rq1_phase_summary.csv")
    raw = pd.read_csv(RESULTS / "rq1_task_level_results.csv")
    stability = pd.read_csv(RESULTS / "rq1_irpp_seed_stability.csv")
    paired = pd.read_csv(RESULTS / "rq1_paired_vs_irpp.csv")
    main_figure(summary, raw, "2x2")
    main_figure(summary, raw, "1x4")
    diagnostics_figure(raw, phases, stability, paired)
    write_captions()
    print(f"Figures written to {FIGURES}")


if __name__ == "__main__":
    main()
