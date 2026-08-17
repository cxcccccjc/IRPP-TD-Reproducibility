from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

COLORS = {
    "IRPP-TD": "#0B5CAD",
    "CRH-N": "#6B7280",
    "PRTD": "#0F766E",
    "QE": "#B64040",
    "RPPS-TDC": "#B7791F",
    "Full": "#0B5CAD",
    "Binary-Rep.": "#B7791F",
    "No-U": "#7C3AED",
    "All-Anchors": "#B64040",
    "Sequential": "#0F766E",
    "Independent": "#6B7280",
    "Compact": "#0B5CAD",
    "On--Off": "#B7791F",
    "Mature-Anchor": "#B64040",
    "grid": "#D7DEE8",
    "text": "#172033",
}
MARKERS = {"IRPP-TD": "o", "CRH-N": "s", "PRTD": "^", "QE": "D", "RPPS-TDC": "P"}
MODE_NAMES = {"independent": "Independent", "compact": "Compact", "onoff": "On--Off", "mature_anchor": "Mature-Anchor"}


def apply_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.2,
        "axes.labelsize": 7.0,
        "axes.titlesize": 7.5,
        "xtick.labelsize": 6.3,
        "ytick.labelsize": 6.3,
        "legend.fontsize": 5.7,
        "axes.linewidth": .8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": COLORS["text"],
        "axes.labelcolor": COLORS["text"],
        "text.color": COLORS["text"],
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "grid.color": COLORS["grid"],
        "grid.linewidth": .55,
        "grid.alpha": .7,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(.01, .98, f"({letter})", transform=ax.transAxes, fontweight="bold", va="top", ha="left", zorder=20)


def save_bundle(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ["pdf", "svg"]:
        fig.savefig(FIGURES / f"{stem}.{extension}")
    fig.savefig(FIGURES / f"{stem}.png", dpi=300)
    fig.savefig(FIGURES / f"{stem}.tiff", dpi=600)


def prevalence_panel(ax: plt.Axes, summary: pd.DataFrame, target: int, title: str) -> None:
    part = summary.loc[summary.target_workers == target]
    for method in ["IRPP-TD", "CRH-N", "PRTD", "QE"]:
        rows = part.loc[part.method == method].sort_values("malicious_ratio")
        x, y = rows.malicious_ratio.to_numpy(), rows.nrmse.to_numpy()
        ax.plot(x, y, color=COLORS[method], marker=MARKERS[method], markersize=2.8, linewidth=1.05, label=method)
        ax.fill_between(x, rows.nrmse_ci_low, rows.nrmse_ci_high, color=COLORS[method], alpha=.10, linewidth=0)
    ax.set_yscale("log")
    ax.set_xlim(-.015, .815)
    ax.set_xticks([0, .2, .4, .6, .8])
    ax.set_xlabel(r"Malicious-worker ratio $\rho_m$")
    ax.set_ylabel("Returned-task NRMSE")
    ax.set_title(title)
    ax.grid(axis="y", which="both")
    ax.legend(
        ncol=1, loc="center right", bbox_to_anchor=(.995, .53),
        handlelength=1.25, labelspacing=.16, borderpad=.28,
        frameon=True, framealpha=.92, facecolor="white", edgecolor="none",
    )


def mode_method_panel(ax: plt.Axes, summary: pd.DataFrame) -> None:
    order = ["clean", "independent", "compact", "onoff", "mature_anchor"]
    labels = ["Clean", "Ind.", "Compact", "On--Off", "Mature"]
    methods = ["IRPP-TD", "CRH-N", "PRTD", "QE"]
    offsets = dict(zip(methods, [-.285, -.095, .095, .285]))
    hatches = {"IRPP-TD": "", "CRH-N": "\\\\", "PRTD": "..", "QE": "//"}
    x = np.arange(len(order), dtype=float)
    for method in methods:
        rows = summary.loc[summary.method == method].set_index("mode").loc[order]
        y = rows.nrmse.to_numpy(float)
        yerr = np.vstack([
            y - rows.nrmse_ci_low.to_numpy(float),
            rows.nrmse_ci_high.to_numpy(float) - y,
        ])
        ax.bar(
            x + offsets[method], y, width=.18, color=COLORS[method],
            edgecolor="#172033", linewidth=.35, hatch=hatches[method],
            alpha=.91, label=method, zorder=3,
        )
        ax.errorbar(
            x + offsets[method], y, yerr=yerr, color="#172033",
            marker="none", linestyle="none", elinewidth=.55, capsize=1.1,
            capthick=.55, zorder=4,
        )
    ax.set_yscale("log")
    ax.set_xlim(-.52, 4.52)
    ax.set_xticks(x, labels, rotation=18, ha="right")
    ax.set_xlabel("Replay condition")
    ax.set_ylabel("Active-task NRMSE")
    ax.set_title("Mode accuracy")
    ax.grid(axis="y", which="both")
    ax.legend(
        ncol=2, loc="center right", bbox_to_anchor=(.995, .25),
        handlelength=.95, columnspacing=.42, labelspacing=.10, borderpad=.22,
        frameon=True, framealpha=.88, facecolor="white", edgecolor="none",
    )


def leakage_method_panel(ax: plt.Axes, summary: pd.DataFrame) -> None:
    order = ["independent", "compact", "onoff", "mature_anchor"]
    labels = ["Ind.", "Compact", "On--Off", "Mature"]
    methods = ["IRPP-TD", "RPPS-TDC", "PRTD"]
    offsets = {"IRPP-TD": -.24, "RPPS-TDC": 0.0, "PRTD": .24}
    hatches = {"IRPP-TD": "", "RPPS-TDC": "xx", "PRTD": ".."}
    x = np.arange(len(order), dtype=float)
    for method in methods:
        rows = summary.loc[summary.method == method].set_index("mode").loc[order]
        y = rows.malicious_report_leakage.to_numpy(float)
        low = rows.malicious_report_leakage_ci_low.to_numpy(float)
        high = rows.malicious_report_leakage_ci_high.to_numpy(float)
        ax.bar(
            x + offsets[method], y, width=.225, color=COLORS[method],
            edgecolor="#172033", linewidth=.4, hatch=hatches[method],
            alpha=.91, label=method, zorder=3,
        )
        ax.errorbar(
            x + offsets[method], y,
            yerr=np.vstack([y - low, high - y]), fmt="none",
            ecolor="#172033", elinewidth=.55, capsize=1.1, capthick=.55,
            zorder=4,
        )
        for x0, value, high_point in zip(x + offsets[method], y, high):
            if value == 0.0:
                label = "0"
            elif value < .001:
                label = "<.001"
            else:
                label = f"{value:.2f}"
            label_offset = 7.0 if method == "RPPS-TDC" and value < .001 else 2.0
            ax.annotate(
                label, (x0, high_point), xytext=(0, label_offset),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=3.4, zorder=5,
            )
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, .25, .5, .75, 1.0])
    ax.set_xticks(x, labels, rotation=18, ha="right")
    ax.set_xlabel("Attack mode")
    ax.set_ylabel("Malicious-report leakage")
    ax.set_title("Poison-report penetration")
    ax.grid(axis="y")
    ax.legend(
        ncol=3, loc="upper center", bbox_to_anchor=(.50, .985),
        handlelength=.82, columnspacing=.42, labelspacing=.10, borderpad=.18,
        frameon=True, framealpha=.90, facecolor="white", edgecolor="none",
        fontsize=5.0,
    )


def rate_panel(ax: plt.Axes, modes: pd.DataFrame, value: str, title: str, ylabel: str) -> None:
    order = ["independent", "compact", "onoff", "mature_anchor"]
    labels = ["Ind.", "Compact", "On--Off", "Mature"]
    display = ["Independent", "Compact", "On--Off", "Mature-Anchor"]
    rows = modes.set_index("mode").loc[order]
    y = rows[value].to_numpy(float)
    low = rows[f"{value}_ci_low"].to_numpy(float)
    high = rows[f"{value}_ci_high"].to_numpy(float)
    x = np.arange(len(order), dtype=float)
    bars = ax.bar(
        x, y, width=.66, color=[COLORS[item] for item in display],
        edgecolor="#172033", linewidth=.45, alpha=.90,
    )
    ax.errorbar(
        x, y, yerr=np.vstack([y - low, high - y]), fmt="none",
        ecolor="#172033", elinewidth=.7, capsize=1.5, capthick=.7,
    )
    ceiling = max(.01, float(high.max()) * 1.25)
    ax.set_ylim(0, ceiling)
    ax.set_xticks(x, labels, rotation=22, ha="right")
    ax.set_xlabel("Attack mode")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y")
    for bar, value_point, high_point in zip(bars, y, high):
        label = "0" if value_point < .0005 else f"{value_point:.3f}"
        ax.annotate(
            label, (bar.get_x() + bar.get_width() / 2, high_point),
            xytext=(0, 2.2), textcoords="offset points", ha="center",
            va="bottom", fontsize=4.9,
        )


def strength_panel(ax: plt.Axes, fig: plt.Figure, strength: pd.DataFrame) -> None:
    ratios = sorted(strength.malicious_ratio.unique())
    strengths = sorted(strength.strength.unique())
    grid = strength.pivot(index="strength", columns="malicious_ratio", values="error_ratio").loc[strengths, ratios]
    positive = grid.to_numpy()[grid.to_numpy() > 0]
    vmax = max(5.0, float(np.nanpercentile(positive, 98)))
    mesh = ax.imshow(
        grid, origin="lower", aspect="auto", cmap="YlOrRd",
        norm=LogNorm(vmin=max(.8, float(np.nanmin(positive))), vmax=vmax),
    )
    failed = strength.pivot(index="strength", columns="malicious_ratio", values="operational_failure").loc[strengths, ratios]
    for iy, strength_value in enumerate(strengths):
        for ix, ratio in enumerate(ratios):
            if bool(failed.loc[strength_value, ratio]):
                ax.plot(ix, iy, marker="x", color="#172033", markersize=3.2, markeredgewidth=.8)
    ax.set_xticks(range(len(ratios)), [f"{x:.1f}" for x in ratios], rotation=45, ha="right")
    ax.set_yticks(range(len(strengths)), [f"{x:g}" for x in strengths])
    ax.set_xlabel(r"Malicious-worker ratio $\rho_m$")
    ax.set_ylabel(r"Attack strength $\kappa$")
    ax.set_title("Mature-anchor boundary")
    cax = ax.inset_axes([.925, .51, .022, .38])
    cb = fig.colorbar(mesh, cax=cax, orientation="vertical")
    cb.ax.tick_params(labelsize=4.5, length=1.2, pad=1)
    cb.ax.set_title(r"$R_E$", fontsize=4.8, pad=1)
    ax.text(
        .05, .84, r"$\times$: failure", transform=ax.transAxes,
        ha="left", va="top", fontsize=4.8,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": .72, "pad": .6},
    )


def main_figure() -> None:
    prevalence = pd.read_csv(RESULTS / "rq3_prevalence_summary.csv")
    modes = pd.read_csv(RESULTS / "rq3_mode_summary.csv")
    mode_methods = pd.read_csv(RESULTS / "rq3_mode_method_summary.csv")
    leakage_methods = pd.read_csv(RESULTS / "rq3_leakage_method_summary.csv")
    feedback = pd.read_csv(RESULTS / "rq3_feedback_summary.csv")
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.60), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes

    prevalence_panel(ax_a, prevalence, 27, r"Compact collusion ($\kappa=0.5$)")

    mode_method_panel(ax_b, mode_methods)
    leakage_method_panel(ax_c, leakage_methods)

    line_styles = {"Full": "-", "Binary-Rep.": "--", "All-Anchors": "-.", "Sequential": ":"}
    markers = {"Full": "o", "Binary-Rep.": "s", "All-Anchors": "^", "Sequential": "D"}
    for variant in ["Full", "Binary-Rep.", "All-Anchors", "Sequential"]:
        rows = feedback.loc[feedback.variant == variant].sort_values("block_end")
        ax_d.plot(rows.block_end, rows.ordinary_anchor_purity, color=COLORS[variant], linestyle=line_styles[variant], marker=markers[variant], markersize=2.5, linewidth=1.0, label=variant)
        ax_d.fill_between(rows.block_end, rows.ordinary_anchor_purity_ci_low, rows.ordinary_anchor_purity_ci_high, color=COLORS[variant], alpha=.08, linewidth=0)
    ax_d.axvline(41, color="#6B7280", linestyle="--", linewidth=.75)
    ax_d.set_xlim(8, 102)
    ax_d.set_ylim(.48, 1.015)
    ax_d.set_xticks([20, 40, 60, 80, 100])
    ax_d.set_xlabel("Task-block end")
    ax_d.set_ylabel("Ordinary-anchor purity")
    ax_d.set_title("Mature-anchor feedback")
    ax_d.grid(axis="y")
    ax_d.legend(ncol=2, loc="lower right", handlelength=1.25, columnspacing=.55, labelspacing=.15, fontsize=5.2)

    for letter, ax in zip("abcd", axes):
        if letter == "c":
            ax.text(.01, .83, "(c)", transform=ax.transAxes, fontweight="bold", va="top", ha="left", zorder=20)
        else:
            panel_label(ax, letter)
    save_bundle(fig, "fig_rq3_main_1x4")
    plt.close(fig)


def supplementary_figure() -> None:
    prevalence = pd.read_csv(RESULTS / "rq3_prevalence_summary.csv")
    strength = pd.read_csv(RESULTS / "rq3_strength_summary.csv")
    modes = pd.read_csv(RESULTS / "rq3_mode_summary.csv")
    feedback = pd.read_csv(RESULTS / "rq3_feedback_summary.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.45), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.reshape(-1)
    prevalence_panel(ax_a, prevalence, 39, r"Replication at $\bar n=39$")

    strength_panel(ax_b, fig, strength)
    rate_panel(
        ax_c, modes, "honest_false_low_rate", "IRPP collateral screening",
        "Honest false-low rate",
    )

    for variant in ["Full", "No-U"]:
        rows = feedback.loc[feedback.variant == variant].sort_values("block_end")
        ax_d.plot(rows.block_end, rows.ordinary_anchor_purity, color=COLORS[variant], marker="o" if variant == "Full" else "s", linewidth=1.15, markersize=3, label=variant)
        ax_d.fill_between(rows.block_end, rows.ordinary_anchor_purity_ci_low, rows.ordinary_anchor_purity_ci_high, color=COLORS[variant], alpha=.12)
    ax_d.axvline(41, color="#6B7280", linestyle="--", linewidth=.8)
    ax_d.set_ylim(.48, 1.015)
    ax_d.set_xlabel("Task-block end")
    ax_d.set_ylabel("Ordinary-anchor purity")
    ax_d.set_title("Uncertainty ablation under delayed poisoning")
    ax_d.grid(axis="y")
    ax_d.legend()

    for letter, ax in zip("abcd", axes.reshape(-1)):
        panel_label(ax, letter)
    save_bundle(fig, "fig_rq3_supplement_2x2")
    plt.close(fig)


if __name__ == "__main__":
    apply_style()
    main_figure()
    supplementary_figure()
