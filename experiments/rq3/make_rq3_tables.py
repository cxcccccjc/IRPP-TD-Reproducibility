from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TABLES = ROOT / "tables"


def interval(row, value: str, digits: int = 3) -> str:
    return f"{getattr(row, value):.{digits}f} [{getattr(row, value + '_ci_low'):.{digits}f},{getattr(row, value + '_ci_high'):.{digits}f}]"


def compact_interval(row, value: str) -> str:
    point = float(getattr(row, value))
    half = max(point - float(getattr(row, value + "_ci_low")), float(getattr(row, value + "_ci_high")) - point)
    digits = 5 if point < .01 else (4 if point < .1 else 3)
    return f"{point:.{digits}f}$\\pm${half:.{digits}f}"


def prevalence_table() -> str:
    data = pd.read_csv(RESULTS / "rq3_prevalence_summary.csv")
    data = data.loc[data.malicious_ratio.isin([0.0, .3, .5, .8])]
    lines = [
        r"\begin{table*}[!t]", r"\centering", r"\caption{Compact-Collusion Prevalence Results (Scene-Macro NRMSE)}",
        r"\label{tab:rq3-prevalence-full}", r"\scriptsize", r"\setlength{\tabcolsep}{3.1pt}", r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabular}{ccrrrr}", r"\toprule",
        r"$\bar n$ & $\rho_m$ & IRPP-TD & CRH-N & PRTD & QE \\", r"\midrule",
    ]
    for target in [27, 39]:
        for ratio in [0.0, .3, .5, .8]:
            cells = []
            for method in ["IRPP-TD", "CRH-N", "PRTD", "QE"]:
                row = data.loc[(data.target_workers == target) & np.isclose(data.malicious_ratio, ratio) & (data.method == method)].iloc[0]
                cells.append(compact_interval(row, "nrmse"))
            lines.append(f"{target} & {ratio:.1f} & " + " & ".join(cells) + r" \\")
        if target == 27:
            lines.append(r"\midrule")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\vspace{0.25ex}",
                  r"\parbox{0.98\textwidth}{\scriptsize Values are means $\pm$ the larger 95\% paired-seed bootstrap half-width.}",
                  r"\end{table*}"])
    return "\n".join(lines)


def strength_table() -> str:
    data = pd.read_csv(RESULTS / "rq3_strength_summary.csv")
    boundary = pd.read_csv(RESULTS / "rq3_boundary_summary.csv")
    lines = [
        r"\begin{table}[!t]", r"\centering", r"\caption{IRPP-TD Operational Boundary at $\bar n=27$}", r"\label{tab:rq3-boundary}",
        r"\scriptsize", r"\setlength{\tabcolsep}{4.2pt}", r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabular}{crrr}", r"\toprule", r"$\kappa$ & First failed $\rho_m$ & $R_E$ at $\rho_m=0.8$ & Max NT (\%) \\", r"\midrule",
    ]
    for strength in sorted(data.strength.unique()):
        cell = boundary.loc[np.isclose(boundary.strength, strength), "first_failed_ratio"].iloc[0]
        first = "--" if pd.isna(cell) else f"{cell:.1f}"
        end = data.loc[np.isclose(data.strength, strength) & np.isclose(data.malicious_ratio, .8)].iloc[0]
        max_nt = 100 * data.loc[np.isclose(data.strength, strength), "no_truth_rate"].max()
        lines.append(f"{strength:g} & {first} & {end.error_ratio:.2f} & {max_nt:.2f} " + r"\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def mode_table() -> str:
    data = pd.read_csv(RESULTS / "rq3_mode_summary.csv")
    names = {"independent": "Independent", "compact": "Compact", "onoff": "On--Off", "mature_anchor": "Mature-Anchor"}
    lines = [
        r"\begin{table}[!t]", r"\centering", r"\caption{Attack-Mode Outcomes at $\rho_m=0.3,\kappa=0.5$}", r"\label{tab:rq3-modes}",
        r"\scriptsize", r"\setlength{\tabcolsep}{3.4pt}", r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabular}{lrrr}", r"\toprule", r"Mode & $R_E$ & Leakage & Honest false-low \\", r"\midrule",
    ]
    for mode in ["independent", "compact", "onoff", "mature_anchor"]:
        row = data.loc[data["mode"] == mode].iloc[0]
        lines.append(f"{names[mode]} & {row.error_ratio:.2f} & {row.malicious_report_leakage:.3f} & {row.honest_false_low_rate:.3f} " + r"\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def feedback_table() -> str:
    data = pd.read_csv(RESULTS / "rq3_feedback_summary.csv")
    lines = [
        r"\begin{table}[!t]", r"\centering", r"\caption{Ordinary-Anchor Purity Around Delayed Poisoning}", r"\label{tab:rq3-feedback}",
        r"\scriptsize", r"\setlength{\tabcolsep}{4.1pt}", r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabular}{lrrr}", r"\toprule", r"Variant & Block 40 & Block 50 & Block 100 \\", r"\midrule",
    ]
    for variant in ["Full", "Binary-Rep.", "No-U", "All-Anchors", "Sequential"]:
        cells = []
        for block in [40, 50, 100]:
            row = data.loc[(data.variant == variant) & (data.block_end == block)].iloc[0]
            cells.append(f"{row.ordinary_anchor_purity:.3f}")
        lines.append(f"{variant} & " + " & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


if __name__ == "__main__":
    TABLES.mkdir(parents=True, exist_ok=True)
    outputs = {
        "rq3_prevalence_table.tex": prevalence_table(),
        "rq3_strength_table.tex": strength_table(),
        "rq3_mode_table.tex": mode_table(),
        "rq3_feedback_table.tex": feedback_table(),
    }
    for name, content in outputs.items():
        (TABLES / name).write_text(content + "\n", encoding="utf-8")
        print(name)
