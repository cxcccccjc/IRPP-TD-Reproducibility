#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:?Usage: 20_install_fisco.sh <mounted-Windows-project-dir>}"
asset_src="$project_dir/assets"
install_root="/opt/irpp-rq5"
cache_dir="$install_root/cache"
runtime_dir="$install_root/runtime"
manifest_dir="$install_root/manifests"

node_version="v3.7.3"
console_version="v3.7.0"
node_archive="fisco-bcos-linux-x86_64_${node_version}.tar.gz"
console_archive="console_${console_version}.tar.gz"
build_script="build_chain_${node_version}.sh"
tassl_archive="tassl-1.1.1b-linux-x86_64.tar.gz"

mkdir -p "$cache_dir" "$runtime_dir" "$manifest_dir"

copy_if_present() {
  local name="$1"
  if [[ -s "$asset_src/$name" && ! -s "$cache_dir/$name" ]]; then
    cp "$asset_src/$name" "$cache_dir/$name"
  fi
}

download_checked() {
  local target="$1"
  local expected_size="$2"
  local browser_url="$3"
  local api_url="$4"
  local expected_hash="$5"
  local current_size=0
  if [[ -e "$target" ]]; then
    current_size="$(stat -c %s "$target")"
  fi
  if [[ "$current_size" -gt "$expected_size" ]]; then
    mv "$target" "${target}.invalid.$(date +%Y%m%d_%H%M%S)"
    current_size=0
  fi
  if [[ "$current_size" -lt "$expected_size" ]]; then
    if command -v aria2c >/dev/null 2>&1; then
      aria2c --continue=true --max-connection-per-server=16 --split=16 \
        --min-split-size=1M --file-allocation=none --auto-file-renaming=false \
        --allow-overwrite=true --header='Accept: application/octet-stream' \
        --header='X-GitHub-Api-Version: 2022-11-28' \
        --dir="$(dirname "$target")" --out="$(basename "$target")" "$api_url"
    else
      resume_args=()
      if [[ "$current_size" -gt 0 ]]; then
        resume_args=(-C -)
      fi
      if curl -fL --retry 10 --retry-all-errors --retry-delay 3 \
        "${resume_args[@]}" -H 'Accept: application/octet-stream' \
        -H 'X-GitHub-Api-Version: 2022-11-28' -o "$target" "$api_url"; then
        :
      else
        if [[ -e "$target" ]]; then
          mv "$target" "${target}.invalid.$(date +%Y%m%d_%H%M%S)"
        fi
        curl -fL --retry 10 --retry-all-errors --retry-delay 3 \
          -o "$target" "$browser_url"
      fi
    fi
  fi
  local actual_size
  actual_size="$(stat -c %s "$target")"
  if [[ "$actual_size" -ne "$expected_size" ]]; then
    echo "Asset size mismatch: $target ($actual_size instead of $expected_size bytes)" >&2
    exit 1
  fi
  tar -tzf "$target" >/dev/null
  local actual_hash
  actual_hash="$(sha256sum "$target" | awk '{print toupper($1)}')"
  if [[ "$actual_hash" != "$expected_hash" ]]; then
    echo "Asset SHA-256 mismatch: $target" >&2
    exit 1
  fi
}

copy_if_present "$build_script"
copy_if_present "$node_archive"
copy_if_present "$console_archive"
copy_if_present "$tassl_archive"

if [[ ! -s "$cache_dir/$build_script" ]]; then
  curl -fL --retry 10 --retry-all-errors --retry-delay 3 \
    -o "$cache_dir/$build_script" \
    "https://github.com/FISCO-BCOS/FISCO-BCOS/releases/download/${node_version}/build_chain.sh"
fi

build_hash="$(sha256sum "$cache_dir/$build_script" | awk '{print toupper($1)}')"
expected_build_hash="18A1000A987D2222D8E857D84029ED914BCB78E96D78F8B2D2C408D86C0E05B9"
if [[ "$build_hash" != "$expected_build_hash" ]]; then
  echo "build_chain.sh SHA-256 mismatch." >&2
  exit 1
fi

download_checked "$cache_dir/$node_archive" 30233449 \
  "https://github.com/FISCO-BCOS/FISCO-BCOS/releases/download/${node_version}/fisco-bcos-linux-x86_64.tar.gz" \
  "https://api.github.com/repos/FISCO-BCOS/FISCO-BCOS/releases/assets/175171150" \
  "B2B0121722A612DED5CCF4209BF88D12F224F4EBC75A5F2D9BAFEAC898B27D89"
download_checked "$cache_dir/$console_archive" 151640115 \
  "https://github.com/FISCO-BCOS/console/releases/download/${console_version}/console.tar.gz" \
  "https://api.github.com/repos/FISCO-BCOS/console/releases/assets/163477054" \
  "F82DB3F99E64E2EAFEFE6586D970FE12E0DE47ED810BC78D41432587F88EDF0C"
download_checked "$cache_dir/$tassl_archive" 1780655 \
  "https://github.com/FISCO-BCOS/TASSL/releases/download/V_1.4/${tassl_archive}" \
  "https://api.github.com/repos/FISCO-BCOS/TASSL/releases/assets/197923515" \
  "97700126DF491B4AE15AFAE1BAD99979390DED5D7D1655632E00B40003A9A9E8"

tassl_target="$HOME/.fisco/tassl-1.1.1b"
if [[ ! -x "$tassl_target" ]]; then
  tassl_extract_dir="$(mktemp -d)"
  trap 'rm -rf -- "$tassl_extract_dir"' EXIT
  tar -xzf "$cache_dir/$tassl_archive" \
    -C "$tassl_extract_dir" tassl-1.1.1b-linux-x86_64
  mkdir -p "$(dirname "$tassl_target")"
  install -m 0755 \
    "$tassl_extract_dir/tassl-1.1.1b-linux-x86_64" "$tassl_target"
  "$tassl_target" version
fi

node_runtime="$runtime_dir/fisco-bcos-${node_version}"
if [[ ! -x "$node_runtime/fisco-bcos" ]]; then
  mkdir -p "$node_runtime"
  tar -xzf "$cache_dir/$node_archive" -C "$node_runtime"
  chmod 0755 "$node_runtime/fisco-bcos"
fi

console_runtime="$runtime_dir/console-${console_version}"
if [[ ! -x "$console_runtime/start.sh" ]]; then
  mkdir -p "$console_runtime"
  first_entry="$(tar -tzf "$cache_dir/$console_archive" | sed -n '1p')"
  if [[ "$first_entry" == */* ]]; then
    tar -xzf "$cache_dir/$console_archive" --strip-components=1 -C "$console_runtime"
  else
    tar -xzf "$cache_dir/$console_archive" -C "$console_runtime"
  fi
  chmod 0755 "$console_runtime/start.sh"
fi

sha256sum "$cache_dir/$build_script" "$cache_dir/$node_archive" \
  "$cache_dir/$console_archive" "$cache_dir/$tassl_archive" \
  > "$manifest_dir/asset_sha256.txt"
cp "$manifest_dir/asset_sha256.txt" "$project_dir/manifests/asset_sha256.txt"

"$node_runtime/fisco-bcos" -v
echo "FISCO BCOS and Console release assets installed under $runtime_dir"
