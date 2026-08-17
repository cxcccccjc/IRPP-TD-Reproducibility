#!/usr/bin/env python3
"""Run warmups and paired formal off-chain RQ5 measurements."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import pandas as pd

from protocols import ExperimentSuite, make_workload


ROOT = Path(__file__).resolve().parents[1]


def parse_ints(value: str):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-values", default="10,20,27,39,50")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--dimension", type=int, default=9)
    parser.add_argument("--payload-bytes", type=int, default=256)
    parser.add_argument("--seed-base", type=int, default=2026081000)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    n_values = parse_ints(args.n_values)
    if args.smoke:
        n_values, args.runs, args.warmups = [3], 1, 0
    suite = ExperimentSuite(max_workers=max(n_values + [27]), auditors=5)
    rows = []
    methods = [
        ("IRPP-TD", suite.run_irpp),
        ("BSIF", suite.run_bsif),
        ("RPPS-TDC", suite.run_rpps),
        ("PRTD", suite.run_prtd),
    ]

    for warm in range(args.warmups):
        w = make_workload(min(n_values), args.dimension, args.payload_bytes, args.seed_base - 100 - warm)
        for _, fn in methods:
            suite.reset_state(w.n)
            fn(w)

    total = len(n_values) * args.runs * len(methods)
    done = 0
    started = time.time()
    for n in n_values:
        for run in range(args.runs):
            seed = args.seed_base + n * 10_000 + run
            w = make_workload(n, args.dimension, args.payload_bytes, seed)
            rotation = run % len(methods)
            ordered = methods[rotation:] + methods[:rotation]
            for _, fn in ordered:
                suite.reset_state(n)
                result = fn(w)
                result["run"] = run
                rows.append(result)
                done += 1
                elapsed = time.time() - started
                eta = elapsed / done * (total - done) if done else 0
                print(f"OFFCHAIN {done}/{total} {result['protocol']} n={n} run={run} {result['offchain_active_ms']:.1f} ms ETA={eta/60:.1f} min", flush=True)

    # RQ5 accountability paths are measured only at the target load and kept
    # separate from the matched normal-path rows above.
    if not args.smoke and 27 in n_values:
        for run in range(args.runs):
            seed = args.seed_base + 9_000_000 + run
            w = make_workload(27, args.dimension, args.payload_bytes, seed)
            for audit_mode in ("proactive", "challenged", "delayed"):
                suite.reset_state(27)
                result = suite.run_irpp(w, audit_mode=audit_mode)
                result["run"] = run
                rows.append(result)
                print(f"AUDIT {audit_mode} run={run} {result['offchain_active_ms']:.1f} ms", flush=True)

    raw_dir = ROOT / "raw"
    raw_dir.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(raw_dir / "offchain_runs.csv", index=False)
    pd.DataFrame(suite.setup_rows).to_csv(raw_dir / "setup_metrics.csv", index=False)
    manifest = {
        "python": sys.version,
        "platform": platform.platform(),
        "n_values": n_values,
        "runs": args.runs,
        "warmups": args.warmups,
        "dimension": args.dimension,
        "payload_bytes": args.payload_bytes,
        "seed_base": args.seed_base,
        "elapsed_seconds": time.time() - started,
        "normal_rows": total,
        "audit_rows": 0 if args.smoke or 27 not in n_values else 3 * args.runs,
    }
    (raw_dir / "offchain_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
