# IRPP-TD RQ5 reproducible environment

This directory prepares the fixed execution environment used by RQ5. It does
not modify the earlier IRPP source tree.

## Locked design

- Host: Windows 11 Pro, build 22631, AMD Ryzen 9 9955HX (16C/32T), 31.19 GB RAM.
- Virtualization: Microsoft WSL 2.7.11 with the official `Ubuntu-22.04` distro.
- Guest: Ubuntu 22.04.5 LTS, x86-64, kernel 6.18.33.2.
- WSL resource ceiling: 8 logical processors, 16 GB RAM, 8 GB swap.
- Blockchain node: FISCO BCOS v3.7.3, Air architecture, EVM, PBFT, one group,
  four consensus nodes, non-SM TLS.
- Client: FISCO BCOS Console v3.7.0 and Java SDK v3.7.0 on OpenJDK 11.
- Chain data and benchmark logs: `/opt/irpp-rq5` inside the Linux filesystem.

FISCO BCOS v3.7.3 is deliberately used instead of the latest feature branch:
the v3.16.3 release page identifies v3.7.3 as the production-stable line. The
exact node, Console, SDK, OS, consensus mode, and resource ceiling are locked;
writing only "FISCO BCOS 3.x" would not be reproducible.

## Current status

The Windows Subsystem for Linux and Virtual Machine Platform optional features
are enabled and the required reboot has completed. Microsoft WSL 2.7.11 and
the official Ubuntu 22.04.5 LTS distribution are installed. The resource
ceiling is fixed in `%USERPROFILE%\.wslconfig` at 8 logical processors, 16 GB
RAM, and 8 GB swap.

The four-node chain, all four Console TLS endpoints, PBFT view query, contract
deployment, contract call, and block-height advance have passed. All four
release assets are preserved locally with locked sizes and SHA-256 hashes, so
the environment can be rebuilt without depending on the retired COS URLs.

The FISCO-BCOS/TASSL V_1.4 certificate binary is pinned separately because the
legacy COS URL embedded in `build_chain.sh` is no longer accessible. For the
same reason, chain creation reuses the official `get_account.sh` bundled in the
hash-pinned Console v3.7.0 archive rather than downloading a mutable copy.

## Safe execution order

1. Open an elevated PowerShell in this directory.
2. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
   .\scripts\01_post_reboot_audit.ps1`.
3. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
   .\scripts\70_run_post_reboot.ps1` to install dependencies, retain or build
   the four-node chain, configure Console/SDK, run smoke tests, and collect a
   manifest.

The scripts are intentionally conservative: they do not unregister a WSL
distro, delete a chain, overwrite an existing `.wslconfig`, or rebuild an
existing complete node directory. A partial or conflicting installation stops
for inspection.

Console v3.7.0 may print an optional `libproviders.so` probe diagnostic from
its JNI bundle on this non-HSM Linux configuration. HSM and SM crypto are both
disabled, and this optional provider is outside the measured path. The smoke
test validates the required path explicitly: four TLS sessions, `group0`, PBFT
view, an exact deployment address, a successful receipt, the `Hello, World!`
return value, and advancing block height.

## Evidence

- `logs/post_reboot_audit_*.txt`: WSL and Windows feature audit.
- `manifests/asset_sha256.txt`: checksums of every release asset.
- `manifests/environment_manifest.json`: host/guest/software/node manifest.
- `logs/smoke_*`: four-node process, PBFT progress, Console block query, and
  HelloWorld deployment and call evidence.

Performance results should be collected only after the smoke test passes, with
a warm-up followed by at least 30 measured runs, reporting median, p95, and 95%
intervals. All reproduced protocols must share this same hardware, chain,
payload, worker count, and cryptographic security level.
