#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:?Usage: 60_collect_manifest.sh <mounted-Windows-project-dir>}"
install_root="/opt/irpp-rq5"
output="$install_root/manifests/environment_manifest.json"
node_binary="$install_root/runtime/fisco-bcos-v3.7.3/fisco-bcos"
node_count="$(find "$install_root/chain/nodes" -path '*/node*/config.ini' -type f | wc -l)"

source /etc/os-release
fisco_version="$($node_binary -v 2>&1 | head -n 1)"
java_version="$(java -version 2>&1 | head -n 1)"
maven_version="$(mvn -version 2>&1 | head -n 1 | sed -r 's/\x1B\[[0-9;]*[mK]//g')"
openssl_version="$(openssl version)"
python_version="$(python3 --version 2>&1)"
tassl_version="$("$HOME/.fisco/tassl-1.1.1b" version 2>&1 | head -n 1)"
kernel_version="$(uname -r)"
cpu_model="$(lscpu | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"
logical_cpu="$(nproc)"
memory_kib="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
asset_hashes="$(cat "$install_root/manifests/asset_sha256.txt")"
timestamp="$(date --iso-8601=seconds)"

jq -n \
  --arg timestamp "$timestamp" \
  --arg distro "$PRETTY_NAME" \
  --arg kernel "$kernel_version" \
  --arg arch "$(uname -m)" \
  --arg cpu "$cpu_model" \
  --argjson logical_cpu "$logical_cpu" \
  --argjson memory_kib "$memory_kib" \
  --arg fisco "$fisco_version" \
  --arg console "v3.7.0" \
  --arg java_sdk "v3.7.0" \
  --arg java "$java_version" \
  --arg maven "$maven_version" \
  --arg openssl "$openssl_version" \
  --arg python "$python_version" \
  --arg tassl "$tassl_version" \
  --argjson node_count "$node_count" \
  --arg asset_hashes "$asset_hashes" \
  '{
    timestamp: $timestamp,
    guest: {os: $distro, kernel: $kernel, architecture: $arch},
    resources: {cpu_model: $cpu, logical_processors_visible: $logical_cpu, memory_kib: $memory_kib},
    software: {fisco_bcos: $fisco, console: $console, java_sdk: $java_sdk, java: $java, maven: $maven, openssl: $openssl, tassl: $tassl, python: $python},
    chain: {architecture: "Air", vm: "EVM", consensus: "PBFT", chain_id: "chain0", group_id: "group0", nodes: $node_count, tls: true, sm_crypto: false},
    asset_sha256: $asset_hashes
  }' > "$output"

cp "$output" "$project_dir/manifests/environment_manifest.json"
cp "$install_root/manifests/asset_sha256.txt" "$project_dir/manifests/asset_sha256.txt"
mkdir -p "$project_dir/logs"
cp -f "$install_root/logs"/smoke_* "$project_dir/logs/"
echo "Manifest written to $output and copied to the Windows project."
