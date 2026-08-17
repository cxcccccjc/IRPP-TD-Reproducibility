#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE=${IRPP_FISCO_CONSOLE:-/opt/irpp-rq5/runtime/console-v3.7.0}

cd "$CONSOLE"
./contract2java.sh solidity \
  -s "$ROOT/contracts/IRPPWorkflow.sol" \
  -p rq5.contracts \
  -o "$ROOT/java/generated" \
  -e

bash "$ROOT/scripts/build_java.sh"
