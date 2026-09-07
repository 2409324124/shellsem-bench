#!/bin/bash
set -Eeuo pipefail
export LC_ALL=C
root=$(realpath -e -- "$1")
[[ -d "$root" ]]
tmp=$(mktemp)
trap 'rm -f -- "$tmp"' EXIT
find "$root" -type f -printf '%P\0' | sort -z > "$tmp"
while IFS= read -r -d '' p; do
  size=$(stat -Lc %s -- "$root/$p")
  hash=$(sha256sum < "$root/$p")
  hash=${hash%% *}
  printf '%s\0%s\0%s\0' "$p" "$size" "$hash"
done < "$tmp"
