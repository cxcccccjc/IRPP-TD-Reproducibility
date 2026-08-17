# Compact RQ3 reproducibility package

This package reproduces the final RQ3 analysis and figures while keeping the
repository-local processed workloads and baseline snapshots read-only.

## Final comparison contract

- Fig. 3(a) and Fig. 3(b) use the unchanged RQ1 aggregation adapters and do not
  apply the report-screening thresholds introduced for Fig. 3(c).
- Fig. 3(c) compares IRPP-TD's native RABOD decision, RPPS-TDC's retained
  native threshold `p=0.3`, and PRTD's effective-weight gate calibrated only on
  clean tasks 1--20 to 96% acceptance.
- QE remains an accuracy baseline in Fig. 3(a,b), but is intentionally absent
  from Fig. 3(c) because it is an exhaustive scan rather than the comparable
  reputation-threshold filter.
- All reported intervals use 30 paired seeds and 2,000 bootstrap repetitions.

## Included evidence

- Experiment, analysis, plotting, validation, and table-generation code.
- Configuration, source wrappers, tests, run metadata, and integrity audit.
- Summary and seed/scene CSV files used by every final panel.
- All six formal RPPS-TDC screening shards and clean-threshold records.
- Publication PDF/SVG/PNG figures and the corresponding manuscript sources.

## Deliberately excluded large intermediates

The primary report/task shards, Mature-Anchor grid task shards, mode-baseline
task shards, and PRTD calibrated task shards remain in the local experiment
directory. They total several hundred megabytes and can be regenerated with
the commands in `README.md`. Their aggregate outcomes, per-seed summaries,
configuration, hashes, and integrity checks are included here.
