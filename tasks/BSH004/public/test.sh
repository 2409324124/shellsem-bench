#!/bin/bash
set -euo pipefail
root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
printf 'one\0two\0three\0four\0' > "$root/tasks"
bash /workspace/solution.sh "$root/tasks" "$root/out"
printf 'one\0\n\ntwo\0\n\nthree\0\n\nfour\0\n\n' | cmp - "$root/out/aggregate.bin"
printf 'public PASS\n'
