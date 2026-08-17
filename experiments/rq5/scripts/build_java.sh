#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE=${IRPP_FISCO_CONSOLE:-/opt/irpp-rq5/runtime/console-v3.7.0}
BUILD="$ROOT/java/build/classes"
mkdir -p "$BUILD"
find "$BUILD" -type f -name '*.class' -delete
mapfile -t SOURCES < <(find "$ROOT/java/generated" "$ROOT/java/src" -type f -name '*.java' | sort)
javac -encoding UTF-8 -cp "$CONSOLE/lib/*" -d "$BUILD" "${SOURCES[@]}"
echo "Compiled ${#SOURCES[@]} Java sources into $BUILD"
