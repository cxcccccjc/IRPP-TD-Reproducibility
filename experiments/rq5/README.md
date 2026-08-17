# RQ5 matched end-to-end experiment

This directory contains the complete local implementations and formal
measurement pipeline for IRPP-TD, BSIF, RPPS-TDC, and PRTD.

## Frozen fairness contract

- Platform: WSL2 Ubuntu 22.04, 8 vCPU, 16 GiB RAM.
- Ledger: FISCO BCOS 3.7.3, four PBFT/EVM/TLS nodes.
- Workloads: 10, 20, 27, 39, and 50 workers; 9-D reports; 256-byte plaintext
  payload; one shared seeded workload per paired repetition.
- Statistics: three warmups and 30 measured paired repetitions per cell.
- Security: NTRU+768 and AES-256-GCM for IRPP-TD; Paillier-3072 for the
  Paillier protocols; standard 3072-bit groups/envelopes where a source paper
  leaves an outer mechanism underspecified.
- Scope: deployment and worker registration are reusable setup costs and are
  excluded from per-task latency. PRTD has no ledger path, so all ledger fields
  are N/A. BSIF has no truth-discovery stage, so TD accuracy is N/A.

## Reproduction order

The scripts derive the experiment root from their own location. Set
`IRPP_FISCO_CONSOLE` only when the FISCO BCOS console is not installed at
`/opt/irpp-rq5/runtime/console-v3.7.0`.

1. `scripts/build_ntruplus.sh`
2. `scripts/rebuild_contracts.sh` (regenerates the IRPP threshold-audit wrapper
   and then calls `scripts/build_java.sh`)
3. `python/run_offchain.py --runs 30 --warmups 3`
4. `scripts/run_chain.sh ... 30 10,20,27,39,50 9 256 3 10 300`
5. `python/run_fault_injection.py`
6. `python/analyze_rq5.py`
7. `python/plot_rq5.py`
8. `python/generate_rq5_tables.py`
9. `python/package_rq5.py` after both PDFs have passed visual QA.

The analysis script fails closed when any formal cell is missing, a transaction
fails, a value is non-finite, or PRTD accidentally receives chain values.

Before any measured task, the Java runner executes negative ledger preflights:
an unresolved challenge must reject ordinary finalization; a threshold-approved
correction must reject `finalize(false)`; three disagreeing corrected digests
must not form a quorum; and three distinct registered accounts agreeing on one
digest must authorize `finalize(true)`. Formal execution starts only after the
runner prints `PREFLIGHT ... PASS`.

## File-to-evidence map

| File | Evidence |
|---|---|
| `python/protocols.py` | Four complete off-chain protocol paths and per-entity timing |
| `contracts/*.sol` | IRPP-TD, BSIF, and RPPS-TDC ledger workflows |
| `java/src/rq5/RQ5LedgerRunner.java` | Transaction, confirmation, storage, and TPS measurement |
| `python/analyze_rq5.py` | Paired merge, 95% bootstrap intervals, integrity audit, audit-risk model |
| `python/run_fault_injection.py` | Wrong label/weight/state/aggregate/payment and missing-package P7 checks |
| `python/plot_rq5.py` | Main Fig. 5 and supplementary Figs. S7--S8 |
| `python/generate_rq5_tables.py` | Final lifecycle/measurement table and key findings |

The BSIF replication decision log must disclose that the paper does not define
an outer encryption mechanism for nested Paillier ciphertexts at the matched
security level. We use a standard RSA-3072-OAEP plus AES-256-GCM envelope, a
conservative implementation choice that favors BSIF rather than IRPP-TD.
