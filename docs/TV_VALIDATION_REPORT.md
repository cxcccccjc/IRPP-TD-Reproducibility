# Dirichlet TV hybrid-improvement experiment

## Implemented method

The improved implementation retains the state-seeded stratified Monte Carlo
estimate with `M=1024` as its fast first stage. For a 100-task horizon, the
number of possible integer concentration states is bounded by

`K_max = C(103,3) = 176851`.

With family-wise failure probability `delta=0.05`, each state is assigned
`delta_s=delta/K_max=2.827238749e-7`. Hoeffding's inequality gives the
simultaneous uncertainty radius

`r_U = sqrt(log(2/delta_s)/(2M)) = 0.0877561605`.

For each state, the interval

`I_U = [max(0,U_hat-r_U), min(1,U_hat+r_U)]`

is mapped exactly through the quadratic reputation function `psi(U)`. The two
endpoints and any stationary point inside `I_U` give the exact score interval.
If that interval excludes `theta=0.35`, the M=1024 decision is certified and
retained. If it contains `theta`, the implementation falls back to deterministic
sliced Dirichlet-TV quadrature.

The quadrature uses orders 128, 256, 512, 1024, 2048, 4096, and 8192 and stops
after two consecutive differences satisfy absolute tolerance `1e-6`. Results
are memoized by the concentration triple and numerical settings.

## Validation scope

- Six workloads: Climate, Traffic, and Water at target participation 27 and 39.
- Thirty retained anchor-sampling seeds.
- One hundred tasks per workload.
- 18,000 complete task evaluations and 599,940 TV accesses per timing run.
- Three independent cold-cache paired timing runs.
- Comparison against both the retained M=1024 implementation and the
  deterministic high-precision reference trajectory.

## Decision and numerical correctness

- 7,005 non-uniform unique states were evaluated on the improved trajectory.
- 6,764 states used certified M=1024 results.
- 241 states (3.44%) required deterministic quadrature.
- All 241 quadrature states met the `1e-6` stopping tolerance.
- Required final orders: 512 for 21 states, 1024 for 66, 2048 for 144, and
  4096 for 10; no state required 8192.
- Maximum reported final quadrature difference: `9.90e-7`.
- Threshold flips relative to the high-precision reference: zero.
- Reference structural mismatches over 14,400 held-out task/seed evaluations:
  zero in all three runs.
- Reference metric mismatches above `1e-10`: zero in all three runs.

The improved output differs from the original M=1024 trajectory on 139 of
14,400 held-out task/seed evaluations (0.97%). These are corrections toward the
high-precision reference, not instability of the improved implementation.

## Held-out NRMSE

| Scene | Target n | Original M=1024 | Improved hybrid | High-precision reference | Relative change |
|---|---:|---:|---:|---:|---:|
| Climate | 27 | 0.003143 | 0.003133 | 0.003133 | -0.324% |
| Climate | 39 | 0.002485 | 0.002493 | 0.002493 | +0.343% |
| Traffic | 27 | 0.000526 | 0.000526 | 0.000526 | -0.006% |
| Traffic | 39 | 0.000295 | 0.000295 | 0.000295 | 0.000% |
| Water | 27 | 0.001597 | 0.001596 | 0.001596 | -0.039% |
| Water | 39 | 0.001265 | 0.001265 | 0.001265 | -0.033% |

Thus the aggregate RQ1 conclusions remain stable, while the improved method
reproduces the reference decisions.

## Runtime

Across three cold-cache paired runs on the recorded Windows/Python environment:

| Runtime statistic | Relative overhead, mean +/- sample SD | Paired absolute increase |
|---|---:|---:|
| Median | 1.662% +/- 0.119% | median 0.02498 ms/task |
| p95 | 3.489% +/- 0.368% | -- |
| Mean | 6.690% +/- 0.075% | mean 0.13227 ms/task |

The larger mean than median reflects the one-time deterministic integration of
previously unseen threshold-near states. Subsequent uses are cache hits.

## Manuscript implication

If this hybrid implementation is adopted, the appendix can state an explicit
sample budget, family-wise probability parameter, decision-certification rule,
deterministic fallback tolerance, cache range, and measured cost. The RQ1
accuracy narrative remains valid, but exact manuscript NRMSE values and runtime
numbers should be regenerated from the hybrid run rather than retaining the
old M=1024 values.

