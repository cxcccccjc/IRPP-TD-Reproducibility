#!/usr/bin/env python3
"""Inject malicious-DR output faults into the IRPP P7 verification path.

The chain cost of an audit is content independent and is measured by the Java
runner.  This harness complements it by verifying that every committed output
field named in the reviewer concern is covered by deterministic re-execution.
It also records the intentionally negative no-trigger control: conditional
accountability is reactive unless proactive auditing fires.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from algorithms import irpp_filter_and_td
from protocols import make_workload


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
FAULTS = ["label", "weight", "reputation_state", "aggregate", "payment", "missing_package"]
POLICIES = ["no_trigger", "proactive", "timely_challenge", "delayed_challenge"]
RUNS = 30
N = 27
AUDITORS = 5
THRESHOLD = 3


def h256(*parts: bytes) -> bytes:
    out = hashlib.sha256()
    for part in parts:
        out.update(len(part).to_bytes(4, "big"))
        out.update(part)
    return out.digest()


def final_weights(reports: np.ndarray, retained: np.ndarray, truth: np.ndarray) -> np.ndarray:
    weights = np.zeros(len(reports), dtype=float)
    values = reports[retained]
    residuals = np.sum((values - truth) ** 2, axis=1)
    mean_residual = float(np.mean(residuals))
    raw = np.log1p((mean_residual + 1e-12) / (residuals + mean_residual + 1e-12))
    raw = np.where(np.isfinite(raw) & (raw > 0), raw, 1.0)
    weights[retained] = raw / raw.sum()
    return weights


def correct_output(reports: np.ndarray, seed: int):
    truth, labels, retained, iterations = irpp_filter_and_td(reports, seed)
    weights = final_weights(reports, retained, truth)
    previous = np.tile(np.asarray([10, 2, 1], dtype=np.int64), (len(reports), 1))
    updated = previous.copy()
    for i, label in enumerate(labels):
        updated[i, int(label)] += 1
    quality = np.clip(1.0 - np.linalg.norm(reports - truth, axis=1), 0.0, 1.0)
    payments = quality / max(float(quality.sum()), 1e-12)
    return {
        "labels": labels.astype(np.int64),
        "weights": weights.astype(np.float64),
        "reputation_state": updated.astype(np.int64),
        "aggregate": truth.astype(np.float64),
        "payment": payments.astype(np.float64),
        "iterations": int(iterations),
    }


def digest_output(output) -> bytes:
    return h256(
        np.asarray(output["labels"], dtype=">i8").tobytes(),
        np.asarray(output["weights"], dtype=">f8").tobytes(),
        np.asarray(output["reputation_state"], dtype=">i8").tobytes(),
        np.asarray(output["aggregate"], dtype=">f8").tobytes(),
        np.asarray(output["payment"], dtype=">f8").tobytes(),
        int(output["iterations"]).to_bytes(4, "big"),
    )


def tamper(output, fault: str):
    bad = {key: (value.copy() if isinstance(value, np.ndarray) else value) for key, value in output.items()}
    if fault == "label":
        bad["labels"][0] = (int(bad["labels"][0]) + 1) % 3
    elif fault == "weight":
        bad["weights"][0] += 0.125
    elif fault == "reputation_state":
        bad["reputation_state"][0, 2] += 7
    elif fault == "aggregate":
        bad["aggregate"][0] += 0.1
    elif fault == "payment":
        bad["payment"][0] += 0.2
    elif fault == "missing_package":
        return None
    else:
        raise ValueError(fault)
    return bad


def main():
    rows = []
    for run in range(RUNS):
        seed = 2026081000 + 9_500_000 + run
        workload = make_workload(N, 9, 256, seed)
        correct = correct_output(workload.reports, seed)
        correct_digest = digest_output(correct)
        for fault in FAULTS:
            submitted = tamper(correct, fault)
            submitted_digest = None if submitted is None else digest_output(submitted)
            for policy in POLICIES:
                triggered = policy != "no_trigger"
                t0 = time.perf_counter_ns()
                if triggered:
                    # The five auditors independently replay the deterministic
                    # pipeline. Missing data follows the declared timeout fault.
                    votes = []
                    for _ in range(AUDITORS):
                        if submitted_digest is None:
                            votes.append(True)
                        else:
                            replay = correct_output(workload.reports, seed)
                            votes.append(digest_output(replay) != submitted_digest)
                    detected = sum(votes) >= THRESHOLD
                else:
                    detected = False
                audit_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
                corrected = triggered and detected
                rows.append({
                    "run": run,
                    "seed": seed,
                    "n": N,
                    "fault": fault,
                    "policy": policy,
                    "audit_triggered": triggered,
                    "detected": detected,
                    "corrected": corrected,
                    "bad_finalized": not corrected,
                    "honest_votes": AUDITORS if detected else 0,
                    "audit_reexecution_ms": audit_ms,
                    "correct_digest": correct_digest.hex(),
                    "submitted_digest": "MISSING" if submitted_digest is None else submitted_digest.hex(),
                })
    frame = pd.DataFrame(rows)
    RAW.mkdir(parents=True, exist_ok=True)
    frame.to_csv(RAW / "fault_injection_runs.csv", index=False)
    summary = frame.groupby(["fault", "policy"], as_index=False).agg(
        runs=("run", "size"),
        detection_rate=("detected", "mean"),
        correction_rate=("corrected", "mean"),
        bad_finalization_rate=("bad_finalized", "mean"),
        median_reexecution_ms=("audit_reexecution_ms", "median"),
    )
    summary.to_csv(RAW / "fault_injection_summary.csv", index=False)
    checks = {
        "rows": int(len(frame)),
        "cells": int(len(summary)),
        "triggered_detection_min": float(summary.loc[summary.policy.ne("no_trigger"), "detection_rate"].min()),
        "no_trigger_bad_finalization_min": float(summary.loc[summary.policy.eq("no_trigger"), "bad_finalization_rate"].min()),
        "status": "PASS" if summary.loc[summary.policy.ne("no_trigger"), "detection_rate"].eq(1.0).all()
        and summary.loc[summary.policy.eq("no_trigger"), "bad_finalization_rate"].eq(1.0).all() else "FAIL",
    }
    (RAW / "fault_injection_audit.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
