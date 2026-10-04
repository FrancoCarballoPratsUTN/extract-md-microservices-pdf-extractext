#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
golden="$root/testdata/ref.txt"
minimum="${GATE_MINIMUM:-0.70}"

if [[ ! -f "$golden" ]]; then
  echo "gate: falta el golden '$golden'; generarlo con scripts/gen-fixture.sh" >&2
  exit 2
fi

actual="${1:-}"
temporary=""

if [[ -z "$actual" ]]; then
  binary="${EXTRACTOR:-$root/bin/extract-md}"
  if [[ ! -x "$binary" ]]; then
    echo "gate: no existe el extractor '$binary'; se construye en el paso 5 con" >&2
    echo "      CGO_ENABLED=0 go build -o bin/extract-md ./cmd/extract" >&2
    exit 2
  fi
  temporary="$(mktemp)"
  actual="$temporary"
  trap 'rm -f "$temporary"' EXIT
  "$binary" < "$root/testdata/ref.pdf" > "$actual"
fi

cd "$root"
python3 -m tools.gate.wordmatch "$golden" "$actual" --min "$minimum"