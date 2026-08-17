# RQ5 replication decisions and fairness ledger

This log records implementation choices that are not fully fixed by the source
papers. None is tuned against the measured RQ5 outcome.

## Shared controls

All four systems receive the same seeded sensing vectors, worker counts,
dimension, plaintext payload, execution host, warmup count, and paired run IDs.
Long-lived key generation, contract deployment, and worker registration are
reported as setup rather than charged to every task. Execution order rotates by
run to reduce temperature and background-load bias.

All off-chain paths run in one process and one application thread. We do not
introduce scheme-specific worker parallelism or batching that is absent from a
source protocol. FISCO BCOS uses its native four-node consensus and SDK async
submission only in the separately identified throughput bursts.

The Paillier systems use one GMP-backed implementation and 3072-bit moduli.
This avoids ranking a baseline with a deliberately slow pure-Python modular
arithmetic path. Cryptographic envelopes are serialized at their actual fixed
width; missing protocol phases are N/A rather than zero.

## IRPP-TD

- NTRU+768 uses the authors' optimized implementation at commit
  `0c249d5828b90e8dd5de2c8405323d5ee2a0ce41`.
- KEM output is used through AES-256-GCM KEM--DEM envelopes; Ed25519 provides
  the instantiated message signatures.
- The full hidden-ticket scan, two-hop submission, RABOD/guarded TD,
  one-use credential refresh, feedback verification, and P7 audit paths are
  included. A 500-ms challenge window is excluded from active latency and
  included in normal final latency.
- Five distinct FISCO accounts are registered as auditors. The contract rejects
  an unregistered or duplicate per-round vote, and a corrected finalization is
  authorized only after at least three registered accounts report the DR fault
  and agree on the identical corrected digest.
- A challenged task cannot take the ordinary finalization branch until an audit
  resolves it, and a correction-authorized task cannot be downgraded through
  `finalize(false)`. Negative preflights test both guards and the disagreeing-
  digest case before measured tasks begin.

## BSIF

The paper specifies the inner Paillier layer but does not define how a worker
should place the large Paillier object inside a second public-key encryption
layer at the matched security level. We use a standard RSA-3072-OAEP plus
AES-256-GCM hybrid envelope. Directly applying RSA to the Paillier byte string
would be invalid; the hybrid choice is conventional, runnable, and favorable to
BSIF. BSIF quality evaluation is measured, but TD accuracy is N/A because BSIF
does not implement truth discovery.

## RPPS-TDC

The replication implements the paper's AES/GeoHash task protection,
Paillier-encrypted upload, mining-node scrambling, DBCRH, Trust-MaxHeap/RUBS
state path, encrypted weighted aggregation, reputation update, payment, and
ledger commitments. Where transaction packing is not fixed by the paper, each
native lifecycle update is a conventional independent EVM transaction rather
than an IRPP-specific batching optimization.

## PRTD

The complete non-chain protocol includes Paillier distance computation,
Pedersen/RZKPV material, the two-cloud reliability-level TD loop,
ElGamal-KEM/DEM protected results, and reputation update. PRTD has no blockchain
in the source protocol: transaction count, chain confirmation, ledger storage,
gas, and TPS are therefore N/A. Its valid off-chain latency and communication
remain part of every matched comparison.

## Ledger measurement definition

`ledger_bytes_task` is the sum of encoded confirmed transaction inputs and SDK
receipt bytes. It is a reproducible protocol-level ledger traffic/storage proxy,
not a claim about physical RocksDB file growth, whose compaction and shared
metadata make short-run directory deltas unstable. Contract deployment and
registration are retained in `chain_setup.csv` and excluded from task rows.

TPS bursts contain 300 protocol-native report transactions. Thus their payloads
are intentionally not forced to the same ciphertext length: IRPP-TD submits a
compact commitment/credential record, while BSIF and RPPS-TDC submit their
native serialized encrypted-report records. The plaintext workload remains 256
bytes for every protocol, and the actual burst payload length is recorded in
every throughput row.
