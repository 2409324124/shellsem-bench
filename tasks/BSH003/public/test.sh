#!/bin/bash
set -euo pipefail
root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
bash /workspace/solution.sh /fixture "$root/out"
printf '3\n' | cmp - "$root/out/count.txt"
printf '3\0one\0009\0two\nlines\0000\0\0' | cmp - "$root/out/manifest.bin"
printf 'public PASS\n'
