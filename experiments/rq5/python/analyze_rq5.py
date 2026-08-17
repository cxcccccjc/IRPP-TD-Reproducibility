#!/usr/bin/env python3
"""Audit, merge, and summarize the formal matched RQ5 measurements.

This script deliberately fails closed: the paper artefacts are generated only
after every preregistered cell is complete and valid.  PRTD has no ledger path;
its chain-specific values therefore remain NaN/N/A throughout the pipeline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
RESULTS = ROOT / "results"
PROTOCOLS = ["IRPP-TD", "BSIF", "RPPS-TDC", "PRTD"]
CHAIN_PROTOCOLS = ["IRPP-TD", "BSIF", "RPPS-TDC"]
N_VALUES = [10, 20, 27, 39, 50]
RUNS = 30
CHALLENGE_WINDOW_MS = 500.0
BOOTSTRAP_REPS = 10_000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def truth_mask(values: pd.Series) -> pd.Series:
    """Parse CSV booleans without treating the string 'false' as truthy."""
    return values.astype(str).str.strip().str.lower().isin(["true", "1"])


def bootstrap_interval(values: np.ndarray, statistic="median", seed: int = 20260810):
    values = np.asarray(values, dtype=float)
    require(values.size > 0 and np.isfinite(values).all(), "bootstrap input is empty or non-finite")
    rng = np.random.default_rng(seed)
    draws = values[rng.integers(0, values.size, size=(BOOTSTRAP_REPS, values.size))]
    if statistic == "median":
        estimates = np.median(draws, axis=1)
        center = float(np.median(values))
    elif statistic == "mean":
        estimates = np.mean(draws, axis=1)
        center = float(np.mean(values))
    else:
        raise ValueError(statistic)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return center, float(low), float(high)


def audit_inputs():
    off = pd.read_csv(RAW / "offchain_runs.csv")
    off_setup = pd.read_csv(RAW / "setup_metrics.csv")
    tasks = pd.read_csv(RAW / "chain" / "chain_tasks.csv")
    tx = pd.read_csv(RAW / "chain" / "chain_transactions.csv")
    tp = pd.read_csv(RAW / "chain" / "chain_throughput.csv")
    setup = pd.read_csv(RAW / "chain" / "chain_setup.csv")

    normal = off.loc[off.audit_mode.eq("normal")].copy()
    audit = off.loc[off.audit_mode.ne("normal")].copy()
    require(len(normal) == len(PROTOCOLS) * len(N_VALUES) * RUNS,
            f"off-chain normal row count {len(normal)} != 600")
    require(len(audit) == 3 * RUNS, f"off-chain audit row count {len(audit)} != 90")
    require(truth_mask(normal.valid).all() and truth_mask(audit.valid).all(), "invalid off-chain execution")
    for protocol in PROTOCOLS:
        for n in N_VALUES:
            cell = normal.loc[normal.protocol.eq(protocol) & normal.n.eq(n)]
            require(len(cell) == RUNS and cell.run.nunique() == RUNS,
                    f"incomplete off-chain cell: {protocol}, n={n}")

    formal_tasks = tasks.loc[tasks.run.ge(0)].copy()
    normal_tasks = formal_tasks.loc[formal_tasks.audit_mode.eq("normal")].copy()
    audit_tasks = formal_tasks.loc[formal_tasks.audit_mode.ne("normal")].copy()
    require(len(normal_tasks) == len(CHAIN_PROTOCOLS) * len(N_VALUES) * RUNS,
            f"chain normal task count {len(normal_tasks)} != 450")
    require(len(audit_tasks) == 3 * RUNS, f"chain audit task count {len(audit_tasks)} != 90")
    require(truth_mask(formal_tasks.valid).all(), "invalid chain task")
    expected_tx = np.select(
        [
            formal_tasks.protocol.eq("IRPP-TD") & formal_tasks.audit_mode.eq("normal"),
            formal_tasks.protocol.eq("IRPP-TD") & formal_tasks.audit_mode.eq("proactive"),
            formal_tasks.protocol.eq("IRPP-TD") & formal_tasks.audit_mode.isin(["challenged", "delayed"]),
            formal_tasks.protocol.eq("BSIF"),
            formal_tasks.protocol.eq("RPPS-TDC"),
        ],
        [formal_tasks.n + 4, formal_tasks.n + 9, formal_tasks.n + 10, 2 * formal_tasks.n + 3, 2 * formal_tasks.n + 5],
        default=-1,
    )
    require(np.array_equal(formal_tasks.tx_count.to_numpy(dtype=int), expected_tx.astype(int)),
            "one or more chain tasks has an unexpected native transaction count")
    formal_tx = tx.loc[tx.n.gt(0) & tx.run.ge(0) & tx.audit_mode.ne("setup")].copy()
    require((formal_tx.status.astype(str).isin(["0", "0x0", "0.0"])).all(),
            "one or more formal chain transactions failed")
    require(len(formal_tx) == int(formal_tasks.tx_count.sum()),
            f"transaction/task accounting mismatch: {len(formal_tx)} != {int(formal_tasks.tx_count.sum())}")
    require((tp.successes == tp.transactions).all(), "throughput burst contains failed transactions")
    require(set(tp.protocol.unique()) == set(CHAIN_PROTOCOLS), "throughput protocol set mismatch")
    require(tp.groupby("protocol").size().eq(10).all(), "throughput burst count is not 10 per protocol")

    numeric_off = off.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    numeric_chain = formal_tasks.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    require(np.isfinite(numeric_off).all(), "non-finite off-chain value")
    require(np.isfinite(numeric_chain).all(), "non-finite formal chain value")
    require(np.isfinite(off_setup.setup_ms.to_numpy(dtype=float)).all(), "non-finite off-chain setup value")
    return off, off_setup, tasks, tx, tp, setup


def merge_normal(off: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    normal = off.loc[off.audit_mode.eq("normal")].copy()
    formal_chain = tasks.loc[tasks.run.ge(0) & tasks.audit_mode.eq("normal")].copy()
    chain_cols = [
        "protocol", "n", "run", "chain_active_ms", "tx_count", "confirm_median_ms",
        "confirm_p95_ms", "ledger_bytes_task", "gas_used",
    ]
    merged = normal.merge(formal_chain[chain_cols], how="left", on=["protocol", "n", "run"], validate="one_to_one")
    is_chain = merged.protocol.isin(CHAIN_PROTOCOLS)
    require(merged.loc[is_chain, "chain_active_ms"].notna().all(), "missing chain measurement")
    require(merged.loc[~is_chain, "chain_active_ms"].isna().all(), "PRTD unexpectedly has chain values")
    merged["e2e_active_ms"] = merged.offchain_active_ms + merged.chain_active_ms.fillna(0.0)
    merged["e2e_final_ms"] = merged.e2e_active_ms
    merged.loc[merged.protocol.eq("IRPP-TD"), "e2e_final_ms"] += CHALLENGE_WINDOW_MS
    merged["total_traffic_task_bytes"] = merged.traffic_task_bytes + merged.ledger_bytes_task.fillna(0.0)
    merged["chain_active_ms"] = merged.chain_active_ms.where(is_chain)
    merged["ledger_bytes_task"] = merged.ledger_bytes_task.where(is_chain)
    merged["tx_count"] = merged.tx_count.where(is_chain)
    merged["confirm_median_ms"] = merged.confirm_median_ms.where(is_chain)
    merged["confirm_p95_ms"] = merged.confirm_p95_ms.where(is_chain)
    return merged


def summarize_e2e(merged: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "e2e_active_ms", "e2e_final_ms", "offchain_active_ms", "chain_active_ms",
        "traffic_report_bytes", "traffic_task_bytes", "total_traffic_task_bytes",
        "ledger_bytes_task", "tx_count", "confirm_median_ms", "confirm_p95_ms",
    ]
    rows = []
    for p_index, protocol in enumerate(PROTOCOLS):
        for n in N_VALUES:
            cell = merged.loc[merged.protocol.eq(protocol) & merged.n.eq(n)]
            row = {"protocol": protocol, "n": n, "runs": len(cell)}
            for m_index, metric in enumerate(metrics):
                values = cell[metric].dropna().to_numpy(dtype=float)
                if values.size:
                    center, low, high = bootstrap_interval(values, seed=20260810 + p_index * 100 + n + m_index)
                    row[f"{metric}_median"] = center
                    row[f"{metric}_ci_low"] = low
                    row[f"{metric}_ci_high"] = high
                else:
                    row[f"{metric}_median"] = np.nan
                    row[f"{metric}_ci_low"] = np.nan
                    row[f"{metric}_ci_high"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_entities(merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for protocol in PROTOCOLS:
        cell = merged.loc[merged.protocol.eq(protocol) & merged.n.eq(27)].copy()
        worker = cell.worker_ms
        requester = cell.dr_cloudB_ms
        service_raw = cell.tp_sp_cloudA_ms + cell.rb_rc_ta_ms + cell.auditor_ms
        accounted = worker + requester + service_raw
        residual = np.maximum(0.0, cell.offchain_active_ms - accounted)
        service = service_raw + residual
        chain = cell.chain_active_ms.fillna(0.0)
        for stage, values in {
            "Worker": worker,
            "Service/authority": service,
            "Requester/cloud B": requester,
            "Ledger": chain,
        }.items():
            center, low, high = bootstrap_interval(values.to_numpy(), seed=20260810 + len(rows))
            rows.append({"protocol": protocol, "stage": stage, "median_ms": center, "ci_low": low, "ci_high": high})
    return pd.DataFrame(rows)


def summarize_throughput(tp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for protocol in CHAIN_PROTOCOLS:
        values = tp.loc[tp.protocol.eq(protocol), "tps"].to_numpy(dtype=float)
        center, low, high = bootstrap_interval(values, seed=20260810 + len(rows))
        rows.append({"protocol": protocol, "bursts": len(values), "tps_median": center, "tps_ci_low": low, "tps_ci_high": high})
    return pd.DataFrame(rows)


def merge_audit(off: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    off_a = off.loc[off.protocol.eq("IRPP-TD") & off.n.eq(27)].copy()
    chain_a = tasks.loc[tasks.protocol.eq("IRPP-TD") & tasks.n.eq(27) & tasks.run.ge(0)].copy()
    cols = ["protocol", "n", "run", "audit_mode", "chain_active_ms", "tx_count", "ledger_bytes_task", "confirm_median_ms", "confirm_p95_ms"]
    merged = off_a.merge(chain_a[cols], on=["protocol", "n", "run", "audit_mode"], validate="one_to_one")
    merged["e2e_active_ms"] = merged.offchain_active_ms + merged.chain_active_ms
    merged["e2e_final_ms"] = merged.offchain_final_ms + merged.chain_active_ms
    merged.loc[merged.audit_mode.eq("normal"), "e2e_final_ms"] += CHALLENGE_WINDOW_MS
    merged["total_traffic_task_bytes"] = merged.traffic_task_bytes + merged.ledger_bytes_task
    return merged


def summarize_audit_paths(merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for mode in ["normal", "proactive", "challenged", "delayed"]:
        cell = merged.loc[merged.audit_mode.eq(mode)]
        row = {"audit_mode": mode, "runs": len(cell)}
        for index, metric in enumerate(["e2e_active_ms", "e2e_final_ms", "total_traffic_task_bytes", "tx_count", "ledger_bytes_task"]):
            center, low, high = bootstrap_interval(cell[metric].to_numpy(), seed=20260810 + index + len(rows) * 20)
            row[f"{metric}_median"] = center
            row[f"{metric}_ci_low"] = low
            row[f"{metric}_ci_high"] = high
        rows.append(row)
    return pd.DataFrame(rows)


def committee_failure(rho: float, m_a: int = 5, t_a: int = 3) -> float:
    return sum(math.comb(m_a, k) * rho**k * (1.0 - rho) ** (m_a - k) for k in range(t_a, m_a + 1))


def audit_accountability(audit_paths: pd.DataFrame) -> pd.DataFrame:
    normal_ms = float(audit_paths.loc[audit_paths.audit_mode.eq("normal"), "e2e_active_ms_median"].iloc[0])
    audit_ms = float(audit_paths.loc[audit_paths.audit_mode.eq("proactive"), "e2e_active_ms_median"].iloc[0])
    rng = np.random.default_rng(2026081055)
    rows = []
    trials = 100_000
    for rho in [0.0, 0.2, 0.4, 0.6]:
        first_failure = committee_failure(rho)
        residual = first_failure**2  # one independent replacement committee
        for c_t in [0.0, 0.5, 1.0]:
            for p_a in np.linspace(0.0, 1.0, 11):
                q_t = 1.0 - (1.0 - p_a) * (1.0 - c_t)
                exact_bad = 1.0 - q_t * (1.0 - residual)
                triggered = rng.random(trials) < q_t
                fail_1 = rng.binomial(5, rho, size=trials) >= 3
                fail_2 = rng.binomial(5, rho, size=trials) >= 3
                empirical_bad = np.mean((~triggered) | (fail_1 & fail_2))
                expected_active = normal_ms + q_t * (audit_ms - normal_ms)
                rows.append({
                    "p_A": p_a,
                    "c_T": c_t,
                    "rho_A": rho,
                    "m_A": 5,
                    "t_A": 3,
                    "replacement_committees": 1,
                    "audit_trigger_probability": q_t,
                    "single_committee_failure": first_failure,
                    "bad_finalization_exact": exact_bad,
                    "bad_finalization_empirical": empirical_bad,
                    "expected_active_ms": expected_active,
                    "added_active_ms": expected_active - normal_ms,
                    "trials": trials,
                })
    return pd.DataFrame(rows)


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    off, off_setup, tasks, tx, throughput, setup = audit_inputs()
    fault_runs = pd.read_csv(RAW / "fault_injection_runs.csv")
    fault_summary = pd.read_csv(RAW / "fault_injection_summary.csv")
    require(len(fault_runs) == 720 and len(fault_summary) == 24, "fault-injection grid is incomplete")
    require(fault_summary.loc[fault_summary.policy.ne("no_trigger"), "detection_rate"].eq(1.0).all(),
            "a triggered honest-quorum fault-injection cell was not fully detected")
    require(fault_summary.loc[fault_summary.policy.eq("no_trigger"), "bad_finalization_rate"].eq(1.0).all(),
            "the negative no-trigger control did not finalize the injected fault")
    merged = merge_normal(off, tasks)
    e2e = summarize_e2e(merged)
    entities = summarize_entities(merged)
    tp_summary = summarize_throughput(throughput)
    audit_runs = merge_audit(off, tasks)
    audit_paths = summarize_audit_paths(audit_runs)
    accountability = audit_accountability(audit_paths)

    merged.to_csv(RESULTS / "e2e_paired_runs.csv", index=False)
    e2e.to_csv(RESULTS / "e2e_summary_95ci.csv", index=False)
    entities.to_csv(RESULTS / "entity_stage_summary_95ci.csv", index=False)
    tp_summary.to_csv(RESULTS / "throughput_summary_95ci.csv", index=False)
    audit_runs.to_csv(RESULTS / "audit_paired_runs.csv", index=False)
    audit_paths.to_csv(RESULTS / "audit_path_summary_95ci.csv", index=False)
    accountability.to_csv(RESULTS / "audit_accountability_grid.csv", index=False)
    fault_runs.to_csv(RESULTS / "fault_injection_runs.csv", index=False)
    fault_summary.to_csv(RESULTS / "fault_injection_summary.csv", index=False)
    off_setup.groupby(["protocol", "operation"], as_index=False).agg(
        samples=("setup_ms", "size"),
        setup_median_ms=("setup_ms", "median"),
        setup_mean_ms=("setup_ms", "mean"),
        setup_min_ms=("setup_ms", "min"),
        setup_max_ms=("setup_ms", "max"),
    ).to_csv(RESULTS / "offchain_setup_summary.csv", index=False)
    setup.to_csv(RESULTS / "chain_setup_metrics.csv", index=False)

    integrity = {
        "formal_offchain_rows": int(len(off)),
        "formal_normal_rows": int(off.audit_mode.eq("normal").sum()),
        "formal_audit_rows": int(off.audit_mode.ne("normal").sum()),
        "formal_chain_tasks": int((tasks.run >= 0).sum()),
        "formal_chain_transactions": int((tx.n.gt(0) & tx.run.ge(0) & tx.audit_mode.ne("setup")).sum()),
        "throughput_bursts": int(len(throughput)),
        "failed_transactions": int((~tx.loc[tx.n.gt(0) & tx.run.ge(0) & tx.audit_mode.ne("setup"), "status"].astype(str).isin(["0", "0x0", "0.0"])).sum()),
        "invalid_protocol_runs": int((~truth_mask(off.valid)).sum() + (~truth_mask(tasks.loc[tasks.run.ge(0), "valid"])).sum()),
        "prtd_chain_values_present": int(merged.loc[merged.protocol.eq("PRTD"), "chain_active_ms"].notna().sum()),
        "bootstrap_repetitions": BOOTSTRAP_REPS,
        "accountability_trials_per_cell": 100_000,
        "fault_injection_rows": int(len(fault_runs)),
        "fault_injection_cells": int(len(fault_summary)),
        "challenge_window_ms": CHALLENGE_WINDOW_MS,
        "status": "PASS",
    }
    (RESULTS / "integrity_audit.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")
    print(json.dumps(integrity, indent=2))


if __name__ == "__main__":
    main()
