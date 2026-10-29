#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Regenera los vectores de referencia con las herramientas externas reales.
# Uso: tests/vectors/generate.sh [directorio_de_salida]
# Requiere: JDK ≥ 11 (ejecución directa de .java), Node 22 y un compilador de C.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here/data}"
mkdir -p "$out"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

java "$here/GenJavaVectors.java" > "$out/java_random.json"
node "$here/gen_v8_vectors.mjs" > "$out/v8_math_random.json"
cc -O2 -std=c99 -o "$tmp/xs" "$here/xorshift128plus_ref.c"
"$tmp/xs" > "$out/xorshift128plus.json"

echo "Vectores escritos en $out"
