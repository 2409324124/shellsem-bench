#!/bin/bash
set -euo pipefail
root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
printf abc > "$root/a b"
bash /workspace/solution.sh "$root" > "$root.got"
printf 'a b\0003\000ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\000' > "$root.expected"
cmp "$root.got" "$root.expected"
rm -- "$root.got" "$root.expected"
printf 'public PASS\n'
