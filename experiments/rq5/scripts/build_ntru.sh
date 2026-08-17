#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR=${IRPP_NTRU_BUILD_DIR:-/tmp/pqcrypto-ntru-build}
ARCHIVE=${IRPP_PQCRYPTO_ARCHIVE:-/tmp/pqcrypto_old/pqcrypto-0.1.3.tar.gz}
VENV=${IRPP_VENV:-/opt/irpp-rq5/venv}

if [[ -z "$BUILD_DIR" || "$BUILD_DIR" == "/" ]]; then
  echo "Refusing unsafe build directory: $BUILD_DIR" >&2
  exit 2
fi
rm -rf -- "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
tar -xzf "$ARCHIVE" -C "$BUILD_DIR" --strip-components=1
cd "$BUILD_DIR"
"$VENV/bin/python" -c 'from compile import ntruhps2048509_ffi; ntruhps2048509_ffi.compile(verbose=True)'
cp pqcrypto/_kem/ntruhps2048509*.so "$VENV/lib/python3.10/site-packages/pqcrypto/_kem/"
"$VENV/bin/python" -c 'from pqcrypto.kem import ntruhps2048509 as n; pk,sk=n.generate_keypair(); c,s=n.encrypt(pk); assert n.decrypt(sk,c)==s; print(len(pk),len(sk),len(c),len(s))'
