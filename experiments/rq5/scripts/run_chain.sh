#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE=${IRPP_FISCO_CONSOLE:-/opt/irpp-rq5/runtime/console-v3.7.0}
CONFIG="$CONSOLE/conf/config.toml"
OUT=${1:-"$ROOT/raw/chain"}
RUNS=${2:-30}
N_VALUES=${3:-10,20,27,39,50}
DIMENSION=${4:-9}
PAYLOAD=${5:-256}
WARMUPS=${6:-3}
BURSTS=${7:-10}
BURST_TX=${8:-300}

mkdir -p "$OUT"
cd "$CONSOLE"
java -Dfile.encoding=UTF-8 \
  -cp "$ROOT/java/build/classes:$CONSOLE/lib/*:$CONSOLE/conf" \
  rq5.RQ5LedgerRunner "$CONFIG" "$OUT" "$RUNS" "$N_VALUES" \
  "$DIMENSION" "$PAYLOAD" "$WARMUPS" "$BURSTS" "$BURST_TX"
