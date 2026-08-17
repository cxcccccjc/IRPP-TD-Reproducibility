#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/third_party/ntruplus/Reference_Implementation/NTRU+768"
OUT="$ROOT/native"
mkdir -p "$OUT"

gcc -O3 -fPIC -fvisibility=hidden -shared -I"$SRC" \
  -o "$OUT/libntruplus768.so" \
  "$SRC/kem.c" "$SRC/poly.c" "$SRC/ntt.c" "$SRC/symmetric.c" \
  "$SRC/fips202/fips202.c" "$SRC/randombytes.c"

sha256sum "$OUT/libntruplus768.so"
