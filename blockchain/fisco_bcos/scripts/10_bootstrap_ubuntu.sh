#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this bootstrap as root." >&2
  exit 1
fi

source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
  echo "Expected Ubuntu 22.04, found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Expected x86_64, found $(uname -m)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl wget aria2 git jq openssl unzip xz-utils tar \
  build-essential cmake pkg-config lsof procps net-tools iproute2 \
  openjdk-11-jdk-headless maven python3 python3-pip python3-venv \
  bc time locales sudo
apt-get clean

if ! id irpp >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash irpp
  usermod -aG sudo irpp
fi
printf '%s\n' 'irpp ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-irpp-rq5
chmod 0440 /etc/sudoers.d/90-irpp-rq5

install -d -o irpp -g irpp /opt/irpp-rq5
install -d -o irpp -g irpp /opt/irpp-rq5/{cache,runtime,chain,logs,manifests,sdk}

printf '%s\n' '[boot]' 'systemd=true' '' '[user]' 'default=irpp' > /etc/wsl.conf

locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8

java -version
mvn -version
python3 --version
echo "Ubuntu bootstrap completed. Terminate and restart the distro to activate the default user."
