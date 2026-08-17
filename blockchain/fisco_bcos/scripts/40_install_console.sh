#!/usr/bin/env bash
set -euo pipefail

install_root="/opt/irpp-rq5"
console_dir="$install_root/runtime/console-v3.7.0"
nodes_dir="$install_root/chain/nodes"
sdk_cert_dir="$nodes_dir/127.0.0.1/sdk"
conf_dir="$console_dir/conf"

if [[ ! -x "$console_dir/start.sh" || ! -d "$sdk_cert_dir" ]]; then
  echo "Install assets and build the four-node chain first." >&2
  exit 1
fi

mkdir -p "$conf_dir" "$install_root/sdk/conf"
if [[ ! -f "$conf_dir/config.toml" ]]; then
  cp "$conf_dir/config-example.toml" "$conf_dir/config.toml"
fi
if [[ -f "$conf_dir/log4j2-example.xml" && ! -f "$conf_dir/log4j2.xml" ]]; then
  cp "$conf_dir/log4j2-example.xml" "$conf_dir/log4j2.xml"
fi

cp "$sdk_cert_dir/ca.crt" "$conf_dir/"
cp "$sdk_cert_dir/sdk.crt" "$conf_dir/"
cp "$sdk_cert_dir/sdk.key" "$conf_dir/"
cp "$sdk_cert_dir/ca.crt" "$install_root/sdk/conf/"
cp "$sdk_cert_dir/sdk.crt" "$install_root/sdk/conf/"
cp "$sdk_cert_dir/sdk.key" "$install_root/sdk/conf/"

python3 - "$conf_dir/config.toml" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text, count = re.subn(
    r'(?m)^\s*peers\s*=\s*\[[^\]]*\]',
    'peers=["127.0.0.1:20200", "127.0.0.1:20201", "127.0.0.1:20202", "127.0.0.1:20203"]',
    text,
    count=1,
)
if count != 1:
    raise SystemExit("Unable to locate the peers field in Console config.toml")
path.write_text(text, encoding="utf-8")
PY

java -version
echo "Console v3.7.0 configured for all four TLS RPC endpoints."
echo "Java SDK v3.7.0 is locked for the RQ5 client implementation."
