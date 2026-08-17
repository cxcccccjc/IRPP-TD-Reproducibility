# IRPP-TD Reproducibility Repository

This repository contains the implementation, experiment drivers, frozen
configurations, processed workloads, blockchain contracts, and audit scripts
used to evaluate IRPP-TD. It covers RQ1--RQ5 and intentionally excludes the
RDPP-TD implementation and its dedicated experiment inputs.

## Scope

| Area | Contents |
|---|---|
| `irpp_core/` | Shared guarded Dirichlet-TV evaluator and reputation scoring |
| `experiments/rq1/` | Accuracy, runtime, stage statistics, and Fig. 4 without RDPP-TD |
| `experiments/rq2/` | Cold start, malicious participation, early errors, and state changes |
| `experiments/rq3/` | Worker-side poisoning, attack modes, leakage, and robustness |
| `experiments/rq4/` | Angular budget, stopping, stability, applicability, and scaling |
| `experiments/rq5/` | Off-chain protocols, Solidity contracts, Java ledger runner, audits, and figures |
| `blockchain/fisco_bcos/` | FISCO BCOS 3.7.3 four-node PBFT/WSL setup and locked manifests |
| `baselines/` | Retained comparison adapters and source snapshots, excluding RDPP-TD |
| `data/workloads/` | Six processed workloads for three sensor domains and two participation levels |
| `data_processing/` | Sensor and SUMO preprocessing scripts |
| `tests/` | Shared numerical tests |

Large generated TIFFs, compiled binaries, blockchain release archives, node
databases, certificates, private keys, and redundant task-level result tables
are not tracked. The scripts regenerate or download them with pinned versions
and hashes.

## Environment

The Python experiments were run with Python 3.9 and the versions in
`requirements.txt`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the shared checks first:

```powershell
python tests/test_hybrid_tv.py
python experiments/rq2/tests/test_reorganized.py
```

Each experiment directory has its own reproduction instructions. Typical
entry points are:

```powershell
python experiments/rq1/run_rq1.py --stage all --force
python experiments/rq2/run_rq2_reorganized.py --task-limit 100 --output-tag formal
python experiments/rq3/run_rq3.py --quick
python experiments/rq4/run_rq4.py --quick
```

RQ5 requires WSL2 and the four-node FISCO BCOS environment described in
`blockchain/fisco_bcos/README.md`. Contracts and client code are under
`experiments/rq5/`; its pinned Python environment is listed separately in
`experiments/rq5/config/requirements.lock.txt`.

## Numerical implementation note

The current shared evaluator in `irpp_core/reputation.py` uses state-seeded
stratified Monte Carlo, a simultaneous Hoeffding guard, deterministic sliced
Dirichlet-TV quadrature near the reputation threshold, and state/configuration
caching. RQ3 and RQ4 retain their frozen experiment snapshots so archived
outputs remain traceable; do not silently replace their numerical component
when reproducing those archived tables.

## RDPP-TD exclusion

The RDPP-TD comparison reported in the paper was executed separately using the
code package supplied by its original authors. To comply with their privacy
and security statement, this repository does not contain, redistribute, or
rewrite that implementation, its dedicated experiment scripts, or its inputs.
Consequently, the repository-local RQ1 rerun and Fig. 4(d) plotting path omit
RDPP-TD. See `docs/RDPP_EXCLUSION.md`.

## Data and security

The repository includes processed task workloads but not the large upstream
sensor archives or SUMO route assets. Blockchain scripts create local test
credentials during setup; no credential or production secret is committed.
This code is a research artifact and is not production security software.

Third-party copyright and license information is recorded in
`THIRD_PARTY_NOTICES.md`. No project-wide license is granted unless a root
`LICENSE` file is added by the authors.
