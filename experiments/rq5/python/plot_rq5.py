#!/usr/bin/env python3
"""Generate publication and supplementary RQ5 figures from audited CSVs."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
OUTPUTS = ROOT.parents[1] / "outputs"

COLORS = {
    "IRPP-TD": "#0B5CAD",
    "BSIF": "#B64040",
    "RPPS-TDC": "#0F766E",
    "PRTD": "#B7791F",
    "grid": "#D7DEE8",
    "text": "#172033",
    "neutral": "#6B7280",
}
MARKERS = {"IRPP-TD": "o", "BSIF": "^", "RPPS-TDC": "s", "PRTD": "D"}
LINES = {"IRPP-TD": "-", "BSIF": ":", "RPPS-TDC": "--", "PRTD": "-."}
ORDER = ["IRPP-TD", "BSIF", "RPPS-TDC", "PRTD"]


def apply_style():
    mpl.rcParams.update({
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
    })


def panel_label(ax, letter):
    ax.text(0.01, 0.98, f"({letter})", transform=ax.transAxes, fontweight="bold", va="top", ha="left", zorder=20)


def save_bundle(fig, stem, also_outputs=True):
    FIGURES.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    targets = [FIGURES]
    if also_outputs:
        targets.append(OUTPUTS)
    for target in targets:
        fig.savefig(target / f"{stem}.pdf", bbox_inches="tight")
        fig.savefig(target / f"{stem}.svg", bbox_inches="tight")
        fig.savefig(target / f"{stem}.png", dpi=300, bbox_inches="tight")
        fig.savefig(target / f"{stem}.tiff", dpi=600, bbox_inches="tight")


def main_figure():
    e2e = pd.read_csv(RESULTS / "e2e_summary_95ci.csv")
    entities = pd.read_csv(RESULTS / "entity_stage_summary_95ci.csv")
    audit = pd.read_csv(RESULTS / "audit_accountability_grid.csv")
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.60), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes

    for protocol in ORDER:
        f = e2e.loc[e2e.protocol.eq(protocol)].sort_values("n")
        x = f.n.to_numpy()
        y = f.e2e_active_ms_median.to_numpy() / 1000.0
        low = f.e2e_active_ms_ci_low.to_numpy() / 1000.0
        high = f.e2e_active_ms_ci_high.to_numpy() / 1000.0
        ax_a.plot(x, y, color=COLORS[protocol], marker=MARKERS[protocol], linestyle=LINES[protocol],
                  linewidth=1.05, markersize=3.0, label=protocol)
        ax_a.fill_between(x, low, high, color=COLORS[protocol], alpha=0.12, linewidth=0)
    ax_a.set_xlabel("Workers per task")
    ax_a.set_ylabel("Active latency (s)")
    ax_a.set_title("Matched end-to-end latency")
    ax_a.set_xticks([10, 20, 30, 40, 50])
    ax_a.grid()
    ax_a.legend(
        loc="upper left", bbox_to_anchor=(0.0, 0.92), ncol=1,
        labelspacing=0.15, handlelength=1.35, borderaxespad=0.25,
    )
    panel_label(ax_a, "a")

    target = e2e.loc[e2e.n.eq(27)].set_index("protocol").loc[ORDER]
    ledger = target.ledger_bytes_task_median.fillna(0).to_numpy()
    positive = ledger[ledger > 0]
    sizes = 34 + 54 * np.sqrt(ledger / max(float(positive.max()), 1.0))
    for index, protocol in enumerate(ORDER):
        x = target.loc[protocol, "total_traffic_task_bytes_median"] / 1024.0
        y = target.loc[protocol, "e2e_active_ms_median"] / 1000.0
        face = "none" if protocol == "PRTD" else COLORS[protocol]
        ax_b.scatter(x, y, s=sizes[index], marker=MARKERS[protocol], facecolors=face,
                     edgecolors=COLORS[protocol], linewidth=1.0, zorder=4,
                     label=protocol)
    ax_b.set_xlabel("Total traffic/task (KiB)")
    ax_b.set_ylabel("Active latency (s)")
    ax_b.set_title("Latency--traffic")
    ax_b.set_xlim(290, 640)
    ax_b.set_ylim(9.5, 40.5)
    ax_b.set_xticks([300, 400, 500, 600])
    ax_b.grid()
    legend_handles = [
        Line2D(
            [], [], linestyle="none", marker=MARKERS[protocol], markersize=4.0,
            markerfacecolor="none" if protocol == "PRTD" else COLORS[protocol],
            markeredgecolor=COLORS[protocol], markeredgewidth=0.9, label=protocol,
        )
        for protocol in ORDER
    ]
    ax_b.legend(
        handles=legend_handles,
        loc="center",
        bbox_to_anchor=(0.50, 0.50),
        ncol=2,
        labelspacing=0.12,
        columnspacing=0.65,
        handletextpad=0.35,
        borderaxespad=0.0,
        fontsize=5.0,
    )
    ax_b.text(0.98, 0.04, "area: ledger bytes\nopen: no ledger", transform=ax_b.transAxes,
              ha="right", va="bottom", fontsize=4.8, color=COLORS["neutral"])
    panel_label(ax_b, "b")

    stage_order = ["Worker", "Service/authority", "Requester/cloud B", "Ledger"]
    stage_labels = ["Worker", "TP/RB/authority", "DR/cloud", "Ledger"]
    stage_colors = ["#8EC3F5", "#0F766E", "#B7791F", "#6B7280"]
    stage_hatches = ["", "//", "..", "xx"]
    x = np.arange(len(ORDER))
    bottoms = np.zeros(len(ORDER))
    for stage, display, color, hatch in zip(stage_order, stage_labels, stage_colors, stage_hatches):
        f = entities.loc[entities.stage.eq(stage)].set_index("protocol").loc[ORDER]
        values = f.median_ms.to_numpy() / 1000.0
        ax_c.bar(x, values, bottom=bottoms, width=0.67, color=color, edgecolor="white",
                 linewidth=0.35, hatch=hatch, label=display)
        bottoms += values
    ax_c.set_xticks(x, ["IRPP", "BSIF", "RPPS", "PRTD"], rotation=18, ha="right")
    ax_c.set_ylabel("Latency (s)")
    ax_c.set_title("Stage cost")
    ax_c.set_ylim(0, 46)
    ax_c.grid(axis="y")
    ax_c.legend(
        loc="upper center",
        bbox_to_anchor=(0.54, 1.0),
        ncol=2,
        labelspacing=0.12,
        columnspacing=0.65,
        handlelength=1.05,
        borderaxespad=0.25,
        fontsize=5.2,
    )
    panel_label(ax_c, "c")

    rho = 0.2
    styles = {0.0: ("#B64040", "o", "-", "No challenge"),
              0.5: ("#B7791F", "s", "--", "50% timely"),
              1.0: ("#0B5CAD", "^", "-.", "Timely challenge")}
    for c_t, (color, marker, line, label) in styles.items():
        f = audit.loc[np.isclose(audit.rho_A, rho) & np.isclose(audit.c_T, c_t)].sort_values("p_A")
        ax_d.plot(f.p_A, 100 * f.bad_finalization_exact, color=color, marker=marker,
                  linestyle=line, linewidth=1.0, markersize=2.7, label=label)
        ax_d.scatter(f.p_A.iloc[::2], 100 * f.bad_finalization_empirical.iloc[::2],
                     s=7, facecolors="none", edgecolors=color, linewidth=0.55, zorder=4)
    ax_d.set_xlabel(r"Proactive-audit rate $p_A$")
    ax_d.set_ylabel("Bad finalization (%)")
    ax_d.set_title("Conditional accountability")
    ax_d.set_ylim(-3, 104)
    ax_d.grid()
    ax_d.legend(loc="upper right", labelspacing=0.1, handlelength=1.25, borderaxespad=0.25)
    panel_label(ax_d, "d")
    save_bundle(fig, "Fig5_RQ5_EndToEnd_Accountability_Final")
    plt.close(fig)


def supplementary_figures():
    e2e = pd.read_csv(RESULTS / "e2e_summary_95ci.csv")
    throughput = pd.read_csv(RESULTS / "throughput_summary_95ci.csv")
    audit_paths = pd.read_csv(RESULTS / "audit_path_summary_95ci.csv")
    audit = pd.read_csv(RESULTS / "audit_accountability_grid.csv")

    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.25), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat
    for protocol in ORDER:
        f = e2e.loc[e2e.protocol.eq(protocol)].sort_values("n")
        ax_a.plot(f.n, f.traffic_task_bytes_median / 1024, color=COLORS[protocol], marker=MARKERS[protocol],
                  linestyle=LINES[protocol], label=protocol)
    ax_a.set_xlabel("Workers per task"); ax_a.set_ylabel("Off-chain traffic/task (KiB)")
    ax_a.set_title("Protocol traffic scaling"); ax_a.grid(); ax_a.legend(ncol=2)
    panel_label(ax_a, "a")

    for protocol in ["IRPP-TD", "BSIF", "RPPS-TDC"]:
        f = e2e.loc[e2e.protocol.eq(protocol)].sort_values("n")
        ax_b.plot(f.n, f.ledger_bytes_task_median / 1024, color=COLORS[protocol], marker=MARKERS[protocol],
                  linestyle=LINES[protocol], label=protocol)
    ax_b.set_xlabel("Workers per task"); ax_b.set_ylabel("Encoded ledger bytes/task (KiB)")
    ax_b.set_title("Ledger scaling (PRTD: N/A)"); ax_b.grid(); ax_b.legend()
    panel_label(ax_b, "b")

    x = np.arange(3)
    f = throughput.set_index("protocol").loc[["IRPP-TD", "BSIF", "RPPS-TDC"]]
    y = f.tps_median.to_numpy()
    yerr = np.vstack([y - f.tps_ci_low.to_numpy(), f.tps_ci_high.to_numpy() - y])
    ax_c.bar(x, y, yerr=yerr, capsize=2, color=[COLORS[p] for p in f.index], edgecolor="white")
    ax_c.set_xticks(x, ["IRPP", "BSIF", "RPPS"]); ax_c.set_ylabel("Committed TPS")
    ax_c.set_title("300-transaction async bursts"); ax_c.grid(axis="y")
    panel_label(ax_c, "c")

    for protocol in ["IRPP-TD", "BSIF", "RPPS-TDC"]:
        f = e2e.loc[e2e.protocol.eq(protocol)].sort_values("n")
        ax_d.plot(f.n, f.confirm_p95_ms_median, color=COLORS[protocol], marker=MARKERS[protocol],
                  linestyle=LINES[protocol], label=protocol)
        ax_d.fill_between(
            f.n.to_numpy(),
            f.confirm_p95_ms_ci_low.to_numpy(),
            f.confirm_p95_ms_ci_high.to_numpy(),
            color=COLORS[protocol], alpha=0.10, linewidth=0,
        )
    ax_d.set_xlabel("Workers per task"); ax_d.set_ylabel("Per-tx p95 confirmation (ms)")
    ax_d.set_title("Consensus confirmation"); ax_d.grid(); ax_d.legend()
    panel_label(ax_d, "d")
    save_bundle(fig, "FigS7_RQ5_Resource_Detail_2x2")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.25), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat
    modes = ["normal", "proactive", "challenged", "delayed"]
    labels = ["Normal", "Proactive", "Challenged", "Delayed"]
    f = audit_paths.set_index("audit_mode").loc[modes]
    x = np.arange(4)
    active = f.e2e_active_ms_median.to_numpy() / 1000
    active_yerr = np.vstack([
        active - f.e2e_active_ms_ci_low.to_numpy() / 1000,
        f.e2e_active_ms_ci_high.to_numpy() / 1000 - active,
    ])
    final = f.e2e_final_ms_median.to_numpy() / 1000
    final_yerr = np.vstack([
        final - f.e2e_final_ms_ci_low.to_numpy() / 1000,
        f.e2e_final_ms_ci_high.to_numpy() / 1000 - final,
    ])
    ax_a.bar(x - 0.18, active, width=0.36, yerr=active_yerr, capsize=2,
             label="Active", color="#0B5CAD")
    ax_a.bar(x + 0.18, final, width=0.36, yerr=final_yerr, capsize=2,
             label="Final", color="#8EC3F5")
    ax_a.set_xticks(x, labels, rotation=15); ax_a.set_ylabel("Latency (s)")
    ax_a.set_title("Measured IRPP audit paths"); ax_a.grid(axis="y")
    ax_a.legend(
        loc="center left", bbox_to_anchor=(1.01, 0.50), ncol=1,
        frameon=True, framealpha=0.92, facecolor="white", edgecolor="none",
        borderaxespad=0.0, labelspacing=0.18,
    )
    panel_label(ax_a, "a")

    traffic = f.total_traffic_task_bytes_median.to_numpy() / 1024
    traffic_yerr = np.vstack([
        traffic - f.total_traffic_task_bytes_ci_low.to_numpy() / 1024,
        f.total_traffic_task_bytes_ci_high.to_numpy() / 1024 - traffic,
    ])
    ax_b.bar(x, traffic, yerr=traffic_yerr, capsize=2,
             color=["#6B7280", "#0F766E", "#B7791F", "#B64040"])
    ax_b.set_xticks(x, labels, rotation=15); ax_b.set_ylabel("Total traffic/task (KiB)")
    ax_b.set_title("Audit communication"); ax_b.grid(axis="y")
    panel_label(ax_b, "b")

    no_challenge = audit.loc[np.isclose(audit.c_T, 0.0)]
    pivot = no_challenge.pivot(index="rho_A", columns="p_A", values="bad_finalization_exact")
    im = ax_c.imshow(100 * pivot.to_numpy(), origin="lower", aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)
    ax_c.set_xticks(range(len(pivot.columns)), [f"{v:.1f}" for v in pivot.columns], rotation=45)
    ax_c.set_yticks(range(len(pivot.index)), [f"{v:.1f}" for v in pivot.index])
    ax_c.set_xlabel(r"$p_A$"); ax_c.set_ylabel(r"Auditor corruption $\rho_A$")
    ax_c.set_title("Bad finalization, no challenge")
    fig.colorbar(im, ax=ax_c, fraction=0.045, pad=0.03, label="%")
    panel_label(ax_c, "c")

    for rho, color, marker in [(0.0, "#0B5CAD", "o"), (0.2, "#0F766E", "s"), (0.4, "#B7791F", "^"), (0.6, "#B64040", "D")]:
        g = audit.loc[np.isclose(audit.rho_A, rho) & np.isclose(audit.c_T, 0.0)].sort_values("p_A")
        ax_d.plot(g.added_active_ms / 1000, 100 * g.bad_finalization_exact, marker=marker, color=color, label=rf"$\rho_A={rho:.1f}$")
    ax_d.set_xlabel("Expected added active latency (s)"); ax_d.set_ylabel("Bad finalization (%)")
    ax_d.set_title("No-challenge cost--risk frontier"); ax_d.grid(); ax_d.legend()
    panel_label(ax_d, "d")
    save_bundle(fig, "FigS8_RQ5_Audit_Detail_2x2")
    plt.close(fig)


def main():
    apply_style()
    main_figure()
    supplementary_figures()


if __name__ == "__main__":
    main()
