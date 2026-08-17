# RQ3 worker-side poisoning experiment

This directory is an isolated RQ3 rerun. It reads the processed workloads and
retained baseline snapshots from this repository but does not modify them.

## Frozen contract

- Three primary workloads at target participation 27; target 39 is the replication.
- 100 tasks, 30 paired seeds (`20260808`--`20260837`), and 2,000 bootstrap repetitions.
- Five platform-affiliated HQ workers are fully honest and outside the worker-side adversary.
- Immediate Independent/Compact, On--Off, and task-41 Mature-Anchor attacks.
- Malicious ratio `0.0:0.1:0.8`; normalized strength `{0.1,0.25,0.5,1,2}`.
- Operational failure is `R_E >= 5` or no-truth rate above 5%; it is not a theoretical breakdown point.

## Reproduction

Run from the repository root with the configured Python environment:

```text
python run_rq3.py --shard-index 0 --shard-count 1
python run_mature_grid.py --shard-index 0 --shard-count 1
python run_mode_baselines.py --shard-index 0 --shard-count 1
python run_mode_leakage_baselines.py
python run_calibrated_baselines.py --shard-index 0 --shard-count 1
python run_rpps_calibrated_leakage.py --shard-index 0 --shard-count 1
python analyze_rq3.py
python make_rq3_tables.py
python plot_rq3.py
python validate_rq3.py
```

The delivered compact package includes source, configuration, summary CSVs,
figures, LaTeX tables, run manifests, and the integrity audit. The large raw
task/report CSV shards remain in the local working directory.

## Main verified findings

- Immediate compact collusion: IRPP-TD NRMSE is 0.00215 at malicious ratio 0.8,
  versus 0.406--0.488 for the three unchanged retained baselines; no-truth is
  zero.
- Immediate Independent/Compact attacks at `(rho_m,kappa)=(0.3,0.5)` have zero
  malicious leakage and matched error ratio 1.21.
- At the primary mode comparison, IRPP-TD NRMSE is 0.00137 under Independent
  and Compact attacks. Under On--Off it is 0.03631, close to CRH-N at 0.03544;
  under Mature-Anchor it has the lowest point estimate, 0.03315.
- On--Off and Mature-Anchor attacks expose the feedback limitation, with error
  ratios 63.10 and 50.75 and leakage 0.249 and 0.206.
- Fig. 3(c) uses method-faithful report decisions: IRPP-TD's native RABOD
  label, RPPS-TDC's retained native p=0.3, and a PRTD weight gate fitted only
  on clean tasks 1--20 to 96% acceptance. RPPS-TDC leakage is 0.00025, 0.080,
  0.293, and 0.295 across the four modes; PRTD leakage is 0.719--0.780.
  IRPP-TD combines zero immediate leakage with 0.953--0.993 honest-report
  acceptance and lower timed leakage.
- Under permanent task-41 poisoning, Full ordinary-anchor purity recovers from
  0.700 in block 40 to 0.968 in block 100, and block error ratio falls to 1.35.
