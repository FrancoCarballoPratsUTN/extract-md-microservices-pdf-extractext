#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

mkdir -p testdata

python3 -m tools.fixture.cli --out testdata/ref.pdf "$@"
pdftotext -layout testdata/ref.pdf testdata/ref.txt

printf 'ref.pdf  %s bytes\n' "$(stat -c %s testdata/ref.pdf)"
printf 'ref.txt  %s bytes\n' "$(stat -c %s testdata/ref.txt)"
pdftotext -v 2>&1 | head -1