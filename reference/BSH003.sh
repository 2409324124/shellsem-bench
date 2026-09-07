#!/bin/bash
set -Eeuo pipefail
export LC_ALL=C
root=$1
out=$2
tmp=$(mktemp -d "$(dirname -- "$out")/.scan.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
if /usr/local/bin/scanner "$root" > "$tmp/raw"; then :; else rc=$?; exit "$rc"; fi
count=0
: > "$tmp/manifest.bin"
while IFS= read -r -d '' record; do
  printf '%d\0%s\0' "${#record}" "$record" >> "$tmp/manifest.bin"
  count=$((count+1))
done < "$tmp/raw"
printf '%d\n' "$count" > "$tmp/count.txt"
rm -- "$tmp/raw"
mv -T -- "$tmp" "$out"
