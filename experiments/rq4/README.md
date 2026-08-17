# RQ4 reproducibility package

This directory contains the independent RQ4 implementation, frozen configuration, raw results, summaries, tests, and publication figures used for the parameter-sensitivity, numerical-stability, and scalability evaluation of IRPP-TD.

## Environment

- Python 3.9.13
- NumPy 2.0.2
- pandas 2.3.3
- SciPy 1.13.1
- psutil 7.2.2
- Matplotlib 3.9.4
- Windows 10/11 AMD64, 16 cores/32 threads, 31.2 GiB RAM

Use any Python environment that provides the versions above.

## Inputs and frozen settings

`config.json` records the six RQ1 workload files, tasks 1--20 for calibration, tasks 21--100 for evaluation, seeds 20260808--20260837, all frozen IRPP-TD parameters, the exact-ABOD calibration, sensitivity grids, timing policy, and numerical stress cases. `metadata/input_manifest.json` records SHA-256 hashes for the six input files.

## Reproduction

From this directory, run:

```powershell
python run_rq4.py --phase all
python run_rq4_boundaries.py
python analyze_rq4.py
python plot_rq4.py
python -m unittest discover -s tests -v
```

The full run is intentionally large. For a smoke test, use `python run_rq4.py --quick` and the corresponding `*_quick.csv` outputs. Do not use quick-mode values in the manuscript.

## Artifact map

- `src/rq4_core.py`: formal IRPP-TD/RABOD/TD implementation and safeguards.
- `run_rq4.py`: angular-budget, stopping-grid, scalability, resource, stability, and semantic-applicability experiments.
- `run_rq4_boundaries.py`: input-boundary and component-ablation trials.
- `analyze_rq4.py`: summaries, confidence intervals, slopes, and integrity audit.
- `plot_rq4.py`: main and supplementary publication figures.
- `results/`: complete raw and summarized CSV/JSON results.
- `metadata/`: environment, input hashes, and integrity checks.
- `figures/`: PDF, SVG, PNG, and TIFF exports.
- `tests/test_rq4.py`: invariant tests for the near-aggregate case, identical reports, rank-1 fallback, and protected numerical stability.

## Primary verified outputs

`results/rq4_key_findings.json` contains the exact values quoted in the manuscript. `metadata/integrity_audit.json` verifies row counts, finite metrics, minimum timing repetitions, full protected-trial success, and equality with the frozen RQ1 parameters.
