#!/usr/bin/env bash
set -euo pipefail

install_root="/opt/irpp-rq5"
node_version="v3.7.3"
node_runtime="$install_root/runtime/fisco-bcos-${node_version}"
console_runtime="$install_root/runtime/console-v3.7.0"
build_script="$install_root/cache/build_chain_${node_version}.sh"
chain_root="$install_root/chain"
nodes_dir="$chain_root/nodes"
account_script_source="$console_runtime/get_account.sh"

if [[ ! -x "$node_runtime/fisco-bcos" || ! -s "$build_script" || \
      ! -s "$account_script_source" ]]; then
  echo "Run 20_install_fisco.sh first." >&2
  exit 1
fi

account_script_hash="$(sha256sum "$account_script_source" | awk '{print toupper($1)}')"
expected_account_script_hash="B5ED2B5AB820098B26FFA7168C001502CEEAC83C76566B5DE0DA3474C935D6DC"
if [[ "$account_script_hash" != "$expected_account_script_hash" ]]; then
  echo "Console get_account.sh SHA-256 mismatch." >&2
  exit 1
fi

if [[ -d "$nodes_dir" ]]; then
  node_configs="$(find "$nodes_dir" -path '*/node*/config.ini' -type f | wc -l)"
  if [[ "$node_configs" -eq 4 && -x "$nodes_dir/127.0.0.1/start_all.sh" ]]; then
    echo "Existing complete four-node chain retained at $nodes_dir"
    exit 0
  fi
  echo "A partial nodes directory exists; it was not overwritten: $nodes_dir" >&2
  exit 1
fi

mkdir -p "$chain_root"
cd "$chain_root"
# The release build script otherwise downloads this helper from a retired COS
# URL. Reuse the same official helper bundled in the hash-pinned Console release.
install -m 0755 "$account_script_source" "$chain_root/get_account.sh"
bash "$build_script" \
  -l 127.0.0.1:4 \
  -p 30300,20200 \
  -o "$nodes_dir" \
  -e "$node_runtime/fisco-bcos" \
  -g group0 \
  -I chain0

node_configs="$(find "$nodes_dir" -path '*/node*/config.ini' -type f | wc -l)"
if [[ "$node_configs" -ne 4 ]]; then
  echo "Expected four node configurations, found $node_configs." >&2
  exit 1
fi

echo "Four-node PBFT chain generated at $nodes_dir"
