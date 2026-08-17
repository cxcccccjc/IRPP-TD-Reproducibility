# Formal RQ5 environment record

- Host virtualization: WSL2, Ubuntu 22.04, Linux x86-64.
- CPU allocation: 8 logical CPUs from an AMD Ryzen 9 9955HX 16-Core Processor
  (4 exposed cores, 2 threads/core, one virtual socket).
- Memory allocation: 16,770,523,136 bytes (15.62 GiB); 8 GiB swap.
- FISCO BCOS: 3.7.3, release build, commit
  `5811f123b0a82928de8ec662e84763d67c16fb1e`.
- Ledger topology: four local nodes, PBFT/EVM/TLS; all four node processes were
  live immediately before formal measurement.
- Python: 3.10.12.
- Java: OpenJDK 11.0.31, 64-bit Server VM.
- OpenSSL: 3.0.2.
- NTRU+768: authors' optimized implementation, commit
  `0c249d5828b90e8dd5de2c8405323d5ee2a0ce41`.

The WSL launcher prints a localhost-proxy/NAT warning because the Windows host
has a loopback proxy configured. RQ5 uses only local filesystem paths and local
FISCO BCOS endpoints; the warning does not affect a transaction or a protocol
message, and no external WAN endpoint is measured.
