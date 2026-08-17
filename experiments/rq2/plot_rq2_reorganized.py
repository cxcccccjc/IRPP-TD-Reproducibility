from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

COLORS = {
    "Adaptive-HQ": "#0B5CAD",
    "No-Extra": "#B64040",
    "Random-Extra": "#B7791F",
    "Early (1--20)": "#6B7280",
    "Mature (61--100)": "#0B5CAD",
    "E0": "#6B7280",
    "E1": "#0F766E",
    "E3": "#B64040",
    "Stable 50/50": "#6B7280",
    "H-to-L (50%)": "#B64040",
    "L-to-H (50%)": "#0F766E",
    "grid": "#D7DEE8",
    "text": "#172033",
}
MARKERS = {
    "Adaptive-HQ": "o",
    "No-Extra": "s",
    "Random-Extra": "^",
    "Early (1--20)": "s",
    "Mature (61--100)": "o",
    "E0": "o",
    "E1": "s",
    "E3": "^",
    "Stable 50/50": "o",
    "H-to-L (50%)": "s",
    "L-to-H (50%)": "^",
}
LINESTYLES = {
    "Adaptive-HQ": "-",
    "No-Extra": "--",
    "Random-Extra": ":",
    "Early (1--20)": "--",
    "Mature (61--100)": "-",
    "E0": "--",
    "E1": "-.",
    "E3": "-",
    "Stable 50/50": "--",
    "H-to-L (50%)": "-",
    "L-to-H (50%)": ":",
}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.2,
            "axes.labelsize": 7.0,
            "axes.titlesize": 7.4,
            "xtick.labelsize": 6.2,
            "ytick.labelsize": 6.2,
            "legend.fontsize": 5.6,
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
            "grid.alpha": 0.72,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(0.01, 0.985, f"({letter})", transform=ax.transAxes, fontweight="bold", va="top", ha="left", zorder=10)


def save_bundle(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg"):
        fig.savefig(FIGURES / f"{stem}.{extension}", bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.tiff", dpi=600, bbox_inches="tight")


def plot_line_with_ci(ax: plt.Axes, frame: pd.DataFrame, x: str, y: str, label: str, scale: float = 1.0) -> None:
    part = frame.sort_values(x)
    xv = part[x].to_numpy(float)
    center = part[y].to_numpy(float) * scale
    low = part[f"{y}_ci_low"].to_numpy(float) * scale
    high = part[f"{y}_ci_high"].to_numpy(float) * scale
    ax.plot(
        xv,
        center,
        label=label,
        color=COLORS[label],
        marker=MARKERS[label],
        linestyle=LINESTYLES[label],
        linewidth=1.05,
        markersize=3.0,
        markeredgewidth=0.45,
    )
    ax.fill_between(xv, low, high, color=COLORS[label], alpha=0.10, linewidth=0)


def main_figure() -> None:
    cold = pd.read_csv(RESULTS / "rq2_cold_curve_95ci.csv")
    ratio = pd.read_csv(RESULTS / "rq2_ratio_phase_95ci.csv")
    early = pd.read_csv(RESULTS / "rq2_early_delta_95ci.csv")
    switch = pd.read_csv(RESULTS / "rq2_switch_curve_95ci.csv")

    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.60), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes

    for strategy in ("Adaptive-HQ", "No-Extra", "Random-Extra"):
        plot_line_with_ci(ax_a, cold.loc[cold["strategy"] == strategy], "block_end", "nrmse", strategy)
    ax_a.set_yscale("log")
    ax_a.set_ylim(1.0e-3, 4.0e-2)
    ax_a.set_xticks([10, 40, 70, 100])
    ax_a.set_xlabel("Task block end")
    ax_a.set_ylabel("NRMSE (log)")
    ax_a.set_title("Cold-start accuracy")
    ax_a.grid(axis="y", which="both")
    ax_a.legend(
        loc="upper center",
        bbox_to_anchor=(0.54, 1.0),
        ncol=1,
        fontsize=4.8,
        handlelength=1.35,
        handletextpad=0.3,
        labelspacing=0.12,
        borderaxespad=0.1,
    )
    panel_label(ax_a, "a")

    # Normalize by each phase's own clean control so phase difficulty cannot
    # masquerade as a malicious-composition effect.
    ratio_relative = ratio.copy()
    for phase in ("Early (1--20)", "Mature (61--100)"):
        phase_mask = ratio_relative["phase"] == phase
        control = float(ratio_relative.loc[phase_mask & (ratio_relative["malicious_ratio"] == 0.0), "nrmse"].iloc[0])
        for column in ("nrmse", "nrmse_ci_low", "nrmse_ci_high"):
            ratio_relative.loc[phase_mask, column] = 100.0 * (ratio_relative.loc[phase_mask, column] / control - 1.0)
        plot_line_with_ci(ax_b, ratio_relative.loc[phase_mask], "malicious_ratio", "nrmse", phase)
    ax_b.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax_b.set_xlabel(r"Malicious ratio $\rho_m$")
    ax_b.set_ylabel(r"NRMSE increase vs. $\rho_m=0$ (\%)")
    ax_b.set_title("Composition stress")
    ax_b.grid(axis="y")
    ax_b.legend(
        loc="lower right",
        fontsize=4.7,
        handlelength=1.25,
        handletextpad=0.25,
        labelspacing=0.15,
        borderaxespad=0.2,
    )
    panel_label(ax_b, "b")

    for condition in ("E1", "E3"):
        plot_line_with_ci(ax_c, early.loc[early["condition"] == condition], "block_end", "delta_nrmse", condition, 10000.0)
    ax_c.axhline(0.0, color=COLORS["text"], linewidth=0.65, linestyle=(0, (2, 2)))
    ax_c.set_xticks([10, 40, 70, 100])
    ax_c.set_xlabel("Task block end")
    ax_c.set_ylabel(r"Paired $\Delta$NRMSE ($\times10^{-4}$)")
    ax_c.set_title("Early rating errors")
    ax_c.grid(axis="y")
    ax_c.legend(loc="upper right", ncol=2, fontsize=5.0, handlelength=1.2, handletextpad=0.25, columnspacing=0.65)
    panel_label(ax_c, "c")

    for series in ("Stable 50/50", "H-to-L (50%)"):
        plot_line_with_ci(ax_d, switch.loc[switch["series"] == series], "block_end", "nrmse", series, 1000.0)
    ax_d.axvline(41, color=COLORS["text"], linewidth=0.65, linestyle=(0, (2, 2)))
    ax_d.text(42.5, 0.94, "switch", transform=ax_d.get_xaxis_transform(), ha="left", va="top", fontsize=4.8)
    ax_d.set_ylim(bottom=0.0)
    ax_d.set_xticks([10, 40, 70, 100])
    ax_d.set_xlabel("Task block end")
    ax_d.set_ylabel(r"NRMSE ($\times10^{-3}$)")
    ax_d.set_title(r"H$\rightarrow$L response")
    ax_d.grid(axis="y")
    ax_d.legend(loc="center left", fontsize=4.7, handlelength=1.25, handletextpad=0.25, labelspacing=0.15, borderaxespad=0.2)
    panel_label(ax_d, "d")

    fig.set_constrained_layout_pads(w_pad=0.015, h_pad=0.01, wspace=0.015, hspace=0.0)
    save_bundle(fig, "fig_rq2_reorganized_main_1x4")
    plt.close(fig)


def supplementary_figure() -> None:
    cold_curve = pd.read_csv(RESULTS / "rq2_cold_curve_95ci.csv")
    ratio_f1 = pd.read_csv(RESULTS / "rq2_ratio_worker_f1_95ci.csv")
    early_f1 = pd.read_csv(RESULTS / "rq2_early_worker_f1_95ci.csv")
    switch_f1 = pd.read_csv(RESULTS / "rq2_switch_worker_f1_95ci.csv")

    # The main figure uses error as system accuracy evidence. This figure keeps
    # the complementary screening interpretation and abstention-aware coverage.
    task = pd.read_csv(RESULTS / "formal_task_metrics.csv")
    block_size = 10
    task["block_end"] = ((task["task_id"] - 1) // block_size + 1) * block_size

    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.25), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat

    cold_task = task.loc[(task["experiment"] == "cold-start") & (task["target_workers"] == 27)]
    cold_f1_scene = cold_task.groupby(["strategy", "block_end", "seed", "scene"], as_index=False)["worker_macro_f1"].mean()
    cold_f1 = cold_f1_scene.groupby(["strategy", "block_end"], as_index=False)["worker_macro_f1"].mean()
    for strategy in ("Adaptive-HQ", "No-Extra", "Random-Extra"):
        part = cold_f1.loc[cold_f1["strategy"] == strategy]
        ax_a.plot(part["block_end"], part["worker_macro_f1"], color=COLORS[strategy], marker=MARKERS[strategy], linestyle=LINESTYLES[strategy], linewidth=1.1, markersize=3.4, label=strategy)
    ax_a.set(xlabel="Task block end", ylabel="Worker Macro-F1", title="Cold-start worker classification", ylim=(0, 1.03))
    ax_a.legend(loc="lower right", ncol=3, fontsize=5.5)
    ax_a.grid(axis="y")
    panel_label(ax_a, "a")

    heat = ratio_f1.loc[ratio_f1["malicious_ratio"].between(0.1, 0.8)].pivot(index="malicious_ratio", columns="block_end", values="worker_macro_f1")
    image = ax_b.imshow(heat.to_numpy(), origin="lower", aspect="auto", vmin=0, vmax=1, cmap="Blues")
    ax_b.set_xticks(np.arange(heat.shape[1]), [int(x) for x in heat.columns])
    ax_b.set_yticks(np.arange(heat.shape[0]), [f"{x:.1f}" for x in heat.index])
    ax_b.set(xlabel="Task block end", ylabel=r"Malicious ratio $\rho_m$", title="Worker Macro-F1 under composition stress")
    colorbar = fig.colorbar(image, ax=ax_b, fraction=0.046, pad=0.025)
    colorbar.ax.tick_params(labelsize=5.6)
    panel_label(ax_b, "b")

    for condition in ("E0", "E1", "E3"):
        part = early_f1.loc[early_f1["condition"] == condition].sort_values("block_end")
        ax_c.plot(part["block_end"], part["worker_macro_f1"], color=COLORS[condition], marker=MARKERS[condition], linestyle=LINESTYLES[condition], linewidth=1.1, markersize=3.4, label=condition)
    ax_c.set(xlabel="Task block end", ylabel="Worker Macro-F1", title="Classification after early rating errors", ylim=(0, 1.03))
    ax_c.legend(loc="lower right", ncol=3)
    ax_c.grid(axis="y")
    panel_label(ax_c, "c")

    for series in ("Stable 50/50", "H-to-L (50%)", "L-to-H (50%)"):
        part = switch_f1.loc[switch_f1["series"] == series].sort_values("block_end")
        ax_d.plot(part["block_end"], part["worker_macro_f1"], color=COLORS[series], marker=MARKERS[series], linestyle=LINESTYLES[series], linewidth=1.1, markersize=3.4, label=series)
    ax_d.axvline(41, color=COLORS["text"], linewidth=0.7, linestyle=(0, (2, 2)))
    ax_d.set(xlabel="Task block end", ylabel="Worker Macro-F1", title="Behavior-change classification", ylim=(0, 1.03))
    ax_d.legend(loc="lower left", fontsize=5.4)
    ax_d.grid(axis="y")
    panel_label(ax_d, "d")

    save_bundle(fig, "fig_rq2_reorganized_supplement_2x2")
    plt.close(fig)


def replication_figure() -> None:
    cold27 = pd.read_csv(RESULTS / "rq2_cold_summary_95ci.csv")
    cold39 = pd.read_csv(RESULTS / "rq2_cold_n39_summary_95ci.csv")
    severity = pd.read_csv(RESULTS / "rq2_switch_severity_95ci.csv")
    switch = pd.read_csv(RESULTS / "rq2_switch_curve_95ci.csv")
    events = pd.read_csv(RESULTS / "rq2_event_summary_95ci.csv")

    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.05), constrained_layout=True)
    ax_a, ax_b, ax_c = axes
    strategies = ["Adaptive-HQ", "No-Extra", "Random-Extra"]
    x = np.arange(3)
    for offset, target, frame, color, hatch in [(-0.16, 27, cold27, "#0B5CAD", ""), (0.16, 39, cold39, "#8EC3F5", "//")]:
        values = frame.set_index("strategy").loc[strategies, "nrmse"].to_numpy()
        ax_a.bar(x + offset, values, 0.30, color=color, edgecolor=COLORS["text"], linewidth=0.55, hatch=hatch, label=rf"$\bar n={target}$")
    ax_a.set_yscale("log")
    ax_a.set_xticks(x, ["Adaptive\nHQ", "No\nextra", "Random\nextra"])
    ax_a.set(ylabel="NRMSE (log)", title="Participation replication")
    ax_a.legend(loc="lower center", ncol=2)
    ax_a.grid(axis="y", which="both")
    panel_label(ax_a, "a")

    ax_b.errorbar(
        severity["switch_fraction"],
        severity["nrmse"] * 1000,
        yerr=np.vstack([(severity["nrmse"] - severity["nrmse_ci_low"]) * 1000, (severity["nrmse_ci_high"] - severity["nrmse"]) * 1000]),
        color=COLORS["H-to-L (50%)"], marker="o", linewidth=1.1, capsize=2.0,
    )
    ax_b.set(xlabel="Fraction of former H workers switching", ylabel=r"Post-switch NRMSE ($\times10^{-3}$)", title=r"H$\rightarrow$L severity")
    ax_b.set_xticks([0.25, 0.5, 1.0])
    ax_b.grid(axis="y")
    panel_label(ax_b, "b")

    selected = events.loc[
        ((events["experiment"] == "h-to-l") & (events["condition"] == "switch=0.50") & (events["event"] == "detect-h-to-l"))
        | ((events["experiment"] == "l-to-h") & (events["condition"] == "switch=0.50") & (events["event"] == "recover-l-to-h"))
    ].copy()
    labels = [r"Detect H$\to$L", r"Recover L$\to$H"]
    selected = selected.set_index("event").loc[["detect-h-to-l", "recover-l-to-h"]]
    values = selected["restricted_mean_delay"].to_numpy()
    errors = np.vstack([values - selected["delay_ci_low"].to_numpy(), selected["delay_ci_high"].to_numpy() - values])
    ax_c.bar(np.arange(2), values, yerr=errors, capsize=2.0, color=["#F2CCCC", "#B7E0D8"], edgecolor=COLORS["text"], linewidth=0.6)
    for idx, rate in enumerate(selected["censoring_rate"]):
        ax_c.text(idx, values[idx] * 0.55, f"cens.\n{100*rate:.1f}%", ha="center", va="center", fontsize=5.6)
    ax_c.set_xticks(np.arange(2), labels)
    ax_c.set(ylabel="Restricted mean participation delay", title="Detection and recovery")
    ax_c.grid(axis="y")
    panel_label(ax_c, "c")

    save_bundle(fig, "fig_rq2_reorganized_replication_1x3")
    plt.close(fig)


def write_captions() -> None:
    text = r"""\textbf{Fig.~2.} RQ2 closed-loop reputation, cold-start, and feedback behavior on the three SUMO-driven workloads at target participation $\bar n=27$. (a) Ten-task-block NRMSE for adaptive high-quality bootstrap, no-extra temporary ordinary anchors, and a random-extra control that contributes the same $s_0=5$ reports whenever its bootstrap is active. (b) Early and mature NRMSE increase relative to the phase-matched clean control as the stable malicious-worker ratio grows; binary Macro-F1 is undefined at $\rho_m=0$. (c) Paired block-wise NRMSE change after one (E1) or three (E3) forced early false-low updates to otherwise reliable workers, relative to E0. (d) Error response when half of the initially high-quality workers switch permanently to low quality at task 41. Curves and bands are the scene-macro mean and 95\% seed-bootstrap interval over 30 paired seeds; lower is better.

\textbf{Fig.~S2.} Screening interpretation complementary to Fig.~2. (a) Abstention-aware worker Macro-F1 for the three cold-start policies. (b) Worker Macro-F1 over task blocks and nonzero malicious ratios. (c) Worker Macro-F1 under E0/E1/E3. (d) Worker Macro-F1 for stable, H$\to$L, and L$\to$H populations. Unclassified workers reduce recall rather than being discarded from the denominator.

\textbf{Fig.~S3.} Secondary RQ2 accuracy and adaptation evidence. (a) Cold-start NRMSE at target participation 27 and 39. (b) Post-switch NRMSE as the fraction of formerly high-quality workers that becomes low quality increases. (c) Restricted mean participation delay and right-censoring for H$\to$L detection and L$\to$H recovery at a 50\% switch.
"""
    (FIGURES / "rq2_reorganized_captions.tex").write_text(text, encoding="utf-8")


def main() -> None:
    apply_style()
    main_figure()
    supplementary_figure()
    replication_figure()
    write_captions()
    print(f"RQ2 figure bundle written to {FIGURES}")


if __name__ == "__main__":
    main()
