#!/usr/bin/env bash
set -euo pipefail

install_root="/opt/irpp-rq5"
nodes_dir="$install_root/chain/nodes"
console_dir="$install_root/runtime/console-v3.7.0"
log_dir="$install_root/logs"
stamp="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$log_dir"

if [[ ! -x "$nodes_dir/127.0.0.1/start_all.sh" || ! -x "$console_dir/start.sh" ]]; then
  echo "Chain or Console is not configured." >&2
  exit 1
fi

bash "$nodes_dir/127.0.0.1/start_all.sh" | tee "$log_dir/smoke_start_${stamp}.log"

ready=0
for _ in $(seq 1 30); do
  process_count="$(pgrep -af '/fisco-bcos' | grep -v pgrep | wc -l || true)"
  if [[ "$process_count" -ge 4 ]]; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "Four FISCO BCOS node processes did not become ready." >&2
  exit 1
fi

cd "$console_dir"
run_console_command() {
  local command="$1"
  # Console takes groupID as argv[1] and reads operations from stdin.
  printf '%s\n' "$command" | timeout 30s bash start.sh group0
}

run_console_command 'getBlockNumber' | tee "$log_dir/smoke_block_before_${stamp}.log"
run_console_command 'getPbftView' | tee "$log_dir/smoke_pbft_${stamp}.log"
deploy_output="$(run_console_command 'deploy HelloWorld' 2>&1)"
printf '%s\n' "$deploy_output" | tee "$log_dir/smoke_deploy_${stamp}.log"

contract_address="$(printf '%s\n' "$deploy_output" | \
  sed -nE 's/^contract address: (0x[0-9a-fA-F]{40}).*$/\1/p' | tail -n 1)"
if [[ -z "$contract_address" ]]; then
  echo "HelloWorld deployment did not return a contract address." >&2
  exit 1
fi

call_output="$(run_console_command "call HelloWorld $contract_address get" 2>&1)"
printf '%s\n' "$call_output" | tee "$log_dir/smoke_call_${stamp}.log"
if ! printf '%s\n' "$call_output" | grep -q 'Hello, World!'; then
  echo "HelloWorld get() did not return the expected value." >&2
  exit 1
fi
run_console_command 'getBlockNumber' | tee "$log_dir/smoke_block_after_${stamp}.log"

grep -R -m 1 -E 'reachConsensus|Report.*block' "$nodes_dir/127.0.0.1"/node*/log/ \
  > "$log_dir/smoke_consensus_${stamp}.log" || true

echo "Smoke test passed; deployed HelloWorld at $contract_address"
