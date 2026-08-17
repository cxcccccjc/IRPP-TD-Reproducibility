# RQ5 claim–evidence matrix

| Claim | Required evidence | Environment support | Remaining measurement | Review risk |
|---|---|---|---|---|
| IRPP-TD is executable on a practical permissioned blockchain | Real four-node consensus chain, successful SDK query and state-changing transaction | Locked four-node FISCO BCOS v3.7.3 PBFT/EVM/TLS chain and HelloWorld smoke test | Deploy the IRPP-TD contracts and execute the complete task workflow | Critical until smoke test and protocol run pass |
| End-to-end comparison is fair | Same host, resource ceiling, payload, security level, chain, run count, and workload | One WSL2 guest and one matched chain are shared by IRPP-TD, RPPS-TDC, and the FISCO port of BSIF | Implement protocol adapters and verify identical input manifests | Major |
| Runtime and storage numbers are reproducible | Exact software versions, hashes, hardware, warm-up, repeats, and statistical policy | `environment.lock.json`, asset SHA-256 manifest, 30-run policy, median/p95/95% interval | Record measured logs and raw per-run CSV files | Major |
| PRTD is compared without inventing blockchain behavior | Full non-chain workflow timed; chain-only metrics shown as N/A | Measurement policy explicitly marks non-applicable chain metrics as N/A | Run the complete PRTD cryptographic/TD/reputation path on the same host | Major |
| Reported overhead separates computation from settlement delay | Active latency and final latency measured independently | Both latency views are locked in the measurement policy | Instrument protocol phase boundaries and confirmation events | Major |
