from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

COLORS = {
    "proposed": "#0B5CAD",
    "proposed_light": "#8EC3F5",
    "recent": "#0F766E",
    "traditional": "#B64040",
    "cost": "#B7791F",
    "neutral": "#6B7280",
    "grid": "#D7DEE8",
    "text": "#172033",
}


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
            "grid.alpha": 0.7,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_label(ax: plt.Axes, letter: str, color: str = COLORS["text"]) -> None:
    ax.text(0.01, 0.98, f"({letter})", transform=ax.transAxes, fontweight="bold", va="top", ha="left", color=color, zorder=20)


def save_bundle(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.tiff", dpi=600, bbox_inches="tight")


def main_figure() -> None:
    angular = pd.read_csv(RESULTS / "angular_budget_summary_95ci.csv")
    stopping = pd.read_csv(RESULTS / "stopping_grid_summary.csv")
    scaling = pd.read_csv(RESULTS / "scaling_summary.csv")
    stability = pd.read_csv(RESULTS / "stability_summary_wilson.csv")
    slopes = json.loads((RESULTS / "scaling_slopes.json").read_text(encoding="utf-8"))

    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.60), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes

    order = ["cap-3", "cap-4", "cap-5", "cap-6", "cap-7", "cap-20", "Exact"]
    target_styles = {
        27: (COLORS["proposed"], "o", "-"),
        39: (COLORS["recent"], "s", "--"),
    }
    for target in (27, 39):
        frame = angular.loc[angular["target_workers"] == target].set_index("budget").loc[order]
        x = frame["scene_macro_pairs_per_task"].to_numpy()
        y = frame["scene_macro_nrmse"].to_numpy() * 1e3
        yerr = np.vstack([(frame["scene_macro_nrmse"] - frame["nrmse_ci_low"]).to_numpy(), (frame["nrmse_ci_high"] - frame["scene_macro_nrmse"]).to_numpy()]) * 1e3
        color, marker, linestyle = target_styles[target]
        ax_a.errorbar(x[:-1], y[:-1], yerr=yerr[:, :-1], color=color, marker=marker, linestyle=linestyle, linewidth=1.05, markersize=3.0, capsize=1.3, label=rf"$\bar n={target}$")
        ax_a.errorbar(x[-1], y[-1], yerr=yerr[:, -1:].reshape(2, 1), color=color, marker="*", linestyle="none", markersize=5.1, capsize=1.3)
        default_row = frame.loc["cap-20"]
        ax_a.scatter(default_row["scene_macro_pairs_per_task"], default_row["scene_macro_nrmse"] * 1e3, s=37, facecolors="none", edgecolors=color, linewidth=0.75, zorder=5)
    ax_a.set_xscale("log")
    ax_a.set_xlabel("Angular pairs/task (log)")
    ax_a.set_ylabel(r"Scene-macro NRMSE ($10^{-3}$)")
    ax_a.set_title("Angular-budget sensitivity")
    ax_a.grid(which="both")
    ax_a.legend(loc="upper right", handlelength=1.3, labelspacing=0.2, borderaxespad=0.25)
    ax_a.annotate("default", (420.65, 1.7555), xytext=(-3, 8), textcoords="offset points", fontsize=5.0, ha="center", color=COLORS["neutral"])
    ax_a.text(0.97, 0.05, "stars: exact", transform=ax_a.transAxes, ha="right", va="bottom", fontsize=4.9, color=COLORS["neutral"])
    panel_label(ax_a, "a")

    eps_order = [1e-3, 1e-5, 1e-7, 1e-9, 1e-12]
    cap_order = [2, 3, 5, 10, 50]
    gap = stopping.pivot(index="epsilon", columns="max_iterations", values="scene_macro_gap").loc[eps_order, cap_order].to_numpy()
    cap_hit = stopping.pivot(index="epsilon", columns="max_iterations", values="cap_hit_rate").loc[eps_order, cap_order].to_numpy()
    image = ax_b.imshow(gap, norm=LogNorm(vmin=1e-12, vmax=1e-4), cmap="YlGnBu_r", aspect="auto", interpolation="nearest")
    ax_b.set_xticks(range(len(cap_order)), cap_order)
    ax_b.set_yticks(range(len(eps_order)), [r"$10^{-3}$", r"$10^{-5}$", r"$10^{-7}$", r"$10^{-9}$", r"$10^{-12}$"])
    ax_b.set_xlabel(r"Iteration cap $t_{\max}$")
    ax_b.set_ylabel(r"Tolerance $\epsilon$")
    ax_b.set_title("Stopping sensitivity")
    for row, col in np.argwhere(cap_hit > 0.01):
        ax_b.scatter(col + 0.28, row - 0.28, marker="v", s=10, color=COLORS["traditional"], edgecolor="white", linewidth=0.25, zorder=5)
    default_row, default_col = eps_order.index(1e-5), cap_order.index(50)
    ax_b.add_patch(Rectangle((default_col - 0.49, default_row - 0.49), 0.98, 0.98, fill=False, edgecolor=COLORS["proposed"], linewidth=1.2))
    colorbar = fig.colorbar(image, ax=ax_b, fraction=0.050, pad=0.025, ticks=[1e-12, 1e-8, 1e-4])
    colorbar.ax.tick_params(labelsize=4.8, length=2, pad=1)
    colorbar.set_label("Gap", fontsize=5.2, labelpad=0)
    ax_b.text(0.97, 0.03, r"$\blacktriangledown$: cap hit", transform=ax_b.transAxes, ha="right", va="bottom", fontsize=4.8, color=COLORS["traditional"])
    panel_label(ax_b, "b")

    method_styles = {
        "RABOD": (COLORS["proposed"], "o", "-"),
        "Full IRPP": (COLORS["recent"], "s", "--"),
        "Exact ABOD": (COLORS["traditional"], "^", ":"),
    }
    for method, (color, marker, linestyle) in method_styles.items():
        frame = scaling.loc[(scaling["method"] == method) & (~scaling["censored"].fillna(False))]
        ax_c.plot(frame["n"], frame["runtime_median_s"] * 1e3, label=method, color=color, marker=marker, linestyle=linestyle, linewidth=1.05, markersize=3.0)
    ax_c.axvline(400, color=COLORS["neutral"], linestyle="--", linewidth=0.7)
    ax_c.set_xscale("log")
    ax_c.set_yscale("log")
    ax_c.set_xlabel("Reports per task, $n$ (log)")
    ax_c.set_ylabel("Runtime/task (ms, log)")
    ax_c.set_title("Algorithmic scalability")
    ax_c.grid(which="both")
    ax_c.legend(loc="upper left", bbox_to_anchor=(0.02, 0.90), handlelength=1.25, labelspacing=0.15, borderaxespad=0.15)
    ax_c.text(0.98, 0.04, rf"RABOD slope {slopes['rabod_post_cap']['slope']:.2f}", transform=ax_c.transAxes, ha="right", va="bottom", fontsize=5.0, color=COLORS["proposed"])
    ax_c.annotate("exact censored", xy=(800, 800), xytext=(1200, 250), fontsize=4.8, color=COLORS["traditional"], arrowprops={"arrowstyle": "-", "color": COLORS["traditional"], "lw": 0.45})
    ax_c.text(400, 0.70, r"$\delta_{\max}^2$", rotation=90, fontsize=4.8, color=COLORS["neutral"], va="bottom", ha="right")
    panel_label(ax_c, "c")

    tau_order = [1e-3, 1e-6, 1e-9, 1e-12, 1e-50, 1e-150, 0.0]
    x = np.arange(len(tau_order), dtype=float)
    stable_styles = {
        ("Full", "full-rank"): (COLORS["proposed"], "o", "-", -0.035, "Full, rank$\geq2$"),
        ("Full", "rank-1"): (COLORS["recent"], "s", "--", 0.035, "Full, rank-1"),
        ("Unprotected", "full-rank"): (COLORS["traditional"], "^", "-.", -0.035, "No guards, rank$\geq2$"),
        ("Unprotected", "rank-1"): (COLORS["neutral"], "x", ":", 0.035, "No guards, rank-1"),
    }
    for (method, geometry), (color, marker, linestyle, offset, label) in stable_styles.items():
        frame = stability.loc[(stability["method"] == method) & (stability["geometry"] == geometry)].set_index("tau").loc[tau_order]
        y = frame["success_rate"].to_numpy() * 100.0
        low = np.maximum(0.0, (frame["success_rate"] - frame["success_ci_low"]).to_numpy() * 100.0)
        high = np.maximum(0.0, (frame["success_ci_high"] - frame["success_rate"]).to_numpy() * 100.0)
        ax_d.errorbar(x + offset, y, yerr=np.vstack([low, high]), color=color, marker=marker, linestyle=linestyle, linewidth=1.0, markersize=3.0, capsize=1.0, label=label)
    ax_d.set_xticks(x)
    ax_d.set_xticklabels(
        [r"$10^{-3}$", r"$10^{-6}$", r"$10^{-9}$", r"$10^{-12}$", r"$10^{-50}$", r"$10^{-150}$", "0"],
        rotation=0,
        ha="center",
        fontsize=4.35,
    )
    ax_d.tick_params(axis="x", pad=1.0)
    ax_d.set_ylim(-5, 106)
    ax_d.set_yticks([0, 50, 100])
    ax_d.set_xlabel(r"Residual scale $\tau$")
    ax_d.set_ylabel("Finite + correct (%)")
    ax_d.set_title("Near-aggregate stability")
    ax_d.grid(axis="y")
    ax_d.legend(loc="center left", bbox_to_anchor=(0.02, 0.48), ncol=1, handlelength=1.25, labelspacing=0.12, borderaxespad=0.1, fontsize=4.8)
    panel_label(ax_d, "d")

    fig.set_constrained_layout_pads(w_pad=0.015, h_pad=0.01, wspace=0.015, hspace=0.0)
    save_bundle(fig, "fig_rq4_main_1x4")
    plt.close(fig)


def supplementary_scaling() -> None:
    scaling = pd.read_csv(RESULTS / "scaling_summary.csv")
    memory = pd.read_csv(RESULTS / "scaling_memory.csv")
    secondary = pd.read_csv(RESULTS / "secondary_scaling.csv")
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.82), constrained_layout=True)
    for method, color, marker, linestyle in (("RABOD", COLORS["proposed"], "o", "-"), ("Full IRPP", COLORS["recent"], "s", "--"), ("Exact ABOD", COLORS["traditional"], "^", ":")):
        frame = memory.loc[memory["method"] == method]
        axes[0].plot(frame["n"], np.maximum(frame["incremental_peak_rss"] / 2**20, 0.05), color=color, marker=marker, linestyle=linestyle, linewidth=1.0, markersize=3, label=method)
    axes[0].set(xscale="log", yscale="log", xlabel="$n$ (log)", ylabel="Incremental peak RSS (MiB)", title="Isolated memory")
    axes[0].grid(which="both")
    axes[0].legend(loc="upper left", fontsize=4.9, labelspacing=0.12, handlelength=1.2)
    panel_label(axes[0], "a")

    for method, color, marker, linestyle in (("RABOD", COLORS["proposed"], "o", "-"), ("Full IRPP", COLORS["recent"], "s", "--")):
        frame = scaling.loc[(scaling["method"] == method) & (~scaling["censored"].fillna(False))]
        axes[1].plot(frame["n"], frame["reports_per_second"], color=color, marker=marker, linestyle=linestyle, linewidth=1.0, markersize=3, label=method)
    axes[1].set(xscale="log", xlabel="$n$ (log)", ylabel="Reports/s", title="Analytic throughput")
    axes[1].grid(which="both")
    axes[1].legend(loc="lower left", fontsize=5.1, labelspacing=0.12, handlelength=1.2)
    panel_label(axes[1], "b")

    dim = secondary.loc[secondary["sweep"] == "dimension"]
    axes[2].plot(dim["value"], dim["runtime_median_s"] * 1e3, color=COLORS["proposed"], marker="o", linewidth=1.0, markersize=3)
    axes[2].set(xlabel="Report dimension $\ell$", ylabel="Runtime/task (ms)", title=r"Dimension ($n=1000$)")
    axes[2].grid()
    panel_label(axes[2], "c")

    delta = secondary.loc[secondary["sweep"] == "delta_max"]
    axes[3].plot(delta["value"], delta["runtime_median_s"] * 1e3, color=COLORS["cost"], marker="s", linewidth=1.0, markersize=3)
    axes[3].set(xlabel=r"Angular cap $\delta_{\max}$", ylabel="RABOD runtime (ms)", title=r"Cap cost ($n=10^4$)")
    axes[3].grid()
    panel_label(axes[3], "d")
    save_bundle(fig, "fig_rq4_supp_scaling_1x4")
    plt.close(fig)


def supplementary_sensitivity() -> None:
    angular = pd.read_csv(RESULTS / "angular_budget_summary_95ci.csv")
    agreement = pd.read_csv(RESULTS / "angular_exact_agreement_summary.csv")
    stopping = pd.read_csv(RESULTS / "stopping_grid_summary.csv")
    scene_summary = pd.read_csv(RESULTS / "angular_scene_summary.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.25), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.reshape(-1)
    order = ["cap-3", "cap-4", "cap-5", "cap-6", "cap-7", "cap-20", "Exact"]
    labels = ["3", "4", "5", "6", "7", "Default", "Exact"]
    colors = {"Climate": COLORS["proposed"], "Traffic": COLORS["cost"], "Water": COLORS["traditional"]}
    markers = {"Climate": "o", "Traffic": "s", "Water": "^"}
    for scene in ("Climate", "Traffic", "Water"):
        values = (
            scene_summary.loc[
                (scene_summary["scene"] == scene)
                & (scene_summary["target_workers"] == 27)
            ]
            .set_index("budget")
            .loc[order, "nrmse"]
            .to_numpy()
            * 1e3
        )
        ax_a.plot(range(len(order)), values, color=colors[scene], marker=markers[scene], linewidth=1.1, markersize=3.5, label=scene)
    ax_a.set_xticks(range(len(order)), labels, rotation=25, ha="right")
    ax_a.set(ylabel=r"NRMSE ($10^{-3}$)", title=r"Scene sensitivity ($\bar n=27$)")
    ax_a.grid(axis="y")
    ax_a.legend(
        loc="center right", bbox_to_anchor=(0.98, 0.58),
        frameon=True, framealpha=0.92, facecolor="white", edgecolor="none",
        labelspacing=0.18, handlelength=1.2,
    )
    panel_label(ax_a, "a")

    for target, color, marker, linestyle in ((27, COLORS["proposed"], "o", "-"), (39, COLORS["recent"], "s", "--")):
        frame = agreement.loc[agreement["target_workers"] == target].set_index("budget").loc[order[:-1]]
        ax_b.plot(range(6), frame["score_spearman"], color=color, marker=marker, linestyle=linestyle, label=rf"Spearman, $\bar n={target}$")
        ax_b.plot(range(6), frame["retained_jaccard"], color=color, marker=marker, linestyle=":" if target == 27 else "-.", label=rf"Jaccard, $\bar n={target}$")
    ax_b.set_xticks(range(6), labels[:-1], rotation=25, ha="right")
    ax_b.set(ylim=(0.6, 1.0), ylabel="Agreement with exact", title="Score and retained-set fidelity")
    ax_b.grid(axis="y")
    ax_b.legend(loc="lower right", fontsize=5.2, labelspacing=0.15)
    panel_label(ax_b, "b")

    eps_order = [1e-3, 1e-5, 1e-7, 1e-9, 1e-12]
    cap_order = [2, 3, 5, 10, 50]
    iterations = stopping.pivot(index="epsilon", columns="max_iterations", values="iterations_p95").loc[eps_order, cap_order].to_numpy()
    image_c = ax_c.imshow(iterations, cmap="Blues", aspect="auto")
    ax_c.set_xticks(range(5), cap_order)
    ax_c.set_yticks(range(5), [r"$10^{-3}$", r"$10^{-5}$", r"$10^{-7}$", r"$10^{-9}$", r"$10^{-12}$"])
    ax_c.set(xlabel=r"$t_{\max}$", ylabel=r"$\epsilon$", title="p95 TD iterations")
    fig.colorbar(image_c, ax=ax_c, fraction=0.04, pad=0.02)
    panel_label(ax_c, "c", "white")

    cap_hit = stopping.pivot(index="epsilon", columns="max_iterations", values="cap_hit_rate").loc[eps_order, cap_order].to_numpy()
    image_d = ax_d.imshow(cap_hit * 100, cmap="OrRd", vmin=0, vmax=100, aspect="auto")
    ax_d.set_xticks(range(5), cap_order)
    ax_d.set_yticks(range(5), [r"$10^{-3}$", r"$10^{-5}$", r"$10^{-7}$", r"$10^{-9}$", r"$10^{-12}$"])
    ax_d.set(xlabel=r"$t_{\max}$", ylabel=r"$\epsilon$", title="Iteration-cap hit rate (%)")
    fig.colorbar(image_d, ax=ax_d, fraction=0.04, pad=0.02)
    panel_label(ax_d, "d")
    save_bundle(fig, "fig_rq4_supp_sensitivity_2x2")
    plt.close(fig)


def supplementary_stability() -> None:
    stability = pd.read_csv(RESULTS / "stability_summary_wilson.csv")
    applicability = pd.read_csv(RESULTS / "applicability_summary.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.1), constrained_layout=True)
    tau_order = [1e-3, 1e-6, 1e-9, 1e-12, 1e-50, 1e-150, 0.0]
    labels = [r"$10^{-3}$", r"$10^{-6}$", r"$10^{-9}$", r"$10^{-12}$", r"$10^{-50}$", r"$10^{-150}$", "0"]
    for geometry, color, marker, linestyle in (("full-rank", COLORS["proposed"], "o", "-"), ("rank-1", COLORS["recent"], "s", "--")):
        frame = stability.loc[(stability["method"] == "Full") & (stability["geometry"] == geometry)].set_index("tau").loc[tau_order]
        axes[0, 0].plot(range(7), frame["fallback_rate"] * 100, color=color, marker=marker, linestyle=linestyle, label=geometry)
    axes[0, 0].set_xticks(range(7), labels, rotation=25, ha="right")
    axes[0, 0].set(ylabel="Declared fallback (%)", title="Angular fallback boundary")
    axes[0, 0].grid(axis="y")
    axes[0, 0].legend()
    panel_label(axes[0, 0], "a")

    for geometry, color, marker, linestyle in (("full-rank", COLORS["proposed"], "o", "-"), ("rank-1", COLORS["recent"], "s", "--")):
        frame = stability.loc[(stability["method"] == "Full") & (stability["geometry"] == geometry)].set_index("tau").loc[tau_order]
        axes[0, 1].plot(range(7), frame["max_raw_weight"], color=color, marker=marker, linestyle=linestyle, label=geometry)
    axes[0, 1].axhline(np.log(2.0), color=COLORS["traditional"], linestyle=":", label=r"$\log2$")
    axes[0, 1].set_xticks(range(7), labels, rotation=25, ha="right")
    axes[0, 1].set(ylabel="Maximum raw weight", title="Regularized-weight bound")
    axes[0, 1].grid(axis="y")
    axes[0, 1].legend()
    panel_label(axes[0, 1], "b")

    for geometry, color, marker, linestyle in (("full-rank", COLORS["proposed"], "o", "-"), ("rank-1", COLORS["recent"], "s", "--")):
        frame = stability.loc[(stability["method"] == "Full") & (stability["geometry"] == geometry)].set_index("tau").loc[tau_order]
        axes[1, 0].plot(range(7), np.maximum(frame["max_normalization_error"], 1e-18), color=color, marker=marker, linestyle=linestyle, label=geometry)
    axes[1, 0].axhline(1e-12, color=COLORS["traditional"], linestyle=":", label=r"$10^{-12}$ criterion")
    axes[1, 0].set_xticks(range(7), labels, rotation=25, ha="right")
    axes[1, 0].set_yscale("log")
    axes[1, 0].set(ylabel=r"$|\sum_iw_i-1|$", title="Weight-normalization error")
    axes[1, 0].grid(which="both")
    axes[1, 0].legend()
    panel_label(axes[1, 0], "c")

    order = ["single-regime", "unpartitioned-two-regime", "context-partitioned"]
    frame = applicability.set_index("scenario").loc[order]
    x = np.arange(3)
    y = frame["nrmse"].to_numpy()
    yerr = np.vstack([(frame["nrmse"] - frame["nrmse_ci_low"]).to_numpy(), (frame["nrmse_ci_high"] - frame["nrmse"]).to_numpy()])
    axes[1, 1].bar(x, y, yerr=yerr, color=[COLORS["proposed"], COLORS["traditional"], COLORS["recent"]], edgecolor=COLORS["text"], linewidth=0.5, capsize=2)
    axes[1, 1].set_xticks(x, ["Single", "Two-regime\nunpartitioned", "Context\npartitioned"])
    axes[1, 1].set(ylabel="Regime-aware NRMSE", title="Semantic applicability boundary")
    axes[1, 1].grid(axis="y")
    panel_label(axes[1, 1], "d")
    save_bundle(fig, "fig_rq4_supp_stability_2x2")
    plt.close(fig)


def main() -> None:
    apply_style()
    main_figure()
    supplementary_scaling()
    supplementary_sensitivity()
    supplementary_stability()


if __name__ == "__main__":
    main()
