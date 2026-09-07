#!/bin/bash
set -euo pipefail
out=$(mktemp -d)
trap 'rm -rf -- "$out"' EXIT
bash /workspace/solution.sh "$out" > "$out/status"
printf 'source_rc=0\nfilter_rc=0\nsink_rc=0\npipeline_rc=0\n' | cmp - "$out/status"
printf 'abc\0end\n\n' | cmp - "$out/stdout.bin"
printf 'public PASS\n'
